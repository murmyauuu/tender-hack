"""Категории: policy priority и совместимость с PolicyPort C0."""

from __future__ import annotations

import inspect

import pytest
from tenderhack_backend.fakes import FakePolicy
from tenderhack_contracts import PolicyResult, ReasonCode
from tenderhack_contracts.ports import PolicyPort

from knowledge.policy import (
    POLICY_CLOSURE_NOTICE,
    DeterministicPolicy,
    build_policy,
    reason_codes_for,
)

# ------------------------------------------------------------------ priority

PROFANITY_WITH_HANDOFF = [
    "соедините меня с оператором, блядь",
    "позовите человека, это полный пиздец",
    "мне нужен живой человек, хватит этой хуйни",
    "оператора, сука",
]


@pytest.mark.parametrize("text", PROFANITY_WITH_HANDOFF)
def test_profanity_wins_over_human_request(policy, text: str) -> None:
    """Profanity приоритетен: сообщение закрывается по policy, а не уходит в handoff."""
    result = policy.check(text)
    assert result.profanity is True
    assert result.explicit_human_request is False
    assert all(rule.startswith("POL.PROF.") for rule in result.matched_rule_ids)


def test_profanity_short_circuits_human_rules(policy) -> None:
    clean = policy.check("соедините меня с оператором")
    dirty = policy.check("соедините меня с оператором, блядь")
    assert clean.explicit_human_request is True
    assert dirty.explicit_human_request is False


def test_reason_codes_come_from_enum(policy) -> None:
    assert reason_codes_for(policy.check("иди на хуй")) == [ReasonCode.POLICY_LANGUAGE]
    assert reason_codes_for(policy.check("позовите оператора")) == [
        ReasonCode.EXPLICIT_HUMAN_REQUEST
    ]
    assert reason_codes_for(policy.check("как оформить оферту")) == []


def test_closure_notice_matches_specification(policy) -> None:
    assert POLICY_CLOSURE_NOTICE == (
        "Обращение завершено: в сообщении обнаружена нецензурная лексика. "
        "Пожалуйста, соблюдайте правила общения"
    )


# ------------------------------------------------------------- port contract


def test_signature_matches_policy_port_and_fake() -> None:
    # eval_str=True: ports.py и service.py используют `from __future__ import
    # annotations`, fakes.py — нет. Сравниваем разрешённые аннотации.
    expected = inspect.signature(PolicyPort.check, eval_str=True)
    assert inspect.signature(DeterministicPolicy.check, eval_str=True) == expected
    assert inspect.signature(FakePolicy.check, eval_str=True) == expected


def test_check_is_synchronous() -> None:
    assert not inspect.iscoroutinefunction(DeterministicPolicy.check)
    assert not inspect.isasyncgenfunction(DeterministicPolicy.check)


def test_returns_real_contract_policy_result(policy) -> None:
    result = policy.check("иди на хуй")
    assert isinstance(result, PolicyResult)
    assert result.model_dump() == {
        "profanity": True,
        "explicit_human_request": False,
        "matched_rule_ids": ["POL.PROF.HUY"],
    }


def test_drop_in_replacement_for_fake_policy(policy) -> None:
    """Тот же вызов, что в tests/test_fakes.py, но с настоящим модулем."""

    def orchestrate(port: PolicyPort, text: str) -> PolicyResult:
        return port.check(text)

    for port in (FakePolicy(), policy):
        assert isinstance(orchestrate(port, "обычный вопрос"), PolicyResult)
    assert orchestrate(policy, "обычный вопрос").profanity is False


def test_is_deterministic_and_does_not_mutate_input(policy) -> None:
    text = "Соедините меня с ОПЕРАТОРОМ, х*й знает что происходит"
    first = policy.check(text)
    second = policy.check(text)
    assert first.model_dump() == second.model_dump()
    assert text == "Соедините меня с ОПЕРАТОРОМ, х*й знает что происходит"


def test_independent_instances_agree(policy) -> None:
    other = build_policy()
    for text in ("иди на хуй", "позовите оператора", "как оформить оферту"):
        assert policy.check(text).model_dump() == other.check(text).model_dump()


def test_matched_rule_ids_are_stable_strings(policy) -> None:
    result = policy.check("бля, ну и пиздец")
    assert result.matched_rule_ids == sorted(set(result.matched_rule_ids), key=result.matched_rule_ids.index)
    assert all(isinstance(rule, str) and rule for rule in result.matched_rule_ids)
