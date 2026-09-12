from __future__ import annotations

import asyncio
from collections import deque
from contextlib import suppress
from time import perf_counter
from typing import Any
from uuid import UUID

from tenderhack_contracts import (
    CandidateSource,
    CaseStatus,
    ChatInput,
    FeedbackInput,
    FeedbackResponse,
    GateDecision,
    GenerationAnswer,
    GenerationClarify,
    GenerationEscalate,
    GenerationInput,
    HandoffInput,
    Message,
    OperatorReplyInput,
    QueryContext,
    ReasonCode,
    RequestView,
    RoutingResult,
    Session,
    Ticket,
)

from .errors import DomainError
from .storage import Database
from .verifier import InvalidGeneration, verify_proposal


class BackendService:
    def __init__(
        self, database: Database, policy, knowledge, generator, queue_capacity: int = 4
    ) -> None:
        self.database = database
        self.policy = policy
        self.knowledge = knowledge
        self.generator = generator
        self.queue_capacity = queue_capacity
        self._queue: deque[UUID] = deque()
        self._reserved = 0
        self._admission_lock = asyncio.Lock()
        self._processing_lock = asyncio.Lock()
        self._wake = asyncio.Event()

    def create_session(self, session_id: UUID | None) -> tuple[Session, bool]:
        return self.database.get_or_create_session(session_id)

    async def accept_chat(
        self,
        session_id: UUID,
        raw_payload: ChatInput | dict[str, Any],
        *,
        is_demo: bool,
    ):
        payload = (
            raw_payload
            if isinstance(raw_payload, ChatInput)
            else ChatInput.model_validate(raw_payload)
        )
        receipt = self.database.get_receipt(session_id, payload)
        if receipt is not None:
            return receipt
        text = payload.text
        if text is None:
            text = self.database.get_retry_text(session_id, payload.retry_of)
        policy_result = self.policy.check(text)
        if policy_result.profanity:
            chat_mode = "policy"
        elif policy_result.explicit_human_request:
            chat_mode = "handoff"
        elif payload.case_id is not None and self.database.case_has_ticket(
            session_id, payload.case_id
        ):
            chat_mode = "operator"
        else:
            chat_mode = "ai"
        fast = chat_mode != "ai"
        if chat_mode == "ai":
            async with self._admission_lock:
                if self._reserved >= self.queue_capacity:
                    raise DomainError(
                        "QUEUE_FULL",
                        "Очередь обработки заполнена",
                        status_code=429,
                        retryable=True,
                    )
                self._reserved += 1
        try:
            accepted, created = self.database.accept_chat(
                session_id,
                payload,
                is_demo=is_demo,
                supersede_active=fast,
                chat_mode=chat_mode,
            )
        except BaseException:
            if not fast:
                async with self._admission_lock:
                    self._reserved -= 1
            raise
        if not created:
            if not fast:
                async with self._admission_lock:
                    self._reserved -= 1
            return accepted
        if policy_result.profanity:
            self.database.publish_message(
                accepted.request_id,
                case_status=CaseStatus.CLOSED_POLICY,
                role="assistant",
                kind="notice",
                responder_type="system",
                answer_origin="system",
                content=(
                    "Обращение завершено: в сообщении обнаружена нецензурная лексика. "
                    "Пожалуйста, соблюдайте правила общения"
                ),
                source_ids=[],
                route=RoutingResult(reason_codes=[ReasonCode.POLICY_LANGUAGE]),
            )
        elif policy_result.explicit_human_request:
            existing_route = None
            if payload.case_id is not None:
                existing_route = self.database.get_case(
                    session_id, payload.case_id
                ).case.route
            self.database.publish_explicit_handoff(
                accepted.request_id,
                existing_route or RoutingResult(),
                ReasonCode.EXPLICIT_HUMAN_REQUEST,
            )
        elif chat_mode == "ai":
            self._queue.append(accepted.request_id)
            self._wake.set()
        return accepted

    async def process_next(self) -> bool:
        async with self._processing_lock:
            if not self._queue:
                return False
            request_id = self._queue.popleft()
            try:
                await self._process(request_id)
            finally:
                async with self._admission_lock:
                    self._reserved -= 1
            return True

    async def _process(self, request_id: UUID) -> None:
        started = perf_counter()
        context = self.database.get_processing_context(request_id)
        if not self.database.mark_processing(request_id, "retrieving"):
            return
        try:
            knowledge = await self.knowledge.retrieve(
                QueryContext(
                    text=context["question"],
                    confirmed_facts=context["confirmed_facts"],
                    recent_user_messages=context["recent_user_messages"],
                    clarification_count=context["clarification_count"],
                    trace_id=context["trace_id"],
                )
            )
        except Exception:  # noqa: BLE001 - adapter boundary must persist every failure after 202
            self.database.fail_request(request_id, "SEARCH_UNAVAILABLE", retryable=True)
            return
        candidates = [
            CandidateSource(
                source_id=item.source_id,
                title=item.title,
                source_type=item.source_type,
                version=item.version,
                page_from=item.page_from,
                page_to=item.page_to,
            )
            for item in knowledge.candidates
        ]
        self.database.set_candidates(request_id, candidates, knowledge.timings_ms)

        if knowledge.decision is GateDecision.CLARIFY:
            question = (
                knowledge.missing_fact.question
                if knowledge.missing_fact
                else "Уточните данные обращения."
            )
            if context["clarification_count"] >= 1:
                self._offer_handoff(
                    request_id, knowledge.route, ReasonCode.UNRESOLVED_AFTER_STEPS
                )
            else:
                self.database.publish_message(
                    request_id,
                    case_status=CaseStatus.AWAITING_CLARIFICATION,
                    role="assistant",
                    kind="clarification",
                    responder_type="system",
                    answer_origin="system",
                    content=question,
                    source_ids=[],
                    route=knowledge.route,
                    clarification_increment=True,
                )
            return
        if knowledge.decision is GateDecision.ESCALATE:
            reason = (
                knowledge.reason_codes[0]
                if knowledge.reason_codes
                else ReasonCode.NO_EVIDENCE
            )
            self._offer_handoff(request_id, knowledge.route, reason)
            return
        if knowledge.decision is GateDecision.OUT_OF_SCOPE:
            self.database.publish_message(
                request_id,
                case_status=CaseStatus.OPEN,
                role="assistant",
                kind="notice",
                responder_type="system",
                answer_origin="system",
                content="Этот вопрос находится вне границ поддержки Портала поставщиков.",
                source_ids=[],
                route=knowledge.route,
            )
            return

        evidence_by_id = {item.evidence_id: item for item in knowledge.candidates}
        selected = [
            evidence_by_id[item]
            for item in knowledge.selected_evidence_ids
            if item in evidence_by_id
        ]
        allowed = {item.source_id for item in selected}
        self.database.mark_processing(request_id, "generating")
        generation_started = perf_counter()
        try:
            proposal = await self.generator.generate(
                GenerationInput(
                    question=context["question"],
                    confirmed_facts=context["confirmed_facts"],
                    evidence=selected,
                    allowed_source_ids=sorted(allowed),
                )
            )
            required_conditions = [
                condition for item in selected for condition in item.conditions
            ]
            grounding_texts = [context["question"]]
            for item in selected:
                grounding_texts.extend(
                    [item.title, item.text, *item.conditions, item.version or ""]
                )
            proposal = verify_proposal(
                proposal, allowed, required_conditions, grounding_texts
            )
        except InvalidGeneration:
            self._offer_handoff(
                request_id, knowledge.route, ReasonCode.INVALID_GENERATION
            )
            return
        except Exception:  # noqa: BLE001 - adapter boundary must persist every failure after 202
            self.database.fail_request(request_id, "MODEL_UNAVAILABLE", retryable=True)
            return
        elapsed_ms = round((perf_counter() - started) * 1000, 3)
        generation_ms = round((perf_counter() - generation_started) * 1000, 3)
        if isinstance(proposal, GenerationAnswer):
            adapter_timings = dict(getattr(self.generator, "last_timings_ms", {}) or {})
            self.database.publish_message(
                request_id,
                case_status=CaseStatus.AWAITING_FEEDBACK,
                role="assistant",
                kind="answer",
                responder_type="ai",
                answer_origin="rag",
                content=proposal.summary,
                structured_content={
                    "summary": proposal.summary,
                    "conditions": proposal.conditions,
                    "steps": proposal.steps,
                },
                source_ids=proposal.source_ids,
                route=knowledge.route,
                timings={
                    **adapter_timings,
                    "generation_total": generation_ms,
                    "total": elapsed_ms,
                },
            )
        elif isinstance(proposal, GenerationClarify):
            if context["clarification_count"] >= 1:
                self._offer_handoff(
                    request_id, knowledge.route, ReasonCode.UNRESOLVED_AFTER_STEPS
                )
            else:
                self.database.publish_message(
                    request_id,
                    case_status=CaseStatus.AWAITING_CLARIFICATION,
                    role="assistant",
                    kind="clarification",
                    responder_type="system",
                    answer_origin="system",
                    content=proposal.question,
                    source_ids=[],
                    route=knowledge.route,
                    clarification_increment=True,
                )
        elif isinstance(proposal, GenerationEscalate):
            self._offer_handoff(request_id, knowledge.route, proposal.reason_code)
        else:
            raise InvalidGeneration("unsupported proposal")

    def _offer_handoff(self, request_id: UUID, route, reason: ReasonCode) -> None:
        reason_codes = list(route.reason_codes) if route else []
        if reason not in reason_codes:
            reason_codes.append(reason)
        route = (route or RoutingResult()).model_copy(
            update={"reason_codes": reason_codes}
        )
        self.database.publish_message(
            request_id,
            case_status=CaseStatus.HANDOFF_OFFERED,
            role="assistant",
            kind="notice",
            responder_type="system",
            answer_origin="system",
            content=f"Недостаточно проверенных материалов ({reason.value}). Передать специалисту?",
            source_ids=[],
            route=route,
        )

    async def worker_loop(self) -> None:
        while True:
            while await self.process_next():
                pass
            self._wake.clear()
            await self._wake.wait()

    async def stop_worker(self, task: asyncio.Task | None) -> None:
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    def get_request(self, session_id: UUID, request_id: UUID) -> RequestView:
        return self.database.get_request(session_id, request_id)

    def get_case(self, session_id: UUID, case_id: UUID):
        return self.database.get_case(session_id, case_id)

    async def get_source(self, source_id: str):
        return await self.knowledge.get_source(source_id)

    def save_feedback(
        self, session_id: UUID, payload: FeedbackInput
    ) -> FeedbackResponse:
        return self.database.save_feedback(session_id, payload)

    def save_feedback_with_status(
        self, session_id: UUID, payload: FeedbackInput
    ) -> tuple[FeedbackResponse, bool]:
        return self.database.save_feedback_with_status(session_id, payload)

    def confirm_handoff(
        self, session_id: UUID, case_id: UUID, payload: HandoffInput
    ) -> tuple[Ticket, bool]:
        return self.database.confirm_handoff(session_id, case_id, payload)

    def reply_as_operator(
        self, ticket_id: UUID, payload: OperatorReplyInput, *, author_id: str
    ) -> Message:
        return self.database.reply_as_operator(ticket_id, payload, author_id=author_id)
