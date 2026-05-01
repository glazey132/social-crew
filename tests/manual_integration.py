# Social Content Pipeline V1 - Manual Integration Script

"""
Manual integration check for download -> transcribe -> render.

Renamed from integration_test.py so pytest does NOT auto-collect it
(faster_whisper imports segfault during collection).

Run manually:
    PYTHONPATH=. ./venv/bin/python -m tests.manual_integration
"""

import logging
from pathlib import Path

from pipeline.config import PipelineConfig
from tools.clipping import render_clip
from tools.download import download_video
from tools.transcribe import transcribe_video

logging.basicConfig(level=logging.INFO)


def main() -> None:
    config = PipelineConfig.from_env()

    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    try:
        video_path: Path = download_video(
            url=test_url,
            downloads_dir=config.downloads_dir,
            dry_run=False,
            max_resolution=config.max_download_resolution,
            backend=config.download_backend,
            ytdlp=config.ytdlp,
        )
        print(f"OK downloaded: {video_path}")
    except Exception as e:
        print(f"FAIL download: {e}")
        return

    segments = transcribe_video(video_path)
    print(f"OK transcribed: {len(segments)} segments")
    for i, seg in enumerate(segments[:3], 1):
        print(f"  {i}. {seg.start_sec:.1f}s - {seg.end_sec:.1f}s | {seg.hook_text[:40]}...")

    if segments:
        clip = render_clip(
            source_path=video_path,
            output_dir=config.output_dir,
            segment=segments[0],
            dry_run=False,
        )
        print(f"OK rendered: {clip.clip_id} ({clip.duration_sec:.1f}s) -> {clip.video_path}")


if __name__ == "__main__":
    main()
