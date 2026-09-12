"""Пайплайн C03: dedup → роль/применимость → parent expansion → gate.

Юнит-тесты на синтетических `ResolvedCandidate`/`EvidenceGroup` проверяют
отдельные ступени детерминированно, без зависимости от конкретных текстов
реального снимка. Интеграционные тесты внизу гоняют `retrieve()` целиком на
реальном снимке C02 через честный лексический (FTS) fallback — dense-индекс
от G ещё не доставлен (см. C03-handoff.md), поэтому `retrieve()` не выдаёт
mock за семантический поиск: он использует ту же настоящую FTS, что и C02.
"""

from __future__ import annotations

import asyncio

from tenderhack_contracts.models import GateDecision, QueryContext, ReasonCode

from knowledge.kb.retrieval import (
    EvidenceGroup,
    RawHit,
    ResolvedCandidate,
    apply_role_gate,
    decide_gate,
    dedup_hits,
    detect_known_conflict,
    run_pipeline,
)
from knowledge.kb.store import SqliteKnowledgeStore


def _candidate(**overrides) -> ResolvedCandidate:
    base = dict(
        source_id="portal:1:1",
        parent_id="portal:1",
        original_ids=["orig1"],
        source_type="portal_kb",
        source_key="1",
        title="Заголовок",
        text="Текст ответа.",
        section_path=None,
        page_from=None,
        page_to=None,
        version=None,
        audience_raw="supplier",
        applicable_roles=["supplier"],
        role_verified=True,
        content_status="complete",
        eligibility_reason=None,
        method="dense",
        score=0.9,
    )
    base.update(overrides)
    return ResolvedCandidate(**base)


def _group(**overrides) -> EvidenceGroup:
    base = dict(
        parent_id="p1",
        source_id="portal:1:1",
        original_ids=["orig1"],
        source_type="portal_kb",
        source_key="1",
        title="Заголовок",
        text="Текст ответа.",
        section_path=None,
        page_from=None,
        page_to=None,
        version=None,
        audience_raw=None,
        applicable_roles=[],
        role_verified=False,
        content_status="complete",
        eligibility_reason=None,
        method="dense",
        score=0.9,
    )
    base.update(overrides)
    return EvidenceGroup(**base)


# --------------------------------------------------------------------- dedup


def test_dedup_prefers_exact_over_fts_over_dense():
    hits = [
        RawHit(source_id="x", method="dense", score=0.99),
        RawHit(source_id="x", method="fts", score=0.1),
        RawHit(source_id="x", method="exact", score=1.0),
    ]
    result = dedup_hits(hits)
    assert len(result) == 1
    assert result[0].method == "exact"


def test_dedup_keeps_distinct_ids():
    hits = [RawHit(source_id="a", method="dense", score=0.5), RawHit(source_id="b", method="dense", score=0.9)]
    result = dedup_hits(hits)
    assert {h.source_id for h in result} == {"a", "b"}
    assert result[0].source_id == "b", "отсортировано по убыванию score"


def test_dedup_same_method_keeps_higher_score():
    hits = [RawHit(source_id="a", method="dense", score=0.3), RawHit(source_id="a", method="dense", score=0.7)]
    result = dedup_hits(hits)
    assert len(result) == 1
    assert result[0].score == 0.7


# ------------------------------------------------------------------ role gate


def test_role_gate_unverified_is_usable():
    cand = _candidate(role_verified=False, applicable_roles=[])
    apply_role_gate([cand], {})
    assert cand.role_status == "unverified"


def test_role_gate_matches_confirmed_role():
    cand = _candidate(role_verified=True, applicable_roles=["supplier"])
    apply_role_gate([cand], {"role": "supplier"})
    assert cand.role_status == "ok"


def test_role_gate_mismatch_when_role_known_and_different():
    cand = _candidate(role_verified=True, applicable_roles=["supplier"])
    apply_role_gate([cand], {"role": "customer"})
    assert cand.role_status == "mismatch"


def test_role_gate_needs_role_when_role_unknown():
    cand = _candidate(role_verified=True, applicable_roles=["supplier"])
    apply_role_gate([cand], {})
    assert cand.role_status == "needs_role"


# --------------------------------------------------------------- conflict


def test_known_conflict_detected_for_same_source_key_different_versions():
    groups = [
        _group(source_key="reg:s1", version="ред. от 01.01.2025"),
        _group(source_key="reg:s1", version="ред. от 10.06.2025"),
    ]
    assert detect_known_conflict(groups) is True


def test_no_conflict_when_versions_agree_or_are_null():
    groups = [_group(source_key="reg:s1", version=None), _group(source_key="reg:s1", version=None)]
    assert detect_known_conflict(groups) is False
    groups2 = [_group(source_key="reg:s1", version="v1"), _group(source_key="reg:s2", version="v2")]
    assert detect_known_conflict(groups2) is False


# -------------------------------------------------------------------- gate


def test_gate_out_of_scope_for_greeting():
    outcome = decide_gate("привет", [], False, False, [], clarification_count=0)
    assert outcome.decision == GateDecision.OUT_OF_SCOPE
    assert ReasonCode.OUT_OF_SCOPE in outcome.reason_codes


def test_gate_no_evidence_escalates():
    outcome = decide_gate("реальный вопрос без совпадений", [], False, False, [], clarification_count=0)
    assert outcome.decision == GateDecision.ESCALATE
    assert ReasonCode.NO_EVIDENCE in outcome.reason_codes


def test_gate_role_required_clarifies_once_then_escalates():
    first = decide_gate("вопрос", [], True, False, [], clarification_count=0)
    assert first.decision == GateDecision.CLARIFY
    assert ReasonCode.ROLE_REQUIRED in first.reason_codes
    assert first.missing_fact is not None and first.missing_fact.key == "role"

    second = decide_gate("вопрос", [], True, False, [], clarification_count=1)
    assert second.decision == GateDecision.ESCALATE
    assert ReasonCode.UNRESOLVED_AFTER_STEPS in second.reason_codes


def test_gate_role_mismatch_always_escalates_no_clarify_loop():
    outcome = decide_gate("вопрос", [], False, True, [], clarification_count=0)
    assert outcome.decision == GateDecision.ESCALATE
    assert ReasonCode.ROLE_MISMATCH in outcome.reason_codes


def test_gate_unknown_identifier_clarifies_then_escalates():
    first = decide_gate("вопрос", [], False, False, ["ZQXPRT-99"], clarification_count=0)
    assert first.decision == GateDecision.CLARIFY
    assert ReasonCode.UNKNOWN_IDENTIFIER in first.reason_codes

    second = decide_gate("вопрос", [], False, False, ["ZQXPRT-99"], clarification_count=1)
    assert second.decision == GateDecision.ESCALATE
    assert ReasonCode.UNRESOLVED_AFTER_STEPS in second.reason_codes


def test_gate_pointer_only_escalates_without_answering():
    groups = [_group(content_status="pointer", eligibility_reason="POINTER: ...")]
    outcome = decide_gate("вопрос", groups, False, False, [], clarification_count=0)
    assert outcome.decision == GateDecision.ESCALATE
    assert outcome.decision != GateDecision.ANSWER_ALLOWED


def test_gate_incomplete_only_escalates_with_missing_attachment():
    groups = [_group(content_status="incomplete", eligibility_reason="MISSING_ATTACHMENT: ...")]
    outcome = decide_gate("вопрос", groups, False, False, [], clarification_count=0)
    assert outcome.decision == GateDecision.ESCALATE
    assert ReasonCode.MISSING_ATTACHMENT in outcome.reason_codes


def test_gate_known_conflict_escalates_even_with_complete_evidence():
    groups = [
        _group(source_id="a", source_key="reg:s1", version="v1", content_status="complete"),
        _group(source_id="b", source_key="reg:s1", version="v2", content_status="complete"),
    ]
    outcome = decide_gate("вопрос", groups, False, False, [], clarification_count=0)
    assert outcome.decision == GateDecision.ESCALATE
    assert ReasonCode.KNOWN_CONFLICT in outcome.reason_codes


def test_gate_answer_allowed_for_complete_applicable_evidence():
    groups = [_group(content_status="complete", score=0.9), _group(source_id="portal:2:1", content_status="complete", score=0.5)]
    outcome = decide_gate("вопрос", groups, False, False, [], clarification_count=0)
    assert outcome.decision == GateDecision.ANSWER_ALLOWED
    assert outcome.reason_codes == []
    assert len(outcome.evidence) == 2


def test_gate_answer_allowed_caps_evidence_at_five():
    groups = [_group(source_id=f"portal:{i}:1", content_status="complete", score=1.0 - i * 0.01) for i in range(8)]
    outcome = decide_gate("вопрос", groups, False, False, [], clarification_count=0)
    assert outcome.decision == GateDecision.ANSWER_ALLOWED
    assert len(outcome.evidence) == 5


# --------------------------------------------------------- integration (real KB)


def _query(text: str, confirmed_facts: dict | None = None, clarification_count: int = 0) -> QueryContext:
    return QueryContext(
        text=text,
        confirmed_facts=confirmed_facts or {},
        recent_user_messages=[],
        clarification_count=clarification_count,
        trace_id="test-trace",
    )


def test_integration_answer_allowed_on_real_kb_via_fts_fallback(snapshot_dir):
    """Без реального dense-индекса (G ещё не доставил) retrieve() честно
    использует FTS fallback — это РЕАЛЬНЫЙ лексический поиск по реальному
    снимку C02, не mock. Известный вопрос про МЧД находит complete evidence,
    D01 gold source (portal:559622:1) — среди найденных кандидатов (МЧД
    упоминается в ~14 записях снимка, поэтому не фиксируем точную позицию в
    ранжировании — только то, что gold найден и выбранные evidence complete)."""
    store = SqliteKnowledgeStore(snapshot_dir)
    try:
        result = asyncio.run(
            store.retrieve(
                _query(
                    "Нужна ли МЧД индивидуальному предпринимателю для подписания документов?",
                    confirmed_facts={"role": "supplier"},
                )
            )
        )
        assert result.decision == GateDecision.ANSWER_ALLOWED
        assert result.selected_evidence_ids
        assert "portal:559622:1" in {c.source_id for c in result.candidates}
        selected = {c.source_id: c for c in result.candidates if c.evidence_id in result.selected_evidence_ids}
        assert all(c.content_status == "complete" for c in selected.values())
    finally:
        store.close()


def test_integration_role_mismatch_or_incomplete_never_answers_on_real_kb(snapshot_dir):
    """Смена подтверждённой роли на customer для того же supplier-специфичного
    вопроса про МЧД никогда не должна давать необоснованный ANSWER_ALLOWED.
    На реальном снимке для этого запроса встречается ОДИН customer-совместимый
    чанк, но он content_status=incomplete — поэтому решение может быть
    ROLE_MISMATCH ИЛИ MISSING_ATTACHMENT (оба честны), но не ANSWER_ALLOWED."""
    store = SqliteKnowledgeStore(snapshot_dir)
    try:
        result = asyncio.run(
            store.retrieve(
                _query(
                    "Нужна ли МЧД индивидуальному предпринимателю для подписания документов?",
                    confirmed_facts={"role": "customer"},
                )
            )
        )
        assert result.decision == GateDecision.ESCALATE
        assert set(result.reason_codes) & {ReasonCode.ROLE_MISMATCH, ReasonCode.MISSING_ATTACHMENT}
        assert result.selected_evidence_ids == []
    finally:
        store.close()


def test_integration_role_required_clarifies_on_real_kb(snapshot_dir):
    store = SqliteKnowledgeStore(snapshot_dir)
    try:
        result = asyncio.run(
            store.retrieve(
                _query("Нужна ли МЧД индивидуальному предпринимателю для подписания документов?")
            )
        )
        assert result.decision == GateDecision.CLARIFY
        assert ReasonCode.ROLE_REQUIRED in result.reason_codes
        assert result.missing_fact is not None
    finally:
        store.close()


def test_integration_out_of_scope_for_greeting_on_real_kb(snapshot_dir):
    store = SqliteKnowledgeStore(snapshot_dir)
    try:
        result = asyncio.run(store.retrieve(_query("Привет!")))
        assert result.decision == GateDecision.OUT_OF_SCOPE
    finally:
        store.close()


def test_integration_unknown_identifier_clarifies_then_escalates(snapshot_dir):
    store = SqliteKnowledgeStore(snapshot_dir)
    try:
        r1 = asyncio.run(store.retrieve(_query("Что означает код ZQXPRT-99 в отчёте?")))
        assert r1.decision == GateDecision.CLARIFY
        assert ReasonCode.UNKNOWN_IDENTIFIER in r1.reason_codes

        r2 = asyncio.run(
            store.retrieve(_query("Что означает код ZQXPRT-99 в отчёте?", clarification_count=1))
        )
        assert r2.decision == GateDecision.ESCALATE
        assert ReasonCode.UNKNOWN_IDENTIFIER in r2.reason_codes
    finally:
        store.close()


def test_integration_role_answer_allowed_when_role_confirmed_and_matches(snapshot_dir):
    store = SqliteKnowledgeStore(snapshot_dir)
    try:
        result = asyncio.run(
            store.retrieve(
                _query(
                    "Нужна ли МЧД индивидуальному предпринимателю для подписания документов?",
                    confirmed_facts={"role": "supplier"},
                )
            )
        )
        assert result.decision == GateDecision.ANSWER_ALLOWED
        assert result.selected_evidence_ids
    finally:
        store.close()


def test_integration_retrieve_never_invents_confidence_from_score(snapshot_dir):
    """score — внутренний, не вероятность: не в диапазоне [0,1] для FTS/exact —
    это доказывает, что он не может быть перепутан с вероятностью-confidence."""
    store = SqliteKnowledgeStore(snapshot_dir)
    try:
        result = asyncio.run(
            store.retrieve(_query("Нужна ли МЧД индивидуальному предпринимателю?"))
        )
        assert any(c.score > 1.0 or c.score < 0.0 for c in result.candidates), (
            "score должен явно НЕ выглядеть как вероятность [0,1]"
        )
    finally:
        store.close()


def test_integration_snapshot_id_matches_manifest(snapshot_dir, manifest):
    store = SqliteKnowledgeStore(snapshot_dir)
    try:
        result = asyncio.run(store.retrieve(_query("Как обжаловать блокировку на Портале поставщиков?")))
        assert result.snapshot_id == manifest["snapshot_id"]
    finally:
        store.close()
