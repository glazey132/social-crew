import re

from tools.research import discover_candidates


def test_discover_candidates_urls_have_valid_youtube_id_length():
    """YouTube watch?v= IDs must be 11 characters; yt_dlp rejects truncated IDs."""
    pattern = re.compile(r"watch\?v=([A-Za-z0-9_-]{11})(?:&|$)")
    for c in discover_candidates(limit=5):
        match = pattern.search(c.url)
        assert match is not None, f"bad url: {c.url}"


def test_single_test_video_url_env_watch(monkeypatch):
    monkeypatch.setenv(
        "SINGLE_TEST_VIDEO_URL",
        "https://www.youtube.com/watch?v=EvIBrUDnh8s",
    )
    candidates = discover_candidates(limit=5)
    assert len(candidates) == 1
    assert candidates[0].id == "source_EvIBrUDnh8s"
    assert candidates[0].url == "https://www.youtube.com/watch?v=EvIBrUDnh8s"


def test_single_test_video_url_env_short_link(monkeypatch):
    monkeypatch.setenv("SINGLE_TEST_VIDEO_URL", "https://youtu.be/EvIBrUDnh8s")
    candidates = discover_candidates(limit=5)
    assert len(candidates) == 1
    assert candidates[0].url == "https://www.youtube.com/watch?v=EvIBrUDnh8s"
