"""Пайплайн retrieval + evidence gate C03 (§10 спецификации v2.1).

Dense top10 → dedup → применимость/роль/версия → parent expansion →
3–5 evidence → четыре исхода gate. Только stdlib (`sqlite3`, `re`,
`dataclasses`, `math`) — файл лежит прямо в `knowledge/kb/` и подпадает под
сканирование `test_no_model_calls.py`. Математика cosine (модуль `dense/`)
и энкодер запроса передаются извне как объекты — этот модуль не знает,
mock они или реальные; это осознанно, чтобы один и тот же код прогонялся
и на M (mock encoder) и на G (реальный).

Routing (topic/subtopic/L1-L3) — зона C04, здесь не реализуется. `route` в
`KnowledgeResult` заполняется нейтральным пустым `RoutingResult` — retrieve()
не выдумывает тему.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Literal

from tenderhack_contracts.models import (
    EvidenceItem,
    GateDecision,
    KnowledgeResult,
    MissingFact,
    QueryContext,
    ReasonCode,
    RoutingResult,
)

from knowledge.kb.lexical import detect_exact_identifiers, exact_identifier_fts_query
from knowledge.kb.normalize import fts_normalize, fts_tokens

__all__ = [
    "RawHit",
    "ResolvedCandidate",
    "EvidenceGroup",
    "run_pipeline",
    "DENSE_TOP_K",
    "EVIDENCE_MAX",
]

DENSE_TOP_K = 10
EVIDENCE_MAX = 5
CLARIFICATION_MAX_COUNT = 1

_METHOD_PRIORITY = {"exact": 0, "fts": 1, "dense": 2}
# Точный ID — самый надёжный сигнал (§10: «Exact IDs выделяются до
# морфологии»). Он обязан обгонять fts/dense при сортировке top-5 evidence,
# а не проигрывать им из-за того, что у fts/dense естественно больший
# числовой диапазон score (bm25/cosine могут быть заметно больше 1.0).
_EXACT_MATCH_SCORE = 1_000.0
_STATUS_RANK = {"complete": 0, "pointer": 1, "incomplete": 2}

# Русские стоп-слова: только для узкого сигнала OUT_OF_SCOPE (пустой/
# приветственный запрос без единого содержательного токена). Полноценная
# классификация темы — зона C04 (routing), здесь её нет и не имитируется.
_STOPWORDS = {
    "привет", "здравствуйте", "добрый", "день", "вечер", "утро", "спасибо",
    "пожалуйста", "да", "нет", "ок", "хорошо", "и", "в", "на", "с", "по",
    "у", "к", "а", "но", "или", "что", "как", "это", "я", "мне", "вы",
}


@dataclass
class RawHit:
    source_id: str
    method: Literal["exact", "fts", "dense"]
    score: float


@dataclass
class ResolvedCandidate:
    source_id: str
    parent_id: str | None
    original_ids: list[str]
    source_type: str
    source_key: str
    title: str
    text: str
    section_path: str | None
    page_from: int | None
    page_to: int | None
    version: str | None
    audience_raw: str | None
    applicable_roles: list[str]
    role_verified: bool
    content_status: str
    eligibility_reason: str | None
    method: str
    score: float
    role_status: Literal["ok", "unverified", "mismatch", "needs_role"] = "unverified"


@dataclass
class EvidenceGroup:
    parent_id: str | None
    source_id: str  # представительный chunk (лучший score в группе)
    original_ids: list[str]
    source_type: str
    source_key: str
    title: str
    text: str
    section_path: str | None
    page_from: int | None
    page_to: int | None
    version: str | None
    audience_raw: str | None
    applicable_roles: list[str]
    role_verified: bool
    content_status: str
    eligibility_reason: str | None
    method: str
    score: float


# ------------------------------------------------------------- exact/FTS + dense


def _fts_search(conn: sqlite3.Connection, normalized_query: str, limit: int) -> list[RawHit]:
    tokens = [t for t in normalized_query.split() if t]
    if not tokens:
        return []
    match = " OR ".join(f'"{t}"' for t in tokens)
    rows = conn.execute(
        "SELECT source_id, bm25(chunks_fts) AS rank FROM chunks_fts "
        "WHERE chunks_fts MATCH ? ORDER BY rank LIMIT ?",
        (match, limit),
    ).fetchall()
    # bm25() в sqlite отрицателен, и тем меньше (более отрицателен), чем
    # релевантнее строка. score = -rank: положительный, больше = релевантнее,
    # порядок сохраняется. Не вероятность (§10 «Gate»).
    return [RawHit(source_id=r["source_id"], method="fts", score=max(0.0, -r["rank"]))
            for r in rows]


def _exact_search(conn: sqlite3.Connection, identifier: str, limit: int = 20) -> list[tuple[str, float]]:
    """Точный поиск конкретного кода/аббревиатуры в FTS-индексе (нормализованном
    тем же способом, что и текст записей — без английского Porter).

    Возвращает (source_id, bm25_score) — bm25 внутри одного и того же
    точного термина сохраняет содержательную относительную ранжировку
    (одна и та же аббревиатура может встречаться в десятках чанков; без
    этого все точные хиты получили бы одинаковый score и порядок среди них
    стал бы произвольным)."""
    key = exact_identifier_fts_query(identifier)
    if not key.strip():
        return []
    tokens = [t for t in key.split() if t]
    if not tokens:
        return []
    match = " AND ".join(f'"{t}"' for t in tokens)
    rows = conn.execute(
        "SELECT source_id, bm25(chunks_fts) AS rank FROM chunks_fts "
        "WHERE chunks_fts MATCH ? ORDER BY rank LIMIT ?",
        (match, limit),
    ).fetchall()
    return [(r["source_id"], max(0.0, -r["rank"])) for r in rows]


def collect_raw_hits(
    conn: sqlite3.Connection,
    query_text: str,
    dense_index,  # knowledge.kb.dense.vectors.DenseIndex | None
    encoder,  # knowledge.kb.dense.encoder.QueryEncoder | None
) -> tuple[list[RawHit], list[str]]:
    """Собрать сырые хиты exact/FTS/dense. Возвращает (hits, unknown_identifiers).

    `unknown_identifiers` — коды/аббревиатуры, распознанные в запросе, для
    которых точный поиск не дал ни одного совпадения (§10 Gate:
    «Неизвестный exact ID | CLARIFY/ESCALATE без подмены»).
    """
    hits: list[RawHit] = []
    unknown: list[str] = []

    for identifier in detect_exact_identifiers(query_text):
        found = _exact_search(conn, identifier)
        if found:
            hits.extend(
                RawHit(source_id=sid, method="exact", score=_EXACT_MATCH_SCORE + bm25_score)
                for sid, bm25_score in found
            )
        else:
            unknown.append(identifier)

    if dense_index is not None and encoder is not None and len(dense_index) > 0:
        query_vector = encoder.encode_query(query_text)
        for source_id, score in dense_index.top_k(query_vector, k=DENSE_TOP_K):
            hits.append(RawHit(source_id=source_id, method="dense", score=score))
    else:
        # Dense недоступен (нет реального индекса) — честный лексический
        # fallback вместо имитации семантического поиска.
        normalized = fts_normalize(query_text)
        hits.extend(_fts_search(conn, normalized, limit=DENSE_TOP_K))

    return hits, unknown


def dedup_hits(hits: list[RawHit]) -> list[RawHit]:
    """Один source_id — одна запись. При конфликте методов приоритет
    exact > fts > dense (точный ID точнее лексики, лексика точнее dense)."""
    best: dict[str, RawHit] = {}
    for hit in hits:
        current = best.get(hit.source_id)
        if current is None:
            best[hit.source_id] = hit
            continue
        if _METHOD_PRIORITY[hit.method] < _METHOD_PRIORITY[current.method]:
            best[hit.source_id] = hit
        elif hit.method == current.method and hit.score > current.score:
            best[hit.source_id] = hit
    return sorted(best.values(), key=lambda h: h.score, reverse=True)


# ------------------------------------------------------------------- resolve


def resolve_candidates(conn: sqlite3.Connection, hits: list[RawHit]) -> list[ResolvedCandidate]:
    if not hits:
        return []
    by_id = {h.source_id: h for h in hits}
    placeholders = ",".join("?" for _ in hits)
    rows = conn.execute(
        f"""
        SELECT source_id, parent_id, original_ids, source_type, source_key,
               title, text, section_path, page_from, page_to, version,
               audience_raw, applicable_roles, role_verified, content_status,
               eligibility_reason
        FROM chunks WHERE source_id IN ({placeholders})
        """,
        list(by_id.keys()),
    ).fetchall()
    import json as _json

    resolved: list[ResolvedCandidate] = []
    for row in rows:
        hit = by_id[row["source_id"]]
        resolved.append(
            ResolvedCandidate(
                source_id=row["source_id"],
                parent_id=row["parent_id"],
                original_ids=_json.loads(row["original_ids"] or "[]"),
                source_type=row["source_type"],
                source_key=row["source_key"],
                title=row["title"],
                text=row["text"] or "",
                section_path=row["section_path"],
                page_from=row["page_from"],
                page_to=row["page_to"],
                version=row["version"],
                audience_raw=row["audience_raw"],
                applicable_roles=_json.loads(row["applicable_roles"] or "[]"),
                role_verified=bool(row["role_verified"]),
                content_status=row["content_status"],
                eligibility_reason=row["eligibility_reason"],
                method=hit.method,
                score=hit.score,
            )
        )
    return resolved


# --------------------------------------------------------------- role gating


def apply_role_gate(
    candidates: list[ResolvedCandidate], confirmed_facts: dict[str, object]
) -> None:
    """Заполнить `role_status` каждого кандидата на месте (§10.4/классификация C02)."""
    known_role = confirmed_facts.get("role")
    for cand in candidates:
        if not cand.role_verified:
            cand.role_status = "unverified"
            continue
        if not cand.applicable_roles:
            cand.role_status = "unverified"
            continue
        if known_role is None:
            cand.role_status = "needs_role"
        elif known_role in cand.applicable_roles:
            cand.role_status = "ok"
        else:
            cand.role_status = "mismatch"


# ---------------------------------------------------------- parent expansion


def expand_to_evidence_groups(
    conn: sqlite3.Connection, candidates: list[ResolvedCandidate]
) -> list[EvidenceGroup]:
    """Сгруппировать пригодные chunks по parent_id, взять текст parent —
    несколько chunks одной статьи схлопываются в одно evidence, а не
    считаются несколькими независимыми подтверждениями (§10 Gate)."""
    if not candidates:
        return []
    parent_ids = {c.parent_id for c in candidates if c.parent_id}
    parents: dict[str, sqlite3.Row] = {}
    if parent_ids:
        placeholders = ",".join("?" for _ in parent_ids)
        rows = conn.execute(
            f"SELECT parent_id, title, text, section_path, page_from, page_to "
            f"FROM parents WHERE parent_id IN ({placeholders})",
            list(parent_ids),
        ).fetchall()
        parents = {r["parent_id"]: r for r in rows}

    groups: dict[str, list[ResolvedCandidate]] = {}
    order: list[str] = []
    for cand in candidates:
        key = cand.parent_id or f"__no_parent__:{cand.source_id}"
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(cand)

    result: list[EvidenceGroup] = []
    for key in order:
        members = groups[key]
        best = max(members, key=lambda c: c.score)
        worst_status = max(members, key=lambda c: _STATUS_RANK[c.content_status])
        parent_row = parents.get(best.parent_id) if best.parent_id else None
        if parent_row is not None:
            text = parent_row["text"]
            title = parent_row["title"] or best.title
            section_path = parent_row["section_path"] or best.section_path
            page_from = parent_row["page_from"] or best.page_from
            page_to = parent_row["page_to"] or best.page_to
        else:
            text = best.text
            title = best.title
            section_path = best.section_path
            page_from = best.page_from
            page_to = best.page_to
        result.append(
            EvidenceGroup(
                parent_id=best.parent_id,
                source_id=best.source_id,
                original_ids=sorted({oid for c in members for oid in c.original_ids}),
                source_type=best.source_type,
                source_key=best.source_key,
                title=title,
                text=text,
                section_path=section_path,
                page_from=page_from,
                page_to=page_to,
                version=best.version,
                audience_raw=best.audience_raw,
                applicable_roles=best.applicable_roles,
                role_verified=best.role_verified,
                content_status=worst_status.content_status,
                eligibility_reason=worst_status.eligibility_reason,
                method=best.method,
                score=best.score,
            )
        )
    result.sort(key=lambda g: g.score, reverse=True)
    return result


def detect_known_conflict(groups: list[EvidenceGroup]) -> bool:
    """Явный конфликт версий одного и того же источника среди финалистов."""
    by_key: dict[str, set[str]] = {}
    for g in groups:
        if not g.version:
            continue
        by_key.setdefault(g.source_key, set()).add(g.version)
    return any(len(versions) > 1 for versions in by_key.values())


# --------------------------------------------------------------------- gate


def _is_out_of_scope(query_text: str) -> bool:
    """Узкий сигнал: запрос без единого содержательного токена (приветствие,
    пустая строка). Полная классификация темы — C04, здесь не имитируется."""
    tokens = [t.lower() for t in fts_tokens(query_text)]
    meaningful = [t for t in tokens if t not in _STOPWORDS and len(t) > 1]
    return len(meaningful) == 0


@dataclass
class GateOutcome:
    decision: GateDecision
    reason_codes: list[ReasonCode] = field(default_factory=list)
    missing_fact: MissingFact | None = None
    evidence: list[EvidenceGroup] = field(default_factory=list)


def decide_gate(
    query_text: str,
    groups: list[EvidenceGroup],
    role_blocked_needs_role: bool,
    role_blocked_mismatch: bool,
    unknown_identifiers: list[str],
    clarification_count: int,
) -> GateOutcome:
    if _is_out_of_scope(query_text):
        return GateOutcome(decision=GateDecision.OUT_OF_SCOPE, reason_codes=[ReasonCode.OUT_OF_SCOPE])

    exhausted = clarification_count >= CLARIFICATION_MAX_COUNT

    if unknown_identifiers:
        if exhausted:
            return GateOutcome(
                decision=GateDecision.ESCALATE,
                reason_codes=[ReasonCode.UNKNOWN_IDENTIFIER, ReasonCode.UNRESOLVED_AFTER_STEPS],
            )
        return GateOutcome(
            decision=GateDecision.CLARIFY,
            reason_codes=[ReasonCode.UNKNOWN_IDENTIFIER],
            missing_fact=MissingFact(
                key="identifier",
                question=(
                    "Уточните, пожалуйста, точный код/номер/аббревиатуру, "
                    f"которую вы имеете в виду ({', '.join(unknown_identifiers)})."
                ),
            ),
        )

    if detect_known_conflict(groups):
        return GateOutcome(decision=GateDecision.ESCALATE, reason_codes=[ReasonCode.KNOWN_CONFLICT])

    complete = [g for g in groups if g.content_status == "complete"]

    if not groups:
        if role_blocked_needs_role:
            if exhausted:
                return GateOutcome(
                    decision=GateDecision.ESCALATE,
                    reason_codes=[ReasonCode.ROLE_REQUIRED, ReasonCode.UNRESOLVED_AFTER_STEPS],
                )
            return GateOutcome(
                decision=GateDecision.CLARIFY,
                reason_codes=[ReasonCode.ROLE_REQUIRED],
                missing_fact=MissingFact(
                    key="role", question="Уточните, пожалуйста, вы поставщик или заказчик?"
                ),
            )
        if role_blocked_mismatch:
            return GateOutcome(decision=GateDecision.ESCALATE, reason_codes=[ReasonCode.ROLE_MISMATCH])
        return GateOutcome(decision=GateDecision.ESCALATE, reason_codes=[ReasonCode.NO_EVIDENCE])

    if not complete:
        reasons: list[ReasonCode] = []
        if any(g.content_status == "incomplete" for g in groups):
            reasons.append(ReasonCode.MISSING_ATTACHMENT)
        if any(g.content_status == "pointer" for g in groups):
            reasons.append(ReasonCode.NO_EVIDENCE)
        return GateOutcome(decision=GateDecision.ESCALATE, reason_codes=reasons or [ReasonCode.NO_EVIDENCE])

    selected = complete[:EVIDENCE_MAX]
    return GateOutcome(decision=GateDecision.ANSWER_ALLOWED, reason_codes=[], evidence=selected)


# ------------------------------------------------------------------ orchestrator


def run_pipeline(
    conn: sqlite3.Connection,
    snapshot_id: str | None,
    query: QueryContext,
    dense_index,
    encoder,
) -> KnowledgeResult:
    raw_hits, unknown_identifiers = collect_raw_hits(conn, query.text, dense_index, encoder)
    deduped = dedup_hits(raw_hits)
    candidates = resolve_candidates(conn, deduped)
    apply_role_gate(candidates, query.confirmed_facts)

    role_blocked_needs_role = any(c.role_status == "needs_role" for c in candidates)
    role_blocked_mismatch = any(c.role_status == "mismatch" for c in candidates)
    eligible = [c for c in candidates if c.role_status in ("ok", "unverified")]

    groups = expand_to_evidence_groups(conn, eligible)
    outcome = decide_gate(
        query.text,
        groups,
        role_blocked_needs_role=role_blocked_needs_role and not eligible,
        role_blocked_mismatch=role_blocked_mismatch and not eligible,
        unknown_identifiers=unknown_identifiers,
        clarification_count=query.clarification_count,
    )

    all_groups_for_candidates = groups if groups else expand_to_evidence_groups(conn, candidates)
    evidence_items: list[EvidenceItem] = []
    selected_ids: list[str] = []
    selected_group_ids = {id(g) for g in outcome.evidence}
    for i, g in enumerate(all_groups_for_candidates):
        evidence_id = f"ev:{query.trace_id}:{i}"
        evidence_items.append(
            EvidenceItem(
                evidence_id=evidence_id,
                source_id=g.source_id,
                original_ids=g.original_ids,
                parent_id=g.parent_id,
                source_type=g.source_type,
                title=g.title,
                version=g.version,
                source_date=None,
                section_path=g.section_path,
                page_from=g.page_from,
                page_to=g.page_to,
                text=g.text,
                conditions=[],
                audience_raw=g.audience_raw,
                applicable_roles=g.applicable_roles,
                role_verified=g.role_verified,
                content_status=g.content_status,
                eligibility_reason=g.eligibility_reason,
                retrieval_method=g.method,
                score=g.score,
            )
        )
        if id(g) in selected_group_ids:
            selected_ids.append(evidence_id)

    return KnowledgeResult(
        snapshot_id=snapshot_id,
        candidates=evidence_items,
        selected_evidence_ids=selected_ids,
        decision=outcome.decision,
        missing_fact=outcome.missing_fact,
        reason_codes=outcome.reason_codes,
        card_id=None,
        route=RoutingResult(),
        timings_ms={},
    )
