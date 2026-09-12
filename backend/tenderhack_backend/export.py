from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from tenderhack_contracts import (
    CurrentResolution,
    EvaluationExport,
    EvaluationRow,
    ExportFeedback,
    ExportMessage,
    ExportRequest,
    ExportTicket,
    FeedbackReason,
    RoutingResult,
)

from .storage import Database, utc_now


def build_export(
    database: Database,
    *,
    app_commit: str,
    kb_snapshot_id: str | None,
) -> EvaluationExport:
    as_of = utc_now()
    rows: list[EvaluationRow] = []
    with database.transaction() as connection:
        cases = connection.execute(
            "SELECT * FROM cases ORDER BY created_at,case_id"
        ).fetchall()
        for case in cases:
            messages_raw = connection.execute(
                "SELECT * FROM messages WHERE case_id=? ORDER BY seq",
                (case["case_id"],),
            ).fetchall()
            requests_raw = connection.execute(
                "SELECT * FROM requests WHERE case_id=? ORDER BY created_at,request_id",
                (case["case_id"],),
            ).fetchall()
            feedback_raw = connection.execute(
                """SELECT feedback.* FROM feedback JOIN messages USING(message_id)
                WHERE messages.case_id=? ORDER BY feedback.updated_at,feedback.feedback_id""",
                (case["case_id"],),
            ).fetchall()
            ticket_raw = connection.execute(
                "SELECT * FROM tickets WHERE case_id=?", (case["case_id"],)
            ).fetchone()

            messages = [
                ExportMessage(
                    message_id=item["message_id"],
                    seq=item["seq"],
                    kind=item["kind"],
                    responder_type=item["responder_type"],
                    author_id=item["author_id"],
                    answer_origin=item["answer_origin"],
                    text=item["content"],
                    structured_content=(
                        json.loads(item["structured_content_json"])
                        if item["structured_content_json"]
                        else None
                    ),
                    source_ids=json.loads(item["source_ids_json"]),
                    created_at=item["created_at"],
                )
                for item in messages_raw
            ]
            requests = [
                ExportRequest(
                    request_id=item["request_id"],
                    user_message_id=item["user_message_id"],
                    status=item["status"],
                    result_message_ids=json.loads(item["result_message_ids_json"]),
                    error_code=item["error_code"],
                    timings_ms=json.loads(item["timings_json"]),
                )
                for item in requests_raw
            ]
            feedback = [
                ExportFeedback(
                    message_id=item["message_id"],
                    useful=None if item["useful"] is None else bool(item["useful"]),
                    solved=None if item["solved"] is None else bool(item["solved"]),
                    specialist_rating=item["specialist_rating"],
                    reason_codes=[
                        FeedbackReason(code)
                        for code in json.loads(item["reason_codes_json"])
                    ],
                    comment=item["comment"],
                    updated_at=item["updated_at"],
                )
                for item in feedback_raw
            ]
            ticket = None
            if ticket_raw is not None:
                ticket = ExportTicket(
                    ticket_id=ticket_raw["ticket_id"],
                    status=ticket_raw["status"],
                    created_at=ticket_raw["created_at"],
                    resolved_by=ticket_raw["resolved_by"],
                )
            resolution = _current_resolution(case, messages_raw, feedback_raw)
            rows.append(
                EvaluationRow(
                    case_id=case["case_id"],
                    cohort="demo" if case["is_demo"] else "live",
                    created_at=case["created_at"],
                    case_status=case["status"],
                    topic_id=case["topic_id"],
                    subtopic_id=case["subtopic_id"],
                    policy_closed=case["status"] == "closed_policy",
                    route=(
                        RoutingResult.model_validate_json(case["route_json"])
                        if case["route_json"]
                        else RoutingResult()
                    ),
                    ticket=ticket,
                    messages=messages,
                    requests=requests,
                    feedback=feedback,
                    current_resolution=resolution,
                )
            )
    return EvaluationExport(
        schema_version="1.0",
        export_id=uuid4(),
        created_at=as_of,
        as_of=as_of,
        app_commit=app_commit,
        kb_snapshot_id=kb_snapshot_id,
        rows=rows,
    )


def _current_resolution(case, messages, feedback) -> CurrentResolution | None:
    if case["status"] != "resolved":
        return None
    by_id = {item["message_id"]: item for item in messages}
    for item in reversed(feedback):
        message = by_id.get(item["message_id"])
        if item["solved"] == 1 and message and message["kind"] == "answer":
            return CurrentResolution(
                message_id=item["message_id"],
                confirmed_by="user",
                answer_origin=message["answer_origin"],
                confirmed_at=item["updated_at"],
            )
    return None


def write_export(path: Path, exported: EvaluationExport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(exported.model_dump(mode="json"), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
