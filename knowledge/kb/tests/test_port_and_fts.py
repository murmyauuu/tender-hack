"""KnowledgePort: get_source/health/get_card и русская FTS-нормализация."""

from __future__ import annotations

import asyncio

import pytest

from knowledge.kb.normalize import fts_normalize, stem_ru
from knowledge.kb.store import SqliteKnowledgeStore


# --------------------------------------------------------------- source lookup


def test_get_source_returns_a_real_record(snapshot_dir):
    store = SqliteKnowledgeStore(snapshot_dir)
    try:
        record = asyncio.run(store.get_source("portal:225874:1"))
        assert record is not None, "source обязан открываться"
        assert record.source_id == "portal:225874:1"
        assert record.title.strip() and record.excerpt.strip()
        assert record.content_status in {"complete", "pointer", "incomplete"}
    finally:
        store.close()


def test_get_source_never_invents_url_or_date(snapshot_dir):
    store = SqliteKnowledgeStore(snapshot_dir)
    try:
        for source_id in ("portal:225874:1", "reglament:s001:c01"):
            record = asyncio.run(store.get_source(source_id))
            assert record is not None
            assert record.url is None, "адреса статьи в снимке нет"
            assert record.file_url is None
            assert record.source_date is None, "даты актуальности в снимке нет"
    finally:
        store.close()


def test_get_source_returns_none_for_unknown_id(snapshot_dir):
    store = SqliteKnowledgeStore(snapshot_dir)
    try:
        assert asyncio.run(store.get_source("no-such-source")) is None
    finally:
        store.close()


def test_reglament_source_is_openable(snapshot_dir):
    """BL-C00-1: Регламент реально загружен и открывается через порт."""
    store = SqliteKnowledgeStore(snapshot_dir)
    try:
        record = asyncio.run(store.get_source("reglament:s001:c01"))
        assert record is not None and record.source_type == "reglament"
        assert record.page_from and record.page_to
    finally:
        store.close()


def test_health_reports_lexical_only(snapshot_dir, manifest):
    store = SqliteKnowledgeStore(snapshot_dir)
    try:
        health = asyncio.run(store.health())
        assert health.available is True
        assert health.mode == "lexical_only", "dense retrieval в C02 нет"
        assert health.snapshot_id == manifest["snapshot_id"]
    finally:
        store.close()


def test_health_is_unavailable_without_a_snapshot(tmp_path):
    store = SqliteKnowledgeStore(str(tmp_path / "empty"))
    health = asyncio.run(store.health())
    assert health.available is False and health.mode == "unavailable"
    assert health.reason and health.snapshot_id is None


def test_get_card_returns_none_because_no_cards_exist(snapshot_dir):
    store = SqliteKnowledgeStore(snapshot_dir)
    try:
        assert asyncio.run(store.get_card("any-card")) is None
    finally:
        store.close()


def test_retrieve_returns_a_real_knowledge_result(snapshot_dir):
    """C03: retrieve() больше не заглушка — реальный KnowledgeResult с gate."""
    from tenderhack_contracts.models import QueryContext

    store = SqliteKnowledgeStore(snapshot_dir)
    try:
        result = asyncio.run(
            store.retrieve(
                QueryContext(
                    text="Как обжаловать блокировку на Портале поставщиков?",
                    confirmed_facts={},
                    recent_user_messages=[],
                    clarification_count=0,
                    trace_id="test-trace-1",
                )
            )
        )
        assert result.decision in {"ANSWER_ALLOWED", "CLARIFY", "ESCALATE", "OUT_OF_SCOPE"}
        assert result.snapshot_id == store.snapshot_id
    finally:
        store.close()


def test_snapshot_is_opened_read_only(snapshot_dir):
    import sqlite3

    store = SqliteKnowledgeStore(snapshot_dir)
    try:
        with pytest.raises(sqlite3.OperationalError):
            store._conn.execute("DELETE FROM chunks")
    finally:
        store.close()


# ----------------------------------------------------------- русская нормализация


@pytest.mark.parametrize(
    "forms",
    [
        ("контракт", "контракта", "контракту", "контракты", "контрактам"),
        ("оферта", "оферты", "оферте", "оферту"),
        ("поставщик", "поставщика", "поставщику"),
    ],
)
def test_wordforms_collapse_to_one_key(forms):
    """C00/D12: дефолтный unicode61 давал разные ключи для словоформ."""
    stems = {stem_ru(form) for form in forms}
    assert len(stems) == 1, f"словоформы не сведены: {stems}"


def test_abbreviations_and_codes_are_not_stemmed():
    """Exact ID выделяются до морфологии: ИНН не превращается в «ин»."""
    assert fts_normalize("ИНН") == "инн"
    assert fts_normalize("СТЕ УПД КЭП") == "сте упд кэп"
    assert "yml-12" in fts_normalize("YML-12")


def test_english_porter_is_not_applied():
    """Английский Porter не подставляется вместо русской нормализации."""
    assert fts_normalize("running") == "running"
    assert fts_normalize("categories") == "categories"


def test_fts_index_finds_a_different_wordform(snapshot_dir):
    """Запрос одной словоформой находит документ с другой словоформой."""
    store = SqliteKnowledgeStore(snapshot_dir)
    try:
        hits = store.lexical_search(fts_normalize("контракты"), limit=5)
        assert hits, "лексический поиск по нормализованной форме обязан находить"
    finally:
        store.close()


def test_fts_normalization_is_idempotent():
    once = fts_normalize("Контракта и оферты поставщика")
    assert fts_normalize(once) == once, "нормализация должна быть идемпотентной"
