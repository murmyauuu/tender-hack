"""PolicyPort-совместимая реализация. Замена FakePolicy один-в-один.

Контракт (contracts/python/tenderhack_contracts/ports.py)::

    class PolicyPort(Protocol):
        def check(self, text: str) -> PolicyResult: ...

Метод синхронный. Реализация не делает ни одного вызова LLM, embeddings,
retrieval или внешнего API: импортируется только stdlib и DTO контракта.
"""

from __future__ import annotations

import json
from pathlib import Path

from tenderhack_contracts import PolicyResult, ReasonCode

from .human_request import HumanRequestMatcher
from .normalization import Normalizer
from .profanity import ProfanityMatcher

#: Текст notice при policy-closure. Дословно из contracts/fixtures/policy.json.
POLICY_CLOSURE_NOTICE = (
    "Обращение завершено: в сообщении обнаружена нецензурная лексика. "
    "Пожалуйста, соблюдайте правила общения"
)

DEFAULT_RULES_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "knowledge" / "policy_rules.json"
)


def load_ruleset(path: str | Path | None = None) -> dict:
    rules_path = Path(path) if path is not None else DEFAULT_RULES_PATH
    with rules_path.open(encoding="utf-8") as handle:
        return json.load(handle)


class DeterministicPolicy:
    """Детерминированный policy-модуль.

    Приоритет: profanity проверяется первым и при срабатывании закорачивает
    проверку — explicit_human_request в таком сообщении не подтверждается,
    обращение закрывается как ``closed_policy`` (спецификация §9: при
    срабатывании 0 routing, 0 embedding, 0 retrieval, 0 generation).
    """

    def __init__(self, ruleset: dict | None = None) -> None:
        self._ruleset = ruleset if ruleset is not None else load_ruleset()
        self._normalizer = Normalizer(self._ruleset)
        self._profanity = ProfanityMatcher(self._ruleset["profanity_rules"])
        self._human = HumanRequestMatcher(
            self._ruleset["human_request"], self._normalizer
        )

    @property
    def ruleset_version(self) -> str:
        return str(self._ruleset["ruleset_version"])

    @property
    def rule_ids(self) -> list[str]:
        return self._profanity.rule_ids

    def check(self, text: str) -> PolicyResult:
        candidates, _tech_ids = self._normalizer.candidates(text)
        profanity_hits = self._profanity.match(candidates)
        if profanity_hits:
            return PolicyResult(
                profanity=True,
                explicit_human_request=False,
                matched_rule_ids=profanity_hits,
            )
        human_hits = self._human.match(text)
        return PolicyResult(
            profanity=False,
            explicit_human_request=bool(human_hits),
            matched_rule_ids=human_hits,
        )


def build_policy(rules_path: str | Path | None = None) -> DeterministicPolicy:
    """Фабрика для внедрения зависимости на стороне A (вместо FakePolicy)."""
    return DeterministicPolicy(load_ruleset(rules_path))


def reason_codes_for(result: PolicyResult) -> list[ReasonCode]:
    """Reason codes из enum контракта, без строковых литералов.

    PolicyResult в C0 не содержит поля reason_codes, поэтому отображение
    вынесено в отдельную функцию: A использует её при сборке
    KnowledgeResult/Case вместо ручных строк.
    """
    if result.profanity:
        return [ReasonCode.POLICY_LANGUAGE]
    if result.explicit_human_request:
        return [ReasonCode.EXPLICIT_HUMAN_REQUEST]
    return []
