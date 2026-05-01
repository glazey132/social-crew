import os
import re
from datetime import datetime, timedelta
from typing import List

from pipeline.schemas import CandidateVideo

# Real 11-character YouTube IDs so yt_dlp accepts URLs when DRY_RUN=false.
# Replace with YouTube Data API or search results in production.
_DEMO_VIDEO_IDS = (
    "EvIBrUDnh8s",  # default first pick (user integration test)
    "dQw4w9WgXcQ",  # Rick Astley - Never Gonna Give You Up
    "9bZkp7q19f0",  # PSY - GANGNAM STYLE
    "kJQP7kiw5Fk",  # Luis Fonsi - Despacito
    "OPf0YbXqDm0",  # Mark Ronson - Uptown Funk
    "CevxZvSJLk8",  # Taylor Swift - Shake It Off
)


def _youtube_id_from_url(url: str) -> str:
    match = re.search(r"(?:[?&]v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    if not match:
        raise ValueError(f"Could not parse 11-character YouTube id from URL: {url}")
    return match.group(1)


def discover_candidates(limit: int = 5) -> List[CandidateVideo]:
    forced = os.getenv("SINGLE_TEST_VIDEO_URL", "").strip()
    if forced:
        video_id = _youtube_id_from_url(forced)
        url = f"https://www.youtube.com/watch?v={video_id}"
        now = datetime.utcnow().isoformat()
        return [
            CandidateVideo(
                id=f"source_{video_id}",
                url=url,
                title="Single test video (SINGLE_TEST_VIDEO_URL)",
                channel="Manual test",
                published_at=now,
                reason="Forced URL for integration testing; bypasses demo rotation.",
                engagement_signals={"engagement_score": 1.0, "views_24h": 0.0},
            )
        ]

    now = datetime.utcnow()
    candidates: List[CandidateVideo] = []
    for idx in range(limit):
        published = (now - timedelta(hours=(idx + 1) * 4)).isoformat()
        video_id = _DEMO_VIDEO_IDS[idx % len(_DEMO_VIDEO_IDS)]
        candidates.append(
            CandidateVideo(
                id=f"source_{idx+1}",
                url=f"https://www.youtube.com/watch?v={video_id}",
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

