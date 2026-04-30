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
        subtitle_text = f"1\n00:00:00,000 --> 00:00:{int(segment.end_sec - segment.start_sec):02d},000\n{segment.hook_text}"
        subtitle_path.write_text(subtitle_text)
        
        # Step 3: Extract thumbnail at segment start
        _extract_thumbnail(video_path, thumbnail_path, segment.start_sec)
        
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
    
    # FFmpeg command for center crop to 9:16
    # Input: source (any aspect ratio)
    # Crop: -vf "scale='min(9*1920/1080,iw)':9:1920, crop=1080:1920"
    # We first scale to match height, then crop the middle
    
    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output
        "-ss", str(start_time),  # Start time
        "-t", str(duration),  # Duration
        "-i", str(source_path),  # Input
        "-vf", f"scale='min(1080*1080/{1080*1080}':1080:-1,'cropmax=1080:1920',crop=1080:1920",  # Crop to 9:16
        "-c:v", OUTPUT_VIDEO_CODEC,  # Video codec
        "-c:a", OUTPUT_AUDIO_CODEC,  # Audio codec
        "-b:a", "128k",  # Audio bitrate
        "-preset", "medium",  # Encoding speed/quality tradeoff
        "-r", str(OUTPUT_FPS),  # Frame rate
        "-pix_fmt", "yuv420p",  # Compatible pixel format
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
    Extract a high-quality thumbnail from the video at a specific timestamp.
    
    Args:
        video_path: Source video path
        output_path: Where to save thumbnail
        timestamp: Time in seconds to extract frame
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
