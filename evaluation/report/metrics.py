"""Детерминированные метрики по EvaluationRow из одного EvaluationExport JSON.

Определения — спецификация v2.1 §13 (live/demo) и evaluation/README:
- N_eligible = все Cases − policy_closed; пустой знаменатель → value=None.
- Коhort (demo/live) рассчитываются раздельно и не смешиваются.
- Автоответ ≠ решение; подтверждённое авторешение — отдельная метрика.
- Полезность отдельно для AI и operator; solved — отдельный показатель.
- repeated feedback: по message_id берётся актуальная запись (max updated_at);
  переходы по solved применяются к Case однократно (без двойного счёта).
- errors/timeouts учитываются отдельно; latency — total incl. queue, p50/p95.

Расчёт воспроизводимый: сортировка по case_id, фиксированные правила, без LLM.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from tenderhack_contracts import (
    CaseStatus,
    EvaluationExport,
    EvaluationRow,
    ExportFeedback,
    ExportMessage,
)

TIMEOUT_TOTAL_MS = 120_000
RATE_METRICS = ("auto_answer", "confirmed_auto_resolution", "usefulness_ai",
                "usefulness_operator", "solved_rate", "feedback_coverage",
                "handoffs", "no_answer", "errors", "timeouts")


@dataclass
class MetricValue:
    name: str
    n: int
    k: int
    value: float | None = None
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "n": self.n, "k": self.k, "value": self.value, "note": self.note}


@dataclass
class CohortResult:
    cohort: str
    cases: dict[str, int] = field(default_factory=dict)
    metrics: dict[str, MetricValue] = field(default_factory=dict)
    info: dict[str, Any] = field(default_factory=dict)
    timings: dict[str, int | None] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cohort": self.cohort,
            "cases": self.cases,
            "metrics": {k: v.to_dict() for k, v in self.metrics.items()},
            "info": self.info,
            "timings": self.timings,
        }


def nearest_rank(sorted_values: list[int], quantile: float) -> int | None:
    if not sorted_values:
        return None
    index = max(0, math.ceil(quantile * len(sorted_values)) - 1)
    return sorted_values[index]


def latest_feedback_by_message(row: EvaluationRow) -> dict[str, ExportFeedback]:
    """Актуальные записи feedback на сообщение: max updated_at (равные — позже в списке)."""
    by_message: dict[str, ExportFeedback] = {}
    for fb in row.feedback:
        key = str(fb.message_id)
        prev = by_message.get(key)
        if prev is None or fb.updated_at > prev.updated_at:
            by_message[key] = fb
    return by_message


def classify_row(row: EvaluationRow) -> dict[str, Any]:
    """Признаки Case, из которых собираются метрики (детерминированные)."""
    messages = row.messages
    answers = [m for m in messages if m.kind == "answer"]
    has_answer = bool(answers)
    ai_answered = any(m.responder_type == "ai" for m in answers)
    operator_answered = any(m.responder_type == "operator" for m in answers)

    msgs_by_id = {str(m.message_id): m for m in messages}
    fb_by_message = latest_feedback_by_message(row)

    ai_uses = n1 = k1 = 0
    # usefulness_ai: useful not-null on AI answers
    op_uses = k2 = 0
    solved_seen = k3 = 0
    coverage_has_fb = False
    dangling_feedback = False
    for msg_id, fb in fb_by_message.items():
        msg = msgs_by_id.get(msg_id)
        if msg is None:
            dangling_feedback = True
            continue
        if msg.kind != "answer":
            continue
        coverage_has_fb = True
        if fb.useful is not None:
            if msg.responder_type == "ai":
                ai_uses += 1
                if fb.useful:
                    k1 += 1
            elif msg.responder_type == "operator":
                op_uses += 1
                if fb.useful:
                    k2 += 1
        if fb.solved is not None:
            solved_seen += 1
            if fb.solved:
                k3 += 1

    cr = row.current_resolution
    confirmed_auto = bool(
        ai_answered
        and cr is not None
        and cr.confirmed_by == "user"
        and cr.answer_origin in ("rag", "card")
        and not operator_answered
        and row.ticket is None
    )

    requests = row.requests
    errors = [req for req in requests if req.status.value == "error"]
    timeouts = [
        req for req in requests
        if req.status.value in ("final", "error")
        and isinstance(req.timings_ms.get("total"), (int, float))
        and float(req.timings_ms["total"]) >= TIMEOUT_TOTAL_MS
    ]
    error_codes = sorted({req.error_code or "UNKNOWN" for req in errors})

    final_totals = sorted(
        float(req.timings_ms["total"])
        for req in requests
        if req.status.value in ("final", "error")
        and isinstance(req.timings_ms.get("total"), (int, float))
    )
    answer_totals = sorted(
        float(req.timings_ms["total"])
        for req in requests
        if req.status.value == "final"
        and isinstance(req.timings_ms.get("total"), (int, float))
    )

    return {
        "has_answer": has_answer,
        "ai_answered": ai_answered,
        "operator_answered": operator_answered,
        "confirmed_auto": confirmed_auto,
        "has_ticket": row.ticket is not None,
        "no_answer": not has_answer,
        "has_error": bool(errors),
        "has_timeout": bool(timeouts),
        "must_handoff_offered": row.case_status == CaseStatus.HANDOFF_OFFERED,
        "ai_usefulness_n": ai_uses,
        "ai_usefulness_k": k1,
        "op_usefulness_n": op_uses,
        "op_usefulness_k": k2,
        "solved_n": solved_seen,
        "solved_k": k3,
        "coverage_has_fb": coverage_has_fb,
        "dangling_feedback": dangling_feedback,
        "error_codes": error_codes,
        "error_requests": len(errors),
        "timeout_requests": len(timeouts),
        "final_totals_ms": final_totals,
        "answer_totals_ms": answer_totals,
    }


def _rate(metric: str, cohort: CohortResult, n: int, k: int, value: float | None, note: str | None = None) -> None:
    cohort.metrics[metric] = MetricValue(name=metric, n=n, k=k, value=value, note=note)


def compute_cohort(cohort: str, rows: list[EvaluationRow]) -> CohortResult:
    result = CohortResult(cohort=cohort)
    rows = sorted(rows, key=lambda r: str(r.case_id))
    eligible: list[EvaluationRow] = []
    policy_closed = 0
    total = len(rows)
    agg = _Agg()

    for row in rows:
        flags = classify_row(row)
        if row.policy_closed:
            policy_closed += 1
            continue
        eligible.append(row)
        agg.n_auto += int(flags["ai_answered"])
        agg.n_confirmed += int(flags["confirmed_auto"])
        agg.ai_uses += flags["ai_usefulness_n"]
        agg.ai_k += flags["ai_usefulness_k"]
        agg.op_uses += flags["op_usefulness_n"]
        agg.op_k += flags["op_usefulness_k"]
        agg.solved_n += flags["solved_n"]
        agg.solved_k += flags["solved_k"]
        agg.handoffs += int(flags["has_ticket"])
        agg.handoff_offered += int(flags["must_handoff_offered"])
        agg.no_answer += int(flags["no_answer"])
        agg.errors += int(flags["has_error"])
        agg.timeouts += int(flags["has_timeout"])
        agg.error_requests += flags["error_requests"]
        agg.timeout_requests += flags["timeout_requests"]
        for code in flags["error_codes"]:
            agg.error_codes[code] = agg.error_codes.get(code, 0) + 1
        if flags["has_answer"]:
            agg.covered_den += 1
            if flags["coverage_has_fb"]:
                agg.coverage_num += 1
        agg.final_totals.extend(flags["final_totals_ms"])
        if flags["has_answer"]:
            agg.answer_totals.extend(flags["answer_totals_ms"])
        if flags["dangling_feedback"]:
            agg.dangling += 1

    result.cases = {
        "total": total,
        "policy_closed": policy_closed,
        "eligible": len(eligible),
    }

    n_eligible = len(eligible) or None
    _rate("auto_answer", result, n_eligible, agg.n_auto,
          _div(agg.n_auto, n_eligible))
    _rate("confirmed_auto_resolution", result, n_eligible, agg.n_confirmed,
          _div(agg.n_confirmed, n_eligible))
    _rate("usefulness_ai", result, agg.ai_uses, agg.ai_k,
          _div(agg.ai_k, agg.ai_uses or None))
    _rate("usefulness_operator", result, agg.op_uses, agg.op_k,
          _div(agg.op_k, agg.op_uses or None))
    _rate("solved_rate", result, agg.solved_n, agg.solved_k,
          _div(agg.solved_k, agg.solved_n or None))
    _rate("feedback_coverage", result, agg.covered_den, agg.coverage_num,
          _div(agg.coverage_num, agg.covered_den or None))
    _rate("handoffs", result, n_eligible, agg.handoffs,
          _div(agg.handoffs, n_eligible))
    _rate("no_answer", result, n_eligible, agg.no_answer,
          _div(agg.no_answer, n_eligible))
    _rate("errors", result, n_eligible, agg.errors,
          _div(agg.errors, n_eligible))
    _rate("timeouts", result, n_eligible, agg.timeouts,
          _div(agg.timeouts, n_eligible))

    result.info = {
        "handoff_offered_cases": agg.handoff_offered,
        "error_requests": agg.error_requests,
        "timeout_requests": agg.timeout_requests,
        "error_codes": {code: count for code, count in sorted(agg.error_codes.items())},
        "dangling_feedback_cases": agg.dangling,
        "TIMEOUT_TOTAL_MS": TIMEOUT_TOTAL_MS,
    }

    ft = sorted(agg.final_totals)
    at = sorted(agg.answer_totals)
    p50_all = nearest_rank(ft, 0.5)
    p95_all = nearest_rank(ft, 0.95)
    p50_ans = nearest_rank(at, 0.5)
    p95_ans = nearest_rank(at, 0.95)
    result.timings = {
        "latency_total_p50_ms": p50_all,
        "latency_total_p95_ms": p95_all,
        "latency_total_n": len(ft),
        "answer_p50_ms": p50_ans,
        "answer_p95_ms": p95_ans,
        "answer_n": len(at),
    }
    return result


class _Agg:
    """Агрегатор по eligible Case'ам выбранной cohort."""

    def __init__(self) -> None:
        self.n_auto = 0
        self.n_confirmed = 0
        self.ai_uses = 0
        self.ai_k = 0
        self.op_uses = 0
        self.op_k = 0
        self.solved_n = 0
        self.solved_k = 0
        self.handoffs = 0
        self.handoff_offered = 0
        self.no_answer = 0
        self.errors = 0
        self.timeouts = 0
        self.error_requests = 0
        self.timeout_requests = 0
        self.error_codes: dict[str, int] = {}
        self.covered_den = 0
        self.coverage_num = 0
        self.dangling = 0
        self.final_totals: list[float] = []
        self.answer_totals: list[float] = []


def _div(k: int, n: int | None) -> float | None:
    if not n:
        return None
    return k / n


def compute_metrics(export: EvaluationExport) -> dict[str, Any]:
    """Полный метрический вывод по всем cohort (детерминированный)."""
    by_cohort: dict[str, list[EvaluationRow]] = {}
    for row in export.rows:
        by_cohort.setdefault(row.cohort, []).append(row)

    cohorts: dict[str, CohortResult] = {}
    for cohort in sorted(by_cohort):
        cohorts[cohort] = compute_cohort(cohort, by_cohort[cohort])

    total_cases = len(export.rows)
    eligible = sum(c.cases["eligible"] for c in cohorts.values())
    policy_closed = sum(c.cases["policy_closed"] for c in cohorts.values())
    summary = {
        "total_cases": total_cases,
        "eligible_cases": eligible,
        "policy_closed_cases": policy_closed,
    }
    return {
        "schema_version": export.schema_version,
        "export_id": str(export.export_id),
        "as_of": export.as_of.isoformat(),
        "app_commit": export.app_commit,
        "kb_snapshot_id": export.kb_snapshot_id,
        "summary": summary,
        "cohorts": {name: c.to_dict() for name, c in sorted(cohorts.items())},
    }


def format_value(value: float | None, digits: int = 4) -> str:
    if value is None:
        return "null"
    return f"{value:.{digits}f}"