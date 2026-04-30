from pathlib import Path
from typing import Union
from uuid import uuid4

from pipeline.schemas import ClipSegment, RenderedClip


def render_clip(
    source_path: Union[str, Path],
    output_dir: Union[str, Path],
    segment: ClipSegment,
    dry_run: bool = False,
) -> RenderedClip:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    clip_id = f"clip_{uuid4().hex[:10]}"
    video_path = output_dir / f"{clip_id}.mp4"
    subtitle_path = output_dir / f"{clip_id}.srt"
    thumbnail_path = output_dir / f"{clip_id}.jpg"

    # v1 placeholder render, leaving ffmpeg execution for production deployment.
    video_path.write_bytes(b"rendered-video" if not dry_run else b"dry-run-video")
    subtitle_path.write_text("1\n00:00:00,000 --> 00:00:02,000\nDemo subtitle\n")
    thumbnail_path.write_bytes(b"thumbnail")

    return RenderedClip(
        clip_id=clip_id,
        candidate_id=segment.candidate_id,
        video_path=str(video_path),
        subtitle_path=str(subtitle_path),
        thumbnail_path=str(thumbnail_path),
        duration_sec=max(0.0, segment.end_sec - segment.start_sec),
    )

