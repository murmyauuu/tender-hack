"""Типы runner-а: записи операций, ошибки драйверов, результаты.

Детерминированный runner собирает `OperationRecord` на каждую операцию
(session / chat / poll request / case / source / feedback / handoff / reply /
retry / new case) и возвращает SuiteReport — трассу, пригодную для артефакта.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class DriverError(Exception):
    """Ошибка операции в контрактном Envelope-формате (v2.1 §7)."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        trace_id: str | None = None,
        http_status: int | None = None,
        current_case_version: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.trace_id = trace_id
        self.http_status = http_status
        self.current_case_version = current_case_version

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
        }
        if self.trace_id is not None:
            payload["trace_id"] = self.trace_id
        if self.http_status is not None:
            payload["http_status"] = self.http_status
        if self.current_case_version is not None:
            payload["current_case_version"] = self.current_case_version
        return payload


@dataclass
class DriverResult:
    """Ответ драйвера. mock=True маркирует fixture-провайдера (требование AGENTS)."""

    payload: dict[str, Any]
    mock: bool = False
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class OperationRecord:
    operation: str
    outcome: str = "ok"  # ok | error | skipped
    mock: bool = False
    input: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    elapsed_ms: int | None = None
    attempts: int = 1
    statuses_seen: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "operation": self.operation,
            "outcome": self.outcome,
            "mock": self.mock,
            "input": self.input,
            "elapsed_ms": self.elapsed_ms,
            "attempts": self.attempts,
        }
        if self.output is not None:
            rec["output"] = self.output
        if self.error is not None:
            rec["error"] = self.error
        if self.statuses_seen:
            rec["statuses_seen"] = self.statuses_seen
        if self.notes:
            rec["notes"] = self.notes
        return rec


@dataclass
class SuiteReport:
    driver: str
    scenario: str
    started_at: str
    mock: bool
    operations: list[OperationRecord] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def counts(self) -> dict[str, int]:
        total = len(self.operations)
        ok = sum(1 for op in self.operations if op.outcome == "ok")
        errors = sum(1 for op in self.operations if op.outcome == "error")
        skipped = sum(1 for op in self.operations if op.outcome == "skipped")
        return {"total": total, "ok": ok, "errors": errors, "skipped": skipped}

    def add(self, record: OperationRecord) -> None:
        self.operations.append(record)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "tenderhack.d02_suite_trace/v1",
            "driver": self.driver,
            "scenario": self.scenario,
            "started_at": self.started_at,
            "mock": self.mock,
            "summary": self.counts(),
            "meta": self.meta,
            "operations": [op.to_dict() for op in self.operations],
        }

    def write(self, path: str | Any) -> None:
        import json
        from pathlib import Path

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )