"""Детерминированное определение нецензурной лексики.

Матчинг привязан к границе слова/токена: кандидат должен целиком разбираться
как ``[разрешённый префикс] + корень + [окончание не длиннее N]``.
Необоснованный substring matching невозможен по построению — правило
анкорится ``^...$`` по кандидату, а не ищет вхождение куда угодно.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .normalization import SENTINEL, MatchCandidate

_SEP = f"[{re.escape(SENTINEL)}]{{0,3}}"
_SUFFIX_CHAR = f"(?:[а-яa-z]|{re.escape(SENTINEL)})"


def _literal(text: str) -> str:
    """Литерал, терпимый к разделителям между символами (``п.о``)."""
    return _SEP.join(re.escape(ch) for ch in text)


@dataclass(frozen=True)
class ProfanityRule:
    rule_id: str
    pattern: re.Pattern[str] | None
    atom_count: int
    max_masked: int
    exception_token_prefixes: tuple[str, ...]
    exact_tokens: tuple[str, ...] = ()
    script: str = "cyrillic"

    @property
    def is_exact(self) -> bool:
        return bool(self.exact_tokens)


def _compile_stem_rule(spec: dict) -> ProfanityRule:
    atoms: list[str] = list(spec["atoms"])
    prefixes = [p for p in spec.get("prefixes", [""]) if p]
    max_suffix = int(spec.get("max_suffix", 0))

    parts = ["^"]
    if prefixes:
        # Более длинные префиксы первыми: regex-альтернатива не жадная по длине.
        ordered = sorted(set(prefixes), key=len, reverse=True)
        parts.append("(?:" + "|".join(_literal(p) for p in ordered) + ")?")
    parts.append(_SEP)
    atom_parts = [
        f"(?P<a{index}>[{re.escape(atom)}]{{1,3}}|{re.escape(SENTINEL)})"
        for index, atom in enumerate(atoms)
    ]
    parts.append(_SEP.join(atom_parts))
    parts.append(_SEP)
    parts.append(f"{_SUFFIX_CHAR}{{0,{max_suffix}}}" if max_suffix else "")
    parts.append("$")

    return ProfanityRule(
        rule_id=spec["rule_id"],
        pattern=re.compile("".join(parts)),
        atom_count=len(atoms),
        max_masked=int(spec.get("max_masked", 1)),
        exception_token_prefixes=tuple(spec.get("exception_token_prefixes", ())),
    )


def _compile_exact_rule(spec: dict) -> ProfanityRule:
    return ProfanityRule(
        rule_id=spec["rule_id"],
        pattern=None,
        atom_count=0,
        max_masked=int(spec.get("max_masked", 1)),
        exception_token_prefixes=tuple(spec.get("exception_token_prefixes", ())),
        exact_tokens=tuple(spec["tokens"]),
        script=spec.get("script", "cyrillic"),
    )


def compile_rules(specs: list[dict]) -> list[ProfanityRule]:
    compiled: list[ProfanityRule] = []
    for spec in specs:
        if spec.get("kind") == "exact":
            compiled.append(_compile_exact_rule(spec))
        else:
            compiled.append(_compile_stem_rule(spec))
    return compiled


def _matches_exact(rule: ProfanityRule, candidate: MatchCandidate) -> bool:
    if rule.script == "latin" and candidate.has_cyrillic:
        return False
    if rule.script == "cyrillic" and not candidate.has_cyrillic:
        return False
    text = candidate.text
    bare = text.replace(SENTINEL, "")
    for token in rule.exact_tokens:
        if bare == token:
            return True
        if len(text) == len(token):
            masked = 0
            ok = True
            for got, want in zip(text, token):
                if got == want:
                    continue
                if got == SENTINEL:
                    masked += 1
                    continue
                ok = False
                break
            if ok and 0 < masked <= rule.max_masked:
                return True
    return False


def _matches_stem(rule: ProfanityRule, candidate: MatchCandidate) -> bool:
    assert rule.pattern is not None
    if not candidate.has_cyrillic:
        # Правила-корни описаны кириллицей; чисто латинский токен не может быть
        # русским матом без гомоглифов, а гомоглифы уже применены в нормализации.
        return False
    bare = candidate.text.replace(SENTINEL, "")
    for exception in rule.exception_token_prefixes:
        if bare.startswith(exception):
            return False
    match = rule.pattern.match(candidate.text)
    if match is None:
        return False
    masked = sum(
        1
        for index in range(rule.atom_count)
        if match.group(f"a{index}") == SENTINEL
    )
    literal_atoms = rule.atom_count - masked
    if masked > rule.max_masked:
        return False
    return literal_atoms >= min(2, rule.atom_count)


class ProfanityMatcher:
    """Возвращает стабильные rule_id сработавших правил."""

    def __init__(self, specs: list[dict]) -> None:
        self._rules = compile_rules(specs)

    @property
    def rule_ids(self) -> list[str]:
        return [rule.rule_id for rule in self._rules]

    def match(self, candidates: list[MatchCandidate]) -> list[str]:
        hits: list[str] = []
        for rule in self._rules:
            check = _matches_exact if rule.is_exact else _matches_stem
            if any(check(rule, candidate) for candidate in candidates):
                hits.append(rule.rule_id)
        return hits
