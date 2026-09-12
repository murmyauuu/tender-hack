"""A05 — real handoff-during-generation experiment.

1. Client A submits a real AI chat request against a slow (long-generation)
   heavy path.
2. While it is still generating, client A sends a second real chat message on
   the same case containing an explicit human-request phrase the real C01
   policy engine recognizes (`Соедините меня с оператором`), which supersedes
   the in-flight request and hands the case off.
3. Immediately after the handoff HTTP call returns, three more real AI
   requests are fired to prove the original heavy slot is STILL reserved
   (capacity math only reaches QUEUE_FULL once total reserved, including the
   still-computing original request, hits queue_capacity) — i.e. the slot is
   not released early just because the case was handed off.
4. The script then polls until the original request reaches a terminal status
   and records: final status, whether any AI answer message was added to the
   case after handoff, and the case status.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
import uuid
from pathlib import Path

import httpx


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    result: dict = {}

    client_a = httpx.Client(base_url=args.base_url, timeout=30.0)
    client_a.post("/api/v1/sessions").raise_for_status()

    t_submit = time.perf_counter()
    resp = client_a.post(
        "/api/v1/chat",
        json={"request_key": str(uuid.uuid4()), "text": "Как расторгнуть контракт?"},
    )
    resp.raise_for_status()
    accepted = resp.json()
    original_request_id = accepted["request_id"]
    case_id = accepted["case_id"]
    result["original_request_id"] = original_request_id
    result["case_id"] = case_id
    result["original_submit_status"] = resp.status_code

    status_transitions: list[dict] = []
    stop_watcher = threading.Event()

    def watch_status() -> None:
        watcher = httpx.Client(
            base_url=args.base_url, timeout=10.0, cookies=client_a.cookies
        )
        last_status = None
        while not stop_watcher.is_set():
            try:
                body = watcher.get(f"/api/v1/requests/{original_request_id}").json()
            except Exception:  # noqa: BLE001 - best-effort background watcher
                continue
            if body.get("status") != last_status:
                status_transitions.append(
                    {
                        "seconds_since_original_submit": round(
                            time.perf_counter() - t_submit, 4
                        ),
                        "status": body.get("status"),
                        "progress": body.get("progress"),
                        "error_code": (body.get("error") or {}).get("code"),
                    }
                )
                last_status = body.get("status")
            time.sleep(0.02)
        watcher.close()

    watcher_thread = threading.Thread(target=watch_status, daemon=True)
    watcher_thread.start()

    time.sleep(0.4)
    case_before = client_a.get(f"/api/v1/cases/{case_id}").json()
    version_before = case_before["case"]["case_version"]
    result["case_version_before_handoff"] = version_before
    result["case_status_before_handoff"] = case_before["case"]["status"]

    t_handoff_call = time.perf_counter()
    handoff_resp = client_a.post(
        "/api/v1/chat",
        json={
            "case_id": case_id,
            "expected_case_version": version_before,
            "request_key": str(uuid.uuid4()),
            "text": "Соедините меня с оператором",
        },
    )
    handoff_elapsed_ms = round((time.perf_counter() - t_handoff_call) * 1000, 3)
    result["handoff_chat_status"] = handoff_resp.status_code
    result["handoff_chat_elapsed_ms"] = handoff_elapsed_ms
    result["handoff_chat_body"] = handoff_resp.json()
    result["seconds_since_original_submit_at_handoff"] = round(
        time.perf_counter() - t_submit, 3
    )

    probe_results = []
    for i in range(4):
        c = httpx.Client(base_url=args.base_url, timeout=30.0)
        c.post("/api/v1/sessions").raise_for_status()
        r = c.post(
            "/api/v1/chat",
            json={"request_key": str(uuid.uuid4()), "text": f"Пробный вопрос {i}"},
        )
        probe_results.append(
            {"index": i, "status_code": r.status_code, "body": r.json()}
        )
        c.close()
    result["post_handoff_admission_probe"] = probe_results
    result["seconds_since_original_submit_after_probe"] = round(
        time.perf_counter() - t_submit, 3
    )

    # The queue is now saturated (original in-flight + 3 probes = capacity).
    # Re-probe admission repeatedly until it succeeds again, to find the real
    # wall-clock moment the original request's heavy slot is released — this
    # must line up with the generation delay, not with the (much earlier)
    # handoff/supersede moment recorded above.
    slot_release_probe = []
    release_poll_start = time.perf_counter()
    slot_released_at_seconds_since_submit = None
    while time.perf_counter() - release_poll_start < 15.0:
        c = httpx.Client(base_url=args.base_url, timeout=30.0)
        c.post("/api/v1/sessions").raise_for_status()
        r = c.post(
            "/api/v1/chat",
            json={"request_key": str(uuid.uuid4()), "text": "Пробный вопрос release"},
        )
        elapsed_since_submit = round(time.perf_counter() - t_submit, 3)
        slot_release_probe.append(
            {"status_code": r.status_code, "seconds_since_original_submit": elapsed_since_submit}
        )
        c.close()
        if r.status_code != 429:
            slot_released_at_seconds_since_submit = elapsed_since_submit
            break
        time.sleep(0.15)
    result["slot_release_probe"] = slot_release_probe
    result["slot_released_at_seconds_since_original_submit"] = (
        slot_released_at_seconds_since_submit
    )

    poll_start = time.perf_counter()
    final = None
    while time.perf_counter() - poll_start < 30.0:
        poll = client_a.get(f"/api/v1/requests/{original_request_id}")
        poll.raise_for_status()
        body = poll.json()
        if body["status"] in ("final", "error", "cancelled"):
            final = body
            break
        time.sleep(0.1)
    result["original_request_final"] = final
    result["seconds_from_submit_to_original_terminal"] = round(
        time.perf_counter() - t_submit, 3
    )
    stop_watcher.set()
    watcher_thread.join(timeout=2.0)
    result["status_transitions"] = status_transitions

    case_after = client_a.get(f"/api/v1/cases/{case_id}").json()
    result["case_after"] = case_after
    result["stale_ai_message_present"] = any(
        m.get("answer_origin") == "rag" for m in case_after["messages"]
    )

    client_a.close()
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
