"""CLI runner-а D02.

Примеры:
  python -m evaluation.runner --driver fixture --out var/evaluation/d02/suite_fixture.json
  python -m evaluation.runner --driver http --base-url http://127.0.0.1:8000 \
      --out var/evaluation/d02/suite_http.json --reply-key-env TENDERHACK_REPLY_KEY
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from evaluation.runner.fixture_driver import FixtureDriver, state_summary
from evaluation.runner.http_driver import HttpDriver
from evaluation.runner.suite import run_full_scenario

log = logging.getLogger("evaluation.runner")


def build_driver(args: argparse.Namespace):
    if args.driver == "fixture":
        return FixtureDriver(base_time=args.now)
    if args.driver == "http":
        reply_key = None
        env_name = args.reply_key_env or "TENDERHACK_REPLY_KEY"
        if env_name in os.environ:
            reply_key = os.environ[env_name]
        return HttpDriver(args.base_url, reply_key=reply_key, timeout_s=args.timeout_s)
    raise SystemExit(f"unknown driver: {args.driver!r}")


async def amain(args: argparse.Namespace) -> int:
    driver = build_driver(args)
    try:
        report = await run_full_scenario(driver, poll_delay_s=args.poll_delay)
    finally:
        if isinstance(driver, HttpDriver):
            await driver.close()
    counts = report.counts()
    data = report.to_dict()
    data["summary"] = {
        "operations_total": counts["total"],
        "operations_ok": counts["ok"],
        "operations_error": counts["errors"],
        "operations_skipped": counts["skipped"],
        "states": state_summary(driver) if isinstance(driver, FixtureDriver) else "http",
        "not_run_reason": report.meta.get("not_run_reason"),
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data["summary"], ensure_ascii=False, indent=2))
    return 0 if counts["errors"] == 0 else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evaluation.runner", description="D02 runner (fixture/http)")
    parser.add_argument("--driver", choices=["fixture", "http"], default="fixture")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--reply-key-env", default="TENDERHACK_REPLY_KEY",
                        help="env name with the reply key; value is never logged")
    parser.add_argument("--timeout-s", type=float, default=20.0)
    parser.add_argument("--poll-delay", type=float, default=0.0, help="delay between polls, seconds")
    parser.add_argument("--out", default="var/evaluation/d02/suite.json",
                        help="path for suite trace JSON")
    parser.add_argument("--now", default="2026-09-12T09:00:00Z", help="fixture base time (ISO)")
    args = parser.parse_args(argv)
    return asyncio.run(amain(args))


if __name__ == "__main__":
    raise SystemExit(main())