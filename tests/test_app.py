import json
from pathlib import Path

from fastapi.testclient import TestClient
from tenderhack_backend.app import app, create_app
from tenderhack_backend.config import Settings

ROOT = Path(__file__).parents[1]


def test_health_is_runnable_without_models_or_kb(tmp_path: Path) -> None:
    application = create_app(
        settings=Settings(
            db_path=tmp_path / "app.sqlite",
            knowledge_dir=tmp_path / "missing-kb",
            ollama_url="http://127.0.0.1:1",
        )
    )
    response = TestClient(application).get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "ready": True,
        "storage": "ready",
        "knowledge": "unavailable",
        "generator": "unavailable",
        "contracts_version": "2.1.0-a02",
    }


def test_openapi_contains_exactly_nine_required_operations() -> None:
    required = {
        ("post", "/api/v1/sessions"),
        ("post", "/api/v1/chat"),
        ("get", "/api/v1/requests/{request_id}"),
        ("get", "/api/v1/cases/{case_id}"),
        ("post", "/api/v1/cases/{case_id}/handoff"),
        ("get", "/api/v1/sources/{source_id}"),
        ("post", "/api/v1/feedback"),
        ("get", "/api/v1/health"),
        ("post", "/internal/tickets/{ticket_id}/reply"),
    }
    actual = {
        (method, path)
        for path, methods in app.openapi()["paths"].items()
        for method in methods
        if method in {"get", "post", "put", "patch", "delete"}
    }
    assert actual == required


def test_generated_openapi_matches_runtime() -> None:
    generated = json.loads(
        (ROOT / "contracts" / "openapi" / "openapi.json").read_text(encoding="utf-8")
    )
    assert generated == app.openapi()


def test_generated_export_schema_matches_model() -> None:
    from tenderhack_contracts import EvaluationExport

    generated = json.loads(
        (ROOT / "contracts" / "schemas" / "evaluation-export.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert generated == EvaluationExport.model_json_schema()
