from datetime import datetime, timedelta
from typing import List

from pipeline.schemas import CandidateVideo


def discover_candidates(limit: int = 5) -> List[CandidateVideo]:
    now = datetime.utcnow()
    candidates: List[CandidateVideo] = []
    for idx in range(limit):
        published = (now - timedelta(hours=(idx + 1) * 4)).isoformat()
        candidates.append(
            CandidateVideo(
                id=f"source_{idx+1}",
                url=f"https://youtube.com/watch?v=demo{idx+1}",
                title=f"Demo trending video {idx+1}",
                channel="Demo Channel",
                published_at=published,
                reason="Strong opening and high-comment velocity.",
                engagement_signals={
                    "views_24h": float(10000 - idx * 1000),
                    "engagement_score": float(0.9 - idx * 0.1),
                },
            )
        )
    return candidates

