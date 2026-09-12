from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from knowledge.policy import build_policy
from tenderhack_backend.app import create_app
from tenderhack_backend.config import Settings
from tenderhack_backend.fakes import FakeGenerator, FakeKnowledge
from tenderhack_backend.service import BackendService
from tenderhack_backend.storage import Database
from tenderhack_contracts import ReasonCode, RoutingResult


def _state(view: dict) -> str:
    ticket = view["ticket"]
    return f"{view['case']['status']}/ticket:{ticket['status'] if ticket else 'none'}"


def run_smoke(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    database_path = output_dir / f"a04-{uuid4()}.sqlite"
    knowledge = FakeKnowledge()
    knowledge.result = knowledge.result.model_copy(
        update={
            "route": RoutingResult(
                topic_id="TH1",
                subtopic_id="ST01",
                support_line="L2",
                basis_source_ids=["portal:42:1"],
                reason_codes=[ReasonCode.NO_EVIDENCE],
            )
        }
    )
    generator = FakeGenerator()
    service = BackendService(
        Database(database_path), build_policy(), knowledge, generator
    )
    settings = Settings(
        db_path=database_path,
        allowed_origin="http://testserver",
        is_demo=True,
        auto_worker=False,
        runtime_mode="test",
        operator_reply_key="runtime-only-smoke-key",
        operator_author_id="operator-smoke",
    )
    app = create_app(settings=settings, service=service)
    origin = {"origin": "http://testserver"}
    auth = {"authorization": "Bearer runtime-only-smoke-key"}
    transitions: list[str] = []

    with TestClient(app) as client:
        client.post("/api/v1/sessions", headers=origin).raise_for_status()
        accepted_response = client.post(
            "/api/v1/chat",
            headers=origin,
            json={"request_key": str(uuid4()), "text": "Нужна помощь по закупке"},
        )
        accepted_response.raise_for_status()
        accepted = accepted_response.json()
        asyncio.run(service.process_next())
        offered = client.get(f"/api/v1/cases/{accepted['case_id']}").json()
        transitions.append(_state(offered))

        handoff_body = {
            "request_key": str(uuid4()),
            "expected_case_version": offered["case"]["case_version"],
        }
        first_handoff = client.post(
            f"/api/v1/cases/{accepted['case_id']}/handoff",
            headers=origin,
            json=handoff_body,
        )
        first_handoff.raise_for_status()
        repeated_handoff = client.post(
            f"/api/v1/cases/{accepted['case_id']}/handoff",
            headers=origin,
            json=handoff_body,
        )
        repeated_handoff.raise_for_status()
        ticket = first_handoff.json()
        handed_off = client.get(f"/api/v1/cases/{accepted['case_id']}").json()
        transitions.append(_state(handed_off))

        reply_body = {
            "request_key": str(uuid4()),
            "expected_case_version": handed_off["case"]["case_version"],
            "text": "Уточните номер закупки.",
            "next_status": "waiting_user",
        }
        missing_key = client.post(
            f"/internal/tickets/{ticket['ticket_id']}/reply", json=reply_body
        )
        forged = client.post(
            f"/internal/tickets/{ticket['ticket_id']}/reply",
            headers=auth,
            json={**reply_body, "author_id": "forged"},
        )
        first_reply = client.post(
            f"/internal/tickets/{ticket['ticket_id']}/reply",
            headers=auth,
            json=reply_body,
        )
        first_reply.raise_for_status()
        waiting = client.get(f"/api/v1/cases/{accepted['case_id']}").json()
        transitions.append(_state(waiting))

        retrieval_before = knowledge.retrieve_calls
        generation_before = generator.calls
        user_reply = client.post(
            "/api/v1/chat",
            headers=origin,
            json={
                "case_id": accepted["case_id"],
                "expected_case_version": waiting["case"]["case_version"],
                "request_key": str(uuid4()),
                "text": "Номер закупки 123.",
            },
        )
        user_reply.raise_for_status()
        after_user = client.get(f"/api/v1/cases/{accepted['case_id']}").json()
        transitions.append(_state(after_user))

        resolved_reply = client.post(
            f"/internal/tickets/{ticket['ticket_id']}/reply",
            headers=auth,
            json={
                "request_key": str(uuid4()),
                "expected_case_version": after_user["case"]["case_version"],
                "text": "Проблема решена.",
                "next_status": "resolved",
            },
        )
        resolved_reply.raise_for_status()
        resolved = client.get(f"/api/v1/cases/{accepted['case_id']}").json()
        transitions.append(_state(resolved))

        client.cookies.clear()
        client.post("/api/v1/sessions", headers=origin).raise_for_status()
        foreign_case = client.get(f"/api/v1/cases/{accepted['case_id']}")

    first_reply_json = first_reply.json()
    return {
        "classification": "real backend / controlled no-model dependencies",
        "case_id": accepted["case_id"],
        "ticket_id": ticket["ticket_id"],
        "database_path": str(database_path),
        "handoff": {
            "ticket_before_confirmation": offered["ticket"],
            "first_status_code": first_handoff.status_code,
            "repeat_status_code": repeated_handoff.status_code,
            "same_ticket": repeated_handoff.json()["ticket_id"] == ticket["ticket_id"],
        },
        "operator_reply": {
            "message_id": first_reply_json["message_id"],
            "missing_key_status": missing_key.status_code,
            "forged_fields_status": forged.status_code,
            "author_id": first_reply_json["author_id"],
            "responder_type": first_reply_json["responder_type"],
            "answer_origin": first_reply_json["answer_origin"],
        },
        "user_to_operator_reply": {
            "request_status": user_reply.json()["status"],
            "retrieval_delta": knowledge.retrieve_calls - retrieval_before,
            "generation_delta": generator.calls - generation_before,
        },
        "resolved_reply_message_id": resolved_reply.json()["message_id"],
        "transitions": transitions,
        "security": {"foreign_case_status": foreign_case.status_code},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local A04 backend smoke.")
    parser.add_argument("--output-dir", type=Path, default=Path("var/a04"))
    args = parser.parse_args()
    result = run_smoke(args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
