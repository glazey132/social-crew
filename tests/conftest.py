import pytest

from pipeline.config import YtdlpConfig


@pytest.fixture
def ytdlp_minimal() -> YtdlpConfig:
    return YtdlpConfig(
        cookies_file=None,
        cookies_path_requested=None,
        cookies_from_browser=None,
        format_selector="18/best[ext=mp4]/best",
        force_ipv4=False,
        player_clients=(),
    )
