import sys
import types
from pathlib import Path

from pipeline.config import PipelineConfig
from pipeline.orchestrator import HermesOrchestrator
from pipeline.schemas import ApprovalStatus, CandidateVideo, ClipSegment, RenderedClip
from pipeline.state_store import StateStore
from tools.telegram import TelegramClient


def test_orchestrator_run_daily_persists_pending_approvals(tmp_path: Path, monkeypatch, ytdlp_minimal):
    config = PipelineConfig(
        llm_model="ollama/test",
        llm_base_url="http://localhost:11434",
        workspace_dir=tmp_path,
        output_dir=tmp_path / "outputs",
        downloads_dir=tmp_path / "downloads",
        state_db_path=tmp_path / "state.db",
        telegram_bot_token="",
        telegram_chat_id="",
        daily_clip_limit=2,
        max_candidates=3,
        max_download_resolution=1080,
        download_backend="pytubefix",
        dry_run=True,
        ytdlp=ytdlp_minimal,
    )
    store = StateStore(config.state_db_path)
    telegram = TelegramClient(bot_token="", chat_id="")
    orchestrator = HermesOrchestrator(config=config, state_store=store, telegram=telegram)

    monkeypatch.setattr(
        "pipeline.orchestrator.discover_candidates",
        lambda limit=3: [
            CandidateVideo(
                id="src_1",
                url="https://youtube.com/watch?v=1",
                title="A",
                channel="C",
                published_at="2026-01-01T00:00:00",
                reason="R1",
                engagement_signals={"engagement_score": 0.9},
            )
        ],
    )
    monkeypatch.setattr(
        "tools.download.download_video",
        lambda *args, **kwargs: tmp_path / "src_1.mp4",
    )
    # Avoid importing real tools.transcribe (faster_whisper / numpy) during monkeypatch resolution.
    fake_transcribe = types.ModuleType("tools.transcribe")
    fake_transcribe.transcribe_video = lambda _: [
        ClipSegment(candidate_id="src_1", start_sec=0, end_sec=30, hook_text="hook", confidence=0.95)
    ]
    monkeypatch.setitem(sys.modules, "tools.transcribe", fake_transcribe)
    fake_clipping = types.ModuleType("tools.clipping")
    fake_clipping.render_clip = lambda source_path, output_dir, segment, dry_run=True: RenderedClip(
        clip_id="clip_1",
        candidate_id=segment.candidate_id,
        video_path=str(tmp_path / "clip_1.mp4"),
        subtitle_path=str(tmp_path / "clip_1.srt"),
        thumbnail_path=str(tmp_path / "clip_1.jpg"),
        duration_sec=30,
    )
    monkeypatch.setitem(sys.modules, "tools.clipping", fake_clipping)

    run_id = orchestrator.run_daily()
    approvals = store.get_run_approvals(run_id)
    assert len(approvals) == 1
    assert approvals[0][1] == ApprovalStatus.PENDING_APPROVAL.value

    orchestrator.handle_telegram_decision(run_id=run_id, clip_id="clip_1", decision="approve")
    approvals = store.get_run_approvals(run_id)
    assert approvals[0][1] == ApprovalStatus.APPROVED_MANUAL_UPLOAD.value


def test_orchestrator_filters_processed_sources(tmp_path: Path, ytdlp_minimal):
    config = PipelineConfig(
        llm_model="ollama/test",
        llm_base_url="http://localhost:11434",
        workspace_dir=tmp_path,
        output_dir=tmp_path / "outputs",
        downloads_dir=tmp_path / "downloads",
        state_db_path=tmp_path / "state.db",
        telegram_bot_token="",
        telegram_chat_id="",
        daily_clip_limit=1,
        max_candidates=3,
        max_download_resolution=1080,
        download_backend="pytubefix",
        dry_run=True,
        ytdlp=ytdlp_minimal,
    )
    store = StateStore(config.state_db_path)
    store.add_processed_sources(["src_seen"], "2026-01-01T00:00:00")

    orchestrator = HermesOrchestrator(config=config, state_store=store, telegram=TelegramClient("", ""))
    selected = orchestrator._select_candidates(
        [
            CandidateVideo(
                id="src_seen",
                url="https://youtube.com/watch?v=seen",
                title="Seen",
                channel="c",
                published_at="2026-01-01T00:00:00",
                reason="seen",
                engagement_signals={"engagement_score": 0.99},
            ),
            CandidateVideo(
                id="src_new",
                url="https://youtube.com/watch?v=new",
                title="New",
                channel="c",
                published_at="2026-01-01T00:00:00",
                reason="new",
                engagement_signals={"engagement_score": 0.80},
            ),
        ]
    )

    assert len(selected) == 1
    assert selected[0].id == "src_new"

