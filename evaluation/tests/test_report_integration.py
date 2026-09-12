"""Integration tests D02: export JSON → проверки → метрики → Markdown-отчёт.

Проверяется детерминизм report-функций и AC20 (дубли case_id в экспорте).
"""

from __future__ import annotations

from evaluation.report.demo_export import build_demo_live_export
from evaluation.report.export_io import check_export, dumps_deterministic, load_export
from evaluation.report.metrics import compute_metrics
from evaluation.report.report import render_report


def test_check_export_ok_on_demo():
    export, _ = build_demo_live_export()
    assert check_export(export) == []


def test_check_export_detects_duplicate_case_ids():
    export, _ = build_demo_live_export()
    export.rows.append(export.rows[0])
    issues = check_export(export)
    assert any("duplicate case_id" in issue for issue in issues)


def test_json_roundtrip_keeps_metrics():
    export, _ = build_demo_live_export()
    payload = dumps_deterministic(export)
    import tempfile
    import pathlib

    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "export.json"
        path.write_text(payload, encoding="utf-8")
        reloaded = load_export(path)
    assert compute_metrics(reloaded) == compute_metrics(export)
    assert len(reloaded.rows) == len(export.rows) == 9


def test_render_report_contains_cohorts_and_mock_notice():
    export, _ = build_demo_live_export()
    md = render_report(export, generated="test (D02)", mock=True,
                       source_note="deterministic demo fixture")
    assert "## Cohort: `demo`" in md
    assert "## Cohort: `live`" in md
    assert "Auto-answer rate" in md
    assert "mock" in md
    assert "export_id" in md


def test_deterministic_json_bytes():
    e1 = dumps_deterministic(build_demo_live_export()[0])
    e2 = dumps_deterministic(build_demo_live_export()[0])
    assert e1 == e2


def test_no_secrets_in_artifacts():
    export, _ = build_demo_live_export()
    payload = dumps_deterministic(export)
    for token in ("TENDERHACK_REPLY_KEY", "Bearer ", "Authorization", "password", "API_KEY"):
        assert token not in payload