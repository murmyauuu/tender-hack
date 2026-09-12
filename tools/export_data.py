from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from tenderhack_backend.export import build_export, write_export
from tenderhack_backend.storage import Database


def _git_commit() -> str:
    configured = os.getenv("TENDERHACK_APP_COMMIT")
    if configured:
        return configured
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, encoding="utf-8"
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export one EvaluationRow per TenderHack Case"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(os.getenv("TENDERHACK_DB_PATH", "var/app.sqlite")),
    )
    parser.add_argument("--app-commit", default=None)
    parser.add_argument(
        "--kb-snapshot-id", default=os.getenv("TENDERHACK_KB_SNAPSHOT_ID")
    )
    args = parser.parse_args()
    exported = build_export(
        Database(args.db),
        app_commit=args.app_commit or _git_commit(),
        kb_snapshot_id=args.kb_snapshot_id,
    )
    write_export(args.output, exported)
    print(f"exported rows={len(exported.rows)} output={args.output}")


if __name__ == "__main__":
    main()
