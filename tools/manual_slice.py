#!/usr/bin/env python3
"""
Slice a local video by start/end time and render TikTok-ready 9:16 output.

Loads ``.env`` from the repo root when present (OUTPUT_DIR etc.).
Can be run as ``python tools/manual_slice.py`` without setting PYTHONPATH
(the repo root is prepended to ``sys.path``).
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.config import PipelineConfig  # noqa: E402
from pipeline.env_loader import load_dotenv  # noqa: E402
from pipeline.schemas import ClipSegment  # noqa: E402
from tools.clipping import render_clip  # noqa: E402
from tools.timeparse import parse_time_seconds  # noqa: E402
from tools.transcribe import _get_video_duration  # noqa: E402

LOGGER = logging.getLogger(__name__)

_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_-]+")


def _default_candidate_id(video_path: Path) -> str:
    stem = video_path.stem or "manual"
    s = _SAFE_ID_RE.sub("_", stem).strip("_")
    return s[:200] if s else "manual"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Render a vertical 1080×1920 clip between --start and --end from a "
            "local video (same FFmpeg path as the main pipeline)."
        ),
    )
    p.add_argument("video", type=Path, help="Path to local source video")
    p.add_argument(
        "--start",
        required=True,
        metavar="TIME",
        help='Start time (e.g. 3600, "60:30", or "1:15:30")',
    )
    p.add_argument(
        "--end",
        required=True,
        metavar="TIME",
        help="Segment end time on the source timeline (must be greater than --start)",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Defaults to OUTPUT_DIR from .env / PipelineConfig",
    )
    p.add_argument("--hook", default="Manual clip", help="Subtitle / hook text (single cue SRT)")
    p.add_argument(
        "--id",
        dest="candidate_id",
        metavar="NAME",
        default=None,
        help="Output basename id (default: sanitized source filename stem)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not invoke FFmpeg; write placeholder outputs",
    )
    return p


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    env_path = ROOT / ".env"
    if load_dotenv(env_path):
        LOGGER.info("Loaded environment from %s", env_path)

    args = _build_parser().parse_args()

    cfg = PipelineConfig.from_env()
    output_dir = args.output_dir.resolve() if args.output_dir else cfg.output_dir
    video = args.video.resolve()

    if not video.is_file():
        raise SystemExit(f"Video not found: {video}")

    start_sec = parse_time_seconds(args.start)
    end_sec = parse_time_seconds(args.end)

    if start_sec >= end_sec:
        raise SystemExit("--end must be greater than --start")

    try:
        duration = _get_video_duration(str(video))
    except Exception as exc:
        LOGGER.warning("Could not probe duration (ffprobe): %s — continuing anyway", exc)
        duration = None

    eps = 0.05
    if duration is not None:
        if start_sec > duration + eps:
            raise SystemExit(
                f"--start {start_sec}s is beyond file duration (~{duration:.1f}s)"
            )
        if end_sec > duration + eps:
            LOGGER.warning(
                "--end %.3fs is beyond file duration (~%.1fs); FFmpeg may shorten output",
                end_sec,
                duration,
            )

    cid_raw = args.candidate_id.strip() if args.candidate_id else _default_candidate_id(video)
    candidate_id = _SAFE_ID_RE.sub("_", cid_raw).strip("_")[:200]
    if not candidate_id:
        candidate_id = "manual"

    segment = ClipSegment(
        candidate_id=candidate_id,
        start_sec=start_sec,
        end_sec=end_sec,
        hook_text=args.hook,
        confidence=1.0,
    )

    LOGGER.info(
        "Slicing %s [%.3fs .. %.3fs] -> %s",
        video,
        start_sec,
        end_sec,
        output_dir,
    )

    clip = render_clip(
        source_path=video,
        output_dir=output_dir,
        segment=segment,
        dry_run=args.dry_run,
    )

    print(f"video: {clip.video_path}")
    print(f"subtitle: {clip.subtitle_path}")
    print(f"thumbnail: {clip.thumbnail_path}")
    print(f"duration_sec: {clip.duration_sec:.3f}")


if __name__ == "__main__":
    main()
