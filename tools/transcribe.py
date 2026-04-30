"""
Video transcription and clip segment detection using Whisper.

Identifies high-engagement segments (15-60 seconds) suitable for short-form content.
Uses faster-whisper for efficient on-device speech recognition.
"""

import logging
import subprocess
from pathlib import Path
from typing import List, Tuple, Union

from faster_whisper import WhisperModel
from pipeline.schemas import ClipSegment

LOGGER = logging.getLogger(__name__)

# Segment constraints for short-form content
MIN_DURATION_SEC = 15
MAX_DURATION_SEC = 60
MIN_CONFIDENCE = 0.35


def transcribe_video(source_path: Union[str, Path]) -> List[ClipSegment]:
    """
    Transcribe video and identify optimal clip segments using Whisper.
    
    Uses a strategy that focuses on high-confidence, complete thoughts:
    - Finds sentences/phrases that form coherent segments
    - Prioritizes segments with strong opening phrases
    - Ensures segments are between 15-60 seconds
    
    Args:
        source_path: Path to downloaded video file
        
    Returns:
        List of ClipSegment objects sorted by confidence score
    """
    source_path = Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Video file not found: {source_path}")
    
    # Determine candidate ID from filename
    candidate_id = source_path.stem
    
    LOGGER.info("Starting transcription for %s", candidate_id)
    
    # Initialize Whisper model (uses CPU by default, can be configured for GPU)
    model = WhisperModel(size="medium", device="auto")
    
    # Get raw transcript using the Whisper model
    segments = _transcribe_to_segments(model, str(source_path))
    
    # Post-process to find optimal clip segments
    clip_candidates = _identify_clip_segments(segments, candidate_id)
    
    LOGGER.info("Found %d potential clip segments for %s", len(clip_candidates), candidate_id)
    
    return sorted(clip_candidates, key=lambda s: s.confidence, reverse=True)


def _transcribe_to_segments(model: WhisperModel, video_path: str) -> List[Tuple[float, float, str, float]]:
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
        
        # Convert to our format: (start, end, text, confidence)
        result = []
        for seg in segments:
            confidence = (sum(seg.words) for seg in seg.words) / len(seg.words) if seg.words else 0.8
            result.append((
                seg.start,
                seg.end,
                seg.text,
                confidence
            ))
        
        LOGGER.info("Extracted %d transcript segments", len(result))
        return result
        
    except subprocess.CalledProcessError as e:
        LOGGER.error("FFmpeg error extracting duration for %s: %s", video_path, e)
        raise RuntimeError(f"Failed to analyze video: {video_path}")


def _identify_clip_segments(segments: List[Tuple[float, float, str, float]], candidate_id: str) -> List[ClipSegment]:
    """
    Identify optimal clip segments from transcript segments.
    
    Strategy:
    - Look for coherent thoughts that complete in 15-60 seconds
    - Prioritize segments with high confidence scores
    - Focus on segments with engaging openings (questions, strong statements)
    """
    clip_candidates = []
    
    # Group consecutive segments into potential clips
    i = 0
    while i < len(segments):
        current_start, current_end, current_text, current_conf = segments[i]
        
        # Skip very short segments
        if current_end - current_start < MIN_DURATION_SEC - 2:
            i += 1
            continue
        
        # Try to extend segment to capture complete thought
        best_end = current_end
        best_text = current_text
        best_conf = current_conf
        
        for j in range(i + 1, min(i + 5, len(segments))):
            next_start, next_end, next_text, next_conf = segments[j]
            
            # Check for natural break (gap > 1s or new sentence)
            gap = next_start - best_end
            if gap > 1.0 or next_text.startswith(('And', 'But', 'So', 'Well', 'Okay')):
                break
            
            # Update best segment
            best_end = next_end
            best_text = f"{best_text} {next_text}"
            best_conf = (best_conf + next_conf) / 2
        
        # Only keep if duration is appropriate
        duration = best_end - current_start
        if MIN_DURATION_SEC <= duration <= MAX_DURATION_SEC and best_conf >= MIN_CONFIDENCE:
            # Score based on confidence and engagement signals
            score = _calculate_engagement_score(best_text, best_conf, duration)
            
            clip_candidates.append(
                ClipSegment(
                    candidate_id=candidate_id,
                    start_sec=current_start,
                    end_sec=best_end,
                    hook_text=_generate_hook_text(best_text),
                    confidence=score
                )
            )
        
        i += 1
    
    # Always include at least the best 3 segments if we found any
    if not clip_candidates and segments:
        # Fallback: take the first three potential segments
        for i in range(min(3, len(segments))):
            start, end, text, conf = segments[i]
            duration = end - start
            if MIN_DURATION_SEC <= duration <= MAX_DURATION_SEC:
                clip_candidates.append(
                    ClipSegment(
                        candidate_id=candidate_id,
                        start_sec=start,
                        end_sec=end,
                        hook_text=_generate_hook_text(text),
                        confidence=conf
                    )
                )
    
    return clip_candidates


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
    - +0.05 if text length is optimal for short-form
    """
    base_score = confidence
    
    # Engagement boosters
    engaging_starters = ['Why', 'What', 'How', 'Can', 'Would', 'Did', 'When', 'Who']
    if text.split()[0] in engaging_starters if text.split() else False:
        base_score += 0.1
    
    # Optimal text length
    word_count = len(text.split())
    if 10 <= word_count <= 30:
        base_score += 0.05
    
    # Short duration bonus
    if duration < 30:
        base_score += 0.05
    
    return min(1.0, base_score)


def _generate_hook_text(text: str) -> str:
    """Extract a compelling hook from the segment text."""
    # Take first sentence as hook (usually the most engaging)
    sentences = text.split('.')
    if sentences:
        return sentences[0].strip().capitalize() + '.'
    return text.strip().capitalize() + '.'
