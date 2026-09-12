"""Real A04 HTTP backend for reproducible B03 browser verification.

FastAPI, SQLite, policy, version guards, handoff, feedback and protected operator reply are the
accepted production implementations. Knowledge and generation are controlled dependencies so the
browser run can deterministically exercise answer, clarification, escalation, failure and late
response paths without claiming a real RAG/model result.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from knowledge.policy import build_policy
from tenderhack_backend.app import create_app
from tenderhack_backend.config import Settings
from tenderhack_backend.fakes import FakeGenerator, FakeKnowledge
from tenderhack_backend.service import BackendService
from tenderhack_backend.storage import Database
from tenderhack_contracts import (
    EvidenceItem,
    GateDecision,
    GenerationAnswer,
    KnowledgeResult,
    MissingFact,
    QueryContext,
    ReasonCode,
    RoutingResult,
    SourceRecord,
)


OUTPUT_DIR = Path("var/b03-real")
COUNTERS_PATH = OUTPUT_DIR / "counters.json"


class ControlledKnowledge(FakeKnowledge):
    def __init__(self) -> None:
        super().__init__()
        self.embedding_calls = 0
        self.evidence = EvidenceItem(
            evidence_id="b03-evidence",
            source_id="b03-source",
            source_type="portal_knowledge_base_api",
            title="Проверенная инструкция B03",
            text="Поставщик проверяет данные закупки в карточке контракта.",
            conditions=["Действуйте от имени поставщика."],
            applicable_roles=["supplier"],
            role_verified=True,
            content_status="complete",
            retrieval_method="dense",
            score=1.0,
        )
        self.sources[self.evidence.source_id] = SourceRecord(
            source_id=self.evidence.source_id,
            source_type=self.evidence.source_type,
            title=self.evidence.title,
            excerpt=self.evidence.text,
            conditions=self.evidence.conditions,
            applicable_roles=self.evidence.applicable_roles,
            content_status="complete",
        )

    async def retrieve(self, query: QueryContext) -> KnowledgeResult:
        self.retrieve_calls += 1
        if "медленный" in query.text.lower():
            await asyncio.sleep(4)
        if "уточнение" in query.text.lower() and query.clarification_count == 0:
            result = KnowledgeResult(
                snapshot_id="controlled-b03",
                candidates=[],
                selected_evidence_ids=[],
                decision=GateDecision.CLARIFY,
                missing_fact=MissingFact(key="role", question="Уточните, вы поставщик или заказчик?"),
                route=RoutingResult(reason_codes=[ReasonCode.ROLE_REQUIRED]),
            )
        elif "ai ответ" in query.text.lower() or "медленный" in query.text.lower() or "ошибка модели" in query.text.lower():
            result = KnowledgeResult(
                snapshot_id="controlled-b03",
                candidates=[self.evidence],
                selected_evidence_ids=[self.evidence.evidence_id],
                decision=GateDecision.ANSWER_ALLOWED,
                route=RoutingResult(support_line="L1", basis_source_ids=[self.evidence.source_id]),
            )
        else:
            result = KnowledgeResult(
                snapshot_id="controlled-b03",
                candidates=[],
                selected_evidence_ids=[],
                decision=GateDecision.ESCALATE,
                reason_codes=[ReasonCode.NO_EVIDENCE],
                route=RoutingResult(support_line="L2", reason_codes=[ReasonCode.NO_EVIDENCE]),
            )
        write_counters()
        return result


class ControlledGenerator(FakeGenerator):
    def __init__(self) -> None:
        super().__init__(GenerationAnswer(
            summary="Проверьте данные закупки в карточке контракта.",
            conditions=["Действуйте от имени поставщика."],
            steps=["Откройте карточку контракта."],
            source_ids=["b03-source"],
        ))
        self.failed_questions: set[str] = set()

    async def generate(self, task):
        self.calls += 1
        write_counters()
        if "ошибка модели" in task.question.lower() and task.question not in self.failed_questions:
            self.failed_questions.add(task.question)
            raise RuntimeError("controlled first-attempt failure")
        return self.proposal


OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
knowledge = ControlledKnowledge()
generator = ControlledGenerator()


def write_counters() -> None:
    COUNTERS_PATH.write_text(json.dumps({
        "embedding_calls": knowledge.embedding_calls,
        "retrieval_calls": knowledge.retrieve_calls,
        "generation_calls": generator.calls,
    }), encoding="utf-8")


settings = Settings(
    db_path=Path(os.environ.get("TENDERHACK_DB_PATH", OUTPUT_DIR / "app.sqlite")),
    allowed_origin="http://127.0.0.1:5173",
    cookie_secure=False,
    is_demo=True,
    auto_worker=True,
    runtime_mode="test",
    operator_reply_key=os.environ.get("TENDERHACK_OPERATOR_REPLY_KEY"),
    operator_author_id="operator-b03-real",
)
service = BackendService(Database(settings.db_path), build_policy(), knowledge, generator)
write_counters()
app = create_app(settings=settings, service=service)
