"""FixtureDriver — детерминированный провайдер операций на frozen C0 fixtures.

Runner-а работает на fixtures независимо от ещё не готового A02. Драйвер
имитирует контрактные ответы HTTP-операций (v2.1 §7), ВСЕ результаты
помечены mock=True. Ничего не читает из app.sqlite.

Детерминизм: фиксированные UUID, фиксированные timestamps (base_time),
стадийный поллинг, единые значения timings_ms. Новые case-слоты занимаются
по порядку: slot 0=auto-answer, slot 1=handoff, slot 2=model error (retry).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from tenderhack_contracts import (
    CONTRACTS_VERSION,
    AcceptedRequest,
    CandidateSource,
    Case,
    CaseStatus,
    CaseView,
    ChatInput,
    FeedbackResponse,
    HealthResponse,
    Message,
    ReasonCode,
    RequestError,
    RequestProgress,
    RequestStatus,
    RequestView,
    RoutingResult,
    Session,
    SourceRecord,
    Ticket,
    TicketStatus,
)
from evaluation.runner.records import DriverError, DriverResult

log = logging.getLogger(__name__)

SID = "11111111-1111-4111-8111-111111111111"
AUTO_CASE = "22222222-2222-4222-8222-222222222222"
HANDOFF_CASE = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
ERROR_CASE = "eeeeeeef-eeee-4eee-8eee-eeeeeeeeeeee"
AUTO_Q = "33333333-3333-4333-8333-333333333333"
HANDOFF_Q = "44444444-4444-4444-8444-444444444444"
ERROR_Q = "44444445-4444-4444-8444-444444444444"
AUTO_ANSWER = "55555555-5555-4555-8555-555555555555"
RETRY_ANSWER = "99999999-9999-4999-8999-999999999999"
OPER_MSG = "77777777-7777-4777-8777-777777777777"
NOTICE_HANDOFF = "88888888-8888-4888-8888-888888888888"
REQ_AUTO = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
REQ_HANDOFF = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
REQ_ERROR = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
REQ_RETRY = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
FEED_AUTO = "abababab-abab-4bab-8bab-abababababab"
FEED_OPER = "acacacac-acac-4cac-8cac-acacacacacac"
TICKET = "66666666-6666-4666-8666-666666666666"

SOURCE_FIXTURE = "source-demo"

TIMINGS_ANSWER: dict[str, int | None] = {
    "queue": 240,
    "retrieval": 620,
    "generation_total": 1500,
    "time_to_first_source": 660,
    "total": 2380,
    "prompt_eval": 90,
    "decode": 480,
}
TIMINGS_RETRY: dict[str, int | None] = {
    "queue": 180,
    "retrieval": 700,
    "generation_total": 1650,
    "time_to_first_source": 740,
    "total": 3170,
    "prompt_eval": 110,
    "decode": 520,
}
TIMINGS_HANDOFF: dict[str, int | None] = {
    "queue": 180,
    "retrieval": 430,
    "generation_total": None,
    "time_to_first_source": None,
    "total": 860,
    "prompt_eval": None,
    "decode": None,
}
TIMINGS_ERROR: dict[str, int | None] = {
    "queue": 90,
    "retrieval": None,
    "generation_total": None,
    "time_to_first_source": None,
    "total": 2510,
    "prompt_eval": None,
    "decode": None,
}


def _utc_iso(ts: datetime) -> str:
    return ts.isoformat().replace("+00:00", "Z")


class FixtureDriver:
    """Детерминированный драйвер на C0 fixtures (mock)."""

    name = "fixture"
    mock = True

    def __init__(self, base_time: str = "2026-09-12T09:00:00Z") -> None:
        self._base = datetime.fromisoformat(base_time.replace("Z", "+00:00")).astimezone(timezone.utc)
        self._session: Session | None = None
        self._conversations: dict[str, dict[str, Any]] = {}
        self._requests: dict[str, dict[str, Any]] = {}
        self._poll_stage: dict[str, int] = {}
        self._feedbacks: dict[str, dict[str, Any]] = {}
        self._new_case_slot = 0
        self._operator_author = "operator-demo"

    # helpers
    def _now(self, delta_s: int = 0) -> datetime:
        return self._base + timedelta(seconds=delta_s)

    @staticmethod
    def _id(uuid_text: str) -> UUID:
        return UUID(uuid_text)

    # ---- session
    async def create_session(self) -> DriverResult:
        if self._session is None:
            self._session = Session(
                session_id=UUID(SID),
                created_at=self._now(),
                expires_at=self._now(3600),
            )
        return DriverResult(self._session.model_dump(mode="json"), mock=True)

    # ---- chat
    async def chat(
        self,
        *,
        case_id: str | None,
        expected_case_version: int | None,
        request_key: str,
        text: str | None,
        retry_of: str | None,
    ) -> DriverResult:
        try:
            ChatInput.model_validate(
                {
                    "case_id": case_id,
                    "expected_case_version": expected_case_version,
                    "request_key": request_key,
                    "text": text,
                    "retry_of": retry_of,
                }
            )
        except ValidationError as exc:
            raise DriverError("VALIDATION_ERROR", f"chat input invalid: {exc.errors()}", retryable=False)

        if retry_of is not None:
            return await self._chat_retry(request_key=request_key, retry_of=retry_of)

        if case_id is None and expected_case_version is not None:
            raise DriverError("VALIDATION_ERROR", "new case requires expected_case_version=null", retryable=False)

        if case_id is None:
            return await self._chat_new_case(request_key=request_key, text=text)
        return await self._chat_existing_case(
            case_id=case_id, expected_case_version=expected_case_version, request_key=request_key, text=text
        )

    async def _chat_new_case(self, *, request_key: str, text: str | None) -> DriverResult:
        slot = self._new_case_slot
        self._new_case_slot += 1
        plan = {
            0: ("answer", AUTO_CASE, AUTO_Q, REQ_AUTO),
            1: ("handoff", HANDOFF_CASE, HANDOFF_Q, REQ_HANDOFF),
            2: ("error", ERROR_CASE, ERROR_Q, REQ_ERROR),
        }
        if slot not in plan:
            raise DriverError("QUEUE_FULL", "fixture driver supports at most 3 new-case slots", retryable=False)
        flow, case_id, msg_id, req_id = plan[slot]
        case_text = text or ""
        confirmed_facts: dict[str, Any]
        if flow == "answer":
            confirmed_facts = {"role": "supplier"}
        elif flow == "handoff":
            confirmed_facts = {}
        else:
            confirmed_facts = {"role": "supplier"}

        case = Case(
            case_id=UUID(case_id),
            session_id=UUID(SID),
            status=CaseStatus.OPEN,
            case_version=1,
            active_request_id=UUID(req_id),
            clarification_count=0,
            confirmed_facts=confirmed_facts,
            topic_id="contracts" if flow == "answer" else None,
            subtopic_id=None,
            route=None,
            is_demo=False,
            created_at=self._now(),
            updated_at=self._now(),
        )
        user_msg = Message(
            message_id=UUID(msg_id),
            case_id=UUID(case_id),
            seq=1,
            role="user",
            kind="question",
            responder_type=None,
            author_id=None,
            answer_origin=None,
            content=case_text,
            source_ids=[],
            created_at=self._now(),
        )
        self._conversations[case_id] = {"case": case, "messages": [user_msg], "ticket": None, "flow": flow}
        self._requests[req_id] = {"request_id": req_id, "case_id": case_id, "user_message_id": msg_id, "flow": flow}
        self._poll_stage[req_id] = 0
        accepted = AcceptedRequest(
            request_id=UUID(req_id),
            case_id=UUID(case_id),
            user_message_id=UUID(msg_id),
            case_version=case.case_version,
            status=RequestStatus.QUEUED,
            trace_id=f"trace-{flow}-fixture",
        )
        return DriverResult(accepted.model_dump(mode="json"), mock=True, meta={"flow": flow})

    async def _chat_existing_case(
        self,
        *,
        case_id: str,
        expected_case_version: int | None,
        request_key: str,
        text: str | None,
    ) -> DriverResult:
        del request_key, text
        conv = self._conversations.get(case_id)
        if conv is None:
            raise DriverError("NOT_FOUND", f"case {case_id} not found", retryable=False)
        case: Case = conv["case"]
        if expected_case_version != case.case_version:
            raise DriverError(
                "STALE_CASE_VERSION",
                "case version changed",
                retryable=False,
                current_case_version=case.case_version,
            )
        if case.status in (CaseStatus.RESOLVED, CaseStatus.CLOSED_POLICY):
            raise DriverError(
                "CASE_CLOSED", f"case {case_id} is {case.status}", retryable=False, current_case_version=case.case_version
            )
        raise DriverError(
            "INVALID_TRANSITION", "existing-case chat is not exercised by the fixture driver", retryable=False
        )

    async def _chat_retry(self, *, request_key: str, retry_of: str) -> DriverResult:
        base = self._requests.get(retry_of)
        if base is None:
            raise DriverError("NOT_FOUND", f"request {retry_of} not found", retryable=False)
        if base["flow"] != "error":
            raise DriverError(
                "INVALID_TRANSITION", "retry is allowed only for an error/cancelled request", retryable=False
            )
        case_id = base["case_id"]
        conv = self._conversations[case_id]
        case: Case = conv["case"]
        if case.status in (CaseStatus.RESOLVED, CaseStatus.CLOSED_POLICY):
            raise DriverError(
                "CASE_CLOSED", f"case {case_id} is {case.status}", retryable=False, current_case_version=case.case_version
            )
        req_id = REQ_RETRY
        self._requests[req_id] = {
            "request_id": req_id,
            "case_id": case_id,
            "user_message_id": base["user_message_id"],
            "flow": "retry",
        }
        self._poll_stage[req_id] = 0
        case.active_request_id = UUID(req_id)
        case.updated_at = self._now()
        accepted = AcceptedRequest(
            request_id=UUID(req_id),
            case_id=UUID(case_id),
            user_message_id=UUID(base["user_message_id"]),
            case_version=case.case_version,
            status=RequestStatus.QUEUED,
            trace_id="trace-retry-fixture",
        )
        return DriverResult(
            accepted.model_dump(mode="json"),
            mock=True,
            meta={"reused_user_message_id": base["user_message_id"], "retry_of": retry_of},
        )

    # ---- poll
    async def poll_request(self, request_id: str) -> DriverResult:
        rec = self._requests.get(request_id)
        if rec is None:
            raise DriverError("NOT_FOUND", f"request {request_id} not found", retryable=False)
        stage = self._poll_stage.get(request_id, 0)
        self._poll_stage[request_id] = stage + 1
        flow = rec["flow"]
        case_id = rec["case_id"]
        conv = self._conversations[case_id]

        if stage == 0:
            view = RequestView(
                request_id=UUID(request_id),
                case_id=UUID(case_id),
                status=RequestStatus.PROCESSING,
                progress=RequestProgress.RETRIEVING,
            )
            return DriverResult(view.model_dump(mode="json"), mock=True, meta={"stage": "processing"})

        case: Case = conv["case"]
        if flow in ("answer", "retry"):
            return self._poll_answer(rec, conv, case_id, case)
        if flow == "handoff":
            return self._poll_handoff(rec, conv, case_id, case)
        if flow == "error":
            return self._poll_error(rec, conv, case_id, case)
        raise DriverError("INVALID_TRANSITION", f"unknown flow {flow!r}", retryable=False)

    def _poll_answer(
        self, rec: dict[str, Any], conv: dict[str, Any], case_id: str, case: Case
    ) -> DriverResult:
        flow = rec["flow"]
        msg_id = RETRY_ANSWER if flow == "retry" else AUTO_ANSWER
        timings = TIMINGS_RETRY if flow == "retry" else TIMINGS_ANSWER
        content = (
            "Повторная обработка после технического сбоя. Ответ по инструкции (fixture mock)."
            if flow == "retry"
            else "Тестовый ответ по инструкции (fixture mock)."
        )
        if not any(m.message_id == UUID(msg_id) for m in conv["messages"]):
            msg = Message(
                message_id=UUID(msg_id),
                case_id=UUID(case_id),
                seq=len(conv["messages"]) + 1,
                role="assistant",
                kind="answer",
                responder_type="ai",
                author_id=None,
                answer_origin="rag",
                content=content,
                source_ids=[SOURCE_FIXTURE],
                created_at=self._now(),
            )
            conv["messages"].append(msg)
            case.status = CaseStatus.AWAITING_FEEDBACK
            case.case_version = 2
            case.active_request_id = None
            case.updated_at = self._now()
        view = RequestView(
            request_id=UUID(rec["request_id"]),
            case_id=UUID(case_id),
            status=RequestStatus.FINAL,
            progress=None,
            candidate_sources=[
                CandidateSource(
                    source_id=SOURCE_FIXTURE,
                    title="Демонстрационный источник (fixture mock)",
                    source_type="portal_knowledge_base_api",
                )
            ],
            result_message_ids=[UUID(msg_id)],
            timings_ms=timings,
        )
        return DriverResult(view.model_dump(mode="json"), mock=True, meta={"flow": flow})

    def _poll_handoff(self, rec: dict[str, Any], conv: dict[str, Any], case_id: str, case: Case) -> DriverResult:
        if not any(m.message_id == UUID(NOTICE_HANDOFF) for m in conv["messages"]):
            notice = Message(
                message_id=UUID(NOTICE_HANDOFF),
                case_id=UUID(case_id),
                seq=len(conv["messages"]) + 1,
                role="assistant",
                kind="notice",
                responder_type="system",
                author_id=None,
                answer_origin="system",
                content="Недостаточно проверенных материалов. Передать специалисту?",
                source_ids=[],
                created_at=self._now(),
            )
            conv["messages"].append(notice)
            case.status = CaseStatus.HANDOFF_OFFERED
            case.case_version = 2
            case.active_request_id = None
            case.updated_at = self._now()
        view = RequestView(
            request_id=UUID(rec["request_id"]),
            case_id=UUID(case_id),
            status=RequestStatus.FINAL,
            progress=None,
            candidate_sources=[],
            result_message_ids=[],
            timings_ms=TIMINGS_HANDOFF,
        )
        return DriverResult(view.model_dump(mode="json"), mock=True)

    def _poll_error(self, rec: dict[str, Any], conv: dict[str, Any], case_id: str, case: Case) -> DriverResult:
        del conv, case
        err = RequestError(
            code="MODEL_UNAVAILABLE",
            message="Генератор недоступен (fixture mock). Отказ не считается решением.",
            retryable=True,
        )
        view = RequestView(
            request_id=UUID(rec["request_id"]),
            case_id=UUID(case_id),
            status=RequestStatus.ERROR,
            progress=None,
            candidate_sources=[],
            result_message_ids=[],
            error=err,
            timings_ms=TIMINGS_ERROR,
        )
        return DriverResult(view.model_dump(mode="json"), mock=True)

    # ---- case
    async def get_case(self, case_id: str) -> DriverResult:
        conv = self._conversations.get(case_id)
        if conv is None:
            raise DriverError("NOT_FOUND", f"case {case_id} not found", retryable=False)
        case: Case = conv["case"]
        view = CaseView(case=case, ticket=conv.get("ticket"), messages=conv["messages"], limit_reached=False)
        return DriverResult(view.model_dump(mode="json"), mock=True)

    # ---- source
    async def get_source(self, source_id: str) -> DriverResult:
        if source_id != SOURCE_FIXTURE:
            raise DriverError("NOT_FOUND", f"source {source_id} not found", retryable=False)
        record = SourceRecord(
            source_id=SOURCE_FIXTURE,
            source_type="portal_knowledge_base_api",
            title="Демонстрационный источник (fixture mock)",
            excerpt="Тестовый фрагмент содержания для проверки runner на fixtures (не ссылка на KB).",
            version=None,
            source_date=None,
            section_path=None,
            page_from=None,
            page_to=None,
            url=None,
            file_url=None,
            conditions=["Демонстрационное условие (mock)"],
            applicable_roles=["supplier"],
            content_status="complete",
        )
        return DriverResult(
            record.model_dump(mode="json"),
            mock=True,
            meta={"fixture_source": True, "not_a_real_kb_document": True},
        )

    # ---- feedback
    async def post_feedback(
        self,
        *,
        message_id: str,
        useful: bool | None = None,
        solved: bool | None = None,
        specialist_rating: int | None = None,
        reason_codes: list[str] | None = None,
        comment: str | None = None,
    ) -> DriverResult:
        target: Message | None = None
        conv: dict[str, Any] | None = None
        for candidate in self._conversations.values():
            for msg in candidate["messages"]:
                if str(msg.message_id) == message_id:
                    target = msg
                    conv = candidate
                    break
            if target is not None:
                break
        if target is None or conv is None:
            raise DriverError("NOT_FOUND", f"message {message_id} not found", retryable=False)
        if target.kind != "answer":
            raise DriverError(
                "VALIDATION_ERROR", "feedback allowed on answer messages only", retryable=False
            )
        case: Case = conv["case"]
        answers = [m for m in conv["messages"] if m.kind == "answer"]
        last_answer = answers[-1]
        outcome_applied = False
        outcome_reason: str | None = None

        is_operator = target.answer_origin == "operator"
        if str(target.message_id) != str(last_answer.message_id):
            outcome_reason = "feedback targets a stale answer"
        elif not is_operator and conv.get("ticket") is not None:
            outcome_reason = "case already handed off; feedback on AI answer is not applied"
        elif case.active_request_id is not None:
            outcome_reason = "active request in progress"
        elif solved is None:
            outcome_reason = "no solved transition requested"
        else:
            if solved:
                if case.status == CaseStatus.RESOLVED:
                    outcome_reason = "case already resolved; repeated solved does not bump version"
                else:
                    case.status = CaseStatus.RESOLVED
                    case.case_version += 1
                    case.updated_at = self._now()
                    outcome_applied = True
                    if is_operator:
                        ticket: Ticket | None = conv.get("ticket")
                        if ticket is not None:
                            ticket.status = TicketStatus.RESOLVED
                            ticket.resolved_by = "operator"
                            ticket.updated_at = self._now()
            else:
                case.status = CaseStatus.OPEN
                case.case_version += 1
                case.updated_at = self._now()
                outcome_applied = True

        self._feedbacks[str(target.message_id)] = {
            "useful": useful,
            "solved": solved,
            "specialist_rating": specialist_rating,
            "reason_codes": reason_codes or [],
            "comment": comment,
        }
        feedback_id = FEED_AUTO if target.answer_origin in ("rag", "card") else FEED_OPER
        resp = FeedbackResponse(
            feedback_id=UUID(feedback_id),
            message_id=UUID(message_id),
            case_version=case.case_version,
            case_status=case.status,
            outcome_applied=outcome_applied,
            outcome_reason=outcome_reason,
        )
        return DriverResult(resp.model_dump(mode="json"), mock=True)

    # ---- handoff
    async def handoff(
        self, *, case_id: str, request_key: str, expected_case_version: int
    ) -> DriverResult:
        del request_key
        conv = self._conversations.get(case_id)
        if conv is None:
            raise DriverError("NOT_FOUND", f"case {case_id} not found", retryable=False)
        case: Case = conv["case"]
        if expected_case_version != case.case_version:
            raise DriverError(
                "STALE_CASE_VERSION",
                "case version changed",
                retryable=False,
                current_case_version=case.case_version,
            )
        existing = conv.get("ticket")
        if existing is not None:
            return DriverResult(existing.model_dump(mode="json"), mock=True, meta={"created": False})

        last_user_text = next(
            (m.content for m in reversed(conv["messages"]) if m.role == "user"),
            "",
        )
        routing = RoutingResult(
            topic_id=case.topic_id,
            subtopic_id=None,
            support_line=None,
            recommended_recipient=None,
            basis_source_ids=[],
            rule_id=None,
            is_probable_defect=False,
            is_ambiguous=True,
            reason_codes=[ReasonCode.NO_EVIDENCE],
        )
        ticket = Ticket(
            ticket_id=UUID(TICKET),
            case_id=UUID(case_id),
            status=TicketStatus.NEW,
            route=routing,
            reason_codes=[ReasonCode.NO_EVIDENCE],
            missing_information=[],
            context_snapshot={"last_user_message": last_user_text},
            created_at=self._now(),
            updated_at=self._now(),
            resolved_by=None,
        )
        conv["ticket"] = ticket
        case.status = CaseStatus.HANDED_OFF
        case.case_version += 1
        case.active_request_id = None
        case.updated_at = self._now()
        return DriverResult(ticket.model_dump(mode="json"), mock=True, meta={"created": True})

    # ---- operator reply
    async def operator_reply(
        self,
        *,
        ticket_id: str,
        request_key: str,
        expected_case_version: int,
        text: str,
        next_status: str,
    ) -> DriverResult:
        del request_key
        if next_status not in ("waiting_user", "resolved"):
            raise DriverError("VALIDATION_ERROR", f"next_status={next_status!r} not allowed", retryable=False)
        conv = next(
            (c for c in self._conversations.values()
             if c.get("ticket") is not None and str(c["ticket"].ticket_id) == ticket_id),
            None,
        )
        if conv is None:
            raise DriverError("NOT_FOUND", f"ticket {ticket_id} not found", retryable=False)
        case: Case = conv["case"]
        ticket: Ticket = conv["ticket"]
        if expected_case_version != case.case_version:
            raise DriverError(
                "STALE_CASE_VERSION",
                "case version changed",
                retryable=False,
                current_case_version=case.case_version,
            )
        msg = Message(
            message_id=UUID(OPER_MSG),
            case_id=case.case_id,
            seq=len(conv["messages"]) + 1,
            role="assistant",
            kind="answer",
            responder_type="operator",
            author_id=self._operator_author,
            answer_origin="operator",
            content=text,
            source_ids=[],
            created_at=self._now(),
        )
        conv["messages"].append(msg)
        case.status = CaseStatus.RESOLVED if next_status == "resolved" else CaseStatus.HANDED_OFF
        case.case_version += 1
        case.active_request_id = None
        case.updated_at = self._now()
        ticket.status = TicketStatus.RESOLVED if next_status == "resolved" else TicketStatus.WAITING_USER
        ticket.resolved_by = "operator" if next_status == "resolved" else None
        ticket.updated_at = self._now()
        return DriverResult(msg.model_dump(mode="json"), mock=True)

    # ---- health
    async def health(self) -> DriverResult:
        resp = HealthResponse(
            status="ready",
            ready=True,
            storage="ready",
            knowledge="ready",
            generator="ready",
            contracts_version=CONTRACTS_VERSION,
        )
        return DriverResult(resp.model_dump(mode="json"), mock=True)

    def dump_state_signature(self) -> str:
        """Детерминированный отпечаток состояния (для сверки повторяемости)."""
        import hashlib

        blob = []
        for case_id in sorted(self._conversations):
            conv = self._conversations[case_id]
            case: Case = conv["case"]
            blob.append(
                (
                    case_id,
                    case.status.value,
                    case.case_version,
                    [str(m.message_id) for m in conv["messages"]],
                )
            )
        return hashlib.sha256(repr(blob).encode("utf-8")).hexdigest()


def state_summary(driver: FixtureDriver) -> dict[str, Any]:
    """Читаемое резюме состояния fixture-драйвера для трассы."""
    summary: dict[str, Any] = {}
    for case_id, conv in driver._conversations.items():
        case: Case = conv["case"]
        answers = [str(m.message_id) for m in conv["messages"] if m.kind == "answer"]
        summary[case_id] = {
            "status": case.status.value,
            "case_version": case.case_version,
            "answers": answers,
            "ticket": str(conv["ticket"].ticket_id) if conv.get("ticket") else None,
        }
    return summary