import logging
from pathlib import Path

import pytest

from pipeline.config import PipelineConfig, YtdlpConfig
from tools.download import build_ytdlp_opts


def _make(**overrides) -> YtdlpConfig:
    base = dict(
        cookies_file=None,
        cookies_path_requested=None,
        cookies_from_browser=None,
        format_selector="18/best[ext=mp4]/best",
        force_ipv4=False,
        player_clients=(),
    )
    base.update(overrides)
    return YtdlpConfig(**base)


def test_build_ytdlp_opts_cookiefile_wins_over_browser(tmp_path: Path):
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n")
    ytdlp = _make(
        cookies_file=cookies,
        cookies_path_requested=cookies,
        cookies_from_browser=("chrome", "Default", None, None),
    )
    opts = build_ytdlp_opts(ytdlp, tmp_path / "%(id)s.%(ext)s")
    assert opts["cookiefile"] == str(cookies)
    assert "cookiesfrombrowser" not in opts
    assert opts["format"] == "18/best[ext=mp4]/best"
    assert opts["noplaylist"] is True


def test_build_ytdlp_opts_browser_when_no_cookiefile():
    ytdlp = _make(cookies_from_browser=("safari", None, None, None), format_selector="best")
    opts = build_ytdlp_opts(ytdlp, "out.%(ext)s")
    assert opts["cookiesfrombrowser"] == ("safari", None, None, None)
    assert "cookiefile" not in opts


def test_build_ytdlp_opts_force_ipv4_sets_source_address():
    opts = build_ytdlp_opts(_make(force_ipv4=True), "x.%(ext)s")
    assert opts["source_address"] == "0.0.0.0"


def test_build_ytdlp_opts_warns_missing_cookie_file(caplog: pytest.LogCaptureFixture, tmp_path: Path):
    missing = tmp_path / "missing_cookies.txt"
    ytdlp = _make(cookies_path_requested=missing)
    with caplog.at_level(logging.WARNING):
        build_ytdlp_opts(ytdlp, "o.%(ext)s")
    assert "not found" in caplog.text
    assert str(missing) in caplog.text


def test_build_ytdlp_opts_player_clients_set_extractor_args():
    ytdlp = _make(player_clients=("web", "tv", "android"))
    opts = build_ytdlp_opts(ytdlp, "o.%(ext)s")
    assert opts["extractor_args"] == {"youtube": {"player_client": ["web", "tv", "android"]}}


def test_build_ytdlp_opts_no_extractor_args_when_no_player_clients():
    opts = build_ytdlp_opts(_make(), "o.%(ext)s")
    assert "extractor_args" not in opts


def test_from_env_ytdlp_cookies_from_browser(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("STATE_DB_PATH", str(tmp_path / "s.db"))
    monkeypatch.setenv("YTDLP_COOKIES_FROM_BROWSER", "chrome:Default")
    cfg = PipelineConfig.from_env()
    assert cfg.ytdlp.cookies_from_browser == ("chrome", "Default", None, None)
    assert cfg.ytdlp.cookies_file is None
    assert cfg.ytdlp.player_clients == ()


def test_from_env_ytdlp_player_clients_csv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("STATE_DB_PATH", str(tmp_path / "s.db"))
    monkeypatch.setenv("YTDLP_PLAYER_CLIENT", "web, tv ,android")
    cfg = PipelineConfig.from_env()
    assert cfg.ytdlp.player_clients == ("web", "tv", "android")
