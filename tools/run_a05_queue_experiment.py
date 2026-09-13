"""A05 real-client queue/concurrency/overflow/lightweight-path experiment.

Fires real concurrent HTTP requests (httpx, independent session cookies per
client — not mocked) at a harness server started by tools/a05_harness.py, and
records real measured timings for each: queue wait, retrieval, generation,
total, and outcome. Also fires lightweight (policy/feedback/read) requests
while the heavy queue is full to prove they do not wait behind it.

Usage (server must already be running, see docs/coordination/artem/A05-handoff.md
for the exact command used):

    uv run python3 -m tools.run_a05_queue_experiment --base-url http://127.0.0.1:8012 \
        --clients 5 --output var/a05/queue_experiment.json
"""

from __future__ import annotations

import argparse
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx


def new_client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=30.0)


def create_session(client: httpx.Client) -> None:
    r = client.post("/api/v1/sessions")
    r.raise_for_status()


def send_ai_chat(
    base_url: str, index: int, text: str, poll_timeout_seconds: float
) -> dict:
    client = new_client(base_url)
    create_session(client)
    request_key = str(uuid.uuid4())
    t0 = time.perf_counter()
    submit_wall = time.time()
    resp = client.post(
        "/api/v1/chat", json={"request_key": request_key, "text": text}
    )
    submit_elapsed_ms = round((time.perf_counter() - t0) * 1000, 3)
    result = {
        "client_index": index,
        "submit_wall_time": submit_wall,
        "submit_status_code": resp.status_code,
        "submit_elapsed_ms": submit_elapsed_ms,
    }
    if resp.status_code == 429:
        result["outcome"] = "QUEUE_FULL"
        result["error_envelope"] = resp.json()
        client.close()
        return result
    resp.raise_for_status()
    accepted = resp.json()
    request_id = accepted["request_id"]
    result["request_id"] = request_id
    result["case_id"] = accepted["case_id"]

    poll_start = time.perf_counter()
    final = None
    while time.perf_counter() - poll_start < poll_timeout_seconds:
        poll = client.get(f"/api/v1/requests/{request_id}")
        poll.raise_for_status()
        body = poll.json()
        if body["status"] in ("final", "error", "cancelled"):
            final = body
            break
        time.sleep(0.05)
    total_wall_ms = round((time.perf_counter() - t0) * 1000, 3)
    result["total_wall_ms"] = total_wall_ms
    result["final_status"] = final["status"] if final else "timeout"
    result["timings_ms"] = final["timings_ms"] if final else None
    result["error"] = final.get("error") if final else None
    if final and final["status"] == "final":
        case = client.get(f"/api/v1/cases/{accepted['case_id']}").json()
        result["case_status"] = case["case"]["status"]
        last_message = case["messages"][-1]
        result["outcome_kind"] = last_message["kind"]
        result["outcome_answer_origin"] = last_message.get("answer_origin")
    client.close()
    return result


def send_lightweight(base_url: str, kind: str) -> dict:
    client = new_client(base_url)
    create_session(client)
    t0 = time.perf_counter()
    if kind == "profanity":
        resp = client.post(
            "/api/v1/chat",
            json={"request_key": str(uuid.uuid4()), "text": "нах*й иди"},
        )
    elif kind == "read_health":
        resp = client.get("/api/v1/health")
    else:
        raise ValueError(kind)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 3)
    client.close()
    return {"kind": kind, "status_code": resp.status_code, "elapsed_ms": elapsed_ms}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--clients", type=int, default=5)
    parser.add_argument("--output", required=True)
    parser.add_argument("--poll-timeout-seconds", type=float, default=300.0)
    parser.add_argument(
        "--question",
        default="Как изменить банковские реквизиты организации на Портале поставщиков?",
    )
    args = parser.parse_args()

    heavy_texts = [args.question for _ in range(args.clients)]

    lightweight_before = [send_lightweight(args.base_url, "read_health")]

    with ThreadPoolExecutor(max_workers=args.clients + 2) as pool:
        heavy_futures = [
            pool.submit(
                send_ai_chat,
                args.base_url,
                i,
                heavy_texts[i],
                args.poll_timeout_seconds,
            )
            for i in range(args.clients)
        ]
        time.sleep(0.15)
        light_futures = [
            pool.submit(send_lightweight, args.base_url, "profanity"),
            pool.submit(send_lightweight, args.base_url, "read_health"),
        ]
        heavy_results = [f.result() for f in heavy_futures]
        light_results = [f.result() for f in light_futures]

    heavy_results.sort(key=lambda r: r["client_index"])

    output = {
        "clients_fired": args.clients,
        "heavy_results": heavy_results,
        "lightweight_results_during_heavy_load": light_results,
        "lightweight_before": lightweight_before,
        "resource_note": (
            "Backend RAM/VRAM must be sampled from the separate server process; "
            "the client driver does not report its own RSS as runtime evidence."
        ),
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
