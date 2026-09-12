"""Black-box HTTP checks used by the B03 real-browser handoff verification.

The probe uses only the accepted public API plus one unauthenticated security check against the
protected operator route. It never opens the service database or imports backend internals.
"""

from __future__ import annotations

import json
import time
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener
from uuid import uuid4


BASE_URL = "http://127.0.0.1:8000"
ORIGIN = "http://127.0.0.1:5173"
opener = build_opener(HTTPCookieProcessor(CookieJar()))


def call(method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        BASE_URL + path,
        data=body,
        method=method,
        headers={"Content-Type": "application/json", "Origin": ORIGIN},
    )
    try:
        with opener.open(request, timeout=10) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def finish(request_id: str) -> dict:
    for _ in range(100):
        status, result = call("GET", f"/api/v1/requests/{request_id}")
        assert status == 200, result
        if result["status"] in {"final", "error", "cancelled"}:
            return result
        time.sleep(0.05)
    raise TimeoutError(request_id)


def new_case(text: str) -> tuple[dict, dict]:
    status, accepted = call("POST", "/api/v1/chat", {
        "case_id": None,
        "expected_case_version": None,
        "request_key": str(uuid4()),
        "text": text,
        "retry_of": None,
    })
    assert status == 202, accepted
    finish(accepted["request_id"])
    status, view = call("GET", f"/api/v1/cases/{accepted['case_id']}")
    assert status == 200, view
    return accepted, view


def main() -> None:
    status, _ = call("POST", "/api/v1/sessions")
    assert status in {200, 201}

    _, offered = new_case("HTTP probe unknown operation")
    assert offered["case"]["status"] == "handoff_offered"
    assert offered["ticket"] is None
    handoff_body = {
        "request_key": str(uuid4()),
        "expected_case_version": offered["case"]["case_version"],
    }
    first_status, first_ticket = call(
        "POST", f"/api/v1/cases/{offered['case']['case_id']}/handoff", handoff_body,
    )
    second_status, second_ticket = call(
        "POST", f"/api/v1/cases/{offered['case']['case_id']}/handoff", handoff_body,
    )
    assert first_status == 201 and second_status == 200
    assert first_ticket["ticket_id"] == second_ticket["ticket_id"]

    stale_status, stale_body = call("POST", "/api/v1/chat", {
        "case_id": offered["case"]["case_id"],
        "expected_case_version": offered["case"]["case_version"],
        "request_key": str(uuid4()),
        "text": "Этот ввод не должен быть принят вслепую",
        "retry_of": None,
    })
    assert stale_status == 409
    reread_status, reread = call("GET", f"/api/v1/cases/{offered['case']['case_id']}")
    assert reread_status == 200
    assert all(message["content"] != "Этот ввод не должен быть принят вслепую" for message in reread["messages"])

    forged_status, _ = call("POST", "/api/v1/chat", {
        "case_id": offered["case"]["case_id"],
        "expected_case_version": reread["case"]["case_version"],
        "request_key": str(uuid4()),
        "text": "forged",
        "retry_of": None,
        "author_id": "browser-forge",
        "responder_type": "operator",
        "answer_origin": "operator",
    })
    assert forged_status == 422

    _, ai_case = new_case("Нужен AI ответ для HTTP probe")
    ai_answer = next(message for message in ai_case["messages"] if message["kind"] == "answer")
    rating_status, _ = call("POST", "/api/v1/feedback", {
        "message_id": ai_answer["message_id"],
        "specialist_rating": 5,
        "reason_codes": [],
    })
    assert rating_status == 422

    missing_key_status, _ = call(
        "POST", f"/internal/tickets/{first_ticket['ticket_id']}/reply", {
            "request_key": str(uuid4()),
            "expected_case_version": reread["case"]["case_version"],
            "text": "unauthorized",
            "next_status": "waiting_user",
        },
    )
    assert missing_key_status == 401

    slow_status, slow = call("POST", "/api/v1/chat", {
        "case_id": None,
        "expected_case_version": None,
        "request_key": str(uuid4()),
        "text": "Медленный AI ответ для отмены",
        "retry_of": None,
    })
    assert slow_status == 202
    policy_status, policy = call("POST", "/api/v1/chat", {
        "case_id": slow["case_id"],
        "expected_case_version": slow["case_version"],
        "request_key": str(uuid4()),
        "text": "блять",
        "retry_of": None,
    })
    assert policy_status == 202
    policy_request = finish(policy["request_id"])
    slow_request = finish(slow["request_id"])
    _, policy_case = call("GET", f"/api/v1/cases/{slow['case_id']}")
    assert policy_case["case"]["status"] == "closed_policy"
    assert slow_request["status"] == "cancelled"
    assert policy_request["timings_ms"]["retrieval"] is None
    assert policy_request["timings_ms"]["generation_total"] is None

    print(json.dumps({
        "offered_case_id": offered["case"]["case_id"],
        "ticket_id": first_ticket["ticket_id"],
        "ticket_before_confirmation": offered["ticket"],
        "handoff_statuses": [first_status, second_status],
        "same_ticket": first_ticket["ticket_id"] == second_ticket["ticket_id"],
        "stale_status": stale_status,
        "stale_current_case_version": stale_body["error"]["current_case_version"],
        "stale_input_was_written": False,
        "forged_public_fields_status": forged_status,
        "ai_specialist_rating_status": rating_status,
        "operator_route_missing_key_status": missing_key_status,
        "active_request_after_policy": slow_request["status"],
        "policy_case_status": policy_case["case"]["status"],
        "policy_retrieval_ms": policy_request["timings_ms"]["retrieval"],
        "policy_generation_ms": policy_request["timings_ms"]["generation_total"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
