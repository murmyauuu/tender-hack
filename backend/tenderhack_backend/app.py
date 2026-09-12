from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from tenderhack_contracts import (
    CONTRACTS_VERSION,
    AcceptedRequest,
    CaseView,
    ChatInput,
    ErrorDetail,
    ErrorEnvelope,
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

from .config import Settings
from .errors import DomainError
from .generator import OllamaGenerator
from .service import BackendService
from .storage import Database

COOKIE_NAME = "tenderhack_session"


def _error_responses(*codes: int) -> dict[int, dict[str, object]]:
    return {code: {"model": ErrorEnvelope} for code in codes}


def _default_service(settings: Settings) -> BackendService:
    from knowledge.kb.store import open_store
    from knowledge.policy import build_policy

    return BackendService(
        Database(settings.db_path),
        policy=build_policy(),
        knowledge=open_store(),
        generator=OllamaGenerator(base_url=settings.ollama_url),
    )


def create_app(
    *, settings: Settings | None = None, service: BackendService | None = None
) -> FastAPI:
    settings = settings or Settings.from_env()
    service = service or _default_service(settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        service.database.recover_interrupted_requests()
        worker = (
            asyncio.create_task(service.worker_loop()) if settings.auto_worker else None
        )
        application.state.service = service
        try:
            yield
        finally:
            await service.stop_worker(worker)

    application = FastAPI(
        title="TenderHack API",
        version=CONTRACTS_VERSION,
        description="A02 durable backend core; C03 retrieval is dependency-injected in A03.",
        lifespan=lifespan,
    )
    application.state.service = service

    def error_response(error: DomainError, trace_id: str | None = None) -> JSONResponse:
        envelope = ErrorEnvelope(
            error=ErrorDetail(
                code=error.code,
                message=error.message,
                retryable=error.retryable,
                trace_id=trace_id or f"trace-{uuid4()}",
                current_case_version=error.current_case_version,
            )
        )
        return JSONResponse(
            status_code=error.status_code, content=envelope.model_dump(mode="json")
        )

    @application.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        del request
        return error_response(exc)

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        del request
        return error_response(
            DomainError("VALIDATION_ERROR", str(exc), status_code=422)
        )

    def check_origin(request: Request) -> None:
        origin = request.headers.get("origin")
        if origin is not None and origin != settings.allowed_origin:
            raise DomainError(
                "ORIGIN_FORBIDDEN", "Недопустимый Origin", status_code=403
            )

    def require_session(request: Request) -> UUID:
        raw = request.cookies.get(COOKIE_NAME)
        try:
            if raw is None:
                raise ValueError
            return UUID(raw)
        except (ValueError, TypeError):
            raise DomainError(
                "UNAUTHORIZED", "Требуется сессия", status_code=401
            ) from None

    @application.post(
        "/api/v1/sessions",
        response_model=Session,
        status_code=status.HTTP_201_CREATED,
        responses={200: {"model": Session}, **_error_responses(403, 503)},
    )
    async def create_session(request: Request, response: Response) -> Session:
        check_origin(request)
        raw = request.cookies.get(COOKIE_NAME)
        try:
            existing_id = UUID(raw) if raw else None
        except ValueError:
            existing_id = None
        session, created = service.create_session(existing_id)
        response.status_code = (
            status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )
        response.set_cookie(
            COOKIE_NAME,
            str(session.session_id),
            max_age=30 * 24 * 60 * 60,
            httponly=True,
            samesite="strict",
            secure=settings.cookie_secure,
            path="/",
        )
        return session

    @application.post(
        "/api/v1/chat",
        response_model=AcceptedRequest,
        status_code=status.HTTP_202_ACCEPTED,
        responses=_error_responses(401, 403, 404, 409, 422, 429, 503),
    )
    async def accept_chat(request: Request, payload: ChatInput) -> AcceptedRequest:
        check_origin(request)
        return await service.accept_chat(
            require_session(request), payload, is_demo=settings.is_demo
        )

    @application.get(
        "/api/v1/requests/{request_id}",
        response_model=RequestView,
        responses=_error_responses(401, 404),
    )
    async def get_request(request: Request, request_id: UUID) -> RequestView:
        return service.get_request(require_session(request), request_id)

    @application.get(
        "/api/v1/cases/{case_id}",
        response_model=CaseView,
        responses=_error_responses(401, 404),
    )
    async def get_case(request: Request, case_id: UUID) -> CaseView:
        return service.get_case(require_session(request), case_id)

    @application.post(
        "/api/v1/cases/{case_id}/handoff",
        response_model=Ticket,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_handoff(
        request: Request, case_id: UUID, payload: HandoffInput
    ) -> Ticket:
        del case_id, payload
        check_origin(request)
        require_session(request)
        raise DomainError(
            "NOT_IMPLEMENTED", "Handoff реализуется в A04", status_code=501
        )

    @application.get(
        "/api/v1/sources/{source_id}",
        response_model=SourceRecord,
        responses=_error_responses(404),
    )
    async def get_source(source_id: str) -> SourceRecord:
        source = await service.get_source(source_id)
        if source is None:
            raise DomainError("NOT_FOUND", "Ресурс не найден", status_code=404)
        return source

    @application.post(
        "/api/v1/feedback",
        response_model=FeedbackResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            200: {"model": FeedbackResponse},
            **_error_responses(401, 403, 404, 422),
        },
    )
    async def save_feedback(
        request: Request, response: Response, payload: FeedbackInput
    ) -> FeedbackResponse:
        check_origin(request)
        saved, created = service.save_feedback_with_status(
            require_session(request), payload
        )
        response.status_code = (
            status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )
        return saved

    @application.get("/api/v1/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        knowledge = await service.knowledge.health()
        knowledge_status = "ready" if knowledge.mode == "semantic" else knowledge.mode
        return HealthResponse(
            status="ready" if knowledge_status == "ready" else "degraded",
            ready=True,
            storage="ready",
            knowledge=knowledge_status,
            generator="unavailable",
            contracts_version=CONTRACTS_VERSION,
        )

    @application.post("/internal/tickets/{ticket_id}/reply", response_model=Message)
    async def operator_reply(ticket_id: UUID, payload: OperatorReplyInput) -> Message:
        del ticket_id, payload
        raise DomainError(
            "NOT_IMPLEMENTED", "Operator reply реализуется в A04", status_code=501
        )

    return application


app = create_app()
