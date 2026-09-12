from tenderhack_contracts import (
    GateDecision,
    GenerationEscalate,
    GenerationInput,
    GenerationProposal,
    KnowledgeHealth,
    KnowledgeResult,
    PolicyResult,
    QueryContext,
    ReasonCode,
    RoutingResult,
    ScenarioCard,
    SourceRecord,
)


class FakePolicy:
    def __init__(self, result: PolicyResult | None = None) -> None:
        self.result = result or PolicyResult(
            profanity=False,
            explicit_human_request=False,
            matched_rule_ids=[],
        )
        self.calls = 0

    def check(self, text: str) -> PolicyResult:
        del text
        self.calls += 1
        return self.result


class FakeKnowledge:
    def __init__(self, result: KnowledgeResult | None = None) -> None:
        self.result = result or KnowledgeResult(
            snapshot_id="mock-c0",
            candidates=[],
            selected_evidence_ids=[],
            decision=GateDecision.ESCALATE,
            reason_codes=[ReasonCode.NO_EVIDENCE],
            route=RoutingResult(reason_codes=[ReasonCode.NO_EVIDENCE]),
            timings_ms={},
        )
        self.sources: dict[str, SourceRecord] = {}
        self.cards: dict[str, ScenarioCard] = {}
        self.retrieve_calls = 0

    async def retrieve(self, query: QueryContext) -> KnowledgeResult:
        del query
        self.retrieve_calls += 1
        return self.result

    async def get_source(self, source_id: str) -> SourceRecord | None:
        return self.sources.get(source_id)

    async def get_card(self, card_id: str) -> ScenarioCard | None:
        return self.cards.get(card_id)

    async def health(self) -> KnowledgeHealth:
        return KnowledgeHealth(
            available=True,
            mode="semantic",
            snapshot_id=self.result.snapshot_id,
            reason=None,
        )


class FakeGenerator:
    def __init__(self, proposal: GenerationProposal | None = None) -> None:
        self.proposal = proposal or GenerationEscalate(
            reason_code=ReasonCode.MODEL_UNAVAILABLE,
            reason_text="Test fake has no configured proposal.",
        )
        self.calls = 0

    async def generate(self, task: GenerationInput) -> GenerationProposal:
        del task
        self.calls += 1
        return self.proposal

