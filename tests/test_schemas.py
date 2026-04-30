from pipeline.schemas import ApprovalStatus, RunRecord


def test_run_record_new_defaults():
    run = RunRecord.new(run_id="run_1", total_candidates=4)
    assert run.run_id == "run_1"
    assert run.total_candidates == 4
    assert run.total_clips == 0
    assert run.status == ApprovalStatus.CREATED


def test_run_record_to_dict_serializes_status():
    run = RunRecord.new(run_id="run_2", total_candidates=2)
    payload = run.to_dict()
    assert payload["status"] == ApprovalStatus.CREATED.value

