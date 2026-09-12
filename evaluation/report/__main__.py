"""CLI report-функций D02.

Примеры:
  python -m evaluation.report var/evaluation/d02/demo_export.json --mock \
      --out var/evaluation/d02/report.md --json-out var/evaluation/d02/metrics.json
  python -m evaluation.report --demo \
      --out var/evaluation/d02/report_demo.md --json-out var/evaluation/d02/metrics_demo.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from evaluation.report.demo_export import build_demo_live_export
from evaluation.report.export_io import load_export
from evaluation.report.metrics import compute_metrics
from evaluation.report.report import render_metrics_json, render_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evaluation.report",
                                     description="D02 report functions: отчёт по одному EvaluationExport JSON")
    parser.add_argument("export_path", nargs="?", help="path to evaluation-export JSON")
    parser.add_argument("--demo", action="store_true", help="use deterministic mock demo export")
    parser.add_argument("--out", help="path to write Markdown report (default: stdout)")
    parser.add_argument("--json-out", help="path to write metrics JSON")
    parser.add_argument("--source", help="source note for the report block")
    parser.add_argument("--command", help="command used to produce data")
    parser.add_argument("--mock", action="store_true", help="mark report as fully mock/fixture")
    args = parser.parse_args(argv)

    if args.demo:
        export, meta = build_demo_live_export()
        mock = True
        source = args.source or "deterministic demo/live fixture (D02 demo_export)"
    else:
        if not args.export_path:
            parser.error("expected export_path (or --demo)")
        export = load_export(args.export_path)
        mock = args.mock
        source = args.source

    metrics_result = compute_metrics(export)
    report = render_report(
        export,
        generated="evaluation.report (D02)",
        source_note=source,
        mock=mock,
        command=args.command,
    )

    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(render_metrics_json(metrics_result) + "\n", encoding="utf-8")

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(report, encoding="utf-8")
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())