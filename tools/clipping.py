"""
Video clip rendering with FFmpeg.

Extracts specified segments from source videos and renders them as:
- 9:16 vertical format (TikTok/Reels/Shorts)
- Burned-in subtitles for engagement
- Thumbnail extraction
"""

import logging
import subprocess
from pathlib import Path
from typing import Union

from pipeline.schemas import ClipSegment, RenderedClip

LOGGER = logging.getLogger(__name__)


def _format_srt_timestamp(total_seconds: float) -> str:
    """SRT end time for a clip that starts at 00:00:00,000 (HH:MM:SS,mmm)."""
    if total_seconds < 0:
        total_seconds = 0.0
    whole = int(total_seconds)
    ms = int(round((total_seconds - whole) * 1000))
    if ms >= 1000:
        ms = 999
    h, r = divmod(whole, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# Output format specifications
OUTPUT_ASPECT_RATIO = "9:16"
OUTPUT_VIDEO_CODEC = "h264"
OUTPUT_AUDIO_CODEC = "aac"
OUTPUT_FPS = 30
SUBTITLE_FONT_SIZE = 24
SUBTITLE_FONTCOLOR = "white"
SUBTITLE_BACKCOLOR = "black@@0.8"


def render_clip(
    source_path: Union[str, Path],
    output_dir: Union[str, Path],
    segment: ClipSegment,
    dry_run: bool = False,
) -> RenderedClip:
    """
    Render a vertical clip from a source video segment.
    
    Args:
        source_path: Path to source video file
        output_dir: Directory to write output files
        segment: ClipSegment defining the segment boundaries
        dry_run: If True, simulate the rendering process
        
    Returns:
        RenderedClip with paths to generated files
    """
    source_path = Path(source_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    clip_id = f"clip_{segment.candidate_id}_{int(segment.start_sec*100)}"
    
    # Output paths
    video_path = output_dir / f"{clip_id}.mp4"
    subtitle_path = output_dir / f"{clip_id}.srt"
    thumbnail_path = output_dir / f"{clip_id}.jpg"
    
    if dry_run:
        LOGGER.info("DRY RUN: Would render clip %s", clip_id)
        return _create_dry_run_outputs(video_path, subtitle_path, thumbnail_path, segment)
    
    try:
        # Step 1: Extract the segment
        _extract_segment(
            source_path,
            video_path,
            segment.start_sec,
            segment.end_sec
        )
        
        # Step 2: Generate subtitle file (for reference)
        dur = segment.end_sec - segment.start_sec
        subtitle_text = (
            f"1\n00:00:00,000 --> {_format_srt_timestamp(dur)}\n{segment.hook_text}"
        )
        subtitle_path.write_text(subtitle_text)
        
        # Step 3: Thumbnail — seek is relative to the *rendered* clip (starts at t=0).
        # Passing source `segment.start_sec` seeks past EOF on a short output file.
        _extract_thumbnail(video_path, thumbnail_path, 0.0)
        
        LOGGER.info("Successfully rendered %s (%.1f seconds)", clip_id, segment.end_sec - segment.start_sec)
        
        return RenderedClip(
            clip_id=clip_id,
            candidate_id=segment.candidate_id,
            video_path=str(video_path),
            subtitle_path=str(subtitle_path),
            thumbnail_path=str(thumbnail_path),
            duration_sec=max(0.0, segment.end_sec - segment.start_sec),
            aspect_ratio=OUTPUT_ASPECT_RATIO,
        )
        
    except subprocess.CalledProcessError as e:
        LOGGER.error("Failed to render clip %s: %s", clip_id, e)
        raise RuntimeError(f"FFmpeg rendering failed for {clip_id}")


def _extract_segment(
    source_path: Path,
    output_path: Path,
    start_time: float,
    end_time: float
) -> None:
    """
    Extract a segment from a video and render it as 9:16 vertical.
    
    The segment is:
    - Cropped to 9:16 aspect ratio (center crop)
    - Resized to 1080x1920 (typical TikTok/Reels)
    - Audio encoded as AAC
    """
    duration = end_time - start_time

    # Vertical 9:16 (1080x1920) center-crop:
    #   1. scale source so the smaller axis >= the target on that axis
    #      (force_original_aspect_ratio=increase picks the LARGER scale factor)
    #   2. crop=1080:1920 takes a centered 1080x1920 from the scaled frame
    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(start_time),
        "-t", str(duration),
        "-i", str(source_path),
        "-vf", "scale=w=1080:h=1920:force_original_aspect_ratio=increase,crop=1080:1920",
        "-c:v", OUTPUT_VIDEO_CODEC,
        "-c:a", OUTPUT_AUDIO_CODEC,
        "-b:a", "128k",
        "-preset", "medium",
        "-r", str(OUTPUT_FPS),
        "-pix_fmt", "yuv420p",
        str(output_path),
    ]
    
    LOGGER.info("Executing FFmpeg command: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False
    )
    
    if result.returncode != 0:
        LOGGER.error("FFmpeg stderr: %s", result.stderr)
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)


def _extract_thumbnail(video_path: Path, output_path: Path, timestamp: float) -> None:
    """
    Extract one frame from the given media file.

    ``timestamp`` is in **seconds from the start of ``video_path``** (timeline of
    that file). For thumbnails of a freshly rendered clip, use ``0.0``.
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(timestamp),  # Seek to timestamp
        "-i", str(video_path),
        "-vframes", "1",  # Extract one frame
        "-vf", "scale=1080:1920",  # Size to 9:16
        "-q:v", "2",  # High quality (1-31, lower better)
        str(output_path),
    ]
    
    subprocess.run(cmd, capture_output=True, check=True)


def _create_dry_run_outputs(
    video_path: Path,
    subtitle_path: Path,
    thumbnail_path: Path,
    segment: ClipSegment
) -> RenderedClip:
    """Create placeholder files for dry-run mode."""
    video_path.write_bytes(b"fake-dry-run-video-data")
    subtitle_path.write_text(
        f"1\n00:00:00,000 --> 00:00:{int(segment.end_sec - segment.start_sec):02d},000\n{segment.hook_text}"
    )
    thumbnail_path.write_bytes(b"thumbnail-placeholder")
    
    return RenderedClip(
        clip_id=video_path.stem,
        candidate_id=segment.candidate_id,
        video_path=str(video_path),
        subtitle_path=str(subtitle_path),
        thumbnail_path=str(thumbnail_path),
        duration_sec=max(0.0, segment.end_sec - segment.start_sec),
        aspect_ratio=OUTPUT_ASPECT_RATIO,
    )
