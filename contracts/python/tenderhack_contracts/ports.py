from __future__ import annotations

from typing import Protocol

from .models import (
    GenerationInput,
    GenerationProposal,
    KnowledgeHealth,
    KnowledgeResult,
    PolicyResult,
    QueryContext,
    ScenarioCard,
    SourceRecord,
)


class PolicyPort(Protocol):
    def check(self, text: str) -> PolicyResult: ...


class KnowledgePort(Protocol):
    async def retrieve(self, query: QueryContext) -> KnowledgeResult: ...

    async def get_source(self, source_id: str) -> SourceRecord | None: ...

    async def get_card(self, card_id: str) -> ScenarioCard | None: ...

    async def health(self) -> KnowledgeHealth: ...


class GeneratorPort(Protocol):
    async def generate(self, task: GenerationInput) -> GenerationProposal: ...

