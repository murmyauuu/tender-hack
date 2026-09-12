import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from tenderhack_backend.errors import DomainError
from tenderhack_backend.fakes import FakeGenerator, FakeKnowledge, FakePolicy
from tenderhack_backend.service import BackendService
from tenderhack_backend.storage import Database
from tenderhack_backend.verifier import InvalidGeneration
from tenderhack_contracts import (
    EvidenceItem,
    FeedbackInput,
    GateDecision,
    GenerationAnswer,
    KnowledgeResult,
    PolicyResult,
    RequestStatus,
    RoutingResult,
    SourceRecord,
)


def run(coro):
    return asyncio.run(coro)


def answer_dependencies():
    evidence = EvidenceItem(
        evidence_id="evidence-demo",
        source_id="source-demo",
        source_type="portal_knowledge_base_api",
        title="Инструкция",
        text="Поставщик открывает карточку контракта.",
        conditions=["Действуйте от имени поставщика."],
        applicable_roles=["supplier"],
        role_verified=True,
        content_status="complete",
        retrieval_method="dense",
        score=0.9,
    )
    knowledge = FakeKnowledge(
        KnowledgeResult(
            snapshot_id="mock-a02",
            candidates=[evidence],
            selected_evidence_ids=["evidence-demo"],
            decision=GateDecision.ANSWER_ALLOWED,
            route=RoutingResult(support_line="L1", basis_source_ids=["source-demo"]),
            timings_ms={"retrieval": 7},
        )
    )
    knowledge.sources["source-demo"] = SourceRecord(
        source_id="source-demo",
        source_type="portal_knowledge_base_api",
        title="Инструкция",
        excerpt=evidence.text,
        conditions=evidence.conditions,
        applicable_roles=["supplier"],
        content_status="complete",
    )
    generator = FakeGenerator(
        GenerationAnswer(
            summary="Откройте карточку контракта.",
            conditions=["Действуйте от имени поставщика."],
            steps=["Откройте карточку контракта."],
            source_ids=["source-demo"],
        )
    )
    return knowledge, generator


def build_service(tmp_path: Path, *, capacity: int = 4):
    knowledge, generator = answer_dependencies()
    service = BackendService(
        Database(tmp_path / "app.sqlite"),
        policy=FakePolicy(),
        knowledge=knowledge,
        generator=generator,
        queue_capacity=capacity,
    )
    return service, knowledge, generator


def test_chat_poll_answer_source_feedback_flow(tmp_path: Path) -> None:
    service, knowledge, generator = build_service(tmp_path)
    session, _ = service.create_session(None)
    accepted = run(
        service.accept_chat(
            session.session_id,
            {
                "case_id": None,
                "expected_case_version": None,
                "request_key": str(uuid4()),
                "text": "Как подписать контракт?",
                "retry_of": None,
            },
            is_demo=True,
        )
    )

    assert accepted.status is RequestStatus.QUEUED
    assert run(service.process_next()) is True
    request = service.get_request(session.session_id, accepted.request_id)
    case = service.get_case(session.session_id, accepted.case_id)
    source = run(service.get_source("source-demo"))

    assert request.status is RequestStatus.FINAL
    assert set(request.timings_ms) == {
        "queue",
        "retrieval",
        "generation_total",
        "time_to_first_source",
        "total",
        "prompt_eval",
        "decode",
    }
    assert request.timings_ms["queue"] is not None
    assert generator.calls == 1
    assert knowledge.retrieve_calls == 1
    assert case.case.status == "awaiting_feedback"
    assert case.messages[-1].structured_content.steps == [
        "Откройте карточку контракта."
    ]
    assert source is not None and source.source_id == "source-demo"

    feedback = service.save_feedback(
        session.session_id,
        FeedbackInput(
            message_id=case.messages[-1].message_id, useful=True, solved=True
        ),
    )
    assert feedback.outcome_applied is True
    assert feedback.case_status == "resolved"


def test_exact_chat_repeat_does_not_duplicate_queue_or_generation(
    tmp_path: Path,
) -> None:
    service, _, generator = build_service(tmp_path)
    session, _ = service.create_session(None)
    body = {"request_key": str(uuid4()), "text": "Как подписать контракт?"}

    first = run(service.accept_chat(session.session_id, body, is_demo=True))
    second = run(service.accept_chat(session.session_id, body, is_demo=True))
    assert second == first
    assert run(service.process_next()) is True
    assert run(service.process_next()) is False
    assert generator.calls == 1


def test_stale_publication_cancels_request_without_ai_message(tmp_path: Path) -> None:
    service, _, generator = build_service(tmp_path)
    session, _ = service.create_session(None)
    accepted = run(
        service.accept_chat(
            session.session_id,
            {"request_key": str(uuid4()), "text": "Первый вопрос"},
            is_demo=True,
        )
    )
    service.database.invalidate_request(accepted.request_id, "SUPERSEDED")

    assert run(service.process_next()) is True
    request = service.get_request(session.session_id, accepted.request_id)
    case = service.get_case(session.session_id, accepted.case_id)
    assert request.status is RequestStatus.CANCELLED
    assert generator.calls == 1
    assert [message.role for message in case.messages] == ["user"]


def test_stale_request_stays_cancelled_when_adapter_later_fails(tmp_path: Path) -> None:
    class FailingKnowledge(FakeKnowledge):
        async def retrieve(self, query):
            raise OSError("late failure")

    generator = FakeGenerator()
    service = BackendService(
        Database(tmp_path / "app.sqlite"), FakePolicy(), FailingKnowledge(), generator
    )
    session, _ = service.create_session(None)
    accepted = run(
        service.accept_chat(
            session.session_id,
            {"request_key": str(uuid4()), "text": "Вопрос"},
            is_demo=True,
        )
    )
    service.database.invalidate_request(accepted.request_id, "SUPERSEDED")
    run(service.process_next())
    assert (
        service.get_request(session.session_id, accepted.request_id).status
        == "cancelled"
    )


class InvalidGenerator:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, task):
        self.calls += 1
        raise InvalidGeneration("invalid JSON")


def test_invalid_generation_is_one_call_and_offers_handoff(tmp_path: Path) -> None:
    knowledge, _ = answer_dependencies()
    generator = InvalidGenerator()
    service = BackendService(
        Database(tmp_path / "app.sqlite"), FakePolicy(), knowledge, generator
    )
    session, _ = service.create_session(None)
    accepted = run(
        service.accept_chat(
            session.session_id,
            {"request_key": str(uuid4()), "text": "Вопрос"},
            is_demo=True,
        )
    )

    run(service.process_next())
    case = service.get_case(session.session_id, accepted.case_id)
    assert generator.calls == 1
    assert case.case.status == "handoff_offered"
    assert case.messages[-1].kind == "notice"
    assert "INVALID_GENERATION" in case.case.route.reason_codes


def test_unsupported_generator_object_is_invalid_without_retry(tmp_path: Path) -> None:
    knowledge, _ = answer_dependencies()

    class UnsupportedGenerator:
        def __init__(self):
            self.calls = 0

        async def generate(self, task):
            self.calls += 1
            return {"action": "answer", "summary": "not a contract model"}

    generator = UnsupportedGenerator()
    service = BackendService(
        Database(tmp_path / "app.sqlite"), FakePolicy(), knowledge, generator
    )
    session, _ = service.create_session(None)
    accepted = run(
        service.accept_chat(
            session.session_id,
            {"request_key": str(uuid4()), "text": "Вопрос"},
            is_demo=True,
        )
    )
    run(service.process_next())
    case = service.get_case(session.session_id, accepted.case_id)
    assert generator.calls == 1
    assert case.case.status == "handoff_offered"


def test_model_transport_failure_is_retryable_request_error(tmp_path: Path) -> None:
    knowledge, _ = answer_dependencies()

    class UnavailableGenerator:
        def __init__(self):
            self.calls = 0

        async def generate(self, task):
            self.calls += 1
            raise OSError("ollama unavailable")

    generator = UnavailableGenerator()
    service = BackendService(
        Database(tmp_path / "app.sqlite"), FakePolicy(), knowledge, generator
    )
    session, _ = service.create_session(None)
    accepted = run(
        service.accept_chat(
            session.session_id,
            {"request_key": str(uuid4()), "text": "Вопрос"},
            is_demo=True,
        )
    )
    run(service.process_next())
    request = service.get_request(session.session_id, accepted.request_id)
    assert generator.calls == 1
    assert request.status == "error"
    assert request.error is not None and request.error.code == "MODEL_UNAVAILABLE"


def test_queue_overflow_happens_before_case_or_message_is_saved(tmp_path: Path) -> None:
    service, _, _ = build_service(tmp_path, capacity=4)
    sessions = [service.create_session(None)[0] for _ in range(5)]
    for index in range(4):
        run(
            service.accept_chat(
                sessions[index].session_id,
                {"request_key": str(uuid4()), "text": f"Вопрос {index}"},
                is_demo=True,
            )
        )

    with pytest.raises(DomainError) as exc:
        run(
            service.accept_chat(
                sessions[4].session_id,
                {"request_key": str(uuid4()), "text": "Переполнение"},
                is_demo=True,
            )
        )
    assert exc.value.code == "QUEUE_FULL"
    assert service.database.count_cases(sessions[4].session_id) == 0


def test_feedback_rejects_ai_specialist_rating_and_old_solved(tmp_path: Path) -> None:
    service, _, _ = build_service(tmp_path)
    session, _ = service.create_session(None)
    first = run(
        service.accept_chat(
            session.session_id,
            {"request_key": str(uuid4()), "text": "Первый"},
            is_demo=True,
        )
    )
    run(service.process_next())
    first_answer = service.get_case(session.session_id, first.case_id).messages[-1]

    with pytest.raises(DomainError) as exc:
        service.save_feedback(
            session.session_id,
            FeedbackInput(message_id=first_answer.message_id, specialist_rating=5),
        )
    assert exc.value.status_code == 422

    current = service.get_case(session.session_id, first.case_id).case
    run(
        service.accept_chat(
            session.session_id,
            {
                "case_id": str(first.case_id),
                "expected_case_version": current.case_version,
                "request_key": str(uuid4()),
                "text": "Новый вопрос",
            },
            is_demo=True,
        )
    )
    feedback = service.save_feedback(
        session.session_id,
        FeedbackInput(message_id=first_answer.message_id, solved=True),
    )
    assert feedback.outcome_applied is False
    assert feedback.outcome_reason == "ANSWER_NOT_CURRENT"


def test_real_c01_policy_short_circuits_knowledge_and_generation(
    tmp_path: Path,
) -> None:
    from knowledge.policy import build_policy

    knowledge, generator = answer_dependencies()
    service = BackendService(
        Database(tmp_path / "app.sqlite"), build_policy(), knowledge, generator
    )
    session, _ = service.create_session(None)
    accepted = run(
        service.accept_chat(
            session.session_id,
            {"request_key": str(uuid4()), "text": "блять"},
            is_demo=True,
        )
    )
    case = service.get_case(session.session_id, accepted.case_id)
    assert case.case.status == "closed_policy"
    assert "POLICY_LANGUAGE" in case.case.route.reason_codes
    assert knowledge.retrieve_calls == 0
    assert generator.calls == 0


def test_single_worker_prevents_parallel_generations(tmp_path: Path) -> None:
    knowledge, _ = answer_dependencies()

    class ConcurrencyGenerator:
        def __init__(self):
            self.active = 0
            self.max_active = 0

        async def generate(self, task):
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            await asyncio.sleep(0.02)
            self.active -= 1
            return GenerationAnswer(
                summary="Откройте карточку контракта.",
                conditions=["Действуйте от имени поставщика."],
                steps=["Откройте карточку контракта."],
                source_ids=["source-demo"],
            )

    generator = ConcurrencyGenerator()
    service = BackendService(
        Database(tmp_path / "app.sqlite"), FakePolicy(), knowledge, generator
    )
    sessions = [service.create_session(None)[0] for _ in range(2)]
    for session in sessions:
        run(
            service.accept_chat(
                session.session_id,
                {"request_key": str(uuid4()), "text": "Вопрос"},
                is_demo=True,
            )
        )

    async def process_both():
        await asyncio.gather(service.process_next(), service.process_next())

    run(process_both())
    assert generator.max_active == 1


def test_verifier_rejects_dropped_evidence_condition(tmp_path: Path) -> None:
    knowledge, _ = answer_dependencies()
    generator = FakeGenerator(
        GenerationAnswer(
            summary="Откройте карточку контракта.",
            conditions=[],
            steps=["Откройте карточку контракта."],
            source_ids=["source-demo"],
        )
    )
    service = BackendService(
        Database(tmp_path / "app.sqlite"), FakePolicy(), knowledge, generator
    )
    session, _ = service.create_session(None)
    accepted = run(
        service.accept_chat(
            session.session_id,
            {"request_key": str(uuid4()), "text": "Вопрос"},
            is_demo=True,
        )
    )
    run(service.process_next())
    assert (
        service.get_case(session.session_id, accepted.case_id).case.status
        == "handoff_offered"
    )
    assert generator.calls == 1


def test_verifier_rejects_ungrounded_number(tmp_path: Path) -> None:
    knowledge, _ = answer_dependencies()
    generator = FakeGenerator(
        GenerationAnswer(
            summary="Операция займёт 30 дней.",
            conditions=["Действуйте от имени поставщика."],
            steps=["Откройте карточку контракта."],
            source_ids=["source-demo"],
        )
    )
    service = BackendService(
        Database(tmp_path / "app.sqlite"), FakePolicy(), knowledge, generator
    )
    session, _ = service.create_session(None)
    accepted = run(
        service.accept_chat(
            session.session_id,
            {"request_key": str(uuid4()), "text": "Вопрос"},
            is_demo=True,
        )
    )
    run(service.process_next())
    assert (
        service.get_case(session.session_id, accepted.case_id).case.status
        == "handoff_offered"
    )
    assert generator.calls == 1


def test_policy_message_supersedes_active_request_before_busy_check(
    tmp_path: Path,
) -> None:
    class TextPolicy:
        def check(self, text):
            return PolicyResult(
                profanity=text == "блять",
                explicit_human_request=False,
                matched_rule_ids=["POL.PROF.BLYAD"] if text == "блять" else [],
            )

    knowledge, generator = answer_dependencies()
    service = BackendService(
        Database(tmp_path / "app.sqlite"), TextPolicy(), knowledge, generator
    )
    session, _ = service.create_session(None)
    first = run(
        service.accept_chat(
            session.session_id,
            {"request_key": str(uuid4()), "text": "Первый вопрос"},
            is_demo=True,
        )
    )
    second = run(
        service.accept_chat(
            session.session_id,
            {
                "case_id": str(first.case_id),
                "expected_case_version": first.case_version,
                "request_key": str(uuid4()),
                "text": "блять",
            },
            is_demo=True,
        )
    )
    assert (
        service.get_request(session.session_id, first.request_id).status == "cancelled"
    )
    assert (
        service.get_case(session.session_id, second.case_id).case.status
        == "closed_policy"
    )
    run(service.process_next())
    case = service.get_case(session.session_id, first.case_id)
    assert generator.calls == 1
    assert [message.role for message in case.messages] == ["user", "user", "assistant"]


def test_retry_cannot_probe_another_sessions_request(tmp_path: Path) -> None:
    service, _, _ = build_service(tmp_path)
    owner, _ = service.create_session(None)
    stranger, _ = service.create_session(None)
    accepted = run(
        service.accept_chat(
            owner.session_id,
            {"request_key": str(uuid4()), "text": "Вопрос"},
            is_demo=True,
        )
    )
    service.database.fail_request(
        accepted.request_id, "MODEL_UNAVAILABLE", retryable=True
    )

    with pytest.raises(DomainError) as exc:
        run(
            service.accept_chat(
                stranger.session_id,
                {
                    "case_id": str(accepted.case_id),
                    "expected_case_version": 2,
                    "request_key": str(uuid4()),
                    "retry_of": str(accepted.request_id),
                    "text": None,
                },
                is_demo=True,
            )
        )
    assert exc.value.code == "NOT_FOUND"
