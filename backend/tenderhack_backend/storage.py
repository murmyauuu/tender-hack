from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from tenderhack_contracts import (
    AcceptedRequest,
    CandidateSource,
    Case,
    CaseStatus,
    CaseView,
    ChatInput,
    FeedbackInput,
    FeedbackResponse,
    Message,
    RequestError,
    RequestStatus,
    RequestView,
    RoutingResult,
    Session,
    Ticket,
)

from .errors import DomainError, not_found

TIMING_KEYS = (
    "queue",
    "retrieval",
    "generation_total",
    "time_to_first_source",
    "total",
    "prompt_eval",
    "decode",
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def hash_payload(payload: Any) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    @contextmanager
    def transaction(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cases (
                    case_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id),
                    status TEXT NOT NULL,
                    case_version INTEGER NOT NULL,
                    active_request_id TEXT,
                    clarification_count INTEGER NOT NULL DEFAULT 0,
                    confirmed_facts_json TEXT NOT NULL DEFAULT '{}',
                    topic_id TEXT,
                    subtopic_id TEXT,
                    route_json TEXT,
                    is_demo INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL REFERENCES cases(case_id),
                    seq INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    responder_type TEXT,
                    author_id TEXT,
                    answer_origin TEXT,
                    content TEXT NOT NULL,
                    structured_content_json TEXT,
                    source_ids_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    UNIQUE(case_id, seq)
                );
                CREATE TABLE IF NOT EXISTS requests (
                    request_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL REFERENCES cases(case_id),
                    user_message_id TEXT NOT NULL REFERENCES messages(message_id),
                    accepted_case_version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    progress TEXT,
                    candidate_sources_json TEXT NOT NULL DEFAULT '[]',
                    result_message_ids_json TEXT NOT NULL DEFAULT '[]',
                    error_code TEXT,
                    error_message TEXT,
                    error_retryable INTEGER,
                    trace_id TEXT NOT NULL,
                    timings_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    finished_at TEXT
                );
                CREATE TABLE IF NOT EXISTS tickets (
                    ticket_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL UNIQUE REFERENCES cases(case_id),
                    status TEXT NOT NULL,
                    route_json TEXT,
                    reason_codes_json TEXT NOT NULL DEFAULT '[]',
                    missing_information_json TEXT NOT NULL DEFAULT '[]',
                    context_snapshot_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    resolved_by TEXT
                );
                CREATE TABLE IF NOT EXISTS feedback (
                    feedback_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id),
                    message_id TEXT NOT NULL REFERENCES messages(message_id),
                    useful INTEGER,
                    solved INTEGER,
                    specialist_rating INTEGER,
                    reason_codes_json TEXT NOT NULL DEFAULT '[]',
                    comment TEXT,
                    updated_at TEXT NOT NULL,
                    UNIQUE(session_id, message_id)
                );
                CREATE TABLE IF NOT EXISTS receipts (
                    actor_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    request_key TEXT NOT NULL,
                    body_hash TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(actor_id, operation, request_key)
                );
                CREATE INDEX IF NOT EXISTS idx_cases_session ON cases(session_id);
                CREATE INDEX IF NOT EXISTS idx_requests_case ON requests(case_id);
                CREATE INDEX IF NOT EXISTS idx_messages_case_seq ON messages(case_id, seq);
                """
            )

    def get_or_create_session(self, session_id: UUID | None) -> tuple[Session, bool]:
        now = utc_now()
        with self.transaction(immediate=True) as connection:
            if session_id is not None:
                row = connection.execute(
                    "SELECT * FROM sessions WHERE session_id = ? AND expires_at > ?",
                    (str(session_id), now.isoformat()),
                ).fetchone()
                if row is not None:
                    return Session.model_validate(dict(row)), False
            created = Session(
                session_id=uuid4(),
                created_at=now,
                expires_at=now + timedelta(days=30),
            )
            connection.execute(
                "INSERT INTO sessions VALUES (?, ?, ?)",
                (
                    str(created.session_id),
                    created.created_at.isoformat(),
                    created.expires_at.isoformat(),
                ),
            )
            return created, True

    def get_receipt(
        self, session_id: UUID, payload: ChatInput
    ) -> AcceptedRequest | None:
        body_hash = hash_payload(payload.model_dump(mode="json"))
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT body_hash, response_json FROM receipts WHERE actor_id=? AND operation='chat' AND request_key=?",
                (str(session_id), str(payload.request_key)),
            ).fetchone()
        if row is None:
            return None
        if row["body_hash"] != body_hash:
            raise DomainError(
                "IDEMPOTENCY_CONFLICT",
                "Ключ запроса уже использован с другим телом",
                status_code=409,
            )
        return AcceptedRequest.model_validate_json(row["response_json"])

    def accept_chat(
        self,
        session_id: UUID,
        payload: ChatInput,
        *,
        is_demo: bool,
        supersede_active: bool = False,
    ) -> tuple[AcceptedRequest, bool]:
        now = utc_now()
        body_hash = hash_payload(payload.model_dump(mode="json"))
        with self.transaction(immediate=True) as connection:
            session = connection.execute(
                "SELECT 1 FROM sessions WHERE session_id=? AND expires_at>?",
                (str(session_id), now.isoformat()),
            ).fetchone()
            if session is None:
                raise DomainError(
                    "UNAUTHORIZED", "Требуется действующая сессия", status_code=401
                )
            receipt = connection.execute(
                "SELECT body_hash, response_json FROM receipts WHERE actor_id=? AND operation='chat' AND request_key=?",
                (str(session_id), str(payload.request_key)),
            ).fetchone()
            if receipt is not None:
                if receipt["body_hash"] != body_hash:
                    raise DomainError(
                        "IDEMPOTENCY_CONFLICT",
                        "Ключ запроса уже использован с другим телом",
                        status_code=409,
                    )
                return AcceptedRequest.model_validate_json(
                    receipt["response_json"]
                ), False

            request_id = uuid4()
            trace_id = f"trace-{uuid4()}"
            if payload.case_id is None:
                case_id = uuid4()
                case_version = 1
                user_message_id = uuid4()
                connection.execute(
                    """INSERT INTO cases
                    (case_id,session_id,status,case_version,active_request_id,clarification_count,
                     confirmed_facts_json,topic_id,subtopic_id,route_json,is_demo,created_at,updated_at)
                    VALUES (?,?,?,?,?,0,'{}',NULL,NULL,NULL,?,?,?)""",
                    (
                        str(case_id),
                        str(session_id),
                        CaseStatus.OPEN.value,
                        case_version,
                        str(request_id),
                        int(is_demo),
                        now.isoformat(),
                        now.isoformat(),
                    ),
                )
                connection.execute(
                    """INSERT INTO messages
                    (message_id,case_id,seq,role,kind,content,source_ids_json,created_at)
                    VALUES (?,?,1,'user','question',?,'[]',?)""",
                    (str(user_message_id), str(case_id), payload.text, now.isoformat()),
                )
            else:
                case_id = payload.case_id
                case = connection.execute(
                    "SELECT * FROM cases WHERE case_id=? AND session_id=?",
                    (str(case_id), str(session_id)),
                ).fetchone()
                if case is None:
                    raise not_found()
                current_version = int(case["case_version"])
                if payload.expected_case_version != current_version:
                    raise DomainError(
                        "STALE_CASE_VERSION",
                        "Состояние обращения изменилось",
                        status_code=409,
                        current_case_version=current_version,
                    )
                if case["status"] in (
                    CaseStatus.RESOLVED.value,
                    CaseStatus.CLOSED_POLICY.value,
                ):
                    raise DomainError(
                        "CASE_CLOSED", "Обращение закрыто", status_code=409
                    )
                if case["active_request_id"] is not None:
                    if not supersede_active:
                        raise DomainError(
                            "CASE_BUSY", "Обращение уже обрабатывается", status_code=409
                        )
                    connection.execute(
                        """UPDATE requests SET status='cancelled',progress=NULL,
                        error_code='SUPERSEDED_BY_POLICY',error_message='Запрос отменён новым policy-событием',
                        error_retryable=0,finished_at=? WHERE request_id=?""",
                        (now.isoformat(), case["active_request_id"]),
                    )
                    current_version += 1
                    connection.execute(
                        "UPDATE cases SET active_request_id=NULL,case_version=?,updated_at=? WHERE case_id=?",
                        (current_version, now.isoformat(), str(case_id)),
                    )
                if connection.execute(
                    "SELECT 1 FROM tickets WHERE case_id=?", (str(case_id),)
                ).fetchone():
                    raise DomainError(
                        "INVALID_TRANSITION",
                        "Обращение передано специалисту",
                        status_code=409,
                    )

                if payload.retry_of is not None:
                    previous = connection.execute(
                        "SELECT * FROM requests WHERE request_id=? AND case_id=?",
                        (str(payload.retry_of), str(case_id)),
                    ).fetchone()
                    if previous is None or previous["status"] not in (
                        RequestStatus.ERROR.value,
                        RequestStatus.CANCELLED.value,
                    ):
                        raise DomainError(
                            "INVALID_TRANSITION",
                            "Этот запрос нельзя повторить",
                            status_code=409,
                        )
                    user_message_id = UUID(previous["user_message_id"])
                    later = connection.execute(
                        """SELECT 1 FROM messages current_message
                        JOIN messages later ON later.case_id=current_message.case_id
                        WHERE current_message.message_id=? AND later.role='user' AND later.seq>current_message.seq""",
                        (str(user_message_id),),
                    ).fetchone()
                    if later:
                        raise DomainError(
                            "INVALID_TRANSITION",
                            "После запроса уже есть новый вопрос",
                            status_code=409,
                        )
                else:
                    message_count = connection.execute(
                        "SELECT COUNT(*) FROM messages WHERE case_id=?", (str(case_id),)
                    ).fetchone()[0]
                    if message_count >= 98:
                        raise DomainError(
                            "CASE_CLOSED", "Начните новую тему", status_code=409
                        )
                    user_message_id = uuid4()
                    connection.execute(
                        """INSERT INTO messages
                        (message_id,case_id,seq,role,kind,content,source_ids_json,created_at)
                        VALUES (?,?,?,'user','question',?,'[]',?)""",
                        (
                            str(user_message_id),
                            str(case_id),
                            message_count + 1,
                            payload.text,
                            now.isoformat(),
                        ),
                    )
                case_version = current_version + 1
                connection.execute(
                    "UPDATE cases SET status=?,case_version=?,active_request_id=?,updated_at=? WHERE case_id=?",
                    (
                        CaseStatus.OPEN.value,
                        case_version,
                        str(request_id),
                        now.isoformat(),
                        str(case_id),
                    ),
                )

            accepted = AcceptedRequest(
                request_id=request_id,
                case_id=case_id,
                user_message_id=user_message_id,
                case_version=case_version,
                status=RequestStatus.QUEUED,
                trace_id=trace_id,
            )
            connection.execute(
                """INSERT INTO requests
                (request_id,case_id,user_message_id,accepted_case_version,status,progress,trace_id,
                 timings_json,created_at)
                VALUES (?,?,?,?,?,'queued',?,?,?)""",
                (
                    str(request_id),
                    str(case_id),
                    str(user_message_id),
                    case_version,
                    RequestStatus.QUEUED.value,
                    trace_id,
                    json.dumps({key: None for key in TIMING_KEYS}),
                    now.isoformat(),
                ),
            )
            connection.execute(
                "INSERT INTO receipts VALUES (?, 'chat', ?, ?, ?, ?)",
                (
                    str(session_id),
                    str(payload.request_key),
                    body_hash,
                    accepted.model_dump_json(),
                    now.isoformat(),
                ),
            )
            return accepted, True

    def mark_processing(self, request_id: UUID, progress: str) -> None:
        now = utc_now()
        with self.transaction(immediate=True) as connection:
            row = connection.execute(
                "SELECT created_at,timings_json FROM requests WHERE request_id=?",
                (str(request_id),),
            ).fetchone()
            if row is None:
                return
            timings = json.loads(row["timings_json"])
            timings["queue"] = round(
                (now - datetime.fromisoformat(row["created_at"])).total_seconds()
                * 1000,
                3,
            )
            connection.execute(
                """UPDATE requests SET status=?,progress=?,timings_json=?
                WHERE request_id=? AND status IN (?,?)""",
                (
                    RequestStatus.PROCESSING.value,
                    progress,
                    json.dumps(timings),
                    str(request_id),
                    RequestStatus.QUEUED.value,
                    RequestStatus.PROCESSING.value,
                ),
            )

    def set_candidates(
        self,
        request_id: UUID,
        candidates: list[CandidateSource],
        timings: dict[str, Any],
    ) -> None:
        now = utc_now()
        with self.transaction(immediate=True) as connection:
            row = connection.execute(
                "SELECT created_at,timings_json FROM requests WHERE request_id=?",
                (str(request_id),),
            ).fetchone()
            if row is None:
                return
            merged = json.loads(row["timings_json"])
            merged.update(timings)
            if candidates:
                merged["time_to_first_source"] = round(
                    (now - datetime.fromisoformat(row["created_at"])).total_seconds()
                    * 1000,
                    3,
                )
            connection.execute(
                """UPDATE requests SET progress='sources_found',candidate_sources_json=?,timings_json=?
                WHERE request_id=?""",
                (
                    json.dumps(
                        [item.model_dump(mode="json") for item in candidates],
                        ensure_ascii=False,
                    ),
                    json.dumps(merged, ensure_ascii=False),
                    str(request_id),
                ),
            )

    def get_processing_context(self, request_id: UUID) -> dict[str, Any]:
        with self.transaction() as connection:
            request = connection.execute(
                "SELECT * FROM requests WHERE request_id=?", (str(request_id),)
            ).fetchone()
            if request is None:
                raise not_found()
            case = connection.execute(
                "SELECT * FROM cases WHERE case_id=?", (request["case_id"],)
            ).fetchone()
            message = connection.execute(
                "SELECT * FROM messages WHERE message_id=?",
                (request["user_message_id"],),
            ).fetchone()
            recent = connection.execute(
                "SELECT content FROM messages WHERE case_id=? AND role='user' ORDER BY seq DESC LIMIT 5",
                (request["case_id"],),
            ).fetchall()
        return {
            "request_id": UUID(request["request_id"]),
            "case_id": UUID(request["case_id"]),
            "user_message_id": UUID(request["user_message_id"]),
            "accepted_case_version": int(request["accepted_case_version"]),
            "trace_id": request["trace_id"],
            "question": message["content"],
            "confirmed_facts": json.loads(case["confirmed_facts_json"]),
            "clarification_count": int(case["clarification_count"]),
            "recent_user_messages": [item["content"] for item in reversed(recent)],
        }

    def get_retry_text(self, session_id: UUID, request_id: UUID) -> str:
        with self.transaction() as connection:
            row = connection.execute(
                """SELECT messages.content FROM requests
                JOIN cases USING(case_id) JOIN messages ON messages.message_id=requests.user_message_id
                WHERE requests.request_id=? AND cases.session_id=?""",
                (str(request_id), str(session_id)),
            ).fetchone()
        if row is None:
            raise not_found()
        return row["content"]

    def publish_message(
        self,
        request_id: UUID,
        *,
        case_status: CaseStatus,
        role: str,
        kind: str,
        responder_type: str | None,
        answer_origin: str | None,
        content: str,
        source_ids: list[str],
        structured_content: dict[str, Any] | None = None,
        route: RoutingResult | None = None,
        clarification_increment: bool = False,
        timings: dict[str, Any] | None = None,
    ) -> bool:
        now = utc_now().isoformat()
        with self.transaction(immediate=True) as connection:
            request = connection.execute(
                "SELECT * FROM requests WHERE request_id=?", (str(request_id),)
            ).fetchone()
            if request is None:
                return False
            case = connection.execute(
                "SELECT * FROM cases WHERE case_id=?", (request["case_id"],)
            ).fetchone()
            if (
                case is None
                or case["active_request_id"] != str(request_id)
                or int(case["case_version"]) != int(request["accepted_case_version"])
                or case["status"]
                in (
                    CaseStatus.RESOLVED.value,
                    CaseStatus.CLOSED_POLICY.value,
                    CaseStatus.HANDED_OFF.value,
                )
            ):
                connection.execute(
                    """UPDATE requests SET status='cancelled',progress=NULL,finished_at=?
                    WHERE request_id=? AND status NOT IN ('final','error')""",
                    (now, str(request_id)),
                )
                return False
            seq = int(
                connection.execute(
                    "SELECT COALESCE(MAX(seq),0)+1 FROM messages WHERE case_id=?",
                    (request["case_id"],),
                ).fetchone()[0]
            )
            message_id = uuid4()
            connection.execute(
                """INSERT INTO messages
                (message_id,case_id,seq,role,kind,responder_type,answer_origin,content,
                 structured_content_json,source_ids_json,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    str(message_id),
                    request["case_id"],
                    seq,
                    role,
                    kind,
                    responder_type,
                    answer_origin,
                    content,
                    json.dumps(structured_content, ensure_ascii=False)
                    if structured_content
                    else None,
                    json.dumps(source_ids, ensure_ascii=False),
                    now,
                ),
            )
            route_json = route.model_dump_json() if route else case["route_json"]
            connection.execute(
                """UPDATE cases SET status=?,case_version=case_version+1,active_request_id=NULL,
                clarification_count=clarification_count+?,topic_id=COALESCE(?,topic_id),
                subtopic_id=COALESCE(?,subtopic_id),route_json=?,updated_at=? WHERE case_id=?""",
                (
                    case_status.value,
                    int(clarification_increment),
                    route.topic_id if route else None,
                    route.subtopic_id if route else None,
                    route_json,
                    now,
                    request["case_id"],
                ),
            )
            merged_timings = json.loads(request["timings_json"])
            merged_timings.update(timings or {})
            connection.execute(
                """UPDATE requests SET status='final',progress=NULL,result_message_ids_json=?,
                timings_json=?,finished_at=? WHERE request_id=?""",
                (
                    json.dumps([str(message_id)]),
                    json.dumps(merged_timings),
                    now,
                    str(request_id),
                ),
            )
            return True

    def invalidate_request(self, request_id: UUID, reason: str) -> None:
        now = utc_now().isoformat()
        with self.transaction(immediate=True) as connection:
            request = connection.execute(
                "SELECT * FROM requests WHERE request_id=?", (str(request_id),)
            ).fetchone()
            if request is None or request["status"] not in (
                RequestStatus.QUEUED.value,
                RequestStatus.PROCESSING.value,
            ):
                return
            case = connection.execute(
                "SELECT * FROM cases WHERE case_id=?", (request["case_id"],)
            ).fetchone()
            if (
                case is None
                or case["active_request_id"] != str(request_id)
                or int(case["case_version"]) != int(request["accepted_case_version"])
            ):
                connection.execute(
                    "UPDATE requests SET status='cancelled',progress=NULL,finished_at=? WHERE request_id=?",
                    (now, str(request_id)),
                )
                return
            connection.execute(
                """UPDATE requests SET status='cancelled',progress=NULL,error_code=?,error_message=?,
                error_retryable=0,finished_at=? WHERE request_id=?""",
                (reason, reason, now, str(request_id)),
            )
            connection.execute(
                """UPDATE cases SET active_request_id=NULL,case_version=case_version+1,updated_at=?
                WHERE case_id=? AND active_request_id=?""",
                (now, request["case_id"], str(request_id)),
            )

    def save_feedback(
        self, session_id: UUID, payload: FeedbackInput
    ) -> FeedbackResponse:
        return self.save_feedback_with_status(session_id, payload)[0]

    def save_feedback_with_status(
        self, session_id: UUID, payload: FeedbackInput
    ) -> tuple[FeedbackResponse, bool]:
        now = utc_now().isoformat()
        fields = payload.model_fields_set
        with self.transaction(immediate=True) as connection:
            message = connection.execute(
                """SELECT messages.*,cases.session_id,cases.status case_status,cases.case_version,
                cases.active_request_id FROM messages JOIN cases USING(case_id)
                WHERE message_id=? AND cases.session_id=?""",
                (str(payload.message_id), str(session_id)),
            ).fetchone()
            if message is None:
                raise not_found()
            if message["kind"] != "answer":
                raise DomainError(
                    "VALIDATION_ERROR", "Оценивать можно только ответ", status_code=422
                )
            if payload.specialist_rating is not None and not (
                message["responder_type"] == "operator"
                and message["answer_origin"] == "operator"
            ):
                raise DomainError(
                    "VALIDATION_ERROR",
                    "Рейтинг специалиста допустим только для ответа оператора",
                    status_code=422,
                )
            existing = connection.execute(
                "SELECT * FROM feedback WHERE session_id=? AND message_id=?",
                (str(session_id), str(payload.message_id)),
            ).fetchone()
            created = existing is None
            values = {
                "useful": existing["useful"] if existing else None,
                "solved": existing["solved"] if existing else None,
                "specialist_rating": existing["specialist_rating"]
                if existing
                else None,
                "reason_codes": json.loads(existing["reason_codes_json"])
                if existing
                else [],
                "comment": existing["comment"] if existing else None,
            }
            for name in (
                "useful",
                "solved",
                "specialist_rating",
                "reason_codes",
                "comment",
            ):
                if name in fields:
                    value = getattr(payload, name)
                    values[name] = (
                        [item.value for item in value]
                        if name == "reason_codes"
                        else value
                    )
            if created and all(
                values[name] is None
                for name in ("useful", "solved", "specialist_rating")
            ):
                raise DomainError(
                    "VALIDATION_ERROR",
                    "При создании нужна хотя бы одна оценка",
                    status_code=422,
                )
            feedback_id = UUID(existing["feedback_id"]) if existing else uuid4()
            connection.execute(
                """INSERT INTO feedback
                (feedback_id,session_id,message_id,useful,solved,specialist_rating,reason_codes_json,comment,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(session_id,message_id) DO UPDATE SET useful=excluded.useful,
                solved=excluded.solved,specialist_rating=excluded.specialist_rating,
                reason_codes_json=excluded.reason_codes_json,comment=excluded.comment,updated_at=excluded.updated_at""",
                (
                    str(feedback_id),
                    str(session_id),
                    str(payload.message_id),
                    None if values["useful"] is None else int(values["useful"]),
                    None if values["solved"] is None else int(values["solved"]),
                    values["specialist_rating"],
                    json.dumps(values["reason_codes"]),
                    values["comment"],
                    now,
                ),
            )
            outcome_applied = False
            outcome_reason: str | None = None
            if "solved" in fields:
                latest_answer = connection.execute(
                    "SELECT message_id,seq FROM messages WHERE case_id=? AND kind='answer' ORDER BY seq DESC LIMIT 1",
                    (message["case_id"],),
                ).fetchone()
                later_user = connection.execute(
                    "SELECT 1 FROM messages WHERE case_id=? AND role='user' AND seq>?",
                    (message["case_id"], message["seq"]),
                ).fetchone()
                is_current = (
                    latest_answer is not None
                    and latest_answer["message_id"] == str(payload.message_id)
                    and later_user is None
                    and message["active_request_id"] is None
                    and message["case_status"]
                    not in (
                        CaseStatus.RESOLVED.value,
                        CaseStatus.CLOSED_POLICY.value,
                        CaseStatus.HANDED_OFF.value,
                    )
                )
                if is_current and payload.solved is not None:
                    new_status = (
                        CaseStatus.RESOLVED if payload.solved else CaseStatus.OPEN
                    )
                    connection.execute(
                        "UPDATE cases SET status=?,case_version=case_version+1,updated_at=? WHERE case_id=?",
                        (new_status.value, now, message["case_id"]),
                    )
                    outcome_applied = True
                else:
                    outcome_reason = "ANSWER_NOT_CURRENT"
            updated_case = connection.execute(
                "SELECT status,case_version FROM cases WHERE case_id=?",
                (message["case_id"],),
            ).fetchone()
            return FeedbackResponse(
                feedback_id=feedback_id,
                message_id=payload.message_id,
                case_version=updated_case["case_version"],
                case_status=updated_case["status"],
                outcome_applied=outcome_applied,
                outcome_reason=outcome_reason,
            ), created

    def count_cases(self, session_id: UUID) -> int:
        with self.transaction() as connection:
            return int(
                connection.execute(
                    "SELECT COUNT(*) FROM cases WHERE session_id=?", (str(session_id),)
                ).fetchone()[0]
            )

    def fail_request(self, request_id: UUID, code: str, *, retryable: bool) -> None:
        now = utc_now().isoformat()
        with self.transaction(immediate=True) as connection:
            request = connection.execute(
                "SELECT * FROM requests WHERE request_id=?", (str(request_id),)
            ).fetchone()
            if request is None or request["status"] not in (
                RequestStatus.QUEUED.value,
                RequestStatus.PROCESSING.value,
            ):
                return
            case = connection.execute(
                "SELECT * FROM cases WHERE case_id=?", (request["case_id"],)
            ).fetchone()
            if (
                case is None
                or case["active_request_id"] != str(request_id)
                or int(case["case_version"]) != int(request["accepted_case_version"])
            ):
                connection.execute(
                    "UPDATE requests SET status='cancelled',progress=NULL,finished_at=? WHERE request_id=?",
                    (now, str(request_id)),
                )
                return
            connection.execute(
                """UPDATE requests SET status='error',progress=NULL,error_code=?,error_message=?,
                error_retryable=?,finished_at=? WHERE request_id=?""",
                (code, code, int(retryable), now, str(request_id)),
            )
            connection.execute(
                """UPDATE cases SET active_request_id=NULL,case_version=case_version+1,updated_at=?
                WHERE case_id=? AND active_request_id=?""",
                (now, request["case_id"], str(request_id)),
            )

    def recover_interrupted_requests(self) -> int:
        now = utc_now().isoformat()
        with self.transaction(immediate=True) as connection:
            rows = connection.execute(
                "SELECT request_id,case_id FROM requests WHERE status IN ('queued','processing')"
            ).fetchall()
            for row in rows:
                connection.execute(
                    """UPDATE requests SET status='error',progress=NULL,error_code='RESTART_INTERRUPTED',
                    error_message='Обработка прервана перезапуском',error_retryable=1,finished_at=?
                    WHERE request_id=?""",
                    (now, row["request_id"]),
                )
                connection.execute(
                    """UPDATE cases SET active_request_id=NULL,case_version=case_version+1,updated_at=?
                    WHERE case_id=? AND active_request_id=?""",
                    (now, row["case_id"], row["request_id"]),
                )
            return len(rows)

    def get_request(self, session_id: UUID, request_id: UUID) -> RequestView:
        with self.transaction() as connection:
            row = connection.execute(
                """SELECT requests.* FROM requests JOIN cases USING(case_id)
                WHERE request_id=? AND session_id=?""",
                (str(request_id), str(session_id)),
            ).fetchone()
        if row is None:
            raise not_found()
        error = None
        if row["error_code"]:
            error = RequestError(
                code=row["error_code"],
                message=row["error_message"],
                retryable=bool(row["error_retryable"]),
            )
        return RequestView(
            request_id=row["request_id"],
            case_id=row["case_id"],
            status=row["status"],
            progress=row["progress"],
            candidate_sources=[
                CandidateSource.model_validate(item)
                for item in json.loads(row["candidate_sources_json"])
            ],
            result_message_ids=json.loads(row["result_message_ids_json"]),
            error=error,
            timings_ms=json.loads(row["timings_json"]),
        )

    def get_case(self, session_id: UUID, case_id: UUID) -> CaseView:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM cases WHERE case_id=? AND session_id=?",
                (str(case_id), str(session_id)),
            ).fetchone()
            if row is None:
                raise not_found()
            message_rows = connection.execute(
                "SELECT * FROM messages WHERE case_id=? ORDER BY seq", (str(case_id),)
            ).fetchall()
            ticket_row = connection.execute(
                "SELECT * FROM tickets WHERE case_id=?", (str(case_id),)
            ).fetchone()
        case = Case(
            case_id=row["case_id"],
            session_id=row["session_id"],
            status=row["status"],
            case_version=row["case_version"],
            active_request_id=row["active_request_id"],
            clarification_count=row["clarification_count"],
            confirmed_facts=json.loads(row["confirmed_facts_json"]),
            topic_id=row["topic_id"],
            subtopic_id=row["subtopic_id"],
            route=RoutingResult.model_validate_json(row["route_json"])
            if row["route_json"]
            else None,
            is_demo=bool(row["is_demo"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        messages = [
            Message(
                message_id=item["message_id"],
                case_id=item["case_id"],
                seq=item["seq"],
                role=item["role"],
                kind=item["kind"],
                responder_type=item["responder_type"],
                author_id=item["author_id"],
                answer_origin=item["answer_origin"],
                content=item["content"],
                structured_content=json.loads(item["structured_content_json"])
                if item["structured_content_json"]
                else None,
                source_ids=json.loads(item["source_ids_json"]),
                created_at=item["created_at"],
            )
            for item in message_rows
        ]
        ticket = Ticket.model_validate(dict(ticket_row)) if ticket_row else None
        return CaseView(
            case=case,
            ticket=ticket,
            messages=messages,
            limit_reached=len(messages) >= 98,
        )
