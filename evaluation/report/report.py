"""Markdown-отчёт по EvaluationExport + метрикам (детерминированный)."""

from __future__ import annotations

from typing import Any

from tenderhack_contracts import EvaluationExport
from evaluation.report.export_io import check_export
from evaluation.report.metrics import RATE_METRICS, compute_metrics, format_value

RATE_LABELS: dict[str, str] = {
    "auto_answer": "Auto-answer rate",
    "confirmed_auto_resolution": "Подтверждённое авторешение",
    "usefulness_ai": "Полезность (AI)",
    "usefulness_operator": "Полезность (operator)",
    "solved_rate": "solved-rate",
    "feedback_coverage": "Покрытие feedback",
    "handoffs": "Передачи (Ticket / N_eligible)",
    "no_answer": "Без ответа",
    "errors": "Ошибки (Case с error Request)",
    "timeouts": "Timeout (total ≥ лимита)",
}


def _percentage(value: float | None) -> str:
    if value is None:
        return "null"
    return f"{value * 100:.1f}%"


def render_report(
    export: EvaluationExport,
    *,
    generated: str,
    source_note: str | None = None,
    mock: bool = False,
    command: str | None = None,
) -> str:
    """Формирует Markdown-отчёт по одному EvaluationExport (D02 → D09/D07)."""
    issues = check_export(export)
    metrics_result = compute_metrics(export)

    lines: list[str] = []
    lines.append("# Отчёт оценки (D02 report functions)")
    lines.append("")
    lines.append(f"- **schema_version**: `{export.schema_version}`")
    lines.append(f"- **export_id**: `{export.export_id}`")
    lines.append(f"- **created_at**: `{export.created_at.isoformat()}`")
    lines.append(f"- **as_of**: `{export.as_of.isoformat()}`")
    lines.append(f"- **app_commit**: `{export.app_commit}`")
    lines.append(f"- **kb_snapshot_id**: `{export.kb_snapshot_id or 'null'}`")
    lines.append(f"- **generated**: `{generated}`")
    lines.append(f"- **mock**: `{str(mock).lower()}`")
    if command:
        lines.append(f"- **command**: `{command}`")
    if source_note:
        lines.append(f"- **source**: {source_note}")
    lines.append("")

    if mock:
        lines.append("> Полностью `mock`/fixture: эти числа не являются реальными "
                     "наблюдениями пользователей и не описывают качество модели.")
        lines.append("")

    summary = metrics_result["summary"]
    lines.append("## Сводка")
    lines.append("")
    lines.append(
        "| Показатель | Значение |\n"
        "|---|---|\n"
        f"| Cases всего | {summary['total_cases']} |\n"
        f"| N_eligible (без policy_closed) | {summary['eligible_cases']} |\n"
        f"| policy_closed | {summary['policy_closed_cases']} |\n"
    )
    lines.append("")

    for cohort_name, cohort in sorted(metrics_result["cohorts"].items()):
        lines.append(f"## Cohort: `{cohort_name}`")
        lines.append("")
        cases = cohort["cases"]
        lines.append(
            f"- Cases: {cases['total']}; policy_closed: {cases['policy_closed']}; "
            f"eligible: **{cases['eligible']}**."
        )
        lines.append("")
        lines.append("| Метрика | n | k | value |")
        lines.append("|---|---|---|---|")
        for name in RATE_METRICS:
            mv = cohort["metrics"][name]
            label = RATE_LABELS[name]
            lines.append(
                f"| {label} | {mv['n']} | {mv['k']} | {_percentage(mv['value'])} |"
            )
        lines.append("")

        info = cohort["info"]
        timings = cohort["timings"]
        lines.append("### Info")
        lines.append("")
        lines.append(
            "| Показатель | Значение |\n"
            "|---|---|\n"
            f"| handoff_offered (Ticket нет) | {info['handoff_offered_cases']} |\n"
            f"| error Requests | {info['error_requests']} |\n"
            f"| timeout Requests (total ≥ {info['TIMEOUT_TOTAL_MS']} ms) | {info['timeout_requests']} |\n"
            f"| error codes | {info['error_codes'] or '{}'} |\n"
            f"| dangling feedback cases | {info['dangling_feedback_cases']} |\n"
        )
        lines.append("")
        lines.append("### Latency (total ms, включая очередь)")
        lines.append("")
        lat = timings
        lines.append(
            "| Метрика | значение | n |\n"
            "|---|---|---|\n"
            f"| p50 (total) | {lat['latency_total_p50_ms'] or 'null'} | {lat['latency_total_n']} |\n"
            f"| p95 (total) | {lat['latency_total_p95_ms'] or 'null'} | {lat['latency_total_n']} |\n"
            f"| p50 (answer) | {lat['answer_p50_ms'] or 'null'} | {lat['answer_n']} |\n"
            f"| p95 (answer) | {lat['answer_p95_ms'] or 'null'} | {lat['answer_n']} |\n"
        )
        lines.append("")

    lines.append("## Валидация экспорта")
    lines.append("")
    if issues:
        for issue in issues:
            lines.append(f"- ⚠ {issue}")
        lines.append("")
        lines.append("> Проблемы выше требуют исправления данных до публикации отчёта.")
    else:
        lines.append("- экспорт согласован: уникальные case_id, корректные ссылки messages/feedback/resolution.")
    lines.append("")

    lines.append("## Примечания")
    lines.append("")
    lines.append("- Ratio-метрики: value=None при n=0 (пустая выборка не подставляется).")
    lines.append("- Cohort demo/live не смешиваются; фикстуры `mock` помечаются явно.")
    lines.append("- Автоответ ≠ решение; подтверждённое авторешение считается отдельно.")
    lines.append("- Сегменты отчёта: cmds/annotations из actual output, LLM/GPU не требуются.")
    lines.append("")
    return "\n".join(lines)


def render_metrics_json(metrics_result: dict[str, Any]) -> str:
    import json

    return json.dumps(metrics_result, ensure_ascii=False, indent=2, sort_keys=True)