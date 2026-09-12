"""Детерминированный demo/live EvaluationExport для проверки report-функций.

Весь экспорт — mock: фиксированные UUID, даты и значения, чтобы unit-тесты
интеграции отчёта были детерминированными и не зависели от runtime/A02.
Это НЕ реальные данные: demo_export явно помечает export mock=True.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from tenderhack_contracts import (
    CaseStatus,
    CurrentResolution,
    EvaluationExport,
    EvaluationRow,
    ExportFeedback,
    ExportMessage,
    ExportRequest,
    ExportTicket,
    RequestStatus,
    ReasonCode,
    RoutingResult,
    TicketStatus,
)

BASE = datetime.fromisoformat("2026-09-12T08:00:00Z").astimezone(timezone.utc)
_SCHEMA_VERSION = "1.0"
_APP_COMMIT_MOCK = "demo-mock (D02): not a real app commit"
_KB_MOCK = "demo-mock-c0"

DEMO_CASE_IDS = {
    "confirmed": "d0000001-0000-4000-8000-000000000001",
    "no_feedback": "d0000002-0000-4000-8000-000000000002",
    "solved_false": "d0000003-0000-4000-8000-000000000003",
    "operator": "d0000004-0000-4000-8000-000000000004",
    "policy_closed": "d0000005-0000-4000-8000-000000000005",
    "open_no_answer": "d0000006-0000-4000-8000-000000000006",
    "handoff_offered": "d0000007-0000-4000-8000-000000000007",
}
LIVE_CASE_IDS = {
    "confirmed": "00000001-0000-4000-8000-000000000001",
    "error": "00000002-0000-4000-8000-000000000002",
}


def _dt(seconds_from_base: int) -> datetime:
    return BASE + timedelta(seconds=seconds_from_base)


def _message(
    mid: str,
    case_id: str,
    seq: int,
    kind: str,
    text: str,
    *,
    responder_type: str | None = None,
    answer_origin: str | None = None,
    source_ids: list[str] | None = None,
    seconds: int = 0,
) -> ExportMessage:
    return ExportMessage(
        message_id=UUID(mid),
        seq=seq,
        kind=kind,
        responder_type=responder_type,
        author_id=None if responder_type == "ai" else ("operator-demo" if responder_type == "operator" else None),
        answer_origin=answer_origin,
        text=text,
        source_ids=source_ids or [],
        created_at=_dt(seconds),
    )


def _request(req_id: str, user_msg_id: str, status: RequestStatus, total: int | None) -> ExportRequest:
    timings: dict[str, int | None] = {}
    if total is not None:
        timings = {"queue": 100, "retrieval": 200, "generation_total": 300,
                   "time_to_first_source": 250, "total": total, "prompt_eval": 50, "decode": 120}
    return ExportRequest(
        request_id=UUID(req_id),
        user_message_id=UUID(user_msg_id),
        status=status,
        result_message_ids=[],
        error_code=None,
        timings_ms=timings,
    )


def _route() -> RoutingResult:
    return RoutingResult(
        topic_id="contracts",
        subtopic_id=None,
        support_line=None,
        recommended_recipient=None,
        basis_source_ids=[],
        rule_id=None,
        is_probable_defect=False,
        is_ambiguous=False,
        reason_codes=[ReasonCode.NO_EVIDENCE],
    )


def build_demo_live_export() -> tuple[EvaluationExport, dict[str, Any]]:
    demo_rows: list[EvaluationRow] = []

    # demo: подтверждённое авторешение (useful+solved true)
    demo_rows.append(
        EvaluationRow(
            case_id=UUID(DEMO_CASE_IDS["confirmed"]),
            cohort="demo",
            created_at=_dt(1000),
            case_status=CaseStatus.RESOLVED,
            topic_id="contracts",
            subtopic_id=None,
            policy_closed=False,
            route=_route(),
            ticket=None,
            messages=[
                _message("c1000001-0000-4000-8000-000000000001", DEMO_CASE_IDS["confirmed"], 1, "question",
                         "Как зарегистрировать кабинет? (demo mock)"),
                _message("c1000002-0000-4000-8000-000000000002", DEMO_CASE_IDS["confirmed"], 2, "answer",
                         "Ответ по регламенту (demo mock).", responder_type="ai", answer_origin="rag",
                         source_ids=["doc-demo-1"], seconds=60),
            ],
            requests=[
                _request("a1000001-0000-4000-8000-000000000001", "c1000001-0000-4000-8000-000000000001",
                         RequestStatus.FINAL, 2400),
            ],
            feedback=[
                ExportFeedback(
                    message_id=UUID("c1000002-0000-4000-8000-000000000002"),
                    useful=True,
                    solved=True,
                    reason_codes=[],
                    updated_at=_dt(120),
                ),
                ExportFeedback(
                    message_id=UUID("c1000002-0000-4000-8000-000000000002"),
                    useful=True,
                    solved=True,
                    reason_codes=[],
                    updated_at=_dt(80),
                ),
            ],
            current_resolution=CurrentResolution(
                message_id=UUID("c1000002-0000-4000-8000-000000000002"),
                confirmed_by="user",
                answer_origin="rag",
                confirmed_at=_dt(125),
            ),
        )
    )

    # demo: автоответ без feedback
    demo_rows.append(
        EvaluationRow(
            case_id=UUID(DEMO_CASE_IDS["no_feedback"]),
            cohort="demo",
            created_at=_dt(2000),
            case_status=CaseStatus.AWAITING_FEEDBACK,
            topic_id="contracts",
            subtopic_id=None,
            policy_closed=False,
            route=_route(),
            ticket=None,
            messages=[
                _message("c2000001-0000-4000-8000-000000000001", DEMO_CASE_IDS["no_feedback"], 1, "question",
                         "Вопрос без обратной связи (demo mock)"),
                _message("c2000002-0000-4000-8000-000000000002", DEMO_CASE_IDS["no_feedback"], 2, "answer",
                         "Ответ (demo mock).", responder_type="ai", answer_origin="rag",
                         source_ids=["doc-demo-2"], seconds=30),
            ],
            requests=[
                _request("a2000001-0000-4000-8000-000000000001", "c2000001-0000-4000-8000-000000000001",
                         RequestStatus.FINAL, 3100),
            ],
            feedback=[],
            current_resolution=None,
        )
    )

    # demo: автоответ, solved=false (обратная связь отрицательная)
    demo_rows.append(
        EvaluationRow(
            case_id=UUID(DEMO_CASE_IDS["solved_false"]),
            cohort="demo",
            created_at=_dt(3000),
            case_status=CaseStatus.OPEN,
            topic_id="contracts",
            subtopic_id=None,
            policy_closed=False,
            route=_route(),
            ticket=None,
            messages=[
                _message("c3000001-0000-4000-8000-000000000001", DEMO_CASE_IDS["solved_false"], 1, "question",
                         "Вопрос, решённый по feedback=false (demo mock)"),
                _message("c3000002-0000-4000-8000-000000000002", DEMO_CASE_IDS["solved_false"], 2, "answer",
                         "Ответ (demo mock).", responder_type="ai", answer_origin="card",
                         source_ids=["doc-demo-3"], seconds=40),
            ],
            requests=[
                _request("a3000001-0000-4000-8000-000000000001", "c3000001-0000-4000-8000-000000000001",
                         RequestStatus.FINAL, 2850),
            ],
            feedback=[
                ExportFeedback(
                    message_id=UUID("c3000002-0000-4000-8000-000000000002"),
                    useful=True,
                    solved=False,
                    reason_codes=[],
                    updated_at=_dt(90),
                ),
            ],
            current_resolution=None,
        )
    )

    # demo: оператор (передача + ответ оператора + feedback)
    demo_rows.append(
        EvaluationRow(
            case_id=UUID(DEMO_CASE_IDS["operator"]),
            cohort="demo",
            created_at=_dt(4000),
            case_status=CaseStatus.RESOLVED,
            topic_id="contracts",
            subtopic_id=None,
            policy_closed=False,
            route=_route(),
            ticket=ExportTicket(
                ticket_id=UUID("e0000001-0000-4000-8000-000000000001"),
                status=TicketStatus.RESOLVED,
                created_at=_dt(300),
                resolved_by="operator",
            ),
            messages=[
                _message("c4000001-0000-4000-8000-000000000001", DEMO_CASE_IDS["operator"], 1, "question",
                         "Сложный вопрос для оператора (demo mock)"),
                _message("c4000002-0000-4000-8000-000000000002", DEMO_CASE_IDS["operator"], 2, "notice",
                         "Передано оператору (demo mock).", responder_type="system", answer_origin="system",
                         seconds=50),
                _message("c4000003-0000-4000-8000-000000000003", DEMO_CASE_IDS["operator"], 3, "answer",
                         "Ответ оператора (demo mock).", responder_type="operator", answer_origin="operator",
                         seconds=500),
            ],
            requests=[
                _request("a4000001-0000-4000-8000-000000000001", "c4000001-0000-4000-8000-000000000001",
                         RequestStatus.FINAL, 5400),
            ],
            feedback=[
                ExportFeedback(
                    message_id=UUID("c4000003-0000-4000-8000-000000000003"),
                    useful=True,
                    solved=True,
                    reason_codes=[],
                    updated_at=_dt(520),
                ),
            ],
            current_resolution=CurrentResolution(
                message_id=UUID("c4000003-0000-4000-8000-000000000003"),
                confirmed_by="operator",
                answer_origin="operator",
                confirmed_at=_dt(525),
            ),
        )
    )

    # demo: policy_closed — исключается из N_eligible
    demo_rows.append(
        EvaluationRow(
            case_id=UUID(DEMO_CASE_IDS["policy_closed"]),
            cohort="demo",
            created_at=_dt(5000),
            case_status=CaseStatus.CLOSED_POLICY,
            topic_id=None,
            subtopic_id=None,
            policy_closed=True,
            route=RoutingResult(
                topic_id=None,
                subtopic_id=None,
                support_line=None,
                recommended_recipient=None,
                basis_source_ids=[],
                rule_id=None,
                is_probable_defect=False,
                is_ambiguous=False,
                reason_codes=[ReasonCode.POLICY_LANGUAGE],
            ),
            ticket=None,
            messages=[
                _message("c5000001-0000-4000-8000-000000000001", DEMO_CASE_IDS["policy_closed"], 1, "question",
                         "Запрос закрыт политикой (demo mock)"),
            ],
            requests=[],
            feedback=[],
            current_resolution=None,
        )
    )

    # demo: открытый без ответа (очередь)
    demo_rows.append(
        EvaluationRow(
            case_id=UUID(DEMO_CASE_IDS["open_no_answer"]),
            cohort="demo",
            created_at=_dt(6000),
            case_status=CaseStatus.OPEN,
            topic_id="contracts",
            subtopic_id=None,
            policy_closed=False,
            route=_route(),
            ticket=None,
            messages=[
                _message("c6000001-0000-4000-8000-000000000001", DEMO_CASE_IDS["open_no_answer"], 1, "question",
                         "Запрос в очереди (demo mock)"),
            ],
            requests=[
                _request("a6000001-0000-4000-8000-000000000001", "c6000001-0000-4000-8000-000000000001",
                         RequestStatus.PROCESSING, None),
            ],
            feedback=[],
            current_resolution=None,
        )
    )

    # demo: handoff_offered без Ticket (не согласился) — без ответа
    demo_rows.append(
        EvaluationRow(
            case_id=UUID(DEMO_CASE_IDS["handoff_offered"]),
            cohort="demo",
            created_at=_dt(7000),
            case_status=CaseStatus.HANDOFF_OFFERED,
            topic_id=None,
            subtopic_id=None,
            policy_closed=False,
            route=_route(),
            ticket=None,
            messages=[
                _message("c7000001-0000-4000-8000-000000000001", DEMO_CASE_IDS["handoff_offered"], 1, "question",
                         "Вопрос без покрытия KB (demo mock)"),
                _message("c7000002-0000-4000-8000-000000000002", DEMO_CASE_IDS["handoff_offered"], 2, "notice",
                         "Недостаточно материалов (demo mock).", responder_type="system", answer_origin="system",
                         seconds=60),
            ],
            requests=[
                _request("a7000001-0000-4000-8000-000000000001", "c7000001-0000-4000-8000-000000000001",
                         RequestStatus.FINAL, 860),
            ],
            feedback=[],
            current_resolution=None,
        )
    )

    # live: подтверждённое авторешение, но total ≥ TIMEOUT_TOTAL_MS → timeout
    live_rows: list[EvaluationRow] = [
        EvaluationRow(
            case_id=UUID(LIVE_CASE_IDS["confirmed"]),
            cohort="live",
            created_at=_dt(8000),
            case_status=CaseStatus.RESOLVED,
            topic_id="contracts",
            subtopic_id=None,
            policy_closed=False,
            route=_route(),
            ticket=None,
            messages=[
                _message("c8000001-0000-4000-8000-000000000001", LIVE_CASE_IDS["confirmed"], 1, "question",
                         "Реальный вопрос (live mock)"),
                _message("c8000002-0000-4000-8000-000000000002", LIVE_CASE_IDS["confirmed"], 2, "answer",
                         "Ответ (live mock).", responder_type="ai", answer_origin="rag",
                         source_ids=["doc-live-1"], seconds=40),
            ],
            requests=[
                _request("a8000001-0000-4000-8000-000000000001", "c8000001-0000-4000-8000-000000000001",
                         RequestStatus.FINAL, 134000),
            ],
            feedback=[
                ExportFeedback(
                    message_id=UUID("c8000002-0000-4000-8000-000000000002"),
                    useful=True,
                    solved=True,
                    reason_codes=[],
                    updated_at=_dt(100),
                ),
            ],
            current_resolution=CurrentResolution(
                message_id=UUID("c8000002-0000-4000-8000-000000000002"),
                confirmed_by="user",
                answer_origin="rag",
                confirmed_at=_dt(105),
            ),
        ),
        EvaluationRow(
            case_id=UUID(LIVE_CASE_IDS["error"]),
            cohort="live",
            created_at=_dt(9000),
            case_status=CaseStatus.OPEN,
            topic_id=None,
            subtopic_id=None,
            policy_closed=False,
            route=_route(),
            ticket=None,
            messages=[
                _message("c9000001-0000-4000-8000-000000000001", LIVE_CASE_IDS["error"], 1, "question",
                         "Запрос со сбоем модели (live mock)"),
            ],
            requests=[
                ExportRequest(
                    request_id=UUID("a9000001-0000-4000-8000-000000000001"),
                    user_message_id=UUID("c9000001-0000-4000-8000-000000000001"),
                    status=RequestStatus.ERROR,
                    result_message_ids=[],
                    error_code="MODEL_UNAVAILABLE",
                    timings_ms={"queue": 500, "retrieval": None, "generation_total": None,
                                "time_to_first_source": None, "total": 60000,
                                "prompt_eval": None, "decode": None},
                ),
            ],
            feedback=[],
            current_resolution=None,
        ),
    ]

    export = EvaluationExport(
        schema_version=_SCHEMA_VERSION,
        export_id=UUID("d2000001-0000-4000-8000-000000000001"),
        created_at=BASE,
        as_of=BASE + timedelta(seconds=9000),
        app_commit=_APP_COMMIT_MOCK,
        kb_snapshot_id=_KB_MOCK,
        rows=demo_rows + live_rows,
    )
    meta: dict[str, Any] = {
        "mock": True,
        "generated_by": "evaluation.report.demo_export (D02)",
        "note": "Все значения фикстуры: детерминированные пороговые кейсы для проверки report-функций.",
        "expected": {
            "demo.auto_answer": 0.5,
            "demo.confirmed_auto_resolution": 1 / 6,
            "demo.usefulness_ai": 1.0,
            "demo.usefulness_operator": 1.0,
            "demo.solved_rate": 2 / 3,
            "demo.feedback_coverage": 0.75,
            "demo.handoffs": 1 / 6,
            "demo.no_answer": 2 / 6,
            "demo.latency_p50_ms": 2850,
            "demo.latency_p95_ms": 5400,
            "live.auto_answer": 0.5,
            "live.confirmed_auto_resolution": 0.5,
            "live.usefulness_ai": 1.0,
            "live.usefulness_operator": None,
            "live.solved_rate": 1.0,
            "live.feedback_coverage": 1.0,
            "live.handoffs": 0.0,
            "live.no_answer": 0.5,
            "live.errors": 0.5,
            "live.timeouts": 0.5,
            "live.latency_p50_ms": 60000,
            "live.latency_p95_ms": 134000,
        },
    }
    return export, meta