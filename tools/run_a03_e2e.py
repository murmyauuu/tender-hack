from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
from tenderhack_backend.app import create_app
from tenderhack_backend.config import Settings
from tenderhack_backend.export import build_export, write_export
from tenderhack_backend.runtime import build_runtime_service


def _counter(target: Any, name: str) -> int:
    return int(getattr(target, name, 0))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_flow(
    client: TestClient,
    service,
    *,
    question: str,
    app_commit: str,
    kb_snapshot_id: str,
    evidence_path: Path,
    export_path: Path,
    timeout_seconds: float = 180.0,
) -> dict[str, Any]:
    generator_before = _counter(service.generator, "calls")
    knowledge_before = _counter(service.knowledge, "retrieve_calls")
    encoder = getattr(service.knowledge, "encoder", None)
    embedding_before = _counter(encoder, "calls")

    session_response = client.post("/api/v1/sessions")
    session_response.raise_for_status()
    session = session_response.json()
    chat_response = client.post(
        "/api/v1/chat",
        json={"request_key": str(uuid4()), "text": question},
    )
    chat_response.raise_for_status()
    accepted = chat_response.json()

    deadline = time.monotonic() + timeout_seconds
    observed: list[dict[str, Any]] = [
        {"status": accepted["status"], "progress": "queued"}
    ]
    request_payload: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/requests/{accepted['request_id']}")
        response.raise_for_status()
        request_payload = response.json()
        state = {
            "status": request_payload["status"],
            "progress": request_payload.get("progress"),
        }
        if state != observed[-1]:
            observed.append(state)
        if request_payload["status"] in {"final", "error", "cancelled"}:
            break
        time.sleep(0.02)
    if request_payload is None or request_payload["status"] != "final":
        raise RuntimeError(
            f"A03 request did not finish successfully: {request_payload}"
        )

    case_response = client.get(f"/api/v1/cases/{accepted['case_id']}")
    case_response.raise_for_status()
    case = case_response.json()
    answers = [item for item in case["messages"] if item["kind"] == "answer"]
    if len(answers) != 1:
        raise RuntimeError(f"expected exactly one final answer, got {len(answers)}")
    answer = answers[0]

    sources = []
    for source_id in answer["source_ids"]:
        source_response = client.get(f"/api/v1/sources/{source_id}")
        source_response.raise_for_status()
        sources.append(source_response.json())

    feedback_response = client.post(
        "/api/v1/feedback",
        json={
            "message_id": answer["message_id"],
            "useful": True,
            "solved": True,
            "reason_codes": [],
        },
    )
    feedback_response.raise_for_status()
    feedback = feedback_response.json()

    exported = build_export(
        service.database,
        app_commit=app_commit,
        kb_snapshot_id=kb_snapshot_id,
    )
    write_export(export_path, exported)
    rows = [
        row for row in exported.rows if str(row.case_id) == str(accepted["case_id"])
    ]
    if len(rows) != 1:
        raise RuntimeError(f"expected one matching EvaluationRow, got {len(rows)}")

    result = {
        "question": question,
        "session_id": session["session_id"],
        "case_id": accepted["case_id"],
        "request_id": accepted["request_id"],
        "user_message_id": accepted["user_message_id"],
        "http": {
            "session_status": session_response.status_code,
            "chat_status": chat_response.status_code,
            "source_statuses": [200 for _ in sources],
            "feedback_status": feedback_response.status_code,
        },
        "observed_request_states": observed,
        "request": request_payload,
        "answer": answer,
        "sources": sources,
        "feedback": feedback,
        "generation_calls": _counter(service.generator, "calls") - generator_before,
        "retrieval_calls": _counter(service.knowledge, "retrieve_calls")
        - knowledge_before,
        "query_embedding_calls": _counter(encoder, "calls") - embedding_before,
        "export_path": str(export_path),
        "export_row": rows[0].model_dump(mode="json"),
    }
    _write_json(evidence_path, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run and retain the real A03 RAG E2E")
    parser.add_argument("--question", required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--export", dest="export_path", type=Path, required=True)
    parser.add_argument("--app-commit", required=True)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    settings = replace(
        Settings.from_env(),
        db_path=args.db,
        runtime_mode="real",
        is_demo=False,
        auto_worker=True,
    )
    service = build_runtime_service(settings)
    application = create_app(settings=settings, service=service)
    with TestClient(application) as client:
        health_response = client.get("/api/v1/health")
        health_response.raise_for_status()
        health = health_response.json()
        if health.get("knowledge") != "ready" or health.get("generator") != "ready":
            raise RuntimeError(f"real runtime is not ready: {health}")
        result = run_flow(
            client,
            service,
            question=args.question,
            app_commit=args.app_commit,
            kb_snapshot_id="kb-4918a97f0874d1e8",
            evidence_path=args.evidence,
            export_path=args.export_path,
            timeout_seconds=args.timeout,
        )
        result["health"] = health
        result["runtime_mode"] = "real"
        result["knowledge_health"] = asyncio.run(service.knowledge.health()).model_dump(
            mode="json"
        )
        _write_json(args.evidence, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
