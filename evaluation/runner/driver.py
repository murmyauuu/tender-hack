"""Протокол драйвера runner-а (D02).

Драйвер выполняет HTTP-операции контракта v2.1 §7 без чтения app.sqlite:
данные приходят только из API (http_driver) или из frozen C0 fixtures
(fixture_driver). Runner-а обрабатывает ошибки сразу после operation
принимает операцию и возвращает ContractModel JSON payload.
"""

from __future__ import annotations

from typing import Any, Protocol

from evaluation.runner.records import DriverError, DriverResult


class RunnerDriver(Protocol):
    """Единый контракт операций системы для runner-а."""

    name: str
    mock: bool

    async def create_session(self) -> DriverResult:
        """POST /api/v1/sessions — новая или действующая Session (201/200)."""
        ...

    async def chat(
        self,
        *,
        case_id: str | None,
        expected_case_version: int | None,
        request_key: str,
        text: str | None,
        retry_of: str | None,
    ) -> DriverResult:
        """POST /api/v1/chat.

        Новый вопрос: case_id=None, expected_case_version=None, text непустой,
        retry_of=None. Retry: text=None, retry_of=Request ID (ChatInput v2.1 §7).
        """
        ...

    async def poll_request(self, request_id: str) -> DriverResult:
        """GET /api/v1/requests/{id} — текущий snapshot RequestView."""
        ...

    async def get_case(self, case_id: str) -> DriverResult:
        """GET /api/v1/cases/{id} — CaseView."""
        ...

    async def get_source(self, source_id: str) -> DriverResult:
        """GET /api/v1/sources/{id} — карточка источника."""
        ...

    async def post_feedback(
        self,
        *,
        message_id: str,
        useful: bool | None = None,
        solved: bool | None = None,
        specialist_rating: int | None = None,
        reason_codes: list[str] | None = None,
        comment: str | None = None,
    ) -> DriverResult:
        """POST /api/v1/feedback — FeedbackResponse."""
        ...

    async def handoff(
        self,
        *,
        case_id: str,
        request_key: str,
        expected_case_version: int,
    ) -> DriverResult:
        """POST /api/v1/cases/{id}/handoff — Ticket (201/200)."""
        ...

    async def operator_reply(
        self,
        *,
        ticket_id: str,
        request_key: str,
        expected_case_version: int,
        text: str,
        next_status: str,
    ) -> DriverResult:
        """POST /internal/tickets/{id}/reply — operator Message (Bearer)."""
        ...

    async def health(self) -> DriverResult:
        """GET /api/v1/health."""
        ...


async def poll_until_terminal(
    driver: RunnerDriver,
    request_id: str,
    *,
    max_attempts: int = 40,
    delay_s: float = 0.0,
) -> tuple[DriverResult, list[str]]:
    """Поллинг до terminal статуса (final/error/cancelled).

    Fixture-драйверы детерминированно продвигают стадию на каждый вызов.
    timeout после max_attempts → DriverError(POLL_TIMEOUT, retryable=True).
    """
    terminal = {"final", "error", "cancelled"}
    seen: list[str] = []
    for _ in range(max_attempts):
        result = await driver.poll_request(request_id)
        last = result
        status = str(result.payload.get("status", ""))
        seen.append(status)
        if status in terminal:
            return result, seen
        if delay_s > 0:
            import asyncio

            await asyncio.sleep(delay_s)
    if last is None:
        raise DriverError("POLL_TIMEOUT", f"request {request_id}: no response", retryable=True)
    raise DriverError(
        "POLL_TIMEOUT",
        f"request {request_id}: not terminal after {max_attempts} polls (last status {seen[-1]!r})",
        retryable=True,
    )


def require_payload(result: DriverResult, field_path: str) -> Any:
    """Достаёт поле из payload по dot-path; отсутствие — ValueError."""
    node: Any = result.payload
    for part in field_path.split("."):
        node = node.get(part)
        if node is None:
            raise KeyError(f"missing field {field_path!r} in driver payload")
    return node