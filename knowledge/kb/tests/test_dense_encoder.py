"""MockQueryEncoder: детерминированность и честная маркировка mock."""

from __future__ import annotations

import math

import pytest

from knowledge.kb.dense.encoder import (
    EMBEDDING_DIM,
    EMBEDDING_REVISION,
    EMBEDDING_SAFETENSORS_SHA256,
    QUERY_INSTRUCTION_TEMPLATE,
    MockQueryEncoder,
    build_query_instruction,
)


def test_mock_encoder_is_marked_mock():
    enc = MockQueryEncoder()
    assert enc.is_mock is True


def test_mock_encoder_dimension_matches_pinned_adapter():
    enc = MockQueryEncoder()
    vec = enc.encode_query("тестовый запрос")
    assert len(vec) == EMBEDDING_DIM == 1024


def test_mock_encoder_is_deterministic():
    enc = MockQueryEncoder()
    a = enc.encode_query("Как обжаловать блокировку?")
    b = enc.encode_query("Как обжаловать блокировку?")
    assert a == b


def test_mock_encoder_differs_for_different_text():
    enc = MockQueryEncoder()
    a = enc.encode_query("вопрос один")
    b = enc.encode_query("совсем другой вопрос")
    assert a != b


def test_mock_encoder_output_is_l2_normalized():
    enc = MockQueryEncoder()
    vec = enc.encode_query("МЧД индивидуальный предприниматель")
    norm = math.sqrt(sum(x * x for x in vec))
    assert norm == pytest.approx(1.0)


def test_query_instruction_matches_a01_pin_exactly():
    """Строка A01 буквально, без E5-префиксов (query:/passage:)."""
    assert QUERY_INSTRUCTION_TEMPLATE == (
        "Instruct: Given a web search query, retrieve relevant passages "
        "that answer the query\nQuery: {query}"
    )
    rendered = build_query_instruction("тест")
    assert rendered.endswith("Query: тест")
    assert not rendered.lower().startswith("query:"), "E5-префикс query: не переносится (§10)"
    assert "passage:" not in rendered.lower(), "E5-префикс passage: не переносится (§10)"


def test_embedding_pins_are_the_a01_values():
    assert EMBEDDING_REVISION == "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"
    assert EMBEDDING_SAFETENSORS_SHA256 == (
        "0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd"
    )
