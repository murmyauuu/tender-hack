"""Полный сценарий runner-а D02 (10+ операций контракта).

Порядок: session → new_case(ответ) → poll → case → source → feedback(solved)
→ new_case(no-answer) → poll → case → handoff (идемпотентность) → reply →
case → feedback(operator) → new_case(error сценарий) → poll → case → retry →
poll → case. Любая операция логируется OperationRecord; при 501/неготовности
A02 (HttpDriver) прогон корректно завершается как «not run» без потери трассы.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from evaluation.runner.driver import RunnerDriver, poll_until_terminal
from evaluation.runner.records import DriverError, OperationRecord, SuiteReport

log = logging.getLogger(__name__)

ANSWERABLE_QUESTION = "Как зарегистрировать личный кабинет поставщика? (fixture D02)"
HANDOFF_QUESTION = (
    "Каков порядок обжалования решения по жалобе, если регламент покрывает только "
    "чек-лист и не описывает интеграцию предмета? (fixture D02)"
)
ERROR_QUESTION = "Непредусмотренная горящая тема, для которой модель недоступна (fixture D02)"

TERMINAL_POLL_ATTEMPTS = 40


def _utc_now_iso(now: Callable[[], datetime] | None) -> str:
    ts = now() if now else datetime.now(timezone.utc)
    return ts.isoformat().replace("+00:00", "Z")


async def _run_step(
    report: SuiteReport,
    step: str,
    fn: Callable[[], Awaitable["Any"]],
    *,
    inp: Any = None,
    attempts: int = 1,
) -> tuple[Any, Any]:
    """Выполняет шаг, пишет OperationRecord, возвращает (payload, record)."""
    start_ms = int(time.monotonic() * 1000)
    try:
        result = await fn()
        record = OperationRecord(
            operation=step,
            outcome="ok",
            mock=report.mock,
            input=inp,
            output=result.payload,
            error=None,
            elapsed_ms=int(time.monotonic() * 1000) - start_ms,
            attempts=attempts,
            statuses_seen=None,
            notes=None,
        )
        report.add(record)
        return result.payload, record
    except DriverError as exc:
        record = OperationRecord(
            operation=step,
            outcome="error",
            mock=report.mock,
            input=inp,
            output=None,
            error=exc.to_dict(),
            elapsed_ms=int(time.monotonic() * 1000) - start_ms,
            attempts=attempts,
            statuses_seen=None,
            notes=None,
        )
        report.add(record)
        if exc.code in ("NOT_IMPLEMENTED", "CONFIG_ERROR") and not report.mock:
            report.meta["not_run_reason"] = f"API недоступен ({exc.code}): {exc.message}"
        return None, record


def _msg_id(case_payload: dict[str, Any], *, kind: str) -> list[str]:
    """message_id всех сообщений нужного kind из CaseView payload."""
    ids: list[str] = []
    for msg in (case_payload.get("messages") or []):
        if msg.get("kind") == kind:
            ids.append(str(msg["message_id"]))
    return ids


async def run_full_scenario(
    driver: RunnerDriver,
    *,
    poll_delay_s: float = 0.0,
    poll_attempts: int = TERMINAL_POLL_ATTEMPTS,
    now: Callable[[], datetime] | None = None,
) -> SuiteReport:
    report = SuiteReport(
        driver=driver.name,
        scenario="full-v1",
        started_at=_utc_now_iso(now),
        mock=driver.mock,
    )

    def rkey() -> str:
        return uuid.uuid4().hex

    # session
    session_payload, _ = await _run_step(report, "session", driver.create_session)

    # --- case 1: answerable, auto-answer, feedback solved=true
    q1 = ANSWERABLE_QUESTION
    case1_payload, _ = await _run_step(
        report,
        "new_case",
        lambda: driver.chat(
            case_id=None,
            expected_case_version=None,
            request_key=rkey(),
            text=q1,
            retry_of=None,
        ),
        inp={"text": q1, "retry_of": None},
    )
    if case1_payload is None:
        report.meta["stop_reason"] = "new_case failed"
        return report
    req1 = str(case1_payload["request_id"])
    case1_id = str(case1_payload["case_id"])

    start_ms = int(time.monotonic() * 1000)
    poll_result: Any = None
    seen: list[str] = []
    try:
        poll_result, seen = await poll_until_terminal(
            driver, req1, max_attempts=poll_attempts, delay_s=poll_delay_s
        )
        record = OperationRecord(
            operation="poll_request",
            outcome="ok",
            mock=report.mock,
            input={"request_id": req1},
            output=poll_result.payload,
            error=None,
            elapsed_ms=int(time.monotonic() * 1000) - start_ms,
            attempts=len(seen) or 1,
            statuses_seen=seen,
            notes=None,
        )
        report.add(record)
    except DriverError as exc:
        record = OperationRecord(
            operation="poll_request",
            outcome="error",
            mock=report.mock,
            input={"request_id": req1},
            output=None,
            error=exc.to_dict(),
            elapsed_ms=int(time.monotonic() * 1000) - start_ms,
            attempts=poll_attempts,
            statuses_seen=seen or None,
            notes=None,
        )
        report.add(record)
    if poll_result is None:
        report.meta["stop_reason"] = "poll failed"
        return report

    case_view1, _ = await _run_step(report, "case", lambda: driver.get_case(case1_id), inp={"case_id": case1_id})
    if case_view1 is None:
        report.meta["stop_reason"] = "case failed"
        return report

    sources = poll_result.payload.get("candidate_sources") or []
    if sources:
        src = sources[0]
        await _run_step(
            report,
            "source",
            lambda sid=src["source_id"]: driver.get_source(sid),
            inp={"source_id": src["source_id"]},
        )

    ai_answer_ids = [
        mid for mid in _msg_id(case_view1, kind="answer")
    ]
    if ai_answer_ids:
        await _run_step(
            report,
            "feedback",
            lambda mid=ai_answer_ids[-1]: driver.post_feedback(
                message_id=mid, useful=True, solved=True, reason_codes=[]
            ),
            inp={"message_id": ai_answer_ids[-1], "solved": True, "useful": True},
        )

    # --- case 2: unanswerable → handoff → operator reply → feedback
    q2 = HANDOFF_QUESTION
    case2_payload, _ = await _run_step(
        report,
        "new_case",
        lambda: driver.chat(
            case_id=None,
            expected_case_version=None,
            request_key=rkey(),
            text=q2,
            retry_of=None,
        ),
        inp={"text": q2, "retry_of": None},
    )
    if case2_payload is not None:
        req2 = str(case2_payload["request_id"])
        case2_id = str(case2_payload["case_id"])
        start_ms = int(time.monotonic() * 1000)
        try:
            poll2, seen2 = await poll_until_terminal(
                driver, req2, max_attempts=poll_attempts, delay_s=poll_delay_s
            )
            report.add(
                OperationRecord(
                    operation="poll_request",
                    outcome="ok",
                    mock=report.mock,
                    input={"request_id": req2},
                    output=poll2.payload,
                    error=None,
                    elapsed_ms=int(time.monotonic() * 1000) - start_ms,
                    attempts=len(seen2) or 1,
                    statuses_seen=seen2,
                    notes=None,
                )
            )
        except DriverError as exc:
            report.add(
                OperationRecord(
                    operation="poll_request",
                    outcome="error",
                    mock=report.mock,
                    input={"request_id": req2},
                    output=None,
                    error=exc.to_dict(),
                    elapsed_ms=int(time.monotonic() * 1000) - start_ms,
                    attempts=poll_attempts,
                    statuses_seen=seen or None,
                    notes=None,
                )
            )
            poll2 = None
        if poll2 is not None:
            case_view2, _ = await _run_step(
                report, "case", lambda: driver.get_case(case2_id), inp={"case_id": case2_id}
            )
            if case_view2 is not None:
                case2_version = int(case_view2["case"]["case_version"])
                ticket_payload, _ = await _run_step(
                    report,
                    "handoff",
                    lambda: driver.handoff(
                        case_id=case2_id,
                        request_key=rkey(),
                        expected_case_version=case2_version,
                    ),
                    inp={"case_id": case2_id, "expected_case_version": case2_version},
                )
                if ticket_payload is not None:
                    ticket_id = str(ticket_payload["ticket_id"])
                    ticket_case_version = int(case_view2["case"]["case_version"]) + 1
                    reply_payload, _ = await _run_step(
                        report,
                        "reply",
                        lambda: driver.operator_reply(
                            ticket_id=ticket_id,
                            request_key=rkey(),
                            expected_case_version=ticket_case_version,
                            text="Оператор принял запрос, ответ направлен в регламентном порядке (fixture D02).",
                            next_status="waiting_user",
                        ),
                        inp={"ticket_id": ticket_id, "next_status": "waiting_user"},
                    )
                    if reply_payload is not None:
                        case_view2b, _ = await _run_step(
                            report, "case", lambda: driver.get_case(case2_id), inp={"case_id": case2_id}
                        )
                        if case_view2b is not None:
                            oper_answers = _msg_id(case_view2b, kind="answer")
                            if oper_answers:
                                await _run_step(
                                    report,
                                    "feedback",
                                    lambda mid=oper_answers[-1]: driver.post_feedback(
                                        message_id=mid, solved=True, useful=None, reason_codes=[]
                                    ),
                                    inp={"message_id": oper_answers[-1], "solved": True},
                                )
    # --- case 3: model error → retry → final
    q3 = ERROR_QUESTION
    case3_payload, _ = await _run_step(
        report,
        "new_case",
        lambda: driver.chat(
            case_id=None,
            expected_case_version=None,
            request_key=rkey(),
            text=q3,
            retry_of=None,
        ),
        inp={"text": q3, "retry_of": None},
    )
    if case3_payload is not None:
        req3 = str(case3_payload["request_id"])
        case3_id = str(case3_payload["case_id"])
        start_ms = int(time.monotonic() * 1000)
        try:
            poll3, seen3 = await poll_until_terminal(
                driver, req3, max_attempts=poll_attempts, delay_s=poll_delay_s
            )
            report.add(
                OperationRecord(
                    operation="poll_request",
                    outcome="ok",
                    mock=report.mock,
                    input={"request_id": req3},
                    output=poll3.payload,
                    error=None,
                    elapsed_ms=int(time.monotonic() * 1000) - start_ms,
                    attempts=len(seen3) or 1,
                    statuses_seen=seen3,
                    notes=None,
                )
            )
        except DriverError as exc:
            report.add(
                OperationRecord(
                    operation="poll_request",
                    outcome="error",
                    mock=report.mock,
                    input={"request_id": req3},
                    output=None,
                    error=exc.to_dict(),
                    elapsed_ms=int(time.monotonic() * 1000) - start_ms,
                    attempts=poll_attempts,
                    statuses_seen=seen or None,
                    notes=None,
                )
            )
            poll3 = None
        if poll3 is not None and str(poll3.payload.get("status")) == "error":
            case_view3, _ = await _run_step(
                report, "case", lambda: driver.get_case(case3_id), inp={"case_id": case3_id}
            )
            if case_view3 is not None:
                case3_version = int(case_view3["case"]["case_version"])
                retry_payload, _ = await _run_step(
                    report,
                    "retry",
                    lambda: driver.chat(
                        case_id=case3_id,
                        expected_case_version=case3_version,
                        request_key=rkey(),
                        text=None,
                        retry_of=req3,
                    ),
                    inp={"case_id": case3_id, "retry_of": req3, "text": None},
                )
                if retry_payload is not None:
                    req3r = str(retry_payload["request_id"])
                    start_ms = int(time.monotonic() * 1000)
                    try:
                        poll4, seen4 = await poll_until_terminal(
                            driver, req3r, max_attempts=poll_attempts, delay_s=poll_delay_s
                        )
                        report.add(
                            OperationRecord(
                                operation="poll_request",
                                outcome="ok",
                                mock=report.mock,
                                input={"request_id": req3r},
                                output=poll4.payload,
                                error=None,
                                elapsed_ms=int(time.monotonic() * 1000) - start_ms,
                                attempts=len(seen4) or 1,
                                statuses_seen=seen4,
                                notes=None,
                            )
                        )
                    except DriverError as exc:
                        report.add(
                            OperationRecord(
                                operation="poll_request",
                                outcome="error",
                                mock=report.mock,
                                input={"request_id": req3r},
                                output=None,
                                error=exc.to_dict(),
                                elapsed_ms=int(time.monotonic() * 1000) - start_ms,
                                attempts=poll_attempts,
                                statuses_seen=seen or None,
                                notes=None,
                            )
                        )
                    await _run_step(
                        report, "case", lambda: driver.get_case(case3_id), inp={"case_id": case3_id}
                    )
    report.meta["session_id"] = (session_payload or {}).get("session_id")
    report.meta["mock"] = driver.mock
    report.meta.setdefault("not_run_reason", None)
    return report