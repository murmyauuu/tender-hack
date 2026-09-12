"""Условный exact/FTS: распознавание кодов/аббревиатур до морфологии."""

from __future__ import annotations

from knowledge.kb.lexical import detect_exact_identifiers, is_abbreviation_or_code


def test_known_abbreviations_are_detected():
    for token in ("ИНН", "СТЕ", "УПД", "КЭП", "МЧД", "ОГРН"):
        assert is_abbreviation_or_code(token), token


def test_hyphenated_codes_are_detected():
    assert is_abbreviation_or_code("YML-12")
    assert is_abbreviation_or_code("ГОСТ-Р")


def test_clause_numbers_are_detected():
    assert is_abbreviation_or_code("1.2")
    assert is_abbreviation_or_code("10.3.1")


def test_ordinary_words_are_not_flagged_as_codes():
    for word in ("контракт", "поставщик", "portal", "как", "почему"):
        assert not is_abbreviation_or_code(word), word


def test_detect_exact_identifiers_finds_abbreviation_in_sentence():
    ids = detect_exact_identifiers("Нужна ли МЧД индивидуальному предпринимателю?")
    assert "МЧД" in ids


def test_detect_exact_identifiers_deduplicates_and_preserves_order():
    ids = detect_exact_identifiers("ИНН и снова ИНН, а также СТЕ")
    assert ids == ["ИНН", "СТЕ"]


def test_detect_exact_identifiers_returns_empty_for_plain_question():
    ids = detect_exact_identifiers("Как посмотреть статус заявки на портале?")
    assert ids == []


def test_unknown_hyphenated_code_is_detected_as_a_candidate():
    ids = detect_exact_identifiers("Что означает код ZQXPRT-99 в отчёте?")
    assert "ZQXPRT-99" in ids
