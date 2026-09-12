"""Tests: fixture runner полного сценария (D02).

Всё работает на C0 fixtures без A02; mock-результаты помечаются mock=True.
"""

from __future__ import annotations

import asyncio

import pytest

from evaluation.runner import records
from evaluation.runner.driver import poll_until_terminal
from evaluation.runner.fixture_driver import (
    AUTO_CASE,
    ERROR_CASE,
    HANDOFF_CASE,
    RETRY_ANSWER,
    FixtureDriver,
    state_summary,
)
from evaluation.runner.records import DriverError
from evaluation.runner.suite import run_full_scenario

REQUIRED_OPERATIONS = {"session", "new_case", "poll_request", "case", "source",
                       "feedback", "handoff", "reply", "retry"}


def _run(coro):
    return asyncio.run(coro)


def _key(i: int) -> str:
    return f"12345678-1234-4000-8000-{i:012d}"


def test_required_operations_recorded():
    driver = FixtureDriver()
    report = _run(run_full_scenario(driver))
    names = {op.operation for op in report.operations}
    assert REQUIRED_OPERATIONS.issubset(names), f"missing ops: {REQUIRED_OPERATIONS - names}"
    counts = report.counts()
    assert counts["total"] >= 16
    assert counts["errors"] == 0
    assert report.mock is True


def test_auto_answer_feedback_no_double_bump():
    driver = FixtureDriver()
    session = _run(driver.create_session())
    assert str(session.payload["session_id"]) == "11111111-1111-4111-8111-111111111111"

    accepted = _run(driver.chat(case_id=None, expected_case_version=None,
                                request_key=_key(1), text="вопрос", retry_of=None))
    case_id = str(accepted.payload["case_id"])
    assert case_id == AUTO_CASE
    req_id = str(accepted.payload["request_id"])

    res, seen = _run(poll_until_terminal(driver, req_id, max_attempts=5))
    assert res.payload["status"] == "final"
    assert seen == ["processing", "final"]

    case_view = _run(driver.get_case(case_id)).payload
    assert case_view["case"]["case_version"] == 2
    answer_ids = [str(m["message_id"]) for m in case_view["messages"] if m["kind"] == "answer"]
    assert len(answer_ids) == 1

    src = _run(driver.get_source(case_view["messages"][-1]["source_ids"][0])).payload
    assert src["source_id"] == "source-demo"

    fb1 = _run(driver.post_feedback(message_id=answer_ids[0], useful=True, solved=True)).payload
    assert fb1["outcome_applied"] is True
    case_view2 = _run(driver.get_case(case_id)).payload
    assert case_view2["case"]["status"] == "resolved"
    assert case_view2["case"]["case_version"] == 3

    fb2 = _run(driver.post_feedback(message_id=answer_ids[0], useful=True, solved=True)).payload
    assert fb2["outcome_applied"] is False
    assert fb2["case_version"] == 3
    case_view3 = _run(driver.get_case(case_id)).payload
    assert case_view3["case"]["case_version"] == 3


def test_handoff_reply_feedback_operator():
    driver = FixtureDriver()
    # slot 0: answer case
    _run(driver.chat(case_id=None, expected_case_version=None, request_key=_key(1),
                     text="answerable", retry_of=None))
    # slot 1: handoff case
    accepted = _run(driver.chat(case_id=None, expected_case_version=None, request_key=_key(2),
                                text="unanswerable", retry_of=None))
    case_id = str(accepted.payload["case_id"])
    assert case_id == HANDOFF_CASE
    req_id = str(accepted.payload["request_id"])
    res, _ = _run(poll_until_terminal(driver, req_id, max_attempts=5))
    assert res.payload["status"] == "final"

    case_view = _run(driver.get_case(case_id)).payload
    assert case_view["case"]["status"] == "handoff_offered"
    version = case_view["case"]["case_version"]

    ticket = _run(driver.handoff(case_id=case_id, request_key=_key(3),
                                 expected_case_version=version)).payload
    assert ticket["status"] == "new"
    # повтор с актуальной версией (после первого перехода) → существующий Ticket
    ticket2 = _run(driver.handoff(case_id=case_id, request_key=_key(3),
                                  expected_case_version=version + 1)).payload
    assert ticket2["ticket_id"] == ticket["ticket_id"]

    msg = _run(driver.operator_reply(ticket_id=str(ticket["ticket_id"]), request_key=_key(4),
                                     expected_case_version=version + 1,
                                     text="ответ оператора",
                                     next_status="waiting_user")).payload
    assert msg["responder_type"] == "operator"

    case_view2 = _run(driver.get_case(case_id)).payload
    answer_ids = [str(m["message_id"]) for m in case_view2["messages"] if m["kind"] == "answer"]
    assert str(msg["message_id"]) in answer_ids
    fb = _run(driver.post_feedback(message_id=answer_ids[-1], solved=True)).payload
    assert fb["outcome_applied"] is True
    final = _run(driver.get_case(case_id)).payload
    assert final["case"]["status"] == "resolved"
    assert final["ticket"]["resolved_by"] == "operator"


def test_error_then_retry_reuses_user_message():
    driver = FixtureDriver()
    _run(driver.chat(case_id=None, expected_case_version=None, request_key=_key(1),
                     text="a", retry_of=None))
    _run(driver.chat(case_id=None, expected_case_version=None, request_key=_key(2),
                     text="b", retry_of=None))
    accepted = _run(driver.chat(case_id=None, expected_case_version=None, request_key=_key(3),
                                text="errorful", retry_of=None))
    case_id = str(accepted.payload["case_id"])
    assert case_id == ERROR_CASE
    req_id = str(accepted.payload["request_id"])

    res, seen = _run(poll_until_terminal(driver, req_id, max_attempts=5))
    assert res.payload["status"] == "error"
    assert res.payload["error"]["code"] == "MODEL_UNAVAILABLE"
    assert res.payload["error"]["retryable"] is True

    case_view = _run(driver.get_case(case_id)).payload
    assert case_view["case"]["status"] == "open"
    assert all(m["kind"] != "answer" for m in case_view["messages"])

    retry = _run(driver.chat(case_id=case_id, expected_case_version=1,
                             request_key=_key(4), text=None, retry_of=req_id)).payload
    assert retry["user_message_id"] == accepted.payload["user_message_id"]

    res2, _ = _run(poll_until_terminal(driver, str(retry["request_id"]), max_attempts=5))
    assert res2.payload["status"] == "final"
    case_view2 = _run(driver.get_case(case_id)).payload
    answers = [m for m in case_view2["messages"] if m["kind"] == "answer"]
    assert len(answers) == 1
    assert str(answers[0]["message_id"]) == RETRY_ANSWER


def test_stale_case_version_guard():
    driver = FixtureDriver()
    accepted = _run(driver.chat(case_id=None, expected_case_version=None, request_key=_key(1),
                                text="a", retry_of=None))
    case_id = str(accepted.payload["case_id"])
    with pytest.raises(DriverError) as exc:
        _run(driver.chat(case_id=case_id, expected_case_version=99,
                         request_key=_key(2), text="late", retry_of=None))
    assert exc.value.code == "STALE_CASE_VERSION"
    assert exc.value.current_case_version == 1


def test_determinism_between_runs():
    reports = [_run(run_full_scenario(FixtureDriver())) for _ in range(2)]
    sigs = [
        (r.counts(), [(op.operation, op.outcome) for op in r.operations])
        for r in reports
    ]
    assert sigs[0] == sigs[1]
    assert reports[0].counts() == reports[1].counts()


def test_state_signature_is_deterministic():
    d1, d2 = FixtureDriver(), FixtureDriver()
    _run(run_full_scenario(d1))
    _run(run_full_scenario(d2))
    assert d1.dump_state_signature() == d2.dump_state_signature()
    assert state_summary(d1) == state_summary(d2)
    assert state_summary(d1)["22222222-2222-4222-8222-222222222222"]["status"] == "resolved"


def test_poll_timeout_raises_driver_error():
    class NeverFinal:
        name = "never"
        mock = True
        calls = 0

        async def poll_request(self, request_id):
            self.calls += 1
            from tenderhack_contracts import RequestProgress, RequestStatus, RequestView
            from uuid import UUID
            return records.DriverResult(
                RequestView(request_id=UUID(request_id), case_id=UUID("00000000-0000-0000-0000-000000000000"),
                            status=RequestStatus.PROCESSING, progress=RequestProgress.RETRIEVING)
                .model_dump(mode="json"),
                mock=True,
            )

    driver = NeverFinal()
    with pytest.raises(DriverError) as exc:
        _run(poll_until_terminal(driver, "00000000-0000-0000-0000-000000000000",
                                 max_attempts=3, delay_s=0))
    assert exc.value.code == "POLL_TIMEOUT"
    assert exc.value.retryable is True