import json
from pathlib import Path

from fastapi.testclient import TestClient
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


def test_runner_captures_http_source_feedback_and_matching_export(
    tmp_path: Path,
) -> None:
    from tools.run_a03_e2e import run_flow

    evidence = EvidenceItem(
        evidence_id="ev-1",
        source_id="source-real-shape",
        source_type="portal_knowledge_base_api",
        title="Изменение реквизитов",
        text="Добавьте новые реквизиты и перенесите старые в архив.",
        content_status="complete",
        retrieval_method="dense",
        score=0.9,
    )
    knowledge = FakeKnowledge(
        KnowledgeResult(
            snapshot_id="kb-controlled",
            candidates=[evidence],
            selected_evidence_ids=["ev-1"],
            decision=GateDecision.ANSWER_ALLOWED,
            route=RoutingResult(),
            timings_ms={"retrieval": 4.5, "query_embedding": 2.0},
        )
    )
    knowledge.sources[evidence.source_id] = SourceRecord(
        source_id=evidence.source_id,
        source_type=evidence.source_type,
        title=evidence.title,
        excerpt=evidence.text,
        content_status="complete",
    )
    generator = FakeGenerator(
        GenerationAnswer(
            summary="Добавьте новые реквизиты.",
            steps=["Перенесите старые реквизиты в архив."],
            source_ids=[evidence.source_id],
        )
    )
    database = Database(tmp_path / "app.sqlite")
    service = BackendService(database, FakePolicy(), knowledge, generator)
    settings = Settings(
        db_path=tmp_path / "app.sqlite",
        runtime_mode="test",
        is_demo=False,
    )
    app = create_app(settings=settings, service=service)
    evidence_path = tmp_path / "run.json"
    export_path = tmp_path / "export.json"

    with TestClient(app) as client:
        result = run_flow(
            client,
            service,
            question="Как изменить банковские реквизиты?",
            app_commit="test-sha",
            kb_snapshot_id="kb-controlled",
            evidence_path=evidence_path,
            export_path=export_path,
            timeout_seconds=5,
        )

    assert result["http"]["session_status"] == 201
    assert result["http"]["chat_status"] == 202
    assert result["request"]["status"] == "final"
    assert result["answer"]["source_ids"] == ["source-real-shape"]
    assert result["sources"][0]["title"] == "Изменение реквизитов"
    assert result["feedback"]["outcome_applied"] is True
    assert result["generation_calls"] == 1
    assert result["export_row"]["case_id"] == result["case_id"]
    assert result["export_row"]["cohort"] == "live"
    assert (
        json.loads(evidence_path.read_text(encoding="utf-8"))["case_id"]
        == result["case_id"]
    )
    assert (
        json.loads(export_path.read_text(encoding="utf-8"))["rows"][0]["case_id"]
        == result["case_id"]
    )
