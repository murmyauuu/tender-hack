"""Удаление служебных fragments, заголовки, роли, полнота, отсутствие выдумок."""

from __future__ import annotations

import json
import re

from knowledge.kb.classify import attachment_status, derive_roles, service_fragment_reason


# ------------------------------------------- служебные fragments и короткий текст


def test_every_excluded_row_has_a_reason(conn):
    rows = conn.execute("SELECT original_id, reason FROM excluded").fetchall()
    assert rows, "исключённые записи обязаны сохраняться вместе с причиной"
    for row in rows:
        assert row["reason"].strip(), f"причина пуста: {row['original_id']}"


def test_excluded_classes_match_c00(conn):
    counts = dict(
        conn.execute(
            "SELECT CASE WHEN reason LIKE 'content_is_table_of_contents%' "
            "THEN 'toc' ELSE 'page_number' END, COUNT(*) FROM excluded GROUP BY 1"
        ).fetchall()
    )
    # C00/D5: оглавления 27, «только номер страницы» 17 (одна запись входит
    # в оба класса, поэтому объединение — 43, а не 44).
    assert counts["toc"] == 27
    assert counts["page_number"] == 17  # 16 из снимка + 1 дочитанная пустая стр. 3


def test_page_number_only_is_removed():
    assert service_fragment_reason("3", "") == "content_is_page_number_only"
    assert service_fragment_reason("  12  ", "") == "content_is_page_number_only"


def test_table_of_contents_is_removed():
    toc = "Термины и сокращения ................................ 4"
    assert service_fragment_reason(toc, "") == "content_is_table_of_contents"


def test_short_but_meaningful_records_survive(conn, raw_rows):
    """57 коротких портальных записей содержательны и обязаны остаться.

    Порог по длине единственным критерием не является.
    """
    short = [
        r for r in raw_rows
        if r["source_type"] == "portal_knowledge_base_api" and len(r["content"].strip()) < 200
    ]
    assert len(short) == 57, "замер C00: 57 коротких портальных записей"
    kept = conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE source_type='portal_kb'"
    ).fetchone()[0]
    assert kept == 527, "ни одна портальная запись не удалена"
    for row in short:
        assert service_fragment_reason(row["content"], row["title"]) is None


def test_ellipsis_in_body_is_not_a_table_of_contents():
    """«и т.д.» — содержание, а не оглавление: три точки не критерий."""
    body = "Если ваша система управления прайс-листом (1с, интернет-магазин и т.д.) позволяет"
    assert service_fragment_reason(body, "") is None


# ------------------------------------------------------------------- заголовки


def test_filename_titles_are_rebuilt(conn):
    bad = conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE title LIKE '%.pdf' OR title LIKE '%.xlsx'"
    ).fetchone()[0]
    assert bad == 0, "имя файла не может быть заголовком (C00/D8: 27 записей)"


def test_rebuilt_titles_record_their_reason(conn):
    rows = conn.execute(
        "SELECT raw_title, title, title_rebuilt FROM chunks WHERE title_rebuilt IS NOT NULL"
    ).fetchall()
    assert rows, "пересобранные заголовки обязаны быть помечены причиной"
    for row in rows:
        assert row["title_rebuilt"] in {
            "title_was_filename", "title_was_toc_line", "title_was_version_stamp",
            "title_was_empty", "title_too_short",
        } or row["title_rebuilt"].endswith("_no_replacement_in_content")


def test_no_dot_leaders_left_in_titles(conn):
    rows = conn.execute("SELECT title FROM chunks").fetchall()
    assert not [r for r in rows if re.search(r"\.{4,}", r["title"])]


# ----------------------------------------------------------------------- роли


def test_audience_raw_is_preserved(conn, raw_rows):
    raw_values = {r["audience"] for r in raw_rows if r["audience"]}
    stored = {
        r["audience_raw"]
        for r in conn.execute(
            "SELECT DISTINCT audience_raw FROM chunks WHERE audience_raw IS NOT NULL"
        )
    }
    assert stored <= raw_values and stored, "audience_raw хранится как есть"


def test_instruction_is_not_a_role(conn):
    rows = conn.execute(
        "SELECT applicable_roles, role_verified FROM chunks WHERE audience_raw = 'instruction'"
    ).fetchall()
    assert rows, "в снимке 192 записи с audience=instruction"
    for row in rows:
        assert json.loads(row["applicable_roles"]) == []
        assert row["role_verified"] == 0
    assert derive_roles("instruction") == ([], False)


def test_general_and_empty_do_not_mean_all_roles():
    assert derive_roles("general") == ([], False)
    assert derive_roles("") == ([], False)
    assert derive_roles(None) == ([], False)


def test_real_roles_are_verified():
    assert derive_roles("supplier") == (["supplier"], True)
    assert derive_roles("supplier,customer") == (["customer", "supplier"], True)


# ------------------------------------------------- pointer / incomplete / вложения


def test_missing_figure_marks_incomplete(conn):
    count = conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE content_status='incomplete'"
    ).fetchone()[0]
    assert count >= 700, "C00/D6: 776 чанков ссылаются на отсутствующие рисунки"
    status, reason = attachment_status("См. Рисунок 35 – Страница «Обучение»")
    assert status == "incomplete" and "MISSING_ATTACHMENT" in reason


def test_pointer_is_marked_and_not_promoted(conn):
    status, reason = attachment_status("Порядок описан в Приложении 4 к настоящему Регламенту")
    assert status == "pointer" and reason.startswith("POINTER")
    rows = conn.execute(
        "SELECT eligibility_reason FROM chunks WHERE content_status='pointer'"
    ).fetchall()
    assert rows and all(r["eligibility_reason"] for r in rows)


def test_every_non_complete_chunk_explains_itself(conn):
    rows = conn.execute(
        "SELECT source_id, content_status, eligibility_reason FROM chunks "
        "WHERE content_status <> 'complete'"
    ).fetchall()
    for row in rows:
        assert row["eligibility_reason"], f"нет причины у {row['source_id']}"


# -------------------------------------------------------- никаких выдуманных данных


def test_no_invented_article_urls(conn):
    """Адрес статьи не конструируется: в снимке есть только endpoint API."""
    endpoints = {
        r["collection_endpoint"]
        for r in conn.execute(
            "SELECT DISTINCT collection_endpoint FROM chunks "
            "WHERE collection_endpoint IS NOT NULL"
        )
    }
    assert endpoints, "endpoint коллекции сохраняется под своим именем"
    for value in endpoints:
        assert "GetArticlesBySectionType" in value, "это endpoint коллекции, не статья"


def test_collected_at_is_not_a_freshness_date(conn):
    """updated_at переименован в collected_at: одна константа на 527 записей."""
    values = {
        r["collected_at"]
        for r in conn.execute(
            "SELECT DISTINCT collected_at FROM chunks WHERE collected_at IS NOT NULL"
        )
    }
    assert values == {"16.07.2026 15:01:16"}, "один момент выгрузки, не дата актуальности"


def test_schema_has_no_url_or_source_date_columns(conn):
    columns = {r[1] for r in conn.execute("PRAGMA table_info(chunks)")}
    assert "url" not in columns and "source_date" not in columns
    assert "collected_at" in columns and "collection_endpoint" in columns
