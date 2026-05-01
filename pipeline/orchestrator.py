from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Callable, List, Optional
from uuid import uuid4

from pipeline.config import PipelineConfig
from pipeline.schemas import (
    ApprovalItem,
    ApprovalStatus,
    CandidateVideo,
    ClipSegment,
    RenderedClip,
    RunRecord,
    VerificationResult,
)
from pipeline.state_store import StateStore
from tools.download import download_video
from tools.research import discover_candidates
from tools.telegram import TelegramClient

LOGGER = logging.getLogger(__name__)


@dataclass
class HermesOrchestrator:
    config: PipelineConfig
    state_store: StateStore
    telegram: TelegramClient
    now_fn: Callable[[], datetime] = datetime.utcnow

    def run_daily(self) -> str:
        from tools.clipping import render_clip
        from tools.transcribe import transcribe_video

        run_id = f"run_{uuid4().hex[:12]}"
        candidates = self._select_candidates(discover_candidates(limit=self.config.max_candidates))
        run = RunRecord.new(run_id=run_id, total_candidates=len(candidates))
        self.state_store.save_run(run)

        LOGGER.info("run=%s selected_candidates=%d", run_id, len(candidates))
        rendered_clips: List[RenderedClip] = []
        verification: List[VerificationResult] = []

        for candidate in candidates:
            try:
                source_path = self._with_retries(
                    lambda: download_video(
                        candidate.url,
                        self.config.downloads_dir,
                        dry_run=self.config.dry_run,
                        max_resolution=self.config.max_download_resolution,
                        backend=self.config.download_backend,
                        ytdlp=self.config.ytdlp,
                    ),
                    operation="download_video",
                    candidate_id=candidate.id,
                )
                segments = self._with_retries(
                    lambda: transcribe_video(source_path),
                    operation="transcribe_video",
                    candidate_id=candidate.id,
                )
                if not segments:
                    continue
                selected_segment = self._choose_segment(candidate.id, segments)
                rendered = self._with_retries(
                    lambda: render_clip(
                        source_path=source_path,
                        output_dir=self.config.output_dir,
                        segment=selected_segment,
                        dry_run=self.config.dry_run,
                    ),
                    operation="render_clip",
                    candidate_id=candidate.id,
                )
                rendered_clips.append(rendered)
                verification.append(self._verify(rendered))
            except Exception as exc:  # pragma: no cover - defensive
                LOGGER.exception("run=%s candidate=%s failed error=%s", run_id, candidate.id, exc)

        approval_items = self._build_approval_items(run_id, rendered_clips, verification)
        self.state_store.save_approval_items(approval_items, ApprovalStatus.PENDING_APPROVAL)
        self.state_store.update_run_status(
            run_id=run_id,
            status=ApprovalStatus.PENDING_APPROVAL,
            total_clips=len(approval_items),
        )

        self.telegram.send_approval_bundle(run_id=run_id, items=approval_items, dry_run=self.config.dry_run)
        self.state_store.add_processed_sources([c.id for c in candidates], processed_at=self.now_fn().isoformat())
        return run_id

    def handle_telegram_decision(self, run_id: str, clip_id: str, decision: str) -> None:
        if decision == "approve":
            status = ApprovalStatus.APPROVED_MANUAL_UPLOAD
        elif decision == "reject":
            status = ApprovalStatus.REJECTED
        else:
            status = ApprovalStatus.NEEDS_REVISION
        self.state_store.mark_approval(run_id=run_id, clip_id=clip_id, status=status)

    def _with_retries(self, fn: Callable, operation: str, candidate_id: str):
        attempts = 3
        last_error: Optional[Exception] = None
        for attempt in range(1, attempts + 1):
            try:
                return fn()
            except Exception as exc:  # pragma: no cover - defensive
                last_error = exc
                LOGGER.warning(
                    "operation=%s candidate=%s attempt=%d/%d error=%s",
                    operation,
                    candidate_id,
                    attempt,
                    attempts,
                    exc,
                )
        raise RuntimeError(f"{operation} failed for {candidate_id}") from last_error

    def _select_candidates(self, discovered: List[CandidateVideo]) -> List[CandidateVideo]:
        processed = self.state_store.get_processed_source_ids()
        fresh = [item for item in discovered if item.id not in processed]
        fresh.sort(key=lambda c: c.score(), reverse=True)
        return fresh[: self.config.daily_clip_limit]

    def _choose_segment(self, candidate_id: str, segments: List[ClipSegment]) -> ClipSegment:
        ranked = sorted(segments, key=lambda s: s.confidence, reverse=True)
        if not ranked:
            raise ValueError(f"No clip segments found for candidate {candidate_id}")
        return ranked[0]

    def _verify(self, rendered: RenderedClip) -> VerificationResult:
        policy_flags: List[str] = []
        recommendation = "approve"
        score = 0.8
        if rendered.duration_sec > 60:
            policy_flags.append("too_long")
            recommendation = "needs_revision"
            score = 0.4
        return VerificationResult(
            clip_id=rendered.clip_id,
            quality_score=score,
            policy_flags=policy_flags,
            recommendation=recommendation,
            notes="Auto-verifier baseline score.",
        )

    def _build_approval_items(
        self,
        run_id: str,
        clips: List[RenderedClip],
        checks: List[VerificationResult],
    ) -> List[ApprovalItem]:
        check_by_id = {check.clip_id: check for check in checks}
        items: List[ApprovalItem] = []
        for clip in clips:
            check = check_by_id.get(clip.clip_id)
            if check is None:
                continue
            if check.requires_revision():
                continue
            items.append(
                ApprovalItem(
                    run_id=run_id,
                    clip_id=clip.clip_id,
                    title=f"Clip {clip.clip_id}",
                    caption_suggestion=f"Hook: fast insight from source {clip.candidate_id}",
                    video_path=clip.video_path,
                    metadata={
                        "quality_score": f"{check.quality_score:.2f}",
                        "aspect_ratio": clip.aspect_ratio,
                        "duration_sec": f"{clip.duration_sec:.1f}",
                    },
                )
            )
        return items

