import asyncio

from tenderhack_backend.fakes import FakeGenerator, FakeKnowledge, FakePolicy
from tenderhack_contracts import GenerationAnswer, GenerationInput, QueryContext


def test_fake_ports_are_deterministic_and_count_calls() -> None:
    policy = FakePolicy()
    knowledge = FakeKnowledge()
    generator = FakeGenerator(
        proposal=GenerationAnswer(
            summary="Тестовый ответ",
            conditions=[],
            steps=["Тестовый шаг"],
            source_ids=["source-demo"],
        )
    )

    policy.check("обычный вопрос")
    asyncio.run(
        knowledge.retrieve(
            QueryContext(
                text="обычный вопрос",
                confirmed_facts={},
                recent_user_messages=[],
                clarification_count=0,
                trace_id="trace-demo",
            )
        )
    )
    proposal = asyncio.run(
        generator.generate(
            GenerationInput(
                question="обычный вопрос",
                confirmed_facts={},
                evidence=[],
                allowed_source_ids=["source-demo"],
            )
        )
    )

    assert proposal.action == "answer"
    assert policy.calls == 1
    assert knowledge.retrieve_calls == 1
    assert generator.calls == 1
