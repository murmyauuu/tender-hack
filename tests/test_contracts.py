import inspect
import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError
from tenderhack_contracts import (
    CONTRACTS_VERSION,
    AcceptedRequest,
    CaseView,
    ErrorEnvelope,
    EvaluationExport,
    FeedbackInput,
    GenerationAnswer,
    HandoffInput,
    Message,
    OperatorReplyInput,
    RequestView,
    Session,
    SourceRecord,
    ports,
)

ROOT = Path(__file__).parents[1]


def test_contract_version_includes_a02_extensions() -> None:
    assert CONTRACTS_VERSION == "2.1.0-a02"


@pytest.mark.parametrize(
    ("fixture_name", "model"),
    [
        ("answer.json", CaseView),
        ("clarify.json", CaseView),
        ("handoff_offered.json", CaseView),
        ("ticket.json", CaseView),
        ("operator.json", CaseView),
        ("policy.json", CaseView),
        ("error.json", ErrorEnvelope),
        ("stale.json", ErrorEnvelope),
        ("request_queued.json", RequestView),
        ("request_retrieving.json", RequestView),
        ("request_sources_found.json", RequestView),
        ("source.json", SourceRecord),
    ],
)
def test_frozen_fixture_validates(fixture_name: str, model: type) -> None:
    payload = json.loads(
        (ROOT / "contracts" / "fixtures" / fixture_name).read_text(encoding="utf-8")
    )
    TypeAdapter(model).validate_python(payload)


@pytest.mark.parametrize(
    "model",
    [
        Session,
        AcceptedRequest,
        RequestView,
        CaseView,
        HandoffInput,
        SourceRecord,
        FeedbackInput,
        OperatorReplyInput,
    ],
)
def test_http_contract_models_forbid_unknown_client_fields(model: type) -> None:
    schema = model.model_json_schema()
    assert schema.get("additionalProperties") is False


def test_public_chat_contract_cannot_accept_operator_author() -> None:
    from tenderhack_contracts import ChatInput

    with pytest.raises(ValidationError):
        ChatInput.model_validate(
            {
                "case_id": None,
                "expected_case_version": None,
                "request_key": "00000000-0000-4000-8000-000000000001",
                "text": "Как подписать контракт?",
                "retry_of": None,
                "author_id": "operator-1",
            }
        )


def test_evaluation_export_schema_keeps_cases_without_answers() -> None:
    schema = EvaluationExport.model_json_schema()
    row_schema = schema["$defs"]["EvaluationRow"]
    assert "rows" in schema["required"]
    assert "messages" in row_schema["required"]
    assert row_schema["properties"]["messages"]["type"] == "array"


def test_message_exposes_optional_structured_answer_content() -> None:
    schema = Message.model_json_schema()
    assert "structured_content" in schema["properties"]
    assert "structured_content" not in schema["required"]

    answer = json.loads(
        (ROOT / "contracts" / "fixtures" / "answer.json").read_text(encoding="utf-8")
    )
    structured = answer["messages"][-1]["structured_content"]
    assert structured == {
        "summary": "Тестовый ответ по инструкции.",
        "conditions": ["Действуйте от имени поставщика."],
        "steps": ["Откройте карточку контракта."],
    }


def test_feedback_contract_allows_partial_update_but_backend_decides_creation_rule() -> (
    None
):
    payload = FeedbackInput(
        message_id="55555555-5555-4555-8555-555555555555",
        comment="Дополнение к уже сохранённой оценке",
    )
    assert payload.comment is not None


def test_generation_answer_is_bounded() -> None:
    with pytest.raises(ValidationError):
        GenerationAnswer(summary="x" * 4001, source_ids=["source-demo"])
    with pytest.raises(ValidationError):
        GenerationAnswer(summary="ok", steps=["step"] * 21, source_ids=["source-demo"])


def test_chat_rejects_whitespace_only_question() -> None:
    from tenderhack_contracts import ChatInput

    with pytest.raises(ValidationError):
        ChatInput(request_key="00000000-0000-4000-8000-000000000001", text="   ")


def test_openapi_documents_b02_success_and_error_statuses() -> None:
    document = json.loads(
        (ROOT / "contracts" / "openapi" / "openapi.json").read_text(encoding="utf-8")
    )
    assert {"202", "401", "403", "404", "409", "422", "429", "503"}.issubset(
        document["paths"]["/api/v1/chat"]["post"]["responses"]
    )
    assert {"200", "201"}.issubset(
        document["paths"]["/api/v1/sessions"]["post"]["responses"]
    )
    assert {"200", "201"}.issubset(
        document["paths"]["/api/v1/feedback"]["post"]["responses"]
    )


def test_knowledge_port_has_no_backend_dependency() -> None:
    source = inspect.getsource(ports)
    assert "tenderhack_backend" not in source
    assert "backend." not in source
