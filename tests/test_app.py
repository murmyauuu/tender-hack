import json
import sqlite3
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from tenderhack_backend.app import app, create_app
from tenderhack_backend.config import Settings
from tenderhack_backend.fakes import FakeGenerator, FakeKnowledge, FakePolicy
from tenderhack_backend.service import BackendService
from tenderhack_backend.storage import Database

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


def test_locked_storage_returns_honest_error_not_generic_500(tmp_path: Path) -> None:
    """A05: real sqlite lock contention must surface as a contract-shaped,
    retryable STORAGE_UNAVAILABLE error, not FastAPI's bare 500 fallback."""

    db_path = tmp_path / "app.sqlite"
    database = Database(db_path)
    service = BackendService(
        database,
        policy=FakePolicy(),
        knowledge=FakeKnowledge(),
        generator=FakeGenerator(),
    )
    application = create_app(
        settings=Settings(db_path=db_path, auto_worker=False), service=service
    )
    client = TestClient(application)
    session = client.post("/api/v1/sessions").json()
    client.cookies.set("tenderhack_session", session["session_id"])

    locker = sqlite3.connect(db_path, timeout=1)
    locker.execute("BEGIN EXCLUSIVE")
    try:
        response = client.post(
            "/api/v1/chat",
            json={"request_key": str(uuid4()), "text": "Тест хранилища"},
        )
    finally:
        locker.commit()
        locker.close()

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "STORAGE_UNAVAILABLE"
    assert body["error"]["retryable"] is True


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
