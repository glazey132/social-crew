# Social Content Pipeline V1 - Integration Test Suite

"""
Integration test for transcription and rendering.
Run manually with: python -m tests.integration_test
"""

import logging
from pathlib import Path

from tools.transcribe import transcribe_video
from tools.clipping import render_clip
from tools.download import download_video
from pipeline.config import PipelineConfig
from pipeline.schemas import ClipSegment

logging.basicConfig(level=logging.INFO)


def test_transcription_with_real_video():
    """Test transcription pipeline with an actual downloaded video."""
    config = PipelineConfig.from_env()
    
    # Download a test video
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    try:
        video_path = download_video(
            url=test_url,
            output_dir=config.output_dir,
            dry_run=False,
        )
        print(f"✓ Downloaded video: {video_path}")
    except Exception as e:
        print(f"✗ Download failed (expected if blocked): {e}")
        return
    
    # Transcribe
    segments = transcribe_video(video_path)
    print(f"✓ Found {len(segments)} segments")
    for i, seg in enumerate(segments[:3], 1):
        print(f"  {i}. {seg.start_sec:.1f}s - {seg.end_sec:.1f}s | {seg.hook_text[:40]}...")
    
    # Render first segment
    if segments:
        clip = render_clip(
            source_path=video_path,
            output_dir=config.output_dir,
            segment=segments[0],
            dry_run=False,
        )
        print(f"✓ Rendered clip: {clip.clip_id} ({clip.duration_sec:.1f}s)")
        print(f"  Output: {clip.video_path}")


if __name__ == "__main__":
    test_transcription_with_real_video()
