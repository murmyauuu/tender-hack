"""Controlled-dependency A02 HTTP server for the B02 transport smoke.

This is not a real RAG runtime: policy/knowledge/generator are explicit A02 fakes. The server
exists only to exercise the generated browser transport over a real HTTP socket.
"""

from pathlib import Path

from tenderhack_backend.app import create_app
from tenderhack_backend.config import Settings
from tenderhack_backend.fakes import FakeGenerator, FakeKnowledge, FakePolicy
from tenderhack_backend.service import BackendService
from tenderhack_backend.storage import Database
from tenderhack_contracts import (
    EvidenceItem,
    GateDecision,
    GenerationAnswer,
    KnowledgeResult,
    RoutingResult,
    SourceRecord,
)


evidence = EvidenceItem(
    evidence_id="evidence-demo",
    source_id="source-demo",
    source_type="portal_knowledge_base_api",
    title="Инструкция",
    text="Поставщик открывает карточку контракта.",
    conditions=["Действуйте от имени поставщика."],
    applicable_roles=["supplier"],
    role_verified=True,
    content_status="complete",
    retrieval_method="dense",
    score=0.9,
)
knowledge = FakeKnowledge(
    KnowledgeResult(
        snapshot_id="mock-b02-http-smoke",
        candidates=[evidence],
        selected_evidence_ids=[evidence.evidence_id],
        decision=GateDecision.ANSWER_ALLOWED,
        route=RoutingResult(support_line="L1", basis_source_ids=[evidence.source_id]),
        timings_ms={"retrieval": 0},
    )
)
knowledge.sources[evidence.source_id] = SourceRecord(
    source_id=evidence.source_id,
    source_type=evidence.source_type,
    title=evidence.title,
    excerpt=evidence.text,
    conditions=evidence.conditions,
    applicable_roles=evidence.applicable_roles,
    content_status="complete",
)
generator = FakeGenerator(
    GenerationAnswer(
        summary="Откройте карточку контракта.",
        conditions=evidence.conditions,
        steps=["Откройте карточку контракта."],
        source_ids=[evidence.source_id],
    )
)
settings = Settings(
    db_path=Path("var/b02-smoke/app.sqlite"),
    allowed_origin="http://127.0.0.1:5173",
    cookie_secure=False,
    is_demo=True,
    auto_worker=True,
)
service = BackendService(Database(settings.db_path), FakePolicy(), knowledge, generator)
app = create_app(settings=settings, service=service)
