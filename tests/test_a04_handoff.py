import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from tenderhack_backend.app import create_app
from tenderhack_backend.config import Settings
from tenderhack_backend.errors import DomainError
from tenderhack_backend.fakes import FakeGenerator, FakeKnowledge, FakePolicy
from tenderhack_backend.service import BackendService
from tenderhack_backend.storage import Database
from tenderhack_contracts import (
    EvidenceItem,
    FeedbackInput,
    GateDecision,
    GenerationAnswer,
    HandoffInput,
    KnowledgeResult,
    OperatorReplyInput,
    PolicyResult,
    ReasonCode,
    RoutingResult,
)


def run(coro):
    return asyncio.run(coro)


def build_service(tmp_path: Path, *, policy=None):
    knowledge = FakeKnowledge()
    knowledge.result = knowledge.result.model_copy(
        update={
            "route": RoutingResult(
                topic_id="TH1",
                subtopic_id="ST01",
                support_line="L2",
                recommended_recipient=None,
                basis_source_ids=["portal:42:1"],
                reason_codes=[ReasonCode.NO_EVIDENCE],
            )
        }
    )
    generator = FakeGenerator()
    service = BackendService(
        Database(tmp_path / "app.sqlite"),
        policy or FakePolicy(),
        knowledge,
        generator,
    )
    return service, knowledge, generator


def offered_case(service: BackendService):
    session, _ = service.create_session(None)
    accepted = run(
        service.accept_chat(
            session.session_id,
            {"request_key": str(uuid4()), "text": "Нужна помощь"},
            is_demo=True,
        )
    )
    run(service.process_next())
    view = service.get_case(session.session_id, accepted.case_id)
    assert view.case.status == "handoff_offered"
    assert view.ticket is None
    return session, accepted, view


def test_confirmed_handoff_is_single_ticket_with_c04_context(tmp_path: Path) -> None:
    service, _, _ = build_service(tmp_path)
    session, accepted, offered = offered_case(service)
    payload = HandoffInput(
        request_key=uuid4(), expected_case_version=offered.case.case_version
    )

    ticket, created = service.confirm_handoff(
        session.session_id, accepted.case_id, payload
    )
    repeated, repeated_created = service.confirm_handoff(
        session.session_id, accepted.case_id, payload
    )
    current = service.get_case(session.session_id, accepted.case_id)

    assert created is True
    assert repeated_created is False
    assert repeated.ticket_id == ticket.ticket_id
    assert current.case.status == "handed_off"
    assert current.ticket.status == "new"
    assert current.ticket.route.support_line == "L2"
    assert current.ticket.route.recommended_recipient is None
    assert current.ticket.context_snapshot["case"]["case_id"] == str(accepted.case_id)
    assert current.ticket.context_snapshot["handoff_reason"] == "NO_EVIDENCE"
    assert current.ticket.context_snapshot["routing"]["support_line"] == "L2"
    assert "recommended_recipient" not in current.ticket.context_snapshot["routing"]
    assert current.ticket.context_snapshot["source_context"]["source_ids"] == [
        "portal:42:1"
    ]


def test_operator_conversation_transitions_without_ai(tmp_path: Path) -> None:
    service, knowledge, generator = build_service(tmp_path)
    session, accepted, offered = offered_case(service)
    ticket, _ = service.confirm_handoff(
        session.session_id,
        accepted.case_id,
        HandoffInput(
            request_key=uuid4(), expected_case_version=offered.case.case_version
        ),
    )
    handed_off = service.get_case(session.session_id, accepted.case_id)

    first = service.reply_as_operator(
        ticket.ticket_id,
        OperatorReplyInput(
            request_key=uuid4(),
            expected_case_version=handed_off.case.case_version,
            text="Уточните номер закупки.",
            next_status="waiting_user",
        ),
        author_id="operator-local",
    )
    waiting = service.get_case(session.session_id, accepted.case_id)
    assert first.author_id == "operator-local"
    assert first.responder_type == "operator"
    assert first.answer_origin == "operator"
    assert waiting.ticket.status == "waiting_user"

    retrieval_before = knowledge.retrieve_calls
    generation_before = generator.calls
    user_reply = run(
        service.accept_chat(
            session.session_id,
            {
                "case_id": str(accepted.case_id),
                "expected_case_version": waiting.case.case_version,
                "request_key": str(uuid4()),
                "text": "Номер закупки 123.",
            },
            is_demo=True,
        )
    )
    after_user = service.get_case(session.session_id, accepted.case_id)
    assert user_reply.status == "final"
    assert after_user.ticket.status == "new"
    assert after_user.case.active_request_id is None
    assert knowledge.retrieve_calls == retrieval_before
    assert generator.calls == generation_before

    final = service.reply_as_operator(
        ticket.ticket_id,
        OperatorReplyInput(
            request_key=uuid4(),
            expected_case_version=after_user.case.case_version,
            text="Проблема решена.",
            next_status="resolved",
        ),
        author_id="operator-local",
    )
    resolved = service.get_case(session.session_id, accepted.case_id)
    assert final.seq == first.seq + 2
    assert resolved.case.status == "resolved"
    assert resolved.ticket.status == "resolved"
    assert resolved.ticket.resolved_by == "operator"
    assert [message.message_id for message in resolved.messages].count(first.message_id) == 1


def test_operator_reply_is_idempotent_and_rejects_stale_version(tmp_path: Path) -> None:
    service, _, _ = build_service(tmp_path)
    session, accepted, offered = offered_case(service)
    ticket, _ = service.confirm_handoff(
        session.session_id,
        accepted.case_id,
        HandoffInput(request_key=uuid4(), expected_case_version=offered.case.case_version),
    )
    current = service.get_case(session.session_id, accepted.case_id)
    payload = OperatorReplyInput(
        request_key=uuid4(),
        expected_case_version=current.case.case_version,
        text="Ответ специалиста",
        next_status="waiting_user",
    )
    first = service.reply_as_operator(ticket.ticket_id, payload, author_id="operator-local")
    second = service.reply_as_operator(ticket.ticket_id, payload, author_id="operator-local")
    assert second.message_id == first.message_id

    with pytest.raises(DomainError) as error:
        service.reply_as_operator(
            ticket.ticket_id,
            payload.model_copy(update={"request_key": uuid4()}),
            author_id="operator-local",
        )
    assert error.value.code == "STALE_CASE_VERSION"


class TextPolicy:
    def check(self, text: str) -> PolicyResult:
        return PolicyResult(
            profanity=text == "блять",
            explicit_human_request=text == "позовите оператора",
            matched_rule_ids=[],
        )


def test_explicit_human_request_cancels_active_request_and_blocks_late_result(
    tmp_path: Path,
) -> None:
    service, knowledge, generator = build_service(tmp_path, policy=TextPolicy())
    session, _ = service.create_session(None)
    first = run(
        service.accept_chat(
            session.session_id,
            {"request_key": str(uuid4()), "text": "Первый вопрос"},
            is_demo=True,
        )
    )
    explicit = run(
        service.accept_chat(
            session.session_id,
            {
                "case_id": str(first.case_id),
                "expected_case_version": first.case_version,
                "request_key": str(uuid4()),
                "text": "позовите оператора",
            },
            is_demo=True,
        )
    )

    handed_off = service.get_case(session.session_id, first.case_id)
    assert service.get_request(session.session_id, first.request_id).status == "cancelled"
    assert service.get_request(session.session_id, explicit.request_id).status == "final"
    assert handed_off.ticket is not None
    assert handed_off.case.status == "handed_off"

    run(service.process_next())
    after_late = service.get_case(session.session_id, first.case_id)
    assert all(message.responder_type != "ai" for message in after_late.messages)
    assert generator.calls == 0
    assert knowledge.retrieve_calls == 0


def test_inflight_ai_result_is_not_published_after_explicit_handoff(
    tmp_path: Path,
) -> None:
    evidence = EvidenceItem(
        evidence_id="ev-1",
        source_id="portal:1:1",
        source_type="portal_kb",
        title="Инструкция",
        text="Проверенный текст инструкции.",
        content_status="complete",
        retrieval_method="dense",
        score=0.9,
    )
    knowledge = FakeKnowledge(
        KnowledgeResult(
            snapshot_id="mock",
            candidates=[evidence],
            selected_evidence_ids=["ev-1"],
            decision=GateDecision.ANSWER_ALLOWED,
            route=RoutingResult(support_line="L1"),
        )
    )

    class BlockingGenerator:
        def __init__(self):
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def generate(self, _task):
            self.started.set()
            await self.release.wait()
            return GenerationAnswer(
                summary="Проверенный текст инструкции.",
                steps=["Проверенный текст инструкции."],
                source_ids=["portal:1:1"],
            )

    generator = BlockingGenerator()
    service = BackendService(
        Database(tmp_path / "app.sqlite"), TextPolicy(), knowledge, generator
    )
    session, _ = service.create_session(None)

    async def scenario():
        accepted = await service.accept_chat(
            session.session_id,
            {"request_key": str(uuid4()), "text": "Первый вопрос"},
            is_demo=True,
        )
        processing = asyncio.create_task(service.process_next())
        await generator.started.wait()
        await service.accept_chat(
            session.session_id,
            {
                "case_id": str(accepted.case_id),
                "expected_case_version": accepted.case_version,
                "request_key": str(uuid4()),
                "text": "позовите оператора",
            },
            is_demo=True,
        )
        generator.release.set()
        await processing
        return accepted

    accepted = run(scenario())
    request = service.get_request(session.session_id, accepted.request_id)
    case = service.get_case(session.session_id, accepted.case_id)
    assert request.status == "cancelled"
    assert case.case.status == "handed_off"
    assert case.ticket is not None
    assert all(message.responder_type != "ai" for message in case.messages)


def test_profanity_closes_existing_ticket_without_model_pipeline(tmp_path: Path) -> None:
    from knowledge.policy import build_policy

    service, knowledge, generator = build_service(tmp_path, policy=build_policy())
    session, accepted, offered = offered_case(service)
    service.confirm_handoff(
        session.session_id,
        accepted.case_id,
        HandoffInput(request_key=uuid4(), expected_case_version=offered.case.case_version),
    )
    current = service.get_case(session.session_id, accepted.case_id)
    retrieval_before = knowledge.retrieve_calls
    generation_before = generator.calls

    run(
        service.accept_chat(
            session.session_id,
            {
                "case_id": str(accepted.case_id),
                "expected_case_version": current.case.case_version,
                "request_key": str(uuid4()),
                "text": "блять",
            },
            is_demo=True,
        )
    )
    closed = service.get_case(session.session_id, accepted.case_id)
    assert closed.case.status == "closed_policy"
    assert closed.ticket.status == "closed_policy"
    assert knowledge.retrieve_calls == retrieval_before
    assert generator.calls == generation_before


def test_feedback_applies_only_to_current_operator_answer(tmp_path: Path) -> None:
    service, _, _ = build_service(tmp_path)
    session, accepted, offered = offered_case(service)
    ticket, _ = service.confirm_handoff(
        session.session_id,
        accepted.case_id,
        HandoffInput(request_key=uuid4(), expected_case_version=offered.case.case_version),
    )
    current = service.get_case(session.session_id, accepted.case_id)
    answer = service.reply_as_operator(
        ticket.ticket_id,
        OperatorReplyInput(
            request_key=uuid4(),
            expected_case_version=current.case.case_version,
            text="Готово",
            next_status="waiting_user",
        ),
        author_id="operator-local",
    )
    saved = service.save_feedback(
        session.session_id,
        FeedbackInput(message_id=answer.message_id, specialist_rating=5, solved=True),
    )
    resolved = service.get_case(session.session_id, accepted.case_id)
    assert saved.outcome_applied is True
    assert resolved.case.status == "resolved"
    assert resolved.ticket.status == "resolved"
    assert resolved.ticket.resolved_by == "user"


def test_stale_operator_solved_feedback_does_not_close_newer_case(
    tmp_path: Path,
) -> None:
    service, _, _ = build_service(tmp_path)
    session, accepted, offered = offered_case(service)
    ticket, _ = service.confirm_handoff(
        session.session_id,
        accepted.case_id,
        HandoffInput(request_key=uuid4(), expected_case_version=offered.case.case_version),
    )
    current = service.get_case(session.session_id, accepted.case_id)
    old_answer = service.reply_as_operator(
        ticket.ticket_id,
        OperatorReplyInput(
            request_key=uuid4(),
            expected_case_version=current.case.case_version,
            text="Первый ответ",
            next_status="waiting_user",
        ),
        author_id="operator-local",
    )
    waiting = service.get_case(session.session_id, accepted.case_id)
    run(
        service.accept_chat(
            session.session_id,
            {
                "case_id": str(accepted.case_id),
                "expected_case_version": waiting.case.case_version,
                "request_key": str(uuid4()),
                "text": "Дополнение",
            },
            is_demo=True,
        )
    )
    new_turn = service.get_case(session.session_id, accepted.case_id)
    service.reply_as_operator(
        ticket.ticket_id,
        OperatorReplyInput(
            request_key=uuid4(),
            expected_case_version=new_turn.case.case_version,
            text="Более новый ответ",
            next_status="waiting_user",
        ),
        author_id="operator-local",
    )

    stale = service.save_feedback(
        session.session_id,
        FeedbackInput(message_id=old_answer.message_id, solved=True),
    )
    after = service.get_case(session.session_id, accepted.case_id)
    assert stale.outcome_applied is False
    assert stale.outcome_reason == "ANSWER_NOT_CURRENT"
    assert after.case.status == "handed_off"
    assert after.ticket.status == "waiting_user"


def test_internal_reply_auth_and_server_authorship(tmp_path: Path) -> None:
    service, _, _ = build_service(tmp_path)
    settings = Settings(
        db_path=tmp_path / "app.sqlite",
        allowed_origin="http://testserver",
        auto_worker=False,
        runtime_mode="test",
        operator_reply_key="test-only-secret",
        operator_author_id="operator-local",
    )
    app = create_app(settings=settings, service=service)
    with TestClient(app) as client:
        session = client.post("/api/v1/sessions", headers={"origin": "http://testserver"})
        accepted = client.post(
            "/api/v1/chat",
            headers={"origin": "http://testserver"},
            json={"request_key": str(uuid4()), "text": "Нужна помощь"},
        ).json()
        run(service.process_next())
        offered = client.get(f"/api/v1/cases/{accepted['case_id']}").json()
        handoff = client.post(
            f"/api/v1/cases/{accepted['case_id']}/handoff",
            headers={"origin": "http://testserver"},
            json={
                "request_key": str(uuid4()),
                "expected_case_version": offered["case"]["case_version"],
            },
        )
        assert handoff.status_code == 201
        ticket = handoff.json()
        current = client.get(f"/api/v1/cases/{accepted['case_id']}").json()
        body = {
            "request_key": str(uuid4()),
            "expected_case_version": current["case"]["case_version"],
            "text": "Ответ",
            "next_status": "waiting_user",
        }

        assert client.post(f"/internal/tickets/{ticket['ticket_id']}/reply", json=body).status_code == 401
        assert client.post(
            f"/internal/tickets/{ticket['ticket_id']}/reply",
            headers={"authorization": "Bearer wrong"},
            json=body,
        ).status_code == 401
        for field, value in (
            ("author_id", "forged"),
            ("responder_type", "ai"),
            ("answer_origin", "rag"),
        ):
            forged = {**body, "request_key": str(uuid4()), field: value}
            assert client.post(
                f"/internal/tickets/{ticket['ticket_id']}/reply",
                headers={"authorization": "Bearer test-only-secret"},
                json=forged,
            ).status_code == 422
        reply = client.post(
            f"/internal/tickets/{ticket['ticket_id']}/reply",
            headers={"authorization": "Bearer test-only-secret"},
            json=body,
        )
        assert reply.status_code == 200
        assert reply.json()["author_id"] == "operator-local"
        assert reply.json()["responder_type"] == "operator"
        assert reply.json()["answer_origin"] == "operator"

        stranger = TestClient(app)
        stranger.post("/api/v1/sessions", headers={"origin": "http://testserver"})
        assert stranger.get(f"/api/v1/cases/{accepted['case_id']}").status_code == 404
