"""Реальный forward-pass Qwen3-Embedding-0.6B. Только для машины G.

Требует `torch` + `transformers`, которых нет на M (профиль без GPU) — этот
файл поэтому НЕ импортируется ни из `knowledge/kb/store.py`, ни из любого
другого модуля верхнего уровня `knowledge/kb/`. Его подключает только
`embed_and_smoke.py` (или, в будущем, A03 — на машине, где реально
развёрнута модель).

Все константы (модель, ревизия, dim, pooling, query-инструкция) берутся из
`knowledge.kb.dense.encoder` — единый источник истины, буквально
зафиксированный A01. Документы НЕ получают инструкцию — только запрос
(§10 «Поиск»).
"""

from __future__ import annotations

from knowledge.kb.dense.encoder import (
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    EMBEDDING_REVISION,
    QueryEncoder,
    build_query_instruction,
)

ADAPTER_VERSION = "c03-qwen3-embedding-last-token-l2-1.0.0"


def _last_token_pool(last_hidden_states, attention_mask):
    """Ровно алгоритм last-token pooling из карточки модели Qwen3-Embedding:
    при left-padding последний токен всегда на позиции -1; иначе берём
    позицию по фактической длине последовательности из attention_mask."""
    import torch  # локальный импорт: этот модуль не грузится на M

    left_padding = attention_mask[:, -1].sum() == attention_mask.shape[0]
    if left_padding:
        return last_hidden_states[:, -1]
    sequence_lengths = attention_mask.sum(dim=1) - 1
    batch_size = last_hidden_states.shape[0]
    return last_hidden_states[torch.arange(batch_size, device=last_hidden_states.device), sequence_lengths]


class RealQwen3Encoder:
    """QueryEncoder на реальной модели. Инстанцируется только на G."""

    dim = EMBEDDING_DIM
    is_mock = False

    def __init__(self, device: str = "cuda", max_length: int = 8192) -> None:
        import torch
        from transformers import AutoModel, AutoTokenizer

        self._torch = torch
        self.device = device
        self.max_length = max_length
        self.tokenizer = AutoTokenizer.from_pretrained(
            EMBEDDING_MODEL, revision=EMBEDDING_REVISION
        )
        # Обязательно left padding — иначе last-token pooling без
        # attention_mask-компенсации возьмёт не тот токен в батче.
        self.tokenizer.padding_side = "left"
        self.model = AutoModel.from_pretrained(
            EMBEDDING_MODEL, revision=EMBEDDING_REVISION
        ).to(device)
        self.model.eval()

    def _encode_raw(self, texts: list[str]) -> list[list[float]]:
        torch = self._torch
        with torch.no_grad():
            inputs = self.tokenizer(
                texts,
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt",
            ).to(self.device)
            outputs = self.model(**inputs)
            pooled = _last_token_pool(outputs.last_hidden_state, inputs["attention_mask"])
            pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
            return pooled.to("cpu").to(torch.float32).tolist()

    def encode_query(self, text: str) -> list[float]:
        """Запрос ОБОРАЧИВАЕТСЯ query-инструкцией A01. Документы — никогда."""
        instructed = build_query_instruction(text)
        return self._encode_raw([instructed])[0]

    def encode_documents(self, texts: list[str], batch_size: int = 16) -> list[list[float]]:
        """Документы БЕЗ инструкции (§10 «Поиск»: «документы без неё»)."""
        vectors: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            vectors.extend(self._encode_raw(texts[i : i + batch_size]))
        return vectors


# `RealQwen3Encoder` реализует протокол `QueryEncoder` структурно (dim,
# is_mock, encode_query) — Protocol не помечен @runtime_checkable, поэтому
# соответствие проверяется тестами на стороне G, а не isinstance/issubclass.
_ = QueryEncoder  # используется только для документации соответствия протоколу
