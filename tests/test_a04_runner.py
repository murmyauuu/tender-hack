from pathlib import Path

from tools.run_a04_e2e import run_smoke


def test_a04_runner_records_real_backend_operator_flow(tmp_path: Path) -> None:
    result = run_smoke(tmp_path)

    assert result["classification"] == "real backend / controlled no-model dependencies"
    assert result["handoff"]["ticket_before_confirmation"] is None
    assert result["handoff"]["first_status_code"] == 201
    assert result["handoff"]["repeat_status_code"] == 200
    assert result["handoff"]["same_ticket"] is True
    assert result["operator_reply"]["missing_key_status"] == 401
    assert result["operator_reply"]["forged_fields_status"] == 422
    assert result["operator_reply"]["author_id"] == "operator-smoke"
    assert result["operator_reply"]["responder_type"] == "operator"
    assert result["operator_reply"]["answer_origin"] == "operator"
    assert result["transitions"] == [
        "handoff_offered/ticket:none",
        "handed_off/ticket:new",
        "handed_off/ticket:waiting_user",
        "handed_off/ticket:new",
        "resolved/ticket:resolved",
    ]
    assert result["user_to_operator_reply"]["generation_delta"] == 0
    assert result["user_to_operator_reply"]["retrieval_delta"] == 0
    assert result["security"]["foreign_case_status"] == 404
