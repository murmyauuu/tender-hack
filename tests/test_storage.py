from pathlib import Path
from uuid import uuid4

import pytest
from tenderhack_backend.errors import DomainError
from tenderhack_backend.storage import Database, hash_payload
from tenderhack_contracts import ChatInput, RequestStatus


def new_chat(key=None) -> ChatInput:
    return ChatInput(request_key=key or uuid4(), text="Как подписать контракт?")


def test_chat_receipt_is_durable_and_body_bound(tmp_path: Path) -> None:
    path = tmp_path / "app.sqlite"
    db = Database(path)
    session, _ = db.get_or_create_session(None)
    payload = new_chat()

    first, created = db.accept_chat(session.session_id, payload, is_demo=True)
    repeated, repeated_created = db.accept_chat(
        session.session_id, payload, is_demo=True
    )

    assert created is True
    assert repeated_created is False
    assert repeated == first
    assert (
        Database(path).accept_chat(session.session_id, payload, is_demo=True)[0]
        == first
    )

    conflicting = payload.model_copy(update={"text": "Другой вопрос"})
    with pytest.raises(DomainError, match="IDEMPOTENCY_CONFLICT"):
        db.accept_chat(session.session_id, conflicting, is_demo=True)


def test_retry_reuses_original_user_message(tmp_path: Path) -> None:
    db = Database(tmp_path / "app.sqlite")
    session, _ = db.get_or_create_session(None)
    accepted, _ = db.accept_chat(session.session_id, new_chat(), is_demo=True)
    db.fail_request(accepted.request_id, "MODEL_UNAVAILABLE", retryable=True)
    case = db.get_case(session.session_id, accepted.case_id)

    retry = ChatInput(
        case_id=accepted.case_id,
        expected_case_version=case.case.case_version,
        request_key=uuid4(),
        text=None,
        retry_of=accepted.request_id,
    )
    retried, created = db.accept_chat(session.session_id, retry, is_demo=True)

    assert created is True
    assert retried.request_id != accepted.request_id
    assert retried.user_message_id == accepted.user_message_id
    assert len(db.get_case(session.session_id, accepted.case_id).messages) == 1


def test_restart_marks_interrupted_request_error_and_keeps_question(
    tmp_path: Path,
) -> None:
    path = tmp_path / "app.sqlite"
    db = Database(path)
    session, _ = db.get_or_create_session(None)
    accepted, _ = db.accept_chat(session.session_id, new_chat(), is_demo=True)
    db.mark_processing(accepted.request_id, "retrieving")

    recovered = Database(path)
    recovered.recover_interrupted_requests()
    request = recovered.get_request(session.session_id, accepted.request_id)
    case = recovered.get_case(session.session_id, accepted.case_id)

    assert request.status is RequestStatus.ERROR
    assert request.error is not None and request.error.code == "RESTART_INTERRUPTED"
    assert case.case.active_request_id is None
    assert [message.content for message in case.messages] == ["Как подписать контракт?"]


def test_private_case_and_request_are_indistinguishable_from_missing(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "app.sqlite")
    owner, _ = db.get_or_create_session(None)
    stranger, _ = db.get_or_create_session(None)
    accepted, _ = db.accept_chat(owner.session_id, new_chat(), is_demo=True)

    for read in (
        lambda: db.get_case(stranger.session_id, accepted.case_id),
        lambda: db.get_request(stranger.session_id, accepted.request_id),
    ):
        with pytest.raises(DomainError) as exc:
            read()
        assert exc.value.code == "NOT_FOUND"


def test_payload_hash_is_canonical() -> None:
    assert hash_payload({"b": 2, "a": 1}) == hash_payload({"a": 1, "b": 2})
