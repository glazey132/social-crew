"""
Video transcription and clip segment detection using Whisper.

Identifies coherent watchable arcs from transcript (bounded by ``CLIP_*`` env).
Prefer longer units you can trim in-app over short ambiguous cuts.
Uses faster-whisper for efficient on-device speech recognition.
"""

import functools
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

from pipeline.schemas import ClipSegment

LOGGER = logging.getLogger(__name__)

MIN_CONFIDENCE = 0.35


def _clip_strategy_bounds() -> Tuple[float, float, float, float]:
    """(min_duration, max_duration, soft_boundary_min, silence_gap).

    Soft boundary: do not split on punctuation or silence until duration is at least
    this large (errs long toward a coherent "unit").
    """
    mn = float(os.getenv("CLIP_MIN_SEC", "20"))
    mx = float(os.getenv("CLIP_MAX_SEC", "180"))
    soft = float(os.getenv("CLIP_SOFT_BOUNDARY_MIN_SEC", "45"))
    gap = float(os.getenv("CLIP_SILENCE_GAP_SEC", "2.0"))
    if mx < mn:
        mn, mx = mx, mn
    if soft < mn:
        soft = mn
    return mn, mx, soft, gap


def _silence_gap_sec(segments: List[Tuple[float, float, str, float]], prev_j: int, next_j: int) -> float:
    """Time between end of Whisper segment prev_j and start of next_j."""
    return segments[next_j][0] - segments[prev_j][1]


def _text_looks_complete_sentence(text: str) -> bool:
    """Rough check for clause / sentence boundary at end of transcript text."""
    t = text.strip()
    if not t:
        return False
    for suf in ('"', "'", ")", "]", "»"):
        while t.endswith(suf):
            t = t[:-1].rstrip()
    return bool(t[-1] in ".!?…")


def _emit_clip_window(
    candidate_id: str,
    start_t: float,
    end_t: float,
    texts: List[str],
    confs: List[float],
    *,
    min_sec: float,
    max_sec: float,
) -> Optional[ClipSegment]:
    duration = end_t - start_t
    if duration < min_sec or duration > max_sec + 0.001:
        return None
    avg_conf = sum(confs) / len(confs)
    if avg_conf < MIN_CONFIDENCE:
        return None
    full_text = " ".join(texts)
    score = _calculate_engagement_score(full_text, avg_conf, duration)
    return ClipSegment(
        candidate_id=candidate_id,
        start_sec=start_t,
        end_sec=end_t,
        hook_text=_generate_hook_text(full_text),
        confidence=score,
    )


@functools.lru_cache(maxsize=1)
def _get_whisper_model(model_size: str, device: str) -> Any:
    """Module-level model cache."""
    from faster_whisper import WhisperModel

    LOGGER.info("Loading WhisperModel size=%s device=%s (one-time per process)", model_size, device)
    return WhisperModel(model_size, device=device)


def transcribe_video(source_path: Union[str, Path]) -> List[ClipSegment]:
    """Transcribe video and identify optimal clip segments using Whisper.

    Reads model size from env `WHISPER_MODEL_SIZE` (default `medium`) and
    device from `WHISPER_DEVICE` (default `auto` — picks CUDA/MPS/CPU).
    """
    source_path = Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Video file not found: {source_path}")

    candidate_id = source_path.stem
    LOGGER.info("Starting transcription for %s", candidate_id)

    model_size = os.getenv("WHISPER_MODEL_SIZE", "medium").strip() or "medium"
    device = os.getenv("WHISPER_DEVICE", "auto").strip() or "auto"
    model = _get_whisper_model(model_size, device)

    segments = _transcribe_to_segments(model, str(source_path))
    
    # Post-process to find optimal clip segments
    clip_candidates = _identify_clip_segments(segments, candidate_id)
    
    LOGGER.info("Found %d potential clip segments for %s", len(clip_candidates), candidate_id)
    
    return sorted(clip_candidates, key=lambda s: s.confidence, reverse=True)


def _transcribe_to_segments(model: Any, video_path: str) -> List[Tuple[float, float, str, float]]:
    """
    Transcribe video and return segments with timestamps.
    
    Returns:
        List of (start_sec, end_sec, text, avg_confidence) tuples
    """
    try:
        # Get duration from FFmpeg
        duration = _get_video_duration(video_path)
        LOGGER.info("Video duration: %.1f seconds", duration)
        
        # Transcribe using Whisper with beam search for better accuracy
        segments, _ = model.transcribe(
            video_path,
            language="en",
            beam_size=5,
            word_timestamps=True
        )
        
        result = []
        for seg in segments:
            if seg.words:
                confidence = sum(w.probability for w in seg.words) / len(seg.words)
            else:
                confidence = 0.8
            result.append((
                seg.start,
                seg.end,
                seg.text,
                confidence,
            ))
        
        LOGGER.info("Extracted %d transcript segments", len(result))
        return result
        
    except subprocess.CalledProcessError as e:
        LOGGER.error("FFmpeg error extracting duration for %s: %s", video_path, e)
        raise RuntimeError(f"Failed to analyze video: {video_path}")


def _identify_clip_segments(segments: List[Tuple[float, float, str, float]], candidate_id: str) -> List[ClipSegment]:
    """Build ``CLIP_MIN_SEC``–``CLIP_MAX_SEC`` windows from Whisper fragments.

    Stops merging when:
    - after ``CLIP_SOFT_BOUNDARY_MIN_SEC`` s: punctuation looks like clause end, **or**
    - same threshold: silence ≥ ``CLIP_SILENCE_GAP_SEC`` before next line, **or**
    - hard cap ``CLIP_MAX_SEC``.

    Earlier sentence boundaries are ignored so windows stay coherent (trim later).
    """
    min_sec, max_sec, soft_sec, silence_gap = _clip_strategy_bounds()
    candidates: List[ClipSegment] = []
    n = len(segments)

    for i in range(n):
        start_t = segments[i][0]
        texts: List[str] = []
        confs: List[float] = []
        emitted = False

        for j in range(i, n):
            s0, s1, st, sc = segments[j]

            if j > i and silence_gap > 0:
                gap = _silence_gap_sec(segments, j - 1, j)
                if gap >= silence_gap:
                    prev_end = segments[j - 1][1]
                    if prev_end - start_t >= soft_sec:
                        clip = _emit_clip_window(
                            candidate_id, start_t, prev_end, texts, confs,
                            min_sec=min_sec, max_sec=max_sec,
                        )
                        if clip is not None:
                            candidates.append(clip)
                            emitted = True
                        break

            if s1 - start_t > max_sec:
                if j > i:
                    prev_end = segments[j - 1][1]
                    clip = _emit_clip_window(
                        candidate_id, start_t, prev_end, texts, confs,
                        min_sec=min_sec, max_sec=max_sec,
                    )
                    if clip is not None:
                        candidates.append(clip)
                        emitted = True
                break

            texts.append(st.strip())
            confs.append(sc)
            dur = s1 - start_t
            full = " ".join(texts)

            if dur >= min_sec:
                if dur >= soft_sec and _text_looks_complete_sentence(full):
                    clip = _emit_clip_window(
                        candidate_id, start_t, s1, texts, confs,
                        min_sec=min_sec, max_sec=max_sec,
                    )
                    if clip is not None:
                        candidates.append(clip)
                        emitted = True
                    break
                if dur >= max_sec - 1e-6:
                    clip = _emit_clip_window(
                        candidate_id, start_t, s1, texts, confs,
                        min_sec=min_sec, max_sec=max_sec,
                    )
                    if clip is not None:
                        candidates.append(clip)
                        emitted = True
                    break

        if not emitted and texts:
            last_end = segments[i + len(texts) - 1][1]
            clip = _emit_clip_window(
                candidate_id, start_t, last_end, texts, confs,
                min_sec=min_sec, max_sec=max_sec,
            )
            if clip is not None:
                candidates.append(clip)

    return candidates


def _get_video_duration(video_path: str) -> float:
    """Get video duration in seconds using FFmpeg."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return float(result.stdout.strip())
    raise RuntimeError(f"FFmpeg failed for {video_path}")


def _calculate_engagement_score(text: str, confidence: float, duration: float) -> float:
    """
    Calculate engagement score for a segment.
    
    Factors:
    - Base score from whisper confidence
    - +0.1 if text starts with engaging words
    - mild bonus for longer arcs (users trim in-app; short clips rank lower)
    """
    base_score = confidence

    if _text_looks_complete_sentence(text):
        base_score += 0.12
    else:
        base_score -= 0.03

    # Engagement boosters
    engaging_starters = ['Why', 'What', 'How', 'Can', 'Would', 'Did', 'When', 'Who']
    if text.split()[0] in engaging_starters if text.split() else False:
        base_score += 0.1
    
    word_count = len(text.split())
    if 10 <= word_count <= 120:
        base_score += 0.05

    if duration >= 90:
        base_score += 0.08
    elif duration >= 55:
        base_score += 0.05
    elif duration < 30:
        base_score -= 0.06
    
    return min(1.0, base_score)


def _generate_hook_text(text: str) -> str:
    """Extract a compelling hook from the segment text."""
    # Take first sentence as hook (usually the most engaging)
    sentences = text.split('.')
    if sentences:
        return sentences[0].strip().capitalize() + '.'
    return text.strip().capitalize() + '.'
