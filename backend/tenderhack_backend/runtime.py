from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Any

from tenderhack_contracts import KnowledgeHealth, QueryContext

from .config import Settings
from .generator import OllamaGenerator
from .service import BackendService
from .storage import Database


class LazyRealQwen3Encoder:
    """Load the accepted C03 CUDA encoder only on the first real query."""

    is_mock = False

    def __init__(self, *, device: str, hf_home: Path) -> None:
        from knowledge.kb.dense.encoder import EMBEDDING_DIM

        self.dim = EMBEDDING_DIM
        self.device = device
        self.hf_home = Path(hf_home)
        self._delegate = None
        self._lock = Lock()
        self.calls = 0
        self.last_duration_ms: float | None = None
        os.environ["HF_HOME"] = str(self.hf_home)
        os.environ["HF_HUB_CACHE"] = str(self.hf_home)
        os.environ["TRANSFORMERS_CACHE"] = str(self.hf_home)
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"

    def probe(self) -> None:
        import torch

        if self.device.startswith("cuda") and not torch.cuda.is_available():
            raise RuntimeError(
                "C03 real query encoder requires an available CUDA device"
            )
        if not self.hf_home.exists():
            raise RuntimeError(f"Hugging Face cache does not exist: {self.hf_home}")

    def _load(self):
        if self._delegate is None:
            with self._lock:
                if self._delegate is None:
                    self.probe()
                    from knowledge.kb.gpu.real_encoder import RealQwen3Encoder

                    self._delegate = RealQwen3Encoder(device=self.device)
        return self._delegate

    def encode_query(self, text: str) -> list[float]:
        started = perf_counter()
        try:
            return self._load().encode_query(text)
        finally:
            self.calls += 1
            self.last_duration_ms = round((perf_counter() - started) * 1000, 3)


class SemanticOnlyKnowledge:
    """Fail closed instead of silently using C03's lexical fallback."""

    is_strict_semantic = True

    def __init__(self, delegate: Any, *, encoder: Any) -> None:
        self.delegate = delegate
        self.encoder = encoder
        self.retrieve_calls = 0
        self.last_duration_ms: float | None = None

    async def health(self) -> KnowledgeHealth:
        health = await self.delegate.health()
        if health.mode == "semantic" and hasattr(self.encoder, "probe"):
            try:
                self.encoder.probe()
            except Exception as exc:  # noqa: BLE001 - runtime dependency boundary
                return KnowledgeHealth(
                    available=False,
                    mode="unavailable",
                    snapshot_id=health.snapshot_id,
                    reason=f"real query encoder unavailable: {exc}",
                )
        return health

    async def retrieve(self, query: QueryContext):
        health = await self.health()
        if health.mode != "semantic":
            raise RuntimeError(
                f"real runtime requires semantic knowledge mode, got {health.mode}: "
                f"{health.reason or 'no reason'}"
            )
        started = perf_counter()
        try:
            result = await self.delegate.retrieve(query)
        finally:
            self.retrieve_calls += 1
            self.last_duration_ms = round((perf_counter() - started) * 1000, 3)
        timings = dict(result.timings_ms)
        timings["retrieval"] = self.last_duration_ms
        if getattr(self.encoder, "last_duration_ms", None) is not None:
            timings["query_embedding"] = self.encoder.last_duration_ms
        return result.model_copy(update={"timings_ms": timings})

    async def get_source(self, source_id: str):
        return await self.delegate.get_source(source_id)

    async def get_card(self, card_id: str):
        return await self.delegate.get_card(card_id)


EncoderFactory = Callable[..., Any]
StoreFactory = Callable[..., Any]


def _real_encoder_factory(*, device: str, hf_home: Path) -> LazyRealQwen3Encoder:
    return LazyRealQwen3Encoder(device=device, hf_home=hf_home)


def build_runtime_service(
    settings: Settings,
    *,
    encoder_factory: EncoderFactory = _real_encoder_factory,
    store_factory: StoreFactory | None = None,
) -> BackendService:
    from knowledge.kb.store import open_store
    from knowledge.policy import build_policy

    factory = store_factory or open_store
    if settings.runtime_mode == "real":
        encoder = encoder_factory(
            device=settings.embedding_device, hf_home=settings.hf_home
        )
        store = factory(str(settings.knowledge_dir), encoder=encoder)
        knowledge = SemanticOnlyKnowledge(store, encoder=encoder)
    elif settings.runtime_mode == "test":
        knowledge = factory(str(settings.knowledge_dir), encoder=None)
    else:
        raise ValueError(
            f"unsupported runtime mode {settings.runtime_mode!r}; expected 'real' or 'test'"
        )

    return BackendService(
        Database(settings.db_path),
        policy=build_policy(),
        knowledge=knowledge,
        generator=OllamaGenerator(
            base_url=settings.ollama_url,
            timeout_seconds=settings.ollama_timeout_seconds,
        ),
    )
