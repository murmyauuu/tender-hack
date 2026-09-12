from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from uuid import UUID, uuid4


def send_operator_reply(
    *,
    base_url: str,
    ticket_id: UUID,
    expected_case_version: int,
    text_file: Path,
    next_status: str,
    environ: Mapping[str, str] = os.environ,
    opener: Callable[..., Any] = urlopen,
    request_key: UUID | None = None,
) -> dict[str, Any]:
    secret = environ.get("TENDERHACK_OPERATOR_REPLY_KEY")
    if not secret:
        raise RuntimeError("TENDERHACK_OPERATOR_REPLY_KEY is required")
    text = text_file.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("operator reply text file must not be blank")
    payload = {
        "request_key": str(request_key or uuid4()),
        "expected_case_version": expected_case_version,
        "text": text,
        "next_status": next_status,
    }
    request = Request(
        f"{base_url.rstrip('/')}/internal/tickets/{ticket_id}/reply",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with opener(request, timeout=30) as response:
        return json.loads(response.read())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send a protected TenderHack operator reply."
    )
    parser.add_argument("--ticket-id", type=UUID, required=True)
    parser.add_argument("--expected-case-version", type=int, required=True)
    parser.add_argument("--text-file", type=Path, required=True)
    parser.add_argument(
        "--next-status", choices=("waiting_user", "resolved"), required=True
    )
    parser.add_argument("--request-key", type=UUID)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = send_operator_reply(
        base_url=args.base_url,
        ticket_id=args.ticket_id,
        expected_case_version=args.expected_case_version,
        text_file=args.text_file,
        next_status=args.next_status,
        request_key=args.request_key,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
