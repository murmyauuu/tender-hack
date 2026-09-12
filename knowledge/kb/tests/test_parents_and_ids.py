"""Parent links портала и PDF, near-duplicates, стабильность ID."""

from __future__ import annotations

import collections
import hashlib
import os
import re

from knowledge.kb import ingest as ingest_mod


# ------------------------------------------------------------------ портал


def test_portal_parent_comes_from_article_id(conn, raw_rows):
    """Parent портальной части — article_id из source_key (C00: 480)."""
    article_ids = {
        re.match(r"portal_api:(\d+):\d+$", r["source_key"]).group(1)
        for r in raw_rows
        if r["source_type"] == "portal_knowledge_base_api"
        and re.match(r"portal_api:(\d+):\d+$", r["source_key"])
    }
    assert len(article_ids) == 480
    parents = conn.execute(
        "SELECT COUNT(*) FROM parents WHERE source_type='portal_kb'"
    ).fetchone()[0]
    assert parents == 480
    for row in conn.execute(
        "SELECT source_id, parent_id FROM chunks WHERE source_type='portal_kb'"
    ):
        assert row["parent_id"] == row["source_id"].rsplit(":", 1)[0]


def test_multichunk_articles_are_grouped(conn):
    """36 многочанковых статей (C00) собраны под одним parent."""
    multi = conn.execute(
        "SELECT COUNT(*) FROM parents WHERE source_type='portal_kb' AND child_count > 1"
    ).fetchone()[0]
    assert multi == 36


def test_every_portal_chunk_resolves_to_an_existing_parent(conn):
    orphans = conn.execute(
        "SELECT COUNT(*) FROM chunks c WHERE c.source_type='portal_kb' "
        "AND NOT EXISTS (SELECT 1 FROM parents p WHERE p.parent_id = c.parent_id)"
    ).fetchone()[0]
    assert orphans == 0


# --------------------------------------------------------------------- PDF


def test_pdf_chunking_stays_within_one_page(conn):
    """Чанкинг PDF строго постраничный: границу страницы не пересекает."""
    crossing = conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE source_type='organizer_pdf' "
        "AND page_from IS NOT NULL AND page_to IS NOT NULL AND page_from <> page_to"
    ).fetchone()[0]
    assert crossing == 0


def test_pdf_sections_are_restored_from_the_document_toc(conn):
    with_section = conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE source_type='organizer_pdf' "
        "AND section_path IS NOT NULL"
    ).fetchone()[0]
    assert with_section > 800, "секции восстановлены для подавляющего большинства страниц"
    sample = conn.execute(
        "SELECT section_path FROM chunks WHERE source_key='supplier_instruction' "
        "AND section_path LIKE '%/%' LIMIT 1"
    ).fetchone()
    assert sample and " / " in sample["section_path"], "путь секции иерархичен"


def test_unknown_section_stays_null_instead_of_guessed(conn):
    """Страница до первого раздела оглавления не получает выдуманную секцию."""
    nulls = conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE source_type='organizer_pdf' "
        "AND section_path IS NULL"
    ).fetchone()[0]
    assert nulls > 0, "неизвестное остаётся NULL, а не заполняется догадкой"


def test_reglament_pages_are_real(conn):
    """Страницы Регламента фактические, в пределах 57."""
    rows = conn.execute(
        "SELECT page_from, page_to FROM chunks WHERE source_type='reglament'"
    ).fetchall()
    assert rows, "Регламент загружен (BL-C00-1)"
    for row in rows:
        assert 1 <= row["page_from"] <= row["page_to"] <= 57


# ------------------------------------------------------------ near-duplicates


def test_near_duplicates_are_not_collapsed(conn):
    """156 повторяющихся заголовков (C00) остаются отдельными записями."""
    titles = [r["raw_title"] for r in conn.execute("SELECT raw_title FROM chunks")]
    repeated = [t for t, n in collections.Counter(titles).items() if t and n > 1]
    assert repeated, "повторяющиеся заголовки сохранены, а не схлопнуты"
    ids = [r["source_id"] for r in conn.execute("SELECT source_id FROM chunks")]
    assert len(ids) == len(set(ids)), "source_id уникальны"


def test_exact_duplicate_content_count_is_unchanged(raw_rows):
    """В снимке 0 точных дублей content (C00) — схлопывать нечего."""
    contents = [r["content"] for r in raw_rows]
    assert len(contents) - len(set(contents)) == 0


# ------------------------------------------------------------ стабильность ID


def test_two_ingest_runs_produce_identical_ids_and_hashes(tmp_path):
    """Приёмка: два прогона дают одинаковые ID и одинаковые хеши артефактов."""
    import sqlite3

    def build(target: str) -> tuple[str, list[str]]:
        ingest_mod.run(target)
        db = os.path.join(target, "knowledge.sqlite")
        digest = hashlib.sha256(open(db, "rb").read()).hexdigest()
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        ids = [r[0] for r in conn.execute("SELECT source_id FROM chunks ORDER BY source_id")]
        conn.close()
        return digest, ids

    first_hash, first_ids = build(str(tmp_path / "run1"))
    second_hash, second_ids = build(str(tmp_path / "run2"))
    assert first_ids == second_ids, "ID нестабильны между прогонами"
    assert first_hash == second_hash, "SHA-256 снимка нестабилен между прогонами"


def test_ids_are_derived_from_stable_keys(conn):
    for row in conn.execute("SELECT source_id, source_type FROM chunks LIMIT 200"):
        sid, stype = row["source_id"], row["source_type"]
        if stype == "portal_kb":
            assert re.fullmatch(r"portal:\d+:\d+", sid)
        elif stype == "organizer_pdf":
            assert re.fullmatch(r"pdf:[a-z_]+:p\d+:\d+", sid)
        else:
            assert re.fullmatch(r"reglament:s\d{3}:c\d{2}", sid)
