import argparse
import logging
from pathlib import Path

from pipeline.agent_factory import build_social_crew
from pipeline.config import PipelineConfig
from pipeline.env_loader import load_dotenv
from pipeline.orchestrator import HermesOrchestrator
from pipeline.state_store import StateStore
from tools.telegram import TelegramClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOGGER = logging.getLogger(__name__)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python social_crew.py",
        description=(
            "Run the daily clipping pipeline, or use --download to grab a single "
            "YouTube video into DOWNLOADS_DIR and exit (skips Telegram + agents)."
        ),
    )
    parser.add_argument(
        "--download",
        metavar="URL",
        help="Download a single YouTube video and exit. Uses configured backend + resolution.",
    )
    parser.add_argument(
        "--max-resolution",
        type=int,
        default=None,
        help="Override MAX_DOWNLOAD_RESOLUTION (only used with --download).",
    )
    return parser


def main() -> None:
    args = _build_arg_parser().parse_args()

    env_path = Path(__file__).resolve().parent / ".env"
    if load_dotenv(env_path):
        LOGGER.info("Loaded environment from %s", env_path)

    config = PipelineConfig.from_env()

    if args.download:
        from tools.download import download_video

        max_res = args.max_resolution or config.max_download_resolution
        LOGGER.info(
            "Direct download: url=%s backend=%s max_resolution=%d",
            args.download, config.download_backend, max_res,
        )
        out = download_video(
            args.download,
            config.downloads_dir,
            max_resolution=max_res,
            backend=config.download_backend,
            ytdlp=config.ytdlp,
        )
        print(out)
        return

    if not config.dry_run and (not config.telegram_bot_token or not config.telegram_chat_id):
        LOGGER.error(
            "Telegram credentials missing. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env "
            "or set DRY_RUN=true for local runs without Telegram."
        )
        raise RuntimeError("Missing required Telegram credentials (required when DRY_RUN is false)")
    if config.dry_run and (not config.telegram_bot_token or not config.telegram_chat_id):
        LOGGER.info("Telegram not configured; continuing in DRY_RUN mode without sending messages.")
    
    state_store = StateStore(config.state_db_path)
    telegram = TelegramClient(
        bot_token=config.telegram_bot_token,
        chat_id=config.telegram_chat_id,
    )
    orchestrator = HermesOrchestrator(
        config=config,
        state_store=state_store,
        telegram=telegram,
    )

    # Keep CrewAI configured and available for richer agent reasoning.
    build_social_crew(config.llm_model, config.llm_base_url)

    run_id = orchestrator.run_daily()
    LOGGER.info("Pipeline completed. Approval run_id: %s", run_id)


if __name__ == "__main__":
    main()
