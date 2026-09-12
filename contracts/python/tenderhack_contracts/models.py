from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTRACTS_VERSION = "2.1.0-a02"
AnswerSection = Annotated[str, Field(min_length=1, max_length=2000)]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CaseStatus(StrEnum):
    OPEN = "open"
    AWAITING_CLARIFICATION = "awaiting_clarification"
    AWAITING_FEEDBACK = "awaiting_feedback"
    HANDOFF_OFFERED = "handoff_offered"
    HANDED_OFF = "handed_off"
    RESOLVED = "resolved"
    CLOSED_POLICY = "closed_policy"


class RequestStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    FINAL = "final"
    ERROR = "error"
    CANCELLED = "cancelled"


class RequestProgress(StrEnum):
    QUEUED = "queued"
    RETRIEVING = "retrieving"
    SOURCES_FOUND = "sources_found"
    GENERATING = "generating"


class TicketStatus(StrEnum):
    NEW = "new"
    WAITING_USER = "waiting_user"
    RESOLVED = "resolved"
    CLOSED_POLICY = "closed_policy"


class GateDecision(StrEnum):
    ANSWER_ALLOWED = "ANSWER_ALLOWED"
    CLARIFY = "CLARIFY"
    ESCALATE = "ESCALATE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class ReasonCode(StrEnum):
    NO_EVIDENCE = "NO_EVIDENCE"
    ROLE_REQUIRED = "ROLE_REQUIRED"
    ROLE_MISMATCH = "ROLE_MISMATCH"
    MISSING_ATTACHMENT = "MISSING_ATTACHMENT"
    KNOWN_CONFLICT = "KNOWN_CONFLICT"
    UNKNOWN_IDENTIFIER = "UNKNOWN_IDENTIFIER"
    UNSUPPORTED_OPERATION = "UNSUPPORTED_OPERATION"
    EXPLICIT_HUMAN_REQUEST = "EXPLICIT_HUMAN_REQUEST"
    UNRESOLVED_AFTER_STEPS = "UNRESOLVED_AFTER_STEPS"
    INVALID_GENERATION = "INVALID_GENERATION"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    SEARCH_UNAVAILABLE = "SEARCH_UNAVAILABLE"
    POLICY_LANGUAGE = "POLICY_LANGUAGE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class FeedbackReason(StrEnum):
    NOT_RELEVANT = "NOT_RELEVANT"
    UNCLEAR = "UNCLEAR"
    MISSING_INFORMATION = "MISSING_INFORMATION"
    POSSIBLY_OUTDATED = "POSSIBLY_OUTDATED"


class RoutingResult(ContractModel):
    topic_id: str | None = None
    subtopic_id: str | None = None
    support_line: Literal["L1", "L2", "L3"] | None = None
    recommended_recipient: str | None = None
    basis_source_ids: list[str] = Field(default_factory=list)
    rule_id: str | None = None
    is_probable_defect: bool = False
    is_ambiguous: bool = False
    reason_codes: list[ReasonCode] = Field(default_factory=list)


class Session(ContractModel):
    session_id: UUID
    created_at: datetime
    expires_at: datetime


class Case(ContractModel):
    case_id: UUID
    session_id: UUID
    status: CaseStatus
    case_version: int = Field(ge=0)
    active_request_id: UUID | None = None
    clarification_count: int = Field(ge=0, le=1)
    confirmed_facts: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict
    )
    topic_id: str | None = None
    subtopic_id: str | None = None
    route: RoutingResult | None = None
    is_demo: bool = False
    created_at: datetime
    updated_at: datetime


class StructuredAnswer(ContractModel):
    summary: str = Field(min_length=1, max_length=4000)
    conditions: list[AnswerSection] = Field(default_factory=list, max_length=20)
    steps: list[AnswerSection] = Field(default_factory=list, max_length=20)


class Message(ContractModel):
    message_id: UUID
    case_id: UUID
    seq: int = Field(ge=1)
    role: Literal["user", "assistant", "system"]
    kind: Literal["question", "answer", "clarification", "notice"]
    responder_type: Literal["ai", "operator", "system"] | None = None
    author_id: str | None = None
    answer_origin: Literal["rag", "card", "operator", "system"] | None = None
    content: str
    structured_content: StructuredAnswer | None = None
    source_ids: list[str] = Field(default_factory=list)
    created_at: datetime


class RequestError(ContractModel):
    code: str
    message: str
    retryable: bool


class CandidateSource(ContractModel):
    source_id: str
    title: str
    source_type: str
    version: str | None = None
    page_from: int | None = Field(default=None, ge=1)
    page_to: int | None = Field(default=None, ge=1)


class RequestView(ContractModel):
    request_id: UUID
    case_id: UUID
    status: RequestStatus
    progress: RequestProgress | None = None
    candidate_sources: list[CandidateSource] = Field(default_factory=list)
    result_message_ids: list[UUID] = Field(default_factory=list)
    error: RequestError | None = None
    timings_ms: dict[str, int | float | None] = Field(default_factory=dict)


class Ticket(ContractModel):
    ticket_id: UUID
    case_id: UUID
    status: TicketStatus
    route: RoutingResult | None = None
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    context_snapshot: dict[str, object] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    resolved_by: Literal["user", "operator"] | None = None


class CaseView(ContractModel):
    case: Case
    ticket: Ticket | None = None
    messages: list[Message] = Field(default_factory=list)
    limit_reached: bool = False


class ChatInput(ContractModel):
    case_id: UUID | None = None
    expected_case_version: int | None = Field(default=None, ge=0)
    request_key: UUID
    text: str | None = Field(default=None, min_length=1, max_length=6000)
    retry_of: UUID | None = None

    @model_validator(mode="after")
    def validate_operation_shape(self) -> ChatInput:
        if self.retry_of is None and self.text is None:
            raise ValueError("text is required for a new question")
        if self.text is not None and not self.text.strip():
            raise ValueError("text must not be blank")
        if self.retry_of is not None and self.text is not None:
            raise ValueError("retry requires text=null")
        if self.case_id is None and self.expected_case_version is not None:
            raise ValueError("new case requires expected_case_version=null")
        if self.case_id is not None and self.expected_case_version is None:
            raise ValueError("existing case requires expected_case_version")
        return self


class AcceptedRequest(ContractModel):
    request_id: UUID
    case_id: UUID
    user_message_id: UUID
    case_version: int = Field(ge=0)
    status: RequestStatus
    trace_id: str


class HandoffInput(ContractModel):
    request_key: UUID
    expected_case_version: int = Field(ge=0)


class FeedbackInput(ContractModel):
    message_id: UUID
    useful: bool | None = None
    solved: bool | None = None
    specialist_rating: int | None = Field(default=None, ge=1, le=5)
    reason_codes: list[FeedbackReason] = Field(default_factory=list, max_length=2)
    comment: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_a_rating(self) -> FeedbackInput:
        mutable = {"useful", "solved", "specialist_rating", "reason_codes", "comment"}
        if not self.model_fields_set.intersection(mutable):
            raise ValueError("at least one feedback field is required")
        return self


class FeedbackResponse(ContractModel):
    feedback_id: UUID
    message_id: UUID
    case_version: int = Field(ge=0)
    case_status: CaseStatus
    outcome_applied: bool
    outcome_reason: str | None = None


class OperatorReplyInput(ContractModel):
    request_key: UUID
    expected_case_version: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=6000)
    next_status: Literal["waiting_user", "resolved"]


class SourceRecord(ContractModel):
    source_id: str
    source_type: str
    title: str
    excerpt: str
    version: str | None = None
    source_date: datetime | None = None
    section_path: str | None = None
    page_from: int | None = Field(default=None, ge=1)
    page_to: int | None = Field(default=None, ge=1)
    url: str | None = None
    file_url: str | None = None
    conditions: list[str] = Field(default_factory=list)
    applicable_roles: list[str] = Field(default_factory=list)
    content_status: Literal["complete", "pointer", "incomplete"]


class HealthResponse(ContractModel):
    status: Literal["ready", "degraded"]
    ready: bool
    storage: Literal["ready", "unavailable"]
    knowledge: Literal["ready", "lexical_only", "unavailable"]
    generator: Literal["ready", "unavailable"]
    contracts_version: str


class ErrorDetail(ContractModel):
    code: str
    message: str
    retryable: bool
    trace_id: str
    current_case_version: int | None = Field(default=None, ge=0)


class ErrorEnvelope(ContractModel):
    error: ErrorDetail


class PolicyResult(ContractModel):
    profanity: bool
    explicit_human_request: bool
    matched_rule_ids: list[str] = Field(default_factory=list)


class MissingFact(ContractModel):
    key: str
    question: str


class EvidenceItem(ContractModel):
    evidence_id: str
    source_id: str
    original_ids: list[str] = Field(default_factory=list)
    parent_id: str | None = None
    source_type: str
    title: str
    version: str | None = None
    source_date: datetime | None = None
    section_path: str | None = None
    page_from: int | None = Field(default=None, ge=1)
    page_to: int | None = Field(default=None, ge=1)
    text: str
    conditions: list[str] = Field(default_factory=list)
    audience_raw: str | None = None
    applicable_roles: list[str] = Field(default_factory=list)
    role_verified: bool = False
    content_status: Literal["complete", "pointer", "incomplete"]
    eligibility_reason: str | None = None
    retrieval_method: Literal["dense", "exact", "fts"]
    score: float


class KnowledgeResult(ContractModel):
    snapshot_id: str | None = None
    candidates: list[EvidenceItem] = Field(default_factory=list)
    selected_evidence_ids: list[str] = Field(default_factory=list)
    decision: GateDecision
    missing_fact: MissingFact | None = None
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    card_id: str | None = None
    route: RoutingResult
    timings_ms: dict[str, int | float | None] = Field(default_factory=dict)


class QueryContext(ContractModel):
    text: str
    confirmed_facts: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict
    )
    recent_user_messages: list[str] = Field(default_factory=list)
    clarification_count: int = Field(ge=0, le=1)
    trace_id: str


class KnowledgeHealth(ContractModel):
    available: bool
    mode: Literal["semantic", "lexical_only", "unavailable"]
    snapshot_id: str | None = None
    reason: str | None = None


class GenerationInput(ContractModel):
    question: str
    confirmed_facts: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict
    )
    evidence: list[EvidenceItem] = Field(default_factory=list)
    allowed_source_ids: list[str] = Field(default_factory=list)


class GenerationAnswer(ContractModel):
    action: Literal["answer"] = "answer"
    summary: str = Field(min_length=1, max_length=4000)
    conditions: list[AnswerSection] = Field(default_factory=list, max_length=20)
    steps: list[AnswerSection] = Field(default_factory=list, max_length=20)
    source_ids: list[str] = Field(min_length=1)


class GenerationClarify(ContractModel):
    action: Literal["clarify"] = "clarify"
    missing_fact: str
    question: str


class GenerationEscalate(ContractModel):
    action: Literal["escalate"] = "escalate"
    reason_code: ReasonCode
    reason_text: str


GenerationProposal: TypeAlias = Annotated[
    GenerationAnswer | GenerationClarify | GenerationEscalate,
    Field(discriminator="action"),
]


class RequiredFact(ContractModel):
    key: str
    expected_value: str | int | float | bool | None


class ScenarioContent(ContractModel):
    summary: str
    conditions: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)


class ScenarioCard(ContractModel):
    card_id: str
    intent_id: str
    status: Literal["draft", "reviewed", "disabled"]
    title: str
    utterances: list[str] = Field(default_factory=list)
    applicable_roles: list[str] = Field(default_factory=list)
    required_facts: list[RequiredFact] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    content: ScenarioContent
    handoff_required: bool
    route: RoutingResult
    author_id: str
    reviewer_id: str | None = None
    reviewed_at: datetime | None = None
    snapshot_id: str | None = None


class ExportMessage(ContractModel):
    message_id: UUID
    seq: int = Field(ge=1)
    kind: Literal["question", "answer", "clarification", "notice"]
    responder_type: Literal["ai", "operator", "system"] | None = None
    author_id: str | None = None
    answer_origin: Literal["rag", "card", "operator", "system"] | None = None
    text: str
    structured_content: StructuredAnswer | None = None
    source_ids: list[str] = Field(default_factory=list)
    created_at: datetime


class ExportRequest(ContractModel):
    request_id: UUID
    user_message_id: UUID
    status: RequestStatus
    result_message_ids: list[UUID] = Field(default_factory=list)
    error_code: str | None = None
    timings_ms: dict[str, int | float | None] = Field(default_factory=dict)


class ExportFeedback(ContractModel):
    message_id: UUID
    useful: bool | None = None
    solved: bool | None = None
    specialist_rating: int | None = Field(default=None, ge=1, le=5)
    reason_codes: list[FeedbackReason] = Field(default_factory=list)
    comment: str | None = None
    updated_at: datetime


class ExportTicket(ContractModel):
    ticket_id: UUID
    status: TicketStatus
    created_at: datetime
    resolved_by: Literal["user", "operator"] | None = None


class CurrentResolution(ContractModel):
    message_id: UUID
    confirmed_by: Literal["user", "operator"]
    answer_origin: Literal["rag", "card", "operator"]
    confirmed_at: datetime


class EvaluationRow(ContractModel):
    case_id: UUID
    cohort: Literal["demo", "live"]
    created_at: datetime
    case_status: CaseStatus
    topic_id: str | None = None
    subtopic_id: str | None = None
    policy_closed: bool
    route: RoutingResult
    ticket: ExportTicket | None = None
    messages: list[ExportMessage]
    requests: list[ExportRequest]
    feedback: list[ExportFeedback]
    current_resolution: CurrentResolution | None = None


class EvaluationExport(ContractModel):
    schema_version: str
    export_id: UUID
    created_at: datetime
    as_of: datetime
    app_commit: str
    kb_snapshot_id: str | None = None
    rows: list[EvaluationRow]
