"""Two-phase real model-outage/recovery acceptance driver.

Run ``outage`` while the Ollama server is stopped, then start Ollama and run
``recovery`` with the same state file and unchanged backend process/database.
Both phases use the real HTTP API, session cookie, semantic retrieval and
persisted retry semantics.
"""

from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path

import httpx


TERMINAL = {"final", "error", "cancelled"}
QUESTION = "Как изменить банковские реквизиты организации на Портале поставщиков?"


def poll(client: httpx.Client, request_id: str, timeout_seconds: float = 180.0) -> dict:
    started = time.perf_counter()
    while time.perf_counter() - started < timeout_seconds:
        response = client.get(f"/api/v1/requests/{request_id}")
        response.raise_for_status()
        body = response.json()
        if body["status"] in TERMINAL:
            return body
        time.sleep(0.1)
    raise TimeoutError(f"request {request_id} did not finish in {timeout_seconds}s")


def client_for(base_url: str, session_id: str | None = None) -> httpx.Client:
    client = httpx.Client(base_url=base_url, timeout=180.0)
    if session_id is not None:
        client.cookies.set("tenderhack_session", session_id)
    return client


def run_outage(base_url: str, state_path: Path) -> dict:
    with client_for(base_url) as client:
        session_response = client.post("/api/v1/sessions")
        session_response.raise_for_status()
        session_id = session_response.json()["session_id"]
        accepted_response = client.post(
            "/api/v1/chat",
            json={"request_key": str(uuid.uuid4()), "text": QUESTION},
        )
        accepted_response.raise_for_status()
        accepted = accepted_response.json()
        failed = poll(client, accepted["request_id"])
        case = client.get(f"/api/v1/cases/{accepted['case_id']}").json()

    error = failed.get("error") or {}
    assert failed["status"] == "error", failed
    assert error.get("code") == "MODEL_UNAVAILABLE", failed
    assert error.get("retryable") is True, failed
    assert not any(message.get("answer_origin") == "rag" for message in case["messages"])

    state = {
        "base_url": base_url,
        "session_id": session_id,
        "case_id": accepted["case_id"],
        "original_request_id": accepted["request_id"],
        "original_user_message_id": accepted["user_message_id"],
        "case_version_after_failure": case["case"]["case_version"],
        "messages_after_failure": case["messages"],
        "outage_request": failed,
    }
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


def run_recovery(base_url: str, state_path: Path) -> dict:
    state = json.loads(state_path.read_text(encoding="utf-8-sig"))
    with client_for(base_url, state["session_id"]) as client:
        health = client.get("/api/v1/health")
        health.raise_for_status()
        accepted_response = client.post(
            "/api/v1/chat",
            json={
                "case_id": state["case_id"],
                "expected_case_version": state["case_version_after_failure"],
                "request_key": str(uuid.uuid4()),
                "retry_of": state["original_request_id"],
                "text": None,
            },
        )
        accepted_response.raise_for_status()
        accepted = accepted_response.json()
        completed = poll(client, accepted["request_id"])
        original = client.get(f"/api/v1/requests/{state['original_request_id']}").json()
        case = client.get(f"/api/v1/cases/{state['case_id']}").json()

    assert health.json()["status"] == "ready", health.json()
    assert accepted["request_id"] != state["original_request_id"]
    assert accepted["user_message_id"] == state["original_user_message_id"]
    assert original["status"] == "error" and original["error"]["code"] == "MODEL_UNAVAILABLE"
    assert completed["status"] == "final", completed
    rag_messages = [
        message for message in case["messages"] if message.get("answer_origin") == "rag"
    ]
    assert len(rag_messages) == 1, case
    assert sum(message["message_id"] == state["original_user_message_id"] for message in case["messages"]) == 1

    result = {
        **state,
        "health_after_recovery": health.json(),
        "retry_accepted": accepted,
        "retry_request": completed,
        "original_request_after_retry": original,
        "case_after_retry": case,
        "automatic_generation_retry_within_original_request": False,
    }
    state_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["outage", "recovery"])
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--state", required=True)
    args = parser.parse_args()

    state_path = Path(args.state)
    result = (
        run_outage(args.base_url, state_path)
        if args.phase == "outage"
        else run_recovery(args.base_url, state_path)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
