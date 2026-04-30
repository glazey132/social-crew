import sqlite3
from pathlib import Path
from typing import Iterable, List, Optional, Set

from pipeline.schemas import ApprovalStatus, ApprovalItem, RunRecord


class StateStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    total_candidates INTEGER NOT NULL,
                    total_clips INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS approvals (
                    run_id TEXT NOT NULL,
                    clip_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    caption_suggestion TEXT NOT NULL,
                    video_path TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    PRIMARY KEY (run_id, clip_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_sources (
                    source_id TEXT PRIMARY KEY,
                    processed_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save_run(self, run: RunRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO runs(run_id, created_at, status, total_candidates, total_clips)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run.run_id, run.created_at, run.status.value, run.total_candidates, run.total_clips),
            )
            conn.commit()

    def update_run_status(self, run_id: str, status: ApprovalStatus, total_clips: Optional[int] = None) -> None:
        with self._connect() as conn:
            if total_clips is None:
                conn.execute("UPDATE runs SET status=? WHERE run_id=?", (status.value, run_id))
            else:
                conn.execute(
                    "UPDATE runs SET status=?, total_clips=? WHERE run_id=?",
                    (status.value, total_clips, run_id),
                )
            conn.commit()

    def save_approval_items(self, items: Iterable[ApprovalItem], status: ApprovalStatus) -> None:
        with self._connect() as conn:
            for item in items:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO approvals(run_id, clip_id, title, caption_suggestion, video_path, metadata_json, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.run_id,
                        item.clip_id,
                        item.title,
                        item.caption_suggestion,
                        item.video_path,
                        str(item.metadata),
                        status.value,
                    ),
                )
            conn.commit()

    def mark_approval(self, run_id: str, clip_id: str, status: ApprovalStatus) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE approvals SET status=? WHERE run_id=? AND clip_id=?",
                (status.value, run_id, clip_id),
            )
            conn.commit()

    def add_processed_sources(self, source_ids: Iterable[str], processed_at: str) -> None:
        with self._connect() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO processed_sources(source_id, processed_at) VALUES (?, ?)",
                [(source_id, processed_at) for source_id in source_ids],
            )
            conn.commit()

    def get_processed_source_ids(self) -> Set[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT source_id FROM processed_sources").fetchall()
        return {row[0] for row in rows}

    def get_run_approvals(self, run_id: str) -> List[tuple]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT clip_id, status, video_path FROM approvals WHERE run_id=?",
                (run_id,),
            ).fetchall()

