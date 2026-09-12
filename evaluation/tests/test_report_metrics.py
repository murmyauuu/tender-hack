"""Tests: детерминированные report-метрики по EvaluationExport JSON.

Проверяются границы: no-answer, policy_closed, нулевой знаменатель → null,
dedup repeated feedback, перцентили (nearest-rank), ошибки/timeouts отдельно.
"""

from __future__ import annotations

import math

from evaluation.report.demo_export import build_demo_live_export
from evaluation.report.metrics import nearest_rank, compute_metrics


def _metrics():
    export, meta = build_demo_live_export()
    return export, compute_metrics(export), meta


def test_demo_metrics_match_expected():
    export, result, meta = _metrics()
    assert export.schema_version == "1.0"
    assert result["summary"]["total_cases"] == 9
    assert result["summary"]["eligible_cases"] == 8
    assert result["summary"]["policy_closed_cases"] == 1

    demo = result["cohorts"]["demo"]
    live = result["cohorts"]["live"]
    assert demo["cases"]["eligible"] == 6
    assert live["cases"]["eligible"] == 2

    expected = meta["expected"]
    pairs = [
        ("demo.auto_answer", demo["metrics"]["auto_answer"]["value"]),
        ("demo.confirmed_auto_resolution", demo["metrics"]["confirmed_auto_resolution"]["value"]),
        ("demo.usefulness_ai", demo["metrics"]["usefulness_ai"]["value"]),
        ("demo.usefulness_operator", demo["metrics"]["usefulness_operator"]["value"]),
        ("demo.solved_rate", demo["metrics"]["solved_rate"]["value"]),
        ("demo.feedback_coverage", demo["metrics"]["feedback_coverage"]["value"]),
        ("demo.handoffs", demo["metrics"]["handoffs"]["value"]),
        ("demo.no_answer", demo["metrics"]["no_answer"]["value"]),
        ("live.auto_answer", live["metrics"]["auto_answer"]["value"]),
        ("live.confirmed_auto_resolution", live["metrics"]["confirmed_auto_resolution"]["value"]),
        ("live.usefulness_ai", live["metrics"]["usefulness_ai"]["value"]),
        ("live.usefulness_operator", live["metrics"]["usefulness_operator"]["value"]),
        ("live.handoffs", live["metrics"]["handoffs"]["value"]),
        ("live.errors", live["metrics"]["errors"]["value"]),
        ("live.timeouts", live["metrics"]["timeouts"]["value"]),
    ]
    for key, actual in pairs:
        want = expected[key]
        if want is None:
            assert actual is None, f"{key}: expected null, got {actual}"
        else:
            assert actual is not None and math.isclose(actual, want, rel_tol=1e-9), \
                f"{key}: expected {want}, got {actual}"

    assert demo["timings"]["latency_total_p50_ms"] == 2850
    assert demo["timings"]["latency_total_p95_ms"] == 5400
    # latency_total считает все terminal requests (вкл. handoff без ответа): 4 answer + 1 handoff
    assert demo["timings"]["latency_total_n"] == 5
    assert demo["timings"]["answer_n"] == 4
    assert live["timings"]["latency_total_p50_ms"] == 60000
    assert live["timings"]["latency_total_p95_ms"] == 134000
    assert live["info"]["error_codes"] == {"MODEL_UNAVAILABLE": 1}
    assert live["info"]["timeout_requests"] == 1


def test_null_denominator_when_empty_eligible():
    export, _ = build_demo_live_export()
    empty_rows = [row for row in export.rows if row.cohort == "demo" and row.policy_closed]
    export.rows = empty_rows
    result = compute_metrics(export)
    cohort = result["cohorts"]["demo"]
    assert cohort["cases"]["eligible"] == 0
    assert cohort["metrics"]["auto_answer"]["value"] is None
    assert cohort["metrics"]["usefulness_ai"]["value"] is None
    assert cohort["metrics"]["handoffs"]["value"] is None
    assert cohort["timings"]["latency_total_p50_ms"] is None


def test_repeated_feedback_counts_once_and_latest_wins():
    export, _ = build_demo_live_export()
    # дважды признанного same-сообщения в демо-"confirmed": latest (solved=True) применяется один раз
    result = compute_metrics(export)
    demo = result["cohorts"]["demo"]
    # solved-rate учитывает одно сообщение (не два), n=3 (confirmed/solved_false/operator)
    assert demo["metrics"]["solved_rate"]["n"] == 3
    assert demo["metrics"]["solved_rate"]["k"] == 2


def test_percentiles_nearest_rank():
    assert nearest_rank([1, 2, 3, 4], 0.5) == 2
    assert nearest_rank([1, 2, 3, 4], 0.95) == 4
    assert nearest_rank([10], 0.5) == 10
    assert nearest_rank([], 0.5) is None
    assert nearest_rank( [860, 2400, 2850, 3100, 5400], 0.5 ) == 2850


def test_determinism_of_metrics():
    a = compute_metrics(build_demo_live_export()[0])
    b = compute_metrics(build_demo_live_export()[0])
    assert a == b