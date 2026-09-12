"""Доступная в C02 часть KnowledgePort: get_source, health, get_card.

Область C02 — ingest и source lookup. Dense retrieval и evidence gate
принадлежат C03, поэтому `retrieve` здесь намеренно не реализован: он
поднимает NotImplementedError вместо того, чтобы вернуть правдоподобный
KnowledgeResult. Пустой результат с решением gate выглядел бы как
состоявшийся поиск и как принятое решение gate — ни того, ни другого C02
не делает.

Импорт backend отсутствует (критерий A00: KnowledgePort не зависит от
backend). Пакет contracts импортируется от корня репозитория — см.
CR-EDUARD-001, отдельный CR на то же не создаётся.
"""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Any

from contracts.python.tenderhack_contracts.models import (  # noqa: E402
    KnowledgeHealth,
    ScenarioCard,
    SourceRecord,
)

__all__ = ["SqliteKnowledgeStore", "open_store", "DEFAULT_SNAPSHOT_DIR"]

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_SNAPSHOT_DIR = os.path.join(REPO_ROOT, "var", "knowledge")

_EXCERPT_CHARS = 400


class SqliteKnowledgeStore:
    """Read-only доступ к снимку knowledge.sqlite.

    Соединение открывается в режиме `mode=ro`: runtime KB read-only
    (AGENTS.md). Отсутствие файла снимка не является ошибкой — это
    состояние `unavailable`, которое честно сообщается через health().
    """

    def __init__(self, snapshot_dir: str = DEFAULT_SNAPSHOT_DIR) -> None:
        self.snapshot_dir = snapshot_dir
        self.db_path = os.path.join(snapshot_dir, "knowledge.sqlite")
        self.manifest_path = os.path.join(snapshot_dir, "manifest.json")
        self._conn: sqlite3.Connection | None = None
        self._manifest: dict[str, Any] | None = None
        self._reason: str | None = None
        self._open()

    # ------------------------------------------------------------------ инфра

    def _open(self) -> None:
        if not os.path.exists(self.db_path):
            self._reason = f"snapshot not found: {self.db_path}"
            return
        try:
            self._conn = sqlite3.connect(
                f"file:{self.db_path}?mode=ro", uri=True, check_same_thread=False
            )
            self._conn.row_factory = sqlite3.Row
        except sqlite3.Error as exc:
            self._reason = f"snapshot open failed: {exc}"
            return
        if os.path.exists(self.manifest_path):
            with open(self.manifest_path, encoding="utf-8") as fh:
                self._manifest = json.load(fh)
        else:
            row = self._conn.execute(
                "SELECT value FROM manifest WHERE key = 'snapshot_id'"
            ).fetchone()
            self._manifest = {"snapshot_id": json.loads(row[0])} if row else {}

    @property
    def snapshot_id(self) -> str | None:
        return (self._manifest or {}).get("snapshot_id")

    @property
    def available(self) -> bool:
        return self._conn is not None

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------- KnowledgePort

    async def get_source(self, source_id: str) -> SourceRecord | None:
        """Открыть источник по source_id. Отсутствующий -> None."""
        if self._conn is None:
            return None
        row = self._conn.execute(
            """
            SELECT source_id, source_type, title, text, version, section_path,
                   page_from, page_to, applicable_roles, content_status
            FROM chunks WHERE source_id = ?
            """,
            (source_id,),
        ).fetchone()
        if row is None:
            return None
        text = row["text"] or ""
        excerpt = text if len(text) <= _EXCERPT_CHARS else text[:_EXCERPT_CHARS].rstrip() + "…"
        return SourceRecord(
            source_id=row["source_id"],
            source_type=row["source_type"],
            title=row["title"],
            excerpt=excerpt,
            version=row["version"],
            # Реальной даты актуальности в снимке нет (BL-C00-5): у портала
            # updated_at — один момент выгрузки на все записи, у PDF пусто.
            source_date=None,
            section_path=row["section_path"],
            page_from=row["page_from"],
            page_to=row["page_to"],
            # Адреса статьи в снимке нет: source_url — endpoint API коллекции.
            url=None,
            file_url=None,
            conditions=[],
            applicable_roles=json.loads(row["applicable_roles"] or "[]"),
            content_status=row["content_status"],
        )

    async def get_card(self, card_id: str) -> ScenarioCard | None:
        """Карточек сценариев в снимке нет.

        `content/cards` содержит только README, reviewed-карточек не
        существует. Возвращается None — это фиксированное ограничение
        C02, а не заглушка с выдуманной карточкой.
        """
        return None

    async def health(self) -> KnowledgeHealth:
        """Состояние KB. mode=lexical_only: снимок и FTS есть, dense нет."""
        if self._conn is None:
            return KnowledgeHealth(
                available=False,
                mode="unavailable",
                snapshot_id=None,
                reason=self._reason or "snapshot unavailable",
            )
        return KnowledgeHealth(
            available=True,
            mode="lexical_only",
            snapshot_id=self.snapshot_id,
            reason=(
                "C02: снимок и лексическая нормализация готовы; dense retrieval "
                "и evidence gate не реализованы (зона C03), embeddings не строились"
            ),
        )

    async def retrieve(self, query: Any) -> Any:
        """Не реализовано в C02 — принадлежит C03.

        Сознательно поднимает исключение, а не возвращает пустой
        KnowledgeResult: пустой результат с полем decision выглядел бы как
        выполненный поиск и принятое решение gate.
        """
        raise NotImplementedError(
            "retrieve() — зона C03 (dense retrieval и evidence gate). "
            "C02 предоставляет только get_source/get_card/health. "
            f"health().mode = 'lexical_only', snapshot_id = {self.snapshot_id!r}."
        )

    # ------------------------------------------------------- вспомогательное чтение

    def lexical_search(self, normalized_query: str, limit: int = 10) -> list[str]:
        """Отладочный лексический поиск по FTS. Не retrieval и не gate:
        возвращает только source_id, без score, evidence и решения."""
        if self._conn is None or not normalized_query.strip():
            return []
        tokens = [t for t in normalized_query.split() if t]
        if not tokens:
            return []
        match = " OR ".join(f'"{t}"' for t in tokens)
        rows = self._conn.execute(
            "SELECT source_id FROM chunks_fts WHERE chunks_fts MATCH ? LIMIT ?",
            (match, limit),
        ).fetchall()
        return [r["source_id"] for r in rows]


def open_store(snapshot_dir: str = DEFAULT_SNAPSHOT_DIR) -> SqliteKnowledgeStore:
    """Фабрика для A02/A03: внедряется как реализация KnowledgePort."""
    return SqliteKnowledgeStore(snapshot_dir)
