"""knowledge.policy — детерминированный policy-модуль TenderHack (задача C01).

Точка интеграции для A02::

    from knowledge.policy import build_policy
    policy = build_policy()          # реализует PolicyPort.check(text) -> PolicyResult

Модуль не вызывает LLM, embeddings, retrieval и внешние API.
"""

from .human_request import HumanRequestMatcher
from .normalization import Normalizer
from .profanity import ProfanityMatcher
from .service import (
    POLICY_CLOSURE_NOTICE,
    DeterministicPolicy,
    build_policy,
    load_ruleset,
    reason_codes_for,
)

__all__ = [
    "DeterministicPolicy",
    "HumanRequestMatcher",
    "Normalizer",
    "POLICY_CLOSURE_NOTICE",
    "ProfanityMatcher",
    "build_policy",
    "load_ruleset",
    "reason_codes_for",
]
