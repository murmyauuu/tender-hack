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
    HandoffInput,
    OperatorReplyInput,
    RequestView,
    Session,
    SourceRecord,
)
from tenderhack_contracts import ports


ROOT = Path(__file__).parents[1]


def test_contract_version_is_frozen_c0() -> None:
    assert CONTRACTS_VERSION == "2.0.0-c0"


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
    ],
)
def test_frozen_fixture_validates(fixture_name: str, model: type) -> None:
    payload = json.loads((ROOT / "contracts" / "fixtures" / fixture_name).read_text(encoding="utf-8"))
    TypeAdapter(model).validate_python(payload)


@pytest.mark.parametrize(
    "model",
    [Session, AcceptedRequest, RequestView, CaseView, HandoffInput, SourceRecord, FeedbackInput, OperatorReplyInput],
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


def test_knowledge_port_has_no_backend_dependency() -> None:
    source = inspect.getsource(ports)
    assert "tenderhack_backend" not in source
    assert "backend." not in source

