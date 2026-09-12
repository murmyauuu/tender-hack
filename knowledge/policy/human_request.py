"""Детерминированные правила явной просьбы позвать человека.

Правила работают по словам предложения, а не по подстроке. Неоднозначная
фраза (общее недовольство, «это не работает», «ужасный сервис») не является
подтверждением передачи: она не содержит ни transfer-маркера, ни адресата и
даёт ``False``. Вопрос «как связаться с оператором» — knowledge-вопрос про
контакты, он подавляется suppressor'ом HOWTO.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SENTENCE_SPLIT_RE = re.compile(r"[.!?;\n]+")

RULE_TRANSFER = "POL.HUMAN.TRANSFER_REQUEST"
RULE_NEED = "POL.HUMAN.NEED_PERSON"
RULE_TARGET_ONLY = "POL.HUMAN.TARGET_ONLY"


@dataclass(frozen=True)
class _Suppressor:
    rule_id: str
    question: re.Pattern[str] | None
    contact: re.Pattern[str] | None
    plain: re.Pattern[str] | None

    def applies(self, sentence: str) -> bool:
        if self.plain is not None:
            return bool(self.plain.search(sentence))
        if self.question is not None and self.contact is not None:
            return bool(self.question.search(sentence)) and bool(
                self.contact.search(sentence)
            )
        return False


class HumanRequestMatcher:
    def __init__(self, config: dict, normalizer) -> None:
        self._normalizer = normalizer
        self._person_targets = tuple(config["person_targets"])
        self._channel_targets = tuple(config["channel_targets"])
        self._transfer_markers = frozenset(config["transfer_markers"])
        self._need_markers = frozenset(config["need_markers"])
        self._max_gap = int(config.get("max_gap_tokens", 7))
        self._politeness = frozenset(config.get("politeness_tokens", ()))
        self._phrase_rules = [
            (rule["rule_id"], re.compile(rule["pattern"]))
            for rule in config.get("phrase_rules", [])
        ]
        self._suppressors = [
            _Suppressor(
                rule_id=spec["rule_id"],
                question=(
                    re.compile(spec["question_pattern"])
                    if "question_pattern" in spec
                    else None
                ),
                contact=(
                    re.compile(spec["contact_pattern"])
                    if "contact_pattern" in spec
                    else None
                ),
                plain=re.compile(spec["pattern"]) if "pattern" in spec else None,
            )
            for spec in config.get("suppressors", [])
        ]

    # ------------------------------------------------------------- помощники

    def _target_kind(self, token: str) -> str | None:
        for stem in self._person_targets:
            if token.startswith(stem):
                return "person"
        for stem in self._channel_targets:
            if token.startswith(stem):
                return "channel"
        return None

    def _marker_kind(self, token: str) -> str | None:
        if token in self._transfer_markers:
            return "transfer"
        if token in self._need_markers:
            return "need"
        return None

    def _sentences(self, text: str) -> list[str]:
        cleaned, _ = self._normalizer.strip_technical(text)
        folded = self._normalizer.fold(cleaned)
        sentences: list[str] = []
        for raw in _SENTENCE_SPLIT_RE.split(folded):
            spaced = re.sub(r"[^\w]+", " ", raw, flags=re.UNICODE)
            spaced = re.sub(r"\s+", " ", spaced).strip()
            if spaced:
                sentences.append(spaced)
        return sentences

    # ----------------------------------------------------------------- match

    def match(self, text: str) -> list[str]:
        hits: list[str] = []
        sentences = self._sentences(text)
        for sentence in sentences:
            suppressed = {s.rule_id for s in self._suppressors if s.applies(sentence)}
            howto = "POL.HUMAN.SUPPRESS.HOWTO" in suppressed
            negation = "POL.HUMAN.SUPPRESS.NEGATION" in suppressed
            if howto:
                # Вопрос о контактах/канале — это knowledge-вопрос, не передача.
                continue
            tokens = sentence.split()
            markers = [
                (index, self._marker_kind(token))
                for index, token in enumerate(tokens)
                if self._marker_kind(token) is not None
            ]
            targets = [
                (index, self._target_kind(token))
                for index, token in enumerate(tokens)
                if self._target_kind(token) is not None
            ]
            for m_index, m_kind in markers:
                if m_kind == "need" and negation:
                    continue
                for t_index, t_kind in targets:
                    if abs(t_index - m_index) > self._max_gap:
                        continue
                    if m_kind == "transfer":
                        hits.append(RULE_TRANSFER)
                    elif t_kind == "person":
                        # need-маркеры принимают только адресата-человека:
                        # «нужна поддержка» ещё не просьба позвать человека.
                        hits.append(RULE_NEED)
            for rule_id, pattern in self._phrase_rules:
                if pattern.search(sentence):
                    hits.append(rule_id)
            if not negation and self._is_target_only(tokens):
                hits.append(RULE_TARGET_ONLY)
        return _dedupe(hits)

    def _is_target_only(self, tokens: list[str]) -> bool:
        """Сообщение состоит только из адресата-человека и вежливых слов."""
        if not tokens:
            return False
        has_person = False
        for token in tokens:
            kind = self._target_kind(token)
            if kind == "person":
                has_person = True
                continue
            if token in self._politeness:
                continue
            return False
        return has_person


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
