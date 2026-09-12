"""A05 resilience harness.

Runs the REAL backend (FastAPI app, real SQLite `Database`, real `BackendService`
queue/admission code, real `knowledge.policy` C01 adapter) as a real uvicorn HTTP
server for real-client concurrency/restart/outage testing.

The original A05 run used a non-GPU machine and therefore used the explicitly
labelled controlled/lexical modes below.  The continuation acceptance can also
select ``real_semantic`` on machine G; that mode wires the same strict C03
KnowledgePort and CUDA query encoder as the production runtime and never falls
back to lexical retrieval.

Knowledge/generator modes are chosen explicitly on the CLI:

- "controlled": an in-memory adapter with a configurable `asyncio.sleep` delay
  standing in for embedding+retrieval / generation latency, returning a fixed,
  verifier-valid answer. Used for reproducible queue/concurrency/restart/retry
  timing experiments where real GPU latency would make timing non-deterministic
  and where downloading/running an 8B model on 8 GB RAM is exactly what the
  spec says not to do.
- "real_lexical": the actual `knowledge.kb.store.open_store` reader against the
  real, C07-frozen `var/knowledge/knowledge.sqlite` snapshot with `encoder=None`
  (real lexical/FTS retrieval, `health().mode="lexical_only"` — the same honest
  degraded mode C03/C04/C07 recorded on this same machine class). Paired with
  the real `OllamaGenerator` pointed at a real (usually absent) Ollama endpoint,
  so a real model outage produces a real `MODEL_UNAVAILABLE` failure rather than
  a simulated one.
- "real_semantic": the production strict-semantic wrapper, accepted dense index,
  and real CUDA Qwen3 query encoder. It requires machine G and local artifacts.

Nothing here touches knowledge/** or config/knowledge/** on disk; it only reads
the existing gitignored var/knowledge snapshot through the accepted C03 store
reader, exactly like backend/tenderhack_backend/runtime.py does for
`runtime_mode=test`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import uvicorn
from tenderhack_contracts import (
    EvidenceItem,
    GateDecision,
    GenerationAnswer,
    GenerationInput,
    GenerationProposal,
    KnowledgeHealth,
    KnowledgeResult,
    QueryContext,
    RoutingResult,
    SourceRecord,
)

from tenderhack_backend.app import create_app
from tenderhack_backend.config import Settings
from tenderhack_backend.generator import OllamaGenerator
from tenderhack_backend.service import BackendService
from tenderhack_backend.storage import Database


class DelayedControlledKnowledge:
    """Real BackendService code path; the network/GPU-bound retrieve() call is
    replaced by a configurable sleep standing in for real embedding+retrieval
    latency (see module docstring)."""

    is_mock = True

    def __init__(self, *, delay_seconds: float) -> None:
        self.delay_seconds = delay_seconds
        self.retrieve_calls = 0
        self.evidence = EvidenceItem(
            evidence_id="evidence-a05",
            source_id="source-a05",
            source_type="portal_knowledge_base_api",
            title="A05 controlled evidence",
            text="Поставщик открывает карточку контракта в личном кабинете.",
            conditions=["Действуйте от имени поставщика."],
            applicable_roles=["supplier"],
            role_verified=True,
            content_status="complete",
            retrieval_method="dense",
            score=0.9,
        )
        self.source = SourceRecord(
            source_id="source-a05",
            source_type="portal_knowledge_base_api",
            title="A05 controlled evidence",
            excerpt=self.evidence.text,
            conditions=self.evidence.conditions,
            applicable_roles=["supplier"],
            content_status="complete",
        )

    async def retrieve(self, query: QueryContext) -> KnowledgeResult:
        del query
        self.retrieve_calls += 1
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        return KnowledgeResult(
            snapshot_id="a05-controlled",
            candidates=[self.evidence],
            selected_evidence_ids=["evidence-a05"],
            decision=GateDecision.ANSWER_ALLOWED,
            route=RoutingResult(support_line="L1", basis_source_ids=["source-a05"]),
            timings_ms={"retrieval": round(self.delay_seconds * 1000, 3)},
        )

    async def get_source(self, source_id: str) -> SourceRecord | None:
        return self.source if source_id == "source-a05" else None

    async def get_card(self, card_id: str):
        del card_id
        return None

    async def health(self) -> KnowledgeHealth:
        return KnowledgeHealth(
            available=True,
            mode="lexical_only",
            snapshot_id="a05-controlled",
            reason="A05 controlled substitute: no GPU on this machine",
        )


class DelayedControlledGenerator:
    """Real BackendService code path; the Ollama HTTP call is replaced by a
    configurable sleep standing in for real 8B-model decode latency."""

    def __init__(self, *, delay_seconds: float) -> None:
        self.delay_seconds = delay_seconds
        self.calls = 0
        self.last_timings_ms: dict[str, float] = {}

    async def health(self) -> bool:
        return True

    async def generate(self, task: GenerationInput) -> GenerationProposal:
        self.calls += 1
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        self.last_timings_ms = {"decode": round(self.delay_seconds * 1000, 3)}
        return GenerationAnswer(
            summary="Откройте карточку контракта в личном кабинете поставщика.",
            conditions=["Действуйте от имени поставщика."],
            steps=["Откройте карточку контракта в личном кабинете поставщика."],
            source_ids=list(task.allowed_source_ids),
        )


def _build_knowledge(
    mode: str,
    *,
    knowledge_dir: Path,
    delay_seconds: float,
    embedding_device: str,
    hf_home: Path,
):
    if mode == "controlled":
        return DelayedControlledKnowledge(delay_seconds=delay_seconds)
    if mode == "real_lexical":
        from knowledge.kb.store import open_store

        return open_store(str(knowledge_dir), encoder=None)
    if mode == "real_semantic":
        from knowledge.kb.store import open_store
        from tenderhack_backend.runtime import LazyRealQwen3Encoder, SemanticOnlyKnowledge

        encoder = LazyRealQwen3Encoder(device=embedding_device, hf_home=hf_home)
        store = open_store(str(knowledge_dir), encoder=encoder)
        return SemanticOnlyKnowledge(store, encoder=encoder)
    raise ValueError(f"unknown knowledge mode {mode!r}")


def _build_generator(mode: str, *, delay_seconds: float, ollama_url: str):
    if mode == "controlled":
        return DelayedControlledGenerator(delay_seconds=delay_seconds)
    if mode == "real_ollama":
        return OllamaGenerator(base_url=ollama_url, timeout_seconds=120.0)
    raise ValueError(f"unknown generator mode {mode!r}")


def build_app(
    *,
    db_path: Path,
    knowledge_mode: str,
    generator_mode: str,
    retrieval_delay: float,
    generation_delay: float,
    queue_capacity: int,
    knowledge_dir: Path,
    embedding_device: str,
    hf_home: Path,
    ollama_url: str,
    operator_reply_key: str | None,
    auto_worker: bool = True,
):
    from knowledge.policy import build_policy

    knowledge = _build_knowledge(
        knowledge_mode,
        knowledge_dir=knowledge_dir,
        delay_seconds=retrieval_delay,
        embedding_device=embedding_device,
        hf_home=hf_home,
    )
    generator = _build_generator(
        generator_mode, delay_seconds=generation_delay, ollama_url=ollama_url
    )
    service = BackendService(
        Database(db_path),
        policy=build_policy(),
        knowledge=knowledge,
        generator=generator,
        queue_capacity=queue_capacity,
    )
    settings = Settings(
        db_path=db_path,
        auto_worker=auto_worker,
        is_demo=True,
        operator_reply_key=operator_reply_key,
    )
    app = create_app(settings=settings, service=service)
    return app, service


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--db", required=True)
    parser.add_argument(
        "--knowledge",
        choices=["controlled", "real_lexical", "real_semantic"],
        default="controlled",
    )
    parser.add_argument(
        "--generator", choices=["controlled", "real_ollama"], default="controlled"
    )
    parser.add_argument("--retrieval-delay", type=float, default=0.0)
    parser.add_argument("--generation-delay", type=float, default=0.0)
    parser.add_argument("--queue-capacity", type=int, default=4)
    parser.add_argument("--knowledge-dir", default="var/knowledge")
    parser.add_argument("--hf-home", default="var/huggingface")
    parser.add_argument("--embedding-device", default="cuda")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--no-auto-worker", action="store_true")
    args = parser.parse_args()

    operator_key = os.environ.get("TENDERHACK_OPERATOR_REPLY_KEY")

    app, _service = build_app(
        db_path=Path(args.db),
        knowledge_mode=args.knowledge,
        generator_mode=args.generator,
        retrieval_delay=args.retrieval_delay,
        generation_delay=args.generation_delay,
        queue_capacity=args.queue_capacity,
        knowledge_dir=Path(args.knowledge_dir),
        embedding_device=args.embedding_device,
        hf_home=Path(args.hf_home),
        ollama_url=args.ollama_url,
        operator_reply_key=operator_key,
        auto_worker=not args.no_auto_worker,
    )
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
