from fastapi import FastAPI, HTTPException, status

from tenderhack_contracts import (
    CONTRACTS_VERSION,
    AcceptedRequest,
    CaseView,
    ChatInput,
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


app = FastAPI(
    title="TenderHack API",
    version=CONTRACTS_VERSION,
    description="Frozen C0 contract skeleton. Business behavior is implemented by later tasks.",
)


def _not_implemented() -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Contract frozen in A00; implementation belongs to a later task.",
    )


@app.post("/api/v1/sessions", response_model=Session, status_code=status.HTTP_201_CREATED)
async def create_session() -> Session:
    _not_implemented()


@app.post("/api/v1/chat", response_model=AcceptedRequest, status_code=status.HTTP_202_ACCEPTED)
async def accept_chat(payload: ChatInput) -> AcceptedRequest:
    del payload
    _not_implemented()


@app.get("/api/v1/requests/{request_id}", response_model=RequestView)
async def get_request(request_id: str) -> RequestView:
    del request_id
    _not_implemented()


@app.get("/api/v1/cases/{case_id}", response_model=CaseView)
async def get_case(case_id: str) -> CaseView:
    del case_id
    _not_implemented()


@app.post("/api/v1/cases/{case_id}/handoff", response_model=Ticket, status_code=status.HTTP_201_CREATED)
async def create_handoff(case_id: str, payload: HandoffInput) -> Ticket:
    del case_id, payload
    _not_implemented()


@app.get("/api/v1/sources/{source_id}", response_model=SourceRecord)
async def get_source(source_id: str) -> SourceRecord:
    del source_id
    _not_implemented()


@app.post("/api/v1/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def save_feedback(payload: FeedbackInput) -> FeedbackResponse:
    del payload
    _not_implemented()


@app.get("/api/v1/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="degraded",
        ready=True,
        storage="ready",
        knowledge="unavailable",
        generator="unavailable",
        contracts_version=CONTRACTS_VERSION,
    )


@app.post("/internal/tickets/{ticket_id}/reply", response_model=Message)
async def operator_reply(ticket_id: str, payload: OperatorReplyInput) -> Message:
    del ticket_id, payload
    _not_implemented()

