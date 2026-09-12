"""Загрузка и валидация EvaluationExport (канон C0 + проверки D02)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tenderhack_contracts import EvaluationExport


def load_export(path: str | Path) -> EvaluationExport:
    """Читает evaluation-export JSON и валидирует по контрактной модели C0."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return EvaluationExport.model_validate(data)


def check_export(export: EvaluationExport) -> list[str]:
    """Структурные проверки экспорта (AC20 и достоверность знаменателей).

    Возвращает список проблем; пустой список — экспорт согласован.
    """
    issues: list[str] = []
    rows = export.rows
    if not rows:
        issues.append("export has no rows")
    ids = [str(r.case_id) for r in rows]
    dupes = sorted({cid for cid in ids if ids.count(cid) > 1})
    if dupes:
        issues.append(f"duplicate case_id in export: {dupes}")

    for row in rows:
        msg_ids = {str(m.message_id) for m in row.messages}
        for fb in row.feedback:
            if str(fb.message_id) not in msg_ids:
                issues.append(
                    f"case {row.case_id}: feedback references unknown message {fb.message_id}"
                )
        if row.current_resolution is not None:
            if str(row.current_resolution.message_id) not in msg_ids:
                issues.append(
                    f"case {row.case_id}: current_resolution references message "
                    f"{row.current_resolution.message_id} not present in messages"
                )
        if row.ticket is not None and row.ticket.status in ("resolved", "closed_policy"):
            if row.current_resolution is None:
                issues.append(
                    f"case {row.case_id}: ticket {row.ticket.status} without current_resolution"
                )
    return issues


def export_to_dict(export: EvaluationExport) -> dict[str, Any]:
    return json.loads(export.model_dump_json())


def dumps_deterministic(export: EvaluationExport) -> str:
    """Канонический JSON (сортированные ключи, фикс. разделители) для сравнения."""
    data = export.model_dump(mode="json")

    def order(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: order(obj[k]) for k in sorted(obj)}
        if isinstance(obj, list):
            return [order(item) for item in obj]
        return obj

    return json.dumps(order(data), ensure_ascii=False, indent=2, separators=(",", ": "))