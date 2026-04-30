import logging
from pathlib import Path

from pipeline.agent_factory import build_social_crew
from pipeline.config import PipelineConfig
from pipeline.orchestrator import HermesOrchestrator
from pipeline.state_store import StateStore
from tools.telegram import TelegramClient

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOGGER = logging.getLogger(__name__)


def main() -> None:
    config = PipelineConfig.from_env()
    
    # Validate required secrets
    if not config.telegram_bot_token or not config.telegram_chat_id:
        LOGGER.error("Telegram credentials missing. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        raise RuntimeError("Missing required Telegram credentials")
    
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
