"""Unit tests for tools/download.py — pytubefix path mocked, no network I/O."""
from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import List

import pytest

from tools import download as download_module
from tools.download import download_video


# ---- Stream / YouTube fakes -----------------------------------------------


class _FakeStream:
    def __init__(self, *, itag, codecs, resolution=None, abr=None, only_video=False, only_audio=False):
        self.itag = itag
        self.codecs = list(codecs)
        self.resolution = resolution
        self.abr = abr
        self.only_video = only_video
        self.only_audio = only_audio
        self.file_extension = "mp4"
        self.downloaded_to: Path | None = None

    def download(self, output_path: str, filename: str) -> str:
        out = Path(output_path) / filename
        out.write_bytes(b"FAKE_STREAM_BYTES")
        self.downloaded_to = out
        return str(out)

    def __repr__(self) -> str:
        return f"<FakeStream itag={self.itag} {self.resolution} codecs={self.codecs}>"


class _FakeStreamQuery:
    """Mimics the chainable subset of pytubefix.StreamQuery we use."""

    def __init__(self, streams: List[_FakeStream]):
        self._streams = list(streams)

    def filter(self, *, adaptive=True, only_video=False, only_audio=False, file_extension="mp4"):
        out = []
        for s in self._streams:
            if only_video and not s.only_video:
                continue
            if only_audio and not s.only_audio:
                continue
            if file_extension and s.file_extension != file_extension:
                continue
            out.append(s)
        return _FakeStreamQuery(out)

    def order_by(self, key: str):
        self._streams.sort(key=lambda s: getattr(s, key) or "", reverse=False)
        return self

    def desc(self):
        self._streams.reverse()
        return self

    def first(self):
        return self._streams[0] if self._streams else None

    def __iter__(self):
        return iter(self._streams)

    def __bool__(self):
        return bool(self._streams)


class _FakeYouTube:
    last_url: str | None = None

    def __init__(self, url: str):
        _FakeYouTube.last_url = url
        self.video_id = "TESTID12345"
        self.title = "Test Video"
        self.streams = _FakeStreamQuery(_default_streams())


def _default_streams() -> List[_FakeStream]:
    return [
        _FakeStream(itag=137, codecs=["avc1.640028"], resolution="1080p", only_video=True),
        _FakeStream(itag=136, codecs=["avc1.4d401f"], resolution="720p", only_video=True),
        _FakeStream(itag=313, codecs=["vp9"], resolution="2160p", only_video=True),
        _FakeStream(itag=140, codecs=["mp4a.40.2"], abr="128kbps", only_audio=True),
        _FakeStream(itag=139, codecs=["mp4a.40.2"], abr="48kbps", only_audio=True),
    ]


def _install_fake_pytubefix(monkeypatch):
    """Install a fake `pytubefix` module so the local import inside download_video uses it."""
    fake = types.ModuleType("pytubefix")
    fake.YouTube = _FakeYouTube
    monkeypatch.setitem(sys.modules, "pytubefix", fake)


# ---- Tests -----------------------------------------------------------------


def test_download_video_dry_run_writes_placeholder(tmp_path: Path):
    out = download_video("https://youtube.com/watch?v=anything", tmp_path, dry_run=True)
    assert out.exists()
    assert out.parent == tmp_path
    assert out.read_bytes() == b"dry-run"


def test_download_video_pytubefix_picks_h264_1080p_and_merges(tmp_path: Path, monkeypatch):
    _install_fake_pytubefix(monkeypatch)

    captured: dict = {}

    def fake_merge(video_path: Path, audio_path: Path, out_path: Path) -> None:
        captured["video"] = video_path
        captured["audio"] = audio_path
        captured["out"] = out_path
        out_path.write_bytes(b"FAKE_MERGED_MP4")

    monkeypatch.setattr(download_module, "_ffmpeg_merge", fake_merge)

    final = download_video("https://youtube.com/watch?v=any", tmp_path, max_resolution=1080)

    assert _FakeYouTube.last_url == "https://youtube.com/watch?v=any"
    assert final == tmp_path / "TESTID12345.mp4"
    assert final.exists()
    assert captured["out"] == final
    # Temp dir should have been cleaned up
    leftover = [p for p in tmp_path.iterdir() if p.is_dir() and p.name.startswith("dl_")]
    assert leftover == []


def test_download_video_falls_back_to_non_h264_when_no_avc1_under_cap(tmp_path: Path, monkeypatch):
    _install_fake_pytubefix(monkeypatch)

    monkeypatch.setattr(download_module, "_ffmpeg_merge", lambda v, a, o: o.write_bytes(b"x"))

    only_vp9 = [
        _FakeStream(itag=248, codecs=["vp9"], resolution="1080p", only_video=True),
        _FakeStream(itag=140, codecs=["mp4a.40.2"], abr="128kbps", only_audio=True),
    ]

    class VP9Only(_FakeYouTube):
        def __init__(self, url):
            super().__init__(url)
            self.streams = _FakeStreamQuery(only_vp9)

    sys.modules["pytubefix"].YouTube = VP9Only
    out = download_video("https://youtube.com/watch?v=any", tmp_path, max_resolution=1080)
    assert out.exists()


def test_download_video_raises_when_no_video_under_cap(tmp_path: Path, monkeypatch):
    _install_fake_pytubefix(monkeypatch)

    only_4k = [
        _FakeStream(itag=313, codecs=["vp9"], resolution="2160p", only_video=True),
        _FakeStream(itag=140, codecs=["mp4a.40.2"], abr="128kbps", only_audio=True),
    ]

    class FourKOnly(_FakeYouTube):
        def __init__(self, url):
            super().__init__(url)
            self.streams = _FakeStreamQuery(only_4k)

    sys.modules["pytubefix"].YouTube = FourKOnly
    with pytest.raises(RuntimeError, match="No suitable mp4 video stream"):
        download_video("https://youtube.com/watch?v=any", tmp_path, max_resolution=1080)


def test_download_video_cache_hit_skips_network(tmp_path: Path, monkeypatch):
    _install_fake_pytubefix(monkeypatch)

    cached = tmp_path / "TESTID12345.mp4"
    cached.write_bytes(b"already here")

    def boom(*_a, **_kw):
        raise AssertionError("merge should not run on cache hit")

    monkeypatch.setattr(download_module, "_ffmpeg_merge", boom)
    out = download_video("https://youtube.com/watch?v=any", tmp_path)
    assert out == cached
    assert cached.read_bytes() == b"already here"


def test_download_video_unknown_backend_raises(tmp_path: Path):
    with pytest.raises(ValueError, match="Unknown DOWNLOAD_BACKEND"):
        download_video("u", tmp_path, backend="bogus")


def test_download_video_ytdlp_backend_requires_config(tmp_path: Path):
    with pytest.raises(ValueError, match="requires ytdlp"):
        download_video("u", tmp_path, backend="ytdlp", ytdlp=None)
