import asyncio
from pathlib import Path
from uuid import uuid4

from tenderhack_backend.export import build_export, write_export
from tenderhack_backend.fakes import FakePolicy
from tenderhack_backend.service import BackendService
from tenderhack_backend.storage import Database
from tenderhack_contracts import ChatInput, FeedbackInput
from test_service import answer_dependencies


def test_export_has_exactly_one_row_per_case_including_no_answer(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "app.sqlite")
    knowledge, generator = answer_dependencies()
    service = BackendService(database, FakePolicy(), knowledge, generator)
    session, _ = service.create_session(None)

    unanswered, _ = database.accept_chat(
        session.session_id,
        ChatInput(request_key=uuid4(), text="Останется без ответа"),
        is_demo=True,
    )
    database.fail_request(unanswered.request_id, "MODEL_UNAVAILABLE", retryable=True)

    answered = asyncio.run(
        service.accept_chat(
            session.session_id,
            {"request_key": str(uuid4()), "text": "Как подписать контракт?"},
            is_demo=True,
        )
    )
    asyncio.run(service.process_next())
    answer = service.get_case(session.session_id, answered.case_id).messages[-1]
    service.save_feedback(
        session.session_id,
        FeedbackInput(message_id=answer.message_id, useful=True, solved=True),
    )

    exported = build_export(database, app_commit="abc123", kb_snapshot_id="mock-a02")
    assert len(exported.rows) == 2
    no_answer = next(row for row in exported.rows if row.case_id == unanswered.case_id)
    solved = next(row for row in exported.rows if row.case_id == answered.case_id)
    assert [message.kind for message in no_answer.messages] == ["question"]
    assert no_answer.requests[0].error_code == "MODEL_UNAVAILABLE"
    assert solved.current_resolution is not None
    assert solved.current_resolution.confirmed_by == "user"
    assert solved.messages[-1].structured_content is not None
    assert solved.messages[-1].author_id is None

    output = tmp_path / "export.json"
    write_export(output, exported)
    assert output.exists()
    assert build_export(database, app_commit="abc123", kb_snapshot_id=None).rows
