"""Unit tests for `_identify_clip_segments` — no faster_whisper import at collection time."""

from tools.transcribe import _clip_strategy_bounds, _identify_clip_segments


def test_segmenter_aggregates_short_whisper_segments_into_configured_windows():
    segments = []
    t = 0.0
    for i in range(30):
        segments.append((t, t + 3.5, f"sentence {i} content here", 0.9))
        t += 3.5
    out = _identify_clip_segments(segments, "test_vid")
    assert out, "expected at least one window"
    lo, hi, _, _ = _clip_strategy_bounds()
    for c in out:
        d = c.end_sec - c.start_sec
        assert lo - 1e-6 <= d <= hi + 1e-6, f"window {d}s out of [{lo},{hi}]"


def test_segmenter_returns_empty_for_empty_input():
    assert _identify_clip_segments([], "vid") == []


def test_segmenter_skips_low_confidence_windows():
    segments = [(t, t + 3.5, "txt", 0.10) for t in (0.0, 3.5, 7.0, 10.5, 14.0, 17.5, 21.0)]
    assert _identify_clip_segments(segments, "v") == []


def test_segmenter_ignores_early_punctuation_until_soft_boundary(monkeypatch):
    monkeypatch.delenv("CLIP_MIN_SEC", raising=False)
    monkeypatch.delenv("CLIP_SOFT_BOUNDARY_MIN_SEC", raising=False)
    monkeypatch.setenv("CLIP_MIN_SEC", "10")
    monkeypatch.setenv("CLIP_SOFT_BOUNDARY_MIN_SEC", "40")
    # Two lines: first ends with period at ~20s total; soft=40 → must merge across
    segments = [
        (0.0, 10.0, "Short opener.", 0.9),
        (10.5, 25.0, "Second line continues the thought without ending early.", 0.9),
    ]
    out = _identify_clip_segments(segments, "v")
    assert out
    assert any(o.end_sec - o.start_sec >= 24.9 for o in out)
