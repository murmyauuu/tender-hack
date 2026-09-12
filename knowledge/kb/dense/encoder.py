"""Query encoder: протокол + mock. Реальный forward-pass — только на G.

Все константы embedding-адаптера зафиксированы A01 (см.
`docs/coordination/artem/A01-handoff.md` на ветке `task/a01`) и переданы
буквально, без интерпретации:

* модель `Qwen/Qwen3-Embedding-0.6B`, ревизия закреплена ниже;
* query-инструкция применяется ТОЛЬКО к запросу, никогда к документам
  (§10 «Поиск»: «документы без неё»); префиксы вида E5 (`query:`/`passage:`)
  не используются — это другой адаптер;
* last-token pooling, L2-нормализация выхода, dim=1024.

`MockQueryEncoder` — детерминированная заглушка для CPU-логики на машине M
(нет GPU/torch). Она НЕ моделирует семантику: одинаковый текст даёт
одинаковый вектор, разный текст — разный, но близость двух mock-векторов
ничего не говорит о смысловой близости текстов. Использовать её результат
как признак релевантности запрещено — она нужна только чтобы прогнать
dedup/applicability/parent-expansion/gate код на реальных структурах данных
без реальной модели. `is_mock=True` — обязательный маркер, `health()`
хранилища понижает режим до `lexical_only`, пока энкодер mock (см.
`knowledge/kb/store.py`).
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

__all__ = [
    "EMBEDDING_MODEL",
    "EMBEDDING_REVISION",
    "EMBEDDING_DIM",
    "EMBEDDING_SAFETENSORS_SHA256",
    "POOLING",
    "NORMALIZATION",
    "QUERY_INSTRUCTION_TEMPLATE",
    "build_query_instruction",
    "QueryEncoder",
    "MockQueryEncoder",
]

# --- Пиновано A01, буквально -------------------------------------------------

EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-0.6B"
EMBEDDING_REVISION = "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"
EMBEDDING_DIM = 1024
EMBEDDING_SAFETENSORS_SHA256 = (
    "0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd"
)
POOLING = "last_token"
NORMALIZATION = "l2"

# Ровно строка A01. E5-префиксы (`query:`/`passage:`) не переносятся (§10).
QUERY_INSTRUCTION_TEMPLATE = (
    "Instruct: Given a web search query, retrieve relevant passages "
    "that answer the query\nQuery: {query}"
)


def build_query_instruction(query_text: str) -> str:
    """Обернуть текст запроса в query-инструкцию A01. Только для запроса."""
    return QUERY_INSTRUCTION_TEMPLATE.format(query=query_text)


class QueryEncoder(Protocol):
    """Порт для C03/A03: encode_query получает СЫРОЙ текст запроса (без
    инструкции — обёртку накладывает сама реализация, если она реальная) и
    возвращает L2-нормализованный вектор размерности `dim`."""

    dim: int
    is_mock: bool

    def encode_query(self, text: str) -> list[float]: ...


_TOKEN_RE = re.compile(r"[0-9a-zA-Zа-яёА-ЯЁ]+")


class MockQueryEncoder:
    """Детерминированный hash-based encoder. НЕ семантический. Помечен mock."""

    dim = EMBEDDING_DIM
    is_mock = True

    def encode_query(self, text: str) -> list[float]:
        tokens = _TOKEN_RE.findall((text or "").lower())
        if not tokens:
            tokens = [""]
        vec = [0.0] * self.dim
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for i in range(self.dim):
                byte = digest[i % len(digest)]
                # Знак чередуется по индексу байта, чтобы не получить
                # вырожденный всегда-положительный вектор.
                sign = 1.0 if (byte >> (i % 8)) & 1 else -1.0
                vec[i] += sign * (byte / 255.0)
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]
