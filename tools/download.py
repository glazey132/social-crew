from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Union

from pipeline.config import YtdlpConfig

LOGGER = logging.getLogger(__name__)


def build_ytdlp_opts(ytdlp: YtdlpConfig, output_template: Union[str, Path]) -> Dict[str, Any]:
    """Legacy yt-dlp option builder. Used only when DOWNLOAD_BACKEND=ytdlp."""
    if ytdlp.cookies_path_requested is not None and ytdlp.cookies_file is None:
        LOGGER.warning(
            "YTDLP_COOKIES_FILE is set but file not found: %s (downloads may 403 without cookies)",
            ytdlp.cookies_path_requested,
        )

    opts: Dict[str, Any] = {
        "outtmpl": str(output_template),
        "format": ytdlp.format_selector,
        "quiet": True,
        "noprogress": True,
        "noplaylist": True,
        "retries": 3,
        "fragment_retries": 3,
    }
    if ytdlp.force_ipv4:
        opts["source_address"] = "0.0.0.0"
    if ytdlp.cookies_file is not None:
        opts["cookiefile"] = str(ytdlp.cookies_file)
    elif ytdlp.cookies_from_browser is not None:
        opts["cookiesfrombrowser"] = ytdlp.cookies_from_browser
    if ytdlp.player_clients:
        opts["extractor_args"] = {"youtube": {"player_client": list(ytdlp.player_clients)}}
    return opts


def _resolution_int(stream: Any) -> int:
    res = getattr(stream, "resolution", None)
    if not res:
        return 0
    digits = "".join(c for c in str(res) if c.isdigit())
    return int(digits) if digits else 0


def _is_h264(stream: Any) -> bool:
    codecs = getattr(stream, "codecs", None) or []
    return any(str(c).lower().startswith("avc1") for c in codecs)


def _pick_video_stream(streams: Any, max_resolution: int) -> Any:
    """H.264 mp4 <= max_resolution preferred; falls back to any mp4 video <= cap."""
    mp4_videos = list(streams.filter(adaptive=True, only_video=True, file_extension="mp4"))
    capped = [s for s in mp4_videos if _resolution_int(s) <= max_resolution]
    h264 = [s for s in capped if _is_h264(s)]
    if h264:
        return max(h264, key=_resolution_int)
    if capped:
        LOGGER.warning(
            "No H.264 mp4 video <= %dp found; falling back to non-H.264 (clipping will be slower)",
            max_resolution,
        )
        return max(capped, key=_resolution_int)
    return None


def _pick_audio_stream(streams: Any) -> Any:
    """Highest-bitrate AAC m4a audio."""
    return (
        streams.filter(adaptive=True, only_audio=True, file_extension="mp4")
        .order_by("abr")
        .desc()
        .first()
    )


def _ffmpeg_merge(video_path: Path, audio_path: Path, out_path: Path) -> None:
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-c", "copy",
        str(out_path),
    ]
    LOGGER.info("ffmpeg merge -> %s", out_path)
    subprocess.run(cmd, check=True)


def _download_via_pytubefix(url: str, downloads_dir: Path, max_resolution: int) -> Path:
    from pytubefix import YouTube  # local import; keeps pytest collection light

    yt = YouTube(url)
    video_id = yt.video_id
    final_path = downloads_dir / f"{video_id}.mp4"
    if final_path.exists():
        LOGGER.info("download_video cache hit: %s", final_path)
        return final_path

    video_stream = _pick_video_stream(yt.streams, max_resolution)
    audio_stream = _pick_audio_stream(yt.streams)
    if video_stream is None:
        raise RuntimeError(f"No suitable mp4 video stream <= {max_resolution}p for {url}")
    if audio_stream is None:
        raise RuntimeError(f"No suitable m4a audio stream for {url}")

    LOGGER.info(
        "download id=%s res=%sp video_codec=%s audio_abr=%s",
        video_id,
        _resolution_int(video_stream),
        getattr(video_stream, "codecs", []),
        getattr(audio_stream, "abr", "?"),
    )

    with tempfile.TemporaryDirectory(prefix=f"dl_{video_id}_", dir=str(downloads_dir)) as tmpdir:
        tmp = Path(tmpdir)
        v_path = Path(video_stream.download(output_path=str(tmp), filename="video.mp4"))
        a_path = Path(audio_stream.download(output_path=str(tmp), filename="audio.m4a"))
        _ffmpeg_merge(v_path, a_path, final_path)

    return final_path


def _download_via_ytdlp(url: str, downloads_dir: Path, ytdlp: YtdlpConfig) -> Path:
    import yt_dlp

    output_template = downloads_dir / "%(id)s.%(ext)s"
    ydl_opts = build_ytdlp_opts(ytdlp, output_template)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = ydl.prepare_filename(info)
    return Path(path)


def download_video(
    url: str,
    downloads_dir: Union[str, Path],
    *,
    max_resolution: int = 1080,
    dry_run: bool = False,
    backend: str = "pytubefix",
    ytdlp: Optional[YtdlpConfig] = None,
) -> Path:
    """Download a video into ``downloads_dir`` and return the final mp4 path.

    Default backend is ``pytubefix`` (no cookies / PO token plumbing required).
    Set ``backend="ytdlp"`` to use the legacy yt-dlp + bgutil PO token path
    (requires a configured ``YtdlpConfig``).
    """
    downloads_dir = Path(downloads_dir)
    downloads_dir.mkdir(parents=True, exist_ok=True)

    if dry_run:
        fake = downloads_dir / "dry_run_source.mp4"
        fake.write_bytes(b"dry-run")
        return fake

    if backend == "pytubefix":
        return _download_via_pytubefix(url, downloads_dir, max_resolution)
    if backend == "ytdlp":
        if ytdlp is None:
            raise ValueError("backend='ytdlp' requires ytdlp=YtdlpConfig(...)")
        return _download_via_ytdlp(url, downloads_dir, ytdlp)
    raise ValueError(f"Unknown DOWNLOAD_BACKEND: {backend!r}")
