from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, List


class ApprovalStatus(str, Enum):
    CREATED = "created"
    PENDING_APPROVAL = "pending_approval"
    APPROVED_MANUAL_UPLOAD = "approved_manual_upload"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


@dataclass
class CandidateVideo:
    id: str
    url: str
    title: str
    channel: str
    published_at: str
    reason: str
    engagement_signals: Dict[str, float]

    def score(self) -> float:
        return float(self.engagement_signals.get("engagement_score", 0.0))


@dataclass
class ClipSegment:
    candidate_id: str
    start_sec: float
    end_sec: float
    hook_text: str
    confidence: float


@dataclass
class RenderedClip:
    clip_id: str
    candidate_id: str
    video_path: str
    subtitle_path: str
    thumbnail_path: str
    duration_sec: float
    aspect_ratio: str = "9:16"


@dataclass
class VerificationResult:
    clip_id: str
    quality_score: float
    policy_flags: List[str] = field(default_factory=list)
    recommendation: str = "approve"
    notes: str = ""

    def requires_revision(self) -> bool:
        return bool(self.policy_flags) or self.recommendation == "needs_revision"


@dataclass
class ApprovalItem:
    run_id: str
    clip_id: str
    title: str
    caption_suggestion: str
    video_path: str
    metadata: Dict[str, str]


@dataclass
class RunRecord:
    run_id: str
    created_at: str
    status: ApprovalStatus
    total_candidates: int
    total_clips: int

    @classmethod
    def new(cls, run_id: str, total_candidates: int) -> "RunRecord":
        return cls(
            run_id=run_id,
            created_at=datetime.utcnow().isoformat(),
            status=ApprovalStatus.CREATED,
            total_candidates=total_candidates,
            total_clips=0,
        )

    def to_dict(self) -> Dict[str, object]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload

