"""Схема read-only снимка knowledge.sqlite.

Снимок собирается C02 и в runtime открывается только на чтение
(AGENTS.md: «Runtime KB read-only»). Embeddings в снимке нет — их
строит C03 отдельным артефактом.
"""

from __future__ import annotations

SCHEMA_VERSION = "c02-schema-1.0.0"

DDL = """
PRAGMA journal_mode = DELETE;

-- Родительские единицы: статья портала, секция PDF, секция Регламента.
CREATE TABLE parents (
    parent_id     TEXT PRIMARY KEY,
    source_type   TEXT NOT NULL,
    source_key    TEXT NOT NULL,
    source_name   TEXT NOT NULL,
    title         TEXT NOT NULL,
    section_path  TEXT,
    page_from     INTEGER,
    page_to       INTEGER,
    child_count   INTEGER NOT NULL,
    text          TEXT NOT NULL
);

-- Дочерние чанки: единица цитирования и будущего embedding.
CREATE TABLE chunks (
    source_id         TEXT PRIMARY KEY,
    parent_id         TEXT REFERENCES parents(parent_id),
    original_ids      TEXT NOT NULL,      -- JSON-массив id исходного снимка
    source_type       TEXT NOT NULL,      -- portal_kb | organizer_pdf | reglament
    source_key        TEXT NOT NULL,
    source_name       TEXT NOT NULL,
    title             TEXT NOT NULL,
    title_rebuilt     TEXT,               -- причина пересборки заголовка либо NULL
    raw_title         TEXT,
    text              TEXT NOT NULL,
    section_path      TEXT,
    page_from         INTEGER,
    page_to           INTEGER,
    version           TEXT,
    -- url/source_date намеренно отсутствуют: в снимке нет ни адреса статьи,
    -- ни даты актуальности (BL-C00-5). Выдуманные значения запрещены.
    collected_at      TEXT,               -- бывш. updated_at: момент выгрузки
    collection_endpoint TEXT,             -- бывш. source_url: endpoint API коллекции
    audience_raw      TEXT,
    applicable_roles  TEXT NOT NULL,      -- JSON-массив
    role_verified     INTEGER NOT NULL,
    content_status    TEXT NOT NULL,      -- complete | pointer | incomplete
    eligibility_reason TEXT,
    topic_raw         TEXT,
    subtopic_raw      TEXT,
    ord               INTEGER NOT NULL    -- детерминированный порядок сборки
);

-- Исключённые записи хранятся вместе с причиной, а не молча удаляются.
CREATE TABLE excluded (
    original_id   TEXT PRIMARY KEY,
    source_type   TEXT NOT NULL,
    source_key    TEXT NOT NULL,
    raw_title     TEXT,
    raw_content   TEXT NOT NULL,
    reason        TEXT NOT NULL
);

-- Лексический индекс. Содержимое уже приведено единой русской
-- нормализацией (knowledge/kb/normalize.py), поэтому токенизатор здесь
-- намеренно простой: морфологию делает не он.
CREATE VIRTUAL TABLE chunks_fts USING fts5(
    source_id UNINDEXED,
    title_norm,
    text_norm,
    tokenize = 'unicode61 remove_diacritics 0'
);

CREATE TABLE manifest (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX idx_chunks_parent  ON chunks(parent_id);
CREATE INDEX idx_chunks_type    ON chunks(source_type);
CREATE INDEX idx_chunks_status  ON chunks(content_status);
CREATE INDEX idx_chunks_key     ON chunks(source_key);
"""
