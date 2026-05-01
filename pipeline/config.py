from __future__ import annotations

from dataclasses import dataclass
import os
import re
from pathlib import Path
from typing import Optional, Tuple


def _parse_cookies_from_browser(value: str) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
    """Parse YTDLP_COOKIES_FROM_BROWSER into yt-dlp tuple (browser, profile, keyring, container)."""
    mobj = re.fullmatch(
        r"""(?x)
            (?P<name>[^+:]+)
            (?:\s*\+\s*(?P<keyring>[^:]+))?
            (?:\s*:\s*(?!:)(?P<profile>.+?))?
            (?:\s*::\s*(?P<container>.+))?
        """,
        value.strip(),
    )
    if mobj is None:
        raise ValueError(f"invalid YTDLP_COOKIES_FROM_BROWSER: {value!r}")
    browser_name, keyring, profile, container = mobj.group("name", "keyring", "profile", "container")
    return (browser_name.lower(), profile, keyring.upper() if keyring else None, container)


@dataclass(frozen=True)
class YtdlpConfig:
    """yt-dlp options loaded from environment (see README YouTube section)."""

    cookies_file: Optional[Path]
    cookies_path_requested: Optional[Path]
    cookies_from_browser: Optional[Tuple[str, Optional[str], Optional[str], Optional[str]]]
    format_selector: str
    force_ipv4: bool
    player_clients: Tuple[str, ...]


@dataclass(frozen=True)
class PipelineConfig:
    llm_model: str
    llm_base_url: str
    workspace_dir: Path
    output_dir: Path
    downloads_dir: Path
    state_db_path: Path
    telegram_bot_token: str
    telegram_chat_id: str
    daily_clip_limit: int
    max_candidates: int
    max_download_resolution: int
    download_backend: str
    dry_run: bool
    ytdlp: YtdlpConfig

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        workspace_dir = Path(os.getenv("WORKSPACE_DIR", ".")).resolve()
        output_dir = Path(os.getenv("OUTPUT_DIR", workspace_dir / "outputs")).resolve()
        downloads_dir = Path(os.getenv("DOWNLOADS_DIR", workspace_dir / "downloads")).resolve()
        state_db_path = Path(os.getenv("STATE_DB_PATH", workspace_dir / "pipeline_state.db")).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        downloads_dir.mkdir(parents=True, exist_ok=True)

        daily_clip_limit = int(os.getenv("DAILY_CLIP_LIMIT", "3"))
        max_candidates = int(os.getenv("MAX_CANDIDATES", "5"))
        max_download_resolution = int(os.getenv("MAX_DOWNLOAD_RESOLUTION", "1080"))

        if daily_clip_limit <= 0:
            raise ValueError("DAILY_CLIP_LIMIT must be > 0")
        if max_candidates <= 0:
            raise ValueError("MAX_CANDIDATES must be > 0")
        if max_download_resolution <= 0:
            raise ValueError("MAX_DOWNLOAD_RESOLUTION must be > 0")

        download_backend = (os.getenv("DOWNLOAD_BACKEND", "pytubefix").strip().lower() or "pytubefix")
        if download_backend not in ("pytubefix", "ytdlp"):
            raise ValueError("DOWNLOAD_BACKEND must be 'pytubefix' or 'ytdlp'")

        cookies_raw = os.getenv("YTDLP_COOKIES_FILE", "").strip()
        cookies_path_requested: Optional[Path] = None
        cookies_file: Optional[Path] = None
        if cookies_raw:
            p = Path(cookies_raw)
            if not p.is_absolute():
                p = (workspace_dir / p).resolve()
            else:
                p = p.resolve()
            cookies_path_requested = p
            if p.is_file():
                cookies_file = p

        browser_raw = os.getenv("YTDLP_COOKIES_FROM_BROWSER", "").strip()
        cookies_from_browser: Optional[Tuple[str, Optional[str], Optional[str], Optional[str]]] = None
        if browser_raw:
            cookies_from_browser = _parse_cookies_from_browser(browser_raw)

        format_selector = os.getenv("YTDLP_FORMAT", "18/best[ext=mp4]/best").strip() or "18/best[ext=mp4]/best"
        force_ipv4 = os.getenv("YTDLP_FORCE_IPV4", "false").lower() in ("1", "true", "yes")

        player_clients_raw = os.getenv("YTDLP_PLAYER_CLIENT", "").strip()
        player_clients: Tuple[str, ...] = tuple(
            c.strip() for c in player_clients_raw.split(",") if c.strip()
        )

        ytdlp = YtdlpConfig(
            cookies_file=cookies_file,
            cookies_path_requested=cookies_path_requested,
            cookies_from_browser=cookies_from_browser,
            format_selector=format_selector,
            force_ipv4=force_ipv4,
            player_clients=player_clients,
        )

        return cls(
            llm_model=os.getenv("LLM_MODEL", "ollama/qwen3.5:35b-a3b"),
            llm_base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434"),
            workspace_dir=workspace_dir,
            output_dir=output_dir,
            downloads_dir=downloads_dir,
            state_db_path=state_db_path,
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
            daily_clip_limit=daily_clip_limit,
            max_candidates=max_candidates,
            max_download_resolution=max_download_resolution,
            download_backend=download_backend,
            dry_run=os.getenv("DRY_RUN", "false").lower() in ("1", "true", "yes"),
            ytdlp=ytdlp,
        )
