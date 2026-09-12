import asyncio
from pathlib import Path

import pytest
from tenderhack_backend.config import Settings
from tenderhack_contracts import (
    GateDecision,
    KnowledgeHealth,
    KnowledgeResult,
    QueryContext,
    RoutingResult,
)


class StubKnowledge:
    def __init__(self, mode: str = "semantic") -> None:
        self.mode = mode
        self.retrieve_calls = 0

    async def health(self) -> KnowledgeHealth:
        return KnowledgeHealth(
            available=self.mode != "unavailable",
            mode=self.mode,
            snapshot_id="kb-real" if self.mode != "unavailable" else None,
        )

    async def retrieve(self, query: QueryContext) -> KnowledgeResult:
        self.retrieve_calls += 1
        return KnowledgeResult(
            snapshot_id="kb-real",
            candidates=[],
            selected_evidence_ids=[],
            decision=GateDecision.ESCALATE,
            route=RoutingResult(),
        )

    async def get_source(self, source_id: str):
        return None

    async def get_card(self, card_id: str):
        return None


def query() -> QueryContext:
    return QueryContext(
        text="Как изменить реквизиты?",
        clarification_count=0,
        trace_id="trace-runtime-test",
    )


def test_settings_default_to_real_runtime_and_read_c03_paths(monkeypatch) -> None:
    monkeypatch.setenv("TENDERHACK_KNOWLEDGE_DIR", r"A:\accepted-c03")
    monkeypatch.setenv("TENDERHACK_HF_HOME", r"A:\hf-cache")
    monkeypatch.setenv("TENDERHACK_EMBEDDING_DEVICE", "cuda")

    settings = Settings.from_env()

    assert settings.runtime_mode == "real"
    assert settings.knowledge_dir == Path(r"A:\accepted-c03")
    assert settings.hf_home == Path(r"A:\hf-cache")
    assert settings.embedding_device == "cuda"


def test_lazy_encoder_points_huggingface_hub_at_accepted_cache(
    monkeypatch, tmp_path: Path
) -> None:
    from tenderhack_backend.runtime import LazyRealQwen3Encoder

    monkeypatch.delenv("HF_HOME", raising=False)
    monkeypatch.delenv("HF_HUB_CACHE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_CACHE", raising=False)

    LazyRealQwen3Encoder(device="cuda", hf_home=tmp_path)

    assert __import__("os").environ["HF_HOME"] == str(tmp_path)
    assert __import__("os").environ["HF_HUB_CACHE"] == str(tmp_path)
    assert __import__("os").environ["TRANSFORMERS_CACHE"] == str(tmp_path)


def test_real_runtime_injects_non_mock_encoder_and_configured_store(tmp_path) -> None:
    from tenderhack_backend.runtime import build_runtime_service

    captured = {}
    encoder = object()
    store = StubKnowledge()

    def encoder_factory(*, device: str, hf_home: Path):
        captured["encoder"] = (device, hf_home)
        return encoder

    def store_factory(snapshot_dir: str, *, encoder):
        captured["store"] = (snapshot_dir, encoder)
        return store

    settings = Settings(
        db_path=tmp_path / "app.sqlite",
        runtime_mode="real",
        knowledge_dir=Path(r"A:\accepted-c03"),
        hf_home=Path(r"A:\hf-cache"),
        embedding_device="cuda",
    )
    service = build_runtime_service(
        settings, encoder_factory=encoder_factory, store_factory=store_factory
    )

    assert captured["encoder"] == ("cuda", Path(r"A:\hf-cache"))
    assert captured["store"] == (r"A:\accepted-c03", encoder)
    assert service.knowledge.is_strict_semantic is True
    assert service.knowledge.encoder is encoder


def test_real_runtime_refuses_lexical_fallback() -> None:
    from tenderhack_backend.runtime import SemanticOnlyKnowledge

    store = StubKnowledge(mode="lexical_only")
    knowledge = SemanticOnlyKnowledge(store, encoder=object())

    with pytest.raises(RuntimeError, match="semantic"):
        asyncio.run(knowledge.retrieve(query()))
    assert store.retrieve_calls == 0


def test_test_runtime_is_the_only_mode_that_allows_mock_encoder(tmp_path) -> None:
    from tenderhack_backend.runtime import build_runtime_service

    captured = {}
    store = StubKnowledge(mode="lexical_only")

    def store_factory(snapshot_dir: str, *, encoder=None):
        captured["store"] = (snapshot_dir, encoder)
        return store

    settings = Settings(
        db_path=tmp_path / "app.sqlite",
        runtime_mode="test",
        knowledge_dir=tmp_path / "kb",
    )
    service = build_runtime_service(settings, store_factory=store_factory)

    assert captured["store"] == (str(tmp_path / "kb"), None)
    assert service.knowledge is store


def test_unknown_runtime_mode_fails_closed(tmp_path) -> None:
    from tenderhack_backend.runtime import build_runtime_service

    settings = Settings(db_path=tmp_path / "app.sqlite", runtime_mode="typo")
    with pytest.raises(ValueError, match="runtime mode"):
        build_runtime_service(settings)
