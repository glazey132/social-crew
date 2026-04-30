from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class PipelineConfig:
    llm_model: str
    llm_base_url: str
    workspace_dir: Path
    output_dir: Path
    state_db_path: Path
    telegram_bot_token: str
    telegram_chat_id: str
    daily_clip_limit: int
    max_candidates: int
    dry_run: bool

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        workspace_dir = Path(os.getenv("WORKSPACE_DIR", ".")).resolve()
        output_dir = Path(os.getenv("OUTPUT_DIR", workspace_dir / "outputs")).resolve()
        state_db_path = Path(os.getenv("STATE_DB_PATH", workspace_dir / "pipeline_state.db")).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        daily_clip_limit = int(os.getenv("DAILY_CLIP_LIMIT", "3"))
        max_candidates = int(os.getenv("MAX_CANDIDATES", "5"))

        if daily_clip_limit <= 0:
            raise ValueError("DAILY_CLIP_LIMIT must be > 0")
        if max_candidates <= 0:
            raise ValueError("MAX_CANDIDATES must be > 0")

        return cls(
            llm_model=os.getenv("LLM_MODEL", "ollama/qwen3.5:35b-a3b"),
            llm_base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434"),
            workspace_dir=workspace_dir,
            output_dir=output_dir,
            state_db_path=state_db_path,
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
            daily_clip_limit=daily_clip_limit,
            max_candidates=max_candidates,
            dry_run=os.getenv("DRY_RUN", "false").lower() in ("1", "true", "yes"),
        )

