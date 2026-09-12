from __future__ import annotations

import re

from tenderhack_contracts import (
    GenerationAnswer,
    GenerationClarify,
    GenerationEscalate,
    GenerationProposal,
)


class InvalidGeneration(ValueError):
    pass


_FORBIDDEN_ACTIONS = re.compile(
    r"\b(?:я\s+(?:разблокировал|отправил|подписал)|операция\s+выполнена)\b",
    re.IGNORECASE,
)
_URL = re.compile(r"https?://\S+", re.IGNORECASE)
_NUMBER = re.compile(r"(?<![\w-])\d+(?:[.,]\d+)?")
_LEADING_STEP_NUMBER = re.compile(r"^\s*\d+[.)]\s*")


def verify_proposal(
    proposal: GenerationProposal,
    allowed_source_ids: set[str],
    required_conditions: list[str] | None = None,
    grounding_texts: list[str] | None = None,
) -> GenerationProposal:
    if not isinstance(
        proposal, (GenerationAnswer, GenerationClarify, GenerationEscalate)
    ):
        raise InvalidGeneration("unsupported proposal")
    if not isinstance(proposal, GenerationAnswer):
        return proposal
    if not proposal.summary.strip():
        raise InvalidGeneration("empty answer")
    if not set(proposal.source_ids).issubset(allowed_source_ids):
        raise InvalidGeneration("answer cites a source that was not supplied")
    missing_conditions = set(required_conditions or []) - set(proposal.conditions)
    if missing_conditions:
        raise InvalidGeneration("answer dropped a required evidence condition")
    combined = "\n".join([proposal.summary, *proposal.conditions, *proposal.steps])
    if _FORBIDDEN_ACTIONS.search(combined):
        raise InvalidGeneration("answer claims an action was performed")
    if _URL.search(combined):
        raise InvalidGeneration("generated URLs are not allowed")
    generated_numbers: set[str] = set()
    for value in [proposal.summary, *proposal.conditions, *proposal.steps]:
        generated_numbers.update(_NUMBER.findall(_LEADING_STEP_NUMBER.sub("", value)))
    grounded_numbers = set(_NUMBER.findall("\n".join(grounding_texts or [])))
    if generated_numbers - grounded_numbers:
        raise InvalidGeneration("answer contains an ungrounded number or date")
    return proposal
