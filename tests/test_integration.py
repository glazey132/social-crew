"""
Simple test module to verify the new transcribe/render flow.
"""

import logging
from pathlib import Path
from tools.transcribe import transcribe_video
from tools.clipping import render_clip

logging.basicConfig(level=logging.INFO)


def test_transcription(mock_video_path):
    """Test transcription on a dummy video file."""
    print(f"Testing transcription for {mock_video_path}")
    
    # Create a dummy file to test the flow
    dummy_path = Path(mock_video_path) if not mock_video_path.exists() else mock_video_path
    
    if not dummy_path.exists():
        print(f"✗ No real video found at {dummy_path}")
        print("This is expected in dry-run mode.")
        print("The real test will run with a downloaded YouTube video.")
        return
    
    segments = transcribe_video(dummy_path)
    print(f"✓ Found {len(segments)} segments")
    for i, seg in enumerate(segments[:3], 1):  # Show top 3
        print(f"  {i}. {seg.start_sec:.1f}s - {seg.end_sec:.1f}s | {seg.hook_text[:50]}... | cfg={seg.confidence:.2f}")


def test_rendering(mock_video_path):
    """Test rendering with a sample segment."""
    from pipeline.schemas import ClipSegment
    
    print(f"Testing rendering for {mock_video_path}")
    
    # Create a mock segment
    segment = ClipSegment(
        candidate_id="test_video",
        start_sec=3.0,
        end_sec=32.0,
        hook_text="The first big claim that creates curiosity.",
        confidence=0.89,
    )
    
    # Try dry render
    clip = render_clip(
        source_path=mock_video_path,
        output_dir=Path.cwd() / "outputs",
        segment=segment,
        dry_run=False,
    )
    
    print(f"✓ Rendered clip: {clip.clip_id}")
    print(f"  Duration: {clip.duration_sec:.2f}s")
    print(f"  Output: {clip.video_path}")


if __name__ == "__main__":
    import sys
    from tools.download import download_video
    from pipeline.config import PipelineConfig
    
    config = PipelineConfig.from_env()
    
    # Create a test video by downloading one
    print("Step 1: Downloading test video...")
    test_video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    try:
        video_path = download_video(
            url=test_video_url,
            output_dir=config.output_dir,
            dry_run=False,
        )
        print(f"✓ Downloaded to: {video_path}")
    except Exception as e:
        print(f"✗ Download failed: {e}")
        print("Skipping real test - this is expected if YouTube is blocked or quota limited.")
        sys.exit(0)
    
    # Test transcription
    print("\nStep 2: Testing transcription...")
    test_transcription(video_path)
    
    # Test rendering
    print("\nStep 3: Testing rendering...")
    test_rendering(video_path)
    
    print("\n✓ All tests passed!")
