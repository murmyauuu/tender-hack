"""HttpDriver — реальный API-driver (A02) поверх HTTP-контракта v2.1 §7.

Runner-а не читает app.sqlite: данные приходят только через HTTP. Используется
для real API smoke, когда A02/бэкенд готов; при неготовности операций A02
health работает, а операции возвращают 501 → DriverError NOT_IMPLEMENTED,
и suite помечает прогон как not run / не blocker (см. D02-handoff).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from tenderhack_contracts import (
    AcceptedRequest,
    CaseView,
    FeedbackInput,
    FeedbackResponse,
    HandoffInput,
    HealthResponse,
    Message,
    OperatorReplyInput,
    RequestView,
    Session,
    SourceRecord,
    Ticket,
)
from evaluation.runner.records import DriverError, DriverResult

log = logging.getLogger(__name__)

EXPECTED_CHAT_KEY = "TENDERHACK_REPLY_KEY"


class HttpDriver:
    """Гоняет runner-а по действующему API-эндоинту без доступа к таблицам."""

    name = "http"
    mock = False

    def __init__(
        self,
        base_url: str,
        *,
        reply_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        timeout_s: float = 20.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_s), follow_redirects=True, base_url=self.base_url
        )
        self._owns_client = client is None
        self._reply_key = reply_key

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @staticmethod
    def _raise_from_response(response: httpx.Response) -> None:
        try:
            body = response.json()
            envelope = body.get("error")
        except Exception:
            envelope = None
        if isinstance(envelope, dict):
            raise DriverError(
                code=str(envelope.get("code", "HTTP_ERROR")),
                message=str(envelope.get("message", response.text or "")),
                retryable=bool(envelope.get("retryable", False)),
                trace_id=envelope.get("trace_id"),
                current_case_version=envelope.get("current_case_version"),
                http_status=response.status_code,
            )
        raise DriverError(
            code="HTTP_ERROR",
            message=f"unexpected HTTP {response.status_code}",
            retryable=response.status_code >= 500,
            http_status=response.status_code,
        )

    async def _request(
        self, method: str, path: str, *, json: dict[str, Any] | None = None, bearer: bool = False
    ) -> httpx.Response:
        headers: dict[str, str] = {}
        if bearer:
            if not self._reply_key:
                raise DriverError(
                    code="CONFIG_ERROR",
                    message=f"{EXPECTED_CHAT_KEY} env var is required for operator reply (value never logged)",
                    retryable=False,
                )
            headers["Authorization"] = f"Bearer {self._reply_key}"
        try:
            response = await self._client.request(
                method, self.base_url + path, json=json, headers=headers
            )
        except httpx.TimeoutException as exc:
            raise DriverError("TIMEOUT", f"request {method} {path} timed out", retryable=True)
        except httpx.TransportError as exc:
            raise DriverError("CONNECTION_ERROR", f"{type(exc).__name__}: {exc}", retryable=True)
        if response.status_code in (201, 200, 202):
            return response
        self._raise_from_response(response)
        raise AssertionError("unreachable")

    async def health(self) -> DriverResult:
        response = await self._request("GET", "/api/v1/health")
        return DriverResult(HealthResponse.model_validate(response.json()).model_dump(mode="json"))

    async def create_session(self) -> DriverResult:
        response = await self._request("POST", "/api/v1/sessions", json={})
        assert response.status_code in (201, 200)
        return DriverResult(Session.model_validate(response.json()).model_dump(mode="json"))

    async def chat(
        self,
        *,
        case_id: str | None,
        expected_case_version: int | None,
        request_key: str,
        text: str | None,
        retry_of: str | None,
    ) -> DriverResult:
        body: dict[str, Any] = {
            "case_id": case_id,
            "expected_case_version": expected_case_version,
            "request_key": request_key,
            "text": text,
            "retry_of": retry_of,
        }
        response = await self._request("POST", "/api/v1/chat", json=body)
        assert response.status_code == 202
        return DriverResult(AcceptedRequest.model_validate(response.json()).model_dump(mode="json"))

    async def poll_request(self, request_id: str) -> DriverResult:
        response = await self._request("GET", f"/api/v1/requests/{request_id}")
        return DriverResult(RequestView.model_validate(response.json()).model_dump(mode="json"))

    async def get_case(self, case_id: str) -> DriverResult:
        response = await self._request("GET", f"/api/v1/cases/{case_id}")
        return DriverResult(CaseView.model_validate(response.json()).model_dump(mode="json"))

    async def get_source(self, source_id: str) -> DriverResult:
        response = await self._request("GET", f"/api/v1/sources/{source_id}")
        return DriverResult(SourceRecord.model_validate(response.json()).model_dump(mode="json"))

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
        body_input = FeedbackInput.model_validate(
            {
                "message_id": message_id,
                "useful": useful,
                "solved": solved,
                "specialist_rating": specialist_rating,
                "reason_codes": reason_codes or [],
                "comment": comment,
            }
        )
        response = await self._request("POST", "/api/v1/feedback", json=body_input.model_dump(mode="json"))
        assert response.status_code in (201, 200)
        return DriverResult(FeedbackResponse.model_validate(response.json()).model_dump(mode="json"))

    async def handoff(
        self, *, case_id: str, request_key: str, expected_case_version: int
    ) -> DriverResult:
        body_input = HandoffInput.model_validate(
            {"request_key": request_key, "expected_case_version": expected_case_version}
        )
        response = await self._request(
            "POST", f"/api/v1/cases/{case_id}/handoff", json=body_input.model_dump(mode="json")
        )
        assert response.status_code in (201, 200)
        return DriverResult(Ticket.model_validate(response.json()).model_dump(mode="json"))

    async def operator_reply(
        self,
        *,
        ticket_id: str,
        request_key: str,
        expected_case_version: int,
        text: str,
        next_status: str,
    ) -> DriverResult:
        body_input = OperatorReplyInput.model_validate(
            {
                "request_key": request_key,
                "expected_case_version": expected_case_version,
                "text": text,
                "next_status": next_status,
            }
        )
        response = await self._request(
            "POST",
            f"/internal/tickets/{ticket_id}/reply",
            json=body_input.model_dump(mode="json"),
            bearer=True,
        )
        return DriverResult(Message.model_validate(response.json()).model_dump(mode="json"))