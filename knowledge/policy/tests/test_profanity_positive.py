"""Категории: explicit profanity, регистр, разделители, masking."""

from __future__ import annotations

import pytest

EXPLICIT = [
    ("иди на хуй", "POL.PROF.HUY"),
    ("что за хуйня", "POL.PROF.HUY"),
    ("охуеть", "POL.PROF.HUY"),
    ("пиздец какой-то", "POL.PROF.PIZD"),
    ("распиздяй", "POL.PROF.PIZD"),
    ("заебали уже", "POL.PROF.EB"),
    ("ебать", "POL.PROF.EB"),
    ("ёбаный портал", "POL.PROF.EB"),
    ("долбоеб", "POL.PROF.EB"),
    ("съебался", "POL.PROF.EB"),
    ("въебать", "POL.PROF.EB"),
    ("блядь", "POL.PROF.BLYAD"),
    ("блять", "POL.PROF.BLYAD"),
    ("бля", "POL.PROF.BLYA"),
    ("мудак", "POL.PROF.MUD"),
    ("мудила", "POL.PROF.MUD"),
    ("пидорас", "POL.PROF.PIDOR"),
    ("пидр", "POL.PROF.PIDR"),
    ("залупа", "POL.PROF.ZALUPA"),
    ("гандон", "POL.PROF.GANDON"),
    ("гондон", "POL.PROF.GANDON"),
    ("херня полная", "POL.PROF.HER"),
    ("похер", "POL.PROF.HER"),
    ("сука", "POL.PROF.SUKA"),
    ("сучка", "POL.PROF.SUKA"),
    ("blyat", "POL.PROF.TRANSLIT"),
    ("pizdec", "POL.PROF.TRANSLIT"),
]


@pytest.mark.parametrize(("text", "rule_id"), EXPLICIT)
def test_explicit_profanity_is_detected(policy, text: str, rule_id: str) -> None:
    result = policy.check(text)
    assert result.profanity is True
    assert rule_id in result.matched_rule_ids


CASE_VARIANTS = ["хуй", "ХУЙ", "ХуЙ", "хУй", "БЛЯДЬ", "БлЯтЬ", "МуДаК", "СУКА"]


@pytest.mark.parametrize("text", CASE_VARIANTS)
def test_case_is_ignored(policy, text: str) -> None:
    assert policy.check(text).profanity is True


SEPARATED = [
    "х у й",
    "Х У Й",
    "х.у.й",
    "х-у-й",
    "х_у_й",
    "б л я д ь",
    "бл я дь",
    "с.у.к.а",
    "п и з д е ц",
    "х у й!",
]


@pytest.mark.parametrize("text", SEPARATED)
def test_separators_inside_word_are_ignored(policy, text: str) -> None:
    assert policy.check(text).profanity is True


MASKED = [
    "х*й",
    "х#й",
    "х@й",
    "бл*дь",
    "бл9дь",
    "п*здец",
    "п3здец",
    "пи3дец",
    "с*ка",
    "6лядь",
    "xyй",
    "хуууй",
    "бляяяять",
]


@pytest.mark.parametrize("text", MASKED)
def test_masking_and_homoglyphs_are_detected(policy, text: str) -> None:
    assert policy.check(text).profanity is True


def test_profanity_inside_longer_message(policy) -> None:
    text = "Здравствуйте! Загрузил оферту, а она не проходит. Что за хуйня творится?"
    result = policy.check(text)
    assert result.profanity is True
    assert result.matched_rule_ids == ["POL.PROF.HUY"]
