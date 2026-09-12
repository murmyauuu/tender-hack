"""KnowledgePort: get_source/health/get_card (C02) + retrieve (C03).

C03 реализует dense top10 → dedup → применимость/роль/версия → parent
expansion → gate (`knowledge/kb/retrieval.py`). Query encoder — mock на M
(нет GPU/torch, помечен `is_mock=True`, `health().mode` остаётся
`lexical_only`); реальный forward-pass модели живёт отдельно в
`knowledge/kb/gpu/` (профиль G) и внедряется через параметр `encoder`
конструктора — этот файл не импортирует torch/transformers.

Импорт backend отсутствует (критерий A00: KnowledgePort не зависит от
backend). Контракт импортируется из установленного публичного пакета.
"""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Any

from tenderhack_contracts.models import (
    GateDecision,
    KnowledgeHealth,
    KnowledgeResult,
    QueryContext,
    ReasonCode,
    RoutingResult,
    ScenarioCard,
    SourceRecord,
)

from knowledge.kb.dense.encoder import MockQueryEncoder
from knowledge.kb.dense.vectors import DenseIndex, index_files_exist
from knowledge.kb.retrieval import run_pipeline

__all__ = ["SqliteKnowledgeStore", "open_store", "DEFAULT_SNAPSHOT_DIR"]

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_SNAPSHOT_DIR = os.path.join(REPO_ROOT, "var", "knowledge")

_EXCERPT_CHARS = 400
_DENSE_VECTORS_FILENAME = "index.npy"
_DENSE_IDS_FILENAME = "index_ids.json"


class SqliteKnowledgeStore:
    """Read-only доступ к снимку knowledge.sqlite.

    Соединение открывается в режиме `mode=ro`: runtime KB read-only
    (AGENTS.md). Отсутствие файла снимка не является ошибкой — это
    состояние `unavailable`, которое честно сообщается через health().
    """

    def __init__(
        self, snapshot_dir: str = DEFAULT_SNAPSHOT_DIR, encoder: Any | None = None
    ) -> None:
        self.snapshot_dir = snapshot_dir
        self.db_path = os.path.join(snapshot_dir, "knowledge.sqlite")
        self.manifest_path = os.path.join(snapshot_dir, "manifest.json")
        self._conn: sqlite3.Connection | None = None
        self._manifest: dict[str, Any] | None = None
        self._reason: str | None = None
        # Encoder внедряется извне (A03) — реальный на G, mock здесь по
        # умолчанию. Реализация из knowledge/kb/gpu/* сюда не импортируется.
        self._encoder = encoder if encoder is not None else MockQueryEncoder()
        self._dense_index: DenseIndex | None = None
        self._dense_load_error: str | None = None
        self._open()
        self._load_dense_index()

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

    def _load_dense_index(self) -> None:
        """Загрузить реальный корпус dense-векторов, если G уже его собрал.

        Отсутствие файлов — не ошибка: `retrieve()` тогда работает через
        честный лексический (FTS) fallback вместо dense (см. `health()`).
        """
        if self._conn is None:
            return
        vectors_path = os.path.join(self.snapshot_dir, _DENSE_VECTORS_FILENAME)
        ids_path = os.path.join(self.snapshot_dir, _DENSE_IDS_FILENAME)
        if not index_files_exist(vectors_path, ids_path):
            self._dense_load_error = "index files not found (G embedding build not delivered yet)"
            return
        try:
            self._dense_index = DenseIndex.load(vectors_path, ids_path)
        except Exception as exc:  # noqa: BLE001 - защитная загрузка артефакта
            self._dense_load_error = f"index load failed: {exc}"

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
        """Состояние KB.

        `mode='semantic'` только когда ОБА условия реальны: корпус dense
        векторов загружен (файлы от G) И энкодер запроса не mock. Если
        корпус реальный, но энкодер mock (сегодняшнее состояние на M —
        энкодер всегда mock, потому что forward-pass модели требует
        torch/GPU, которых на M нет), режим честно остаётся
        `lexical_only`: mock-подобие НЕ выдаётся за семантический поиск.
        """
        if self._conn is None:
            return KnowledgeHealth(
                available=False,
                mode="unavailable",
                snapshot_id=None,
                reason=self._reason or "snapshot unavailable",
            )
        encoder_is_mock = bool(getattr(self._encoder, "is_mock", True))
        dense_ready = self._dense_index is not None and len(self._dense_index) > 0
        if dense_ready and not encoder_is_mock:
            mode = "semantic"
            reason = (
                f"C03: корпус dense векторов реальный ({len(self._dense_index)} строк), "
                "query encoder реальный"
            )
        elif dense_ready and encoder_is_mock:
            mode = "lexical_only"
            reason = (
                f"C03: корпус dense векторов реальный ({len(self._dense_index)} строк, "
                "получен от G), но query encoder mock (нет GPU/torch на этой машине) — "
                "dense-режим намеренно не объявляется semantic, пока энкодер mock"
            )
        else:
            mode = "lexical_only"
            reason = (
                "C03: снимок и FTS готовы; " + (self._dense_load_error or "dense index not built") +
                " — retrieve() использует лексический (FTS) fallback вместо dense"
            )
        return KnowledgeHealth(
            available=True,
            mode=mode,
            snapshot_id=self.snapshot_id,
            reason=reason,
        )

    async def retrieve(self, query: QueryContext) -> KnowledgeResult:
        """Dense top10 → dedup → применимость/роль/версия → parent expansion
        → gate (`knowledge/kb/retrieval.py`). Encoder mock на M — см. `health()`.
        """
        if self._conn is None:
            return KnowledgeResult(
                snapshot_id=None,
                candidates=[],
                selected_evidence_ids=[],
                decision=GateDecision.ESCALATE,
                missing_fact=None,
                reason_codes=[ReasonCode.SEARCH_UNAVAILABLE],
                card_id=None,
                route=RoutingResult(),
                timings_ms={},
            )
        return run_pipeline(
            self._conn, self.snapshot_id, query, self._dense_index, self._encoder
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


def open_store(
    snapshot_dir: str = DEFAULT_SNAPSHOT_DIR, encoder: Any | None = None
) -> SqliteKnowledgeStore:
    """Фабрика для A02/A03: внедряется как реализация KnowledgePort.

    `encoder` — точка расширения для A03: когда на машине развёртывания
    появится реальный query encoder (torch/transformers, вне knowledge/kb),
    его можно внедрить сюда без изменений в этом модуле.
    """
    return SqliteKnowledgeStore(snapshot_dir, encoder=encoder)
