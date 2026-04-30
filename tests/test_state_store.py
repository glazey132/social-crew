from pathlib import Path

from pipeline.schemas import ApprovalItem, ApprovalStatus, RunRecord
from pipeline.state_store import StateStore


def test_state_store_run_and_approval_lifecycle(tmp_path: Path):
    db_path = tmp_path / "state.db"
    store = StateStore(db_path)

    run = RunRecord.new(run_id="run_x", total_candidates=3)
    store.save_run(run)
    store.update_run_status("run_x", ApprovalStatus.PENDING_APPROVAL, total_clips=1)

    item = ApprovalItem(
        run_id="run_x",
        clip_id="clip_1",
        title="Clip 1",
        caption_suggestion="test caption",
        video_path="/tmp/clip.mp4",
        metadata={"quality_score": "0.91"},
    )
    store.save_approval_items([item], ApprovalStatus.PENDING_APPROVAL)
    store.mark_approval("run_x", "clip_1", ApprovalStatus.APPROVED_MANUAL_UPLOAD)

    approvals = store.get_run_approvals("run_x")
    assert len(approvals) == 1
    clip_id, status, _ = approvals[0]
    assert clip_id == "clip_1"
    assert status == ApprovalStatus.APPROVED_MANUAL_UPLOAD.value

