import asyncio
import json
from pathlib import Path

import pytest
from tenderhack_backend.generator import (
    A01_MODEL_DIGEST,
    A01_MODEL_NAME,
    OllamaGenerator,
)
from tenderhack_backend.verifier import InvalidGeneration
from tenderhack_contracts import GenerationAnswer, GenerationInput


def task() -> GenerationInput:
    return GenerationInput(
        question="Как подписать контракт?",
        evidence=[],
        allowed_source_ids=["source-demo"],
    )


def test_adapter_uses_a01_pin_and_disables_thinking() -> None:
    calls = []

    def transport(url, payload, timeout):
        calls.append((url, payload, timeout))
        return {
            "response": json.dumps(
                {
                    "action": "answer",
                    "summary": "Откройте карточку.",
                    "conditions": [],
                    "steps": ["Откройте карточку."],
                    "source_ids": ["source-demo"],
                },
                ensure_ascii=False,
            )
        }

    generator = OllamaGenerator(transport=transport)
    proposal = asyncio.run(generator.generate(task()))

    assert isinstance(proposal, GenerationAnswer)
    assert A01_MODEL_NAME == "qwen3:8b-q4_K_M"
    assert (
        A01_MODEL_DIGEST
        == "a0a5ad8024dd21401f07634d0c71393b9c9d37aa57a6b594e02b86ab72c450b4"
    )
    assert len(calls) == 1
    assert calls[0][1]["model"] == A01_MODEL_NAME
    assert calls[0][1]["think"] is False
    assert calls[0][1]["stream"] is False
    assert "/no_think" in calls[0][1]["prompt"]
    assert calls[0][1]["options"]["num_ctx"] == 8192
    assert isinstance(calls[0][1]["format"], dict)
    schema_text = json.dumps(calls[0][1]["format"])
    assert "maxLength" not in schema_text
    assert "minLength" not in schema_text
    assert "maxItems" not in schema_text
    assert generator.calls == 1


def test_adapter_records_ollama_timings_without_another_generation() -> None:
    def transport(url, payload, timeout):
        return {
            "response": json.dumps(
                {
                    "action": "answer",
                    "summary": "Откройте карточку.",
                    "conditions": [],
                    "steps": ["Откройте карточку."],
                    "source_ids": ["source-demo"],
                }
            ),
            "prompt_eval_duration": 12_500_000,
            "eval_duration": 25_000_000,
            "total_duration": 50_000_000,
        }

    generator = OllamaGenerator(transport=transport)
    asyncio.run(generator.generate(task()))

    assert generator.calls == 1
    assert generator.last_timings_ms == {
        "prompt_eval": 12.5,
        "decode": 25.0,
        "ollama_total": 50.0,
    }


def test_health_requires_the_exact_a01_model_digest() -> None:
    checks = []

    def info_transport(url, timeout):
        checks.append((url, timeout))
        return {
            "models": [
                {
                    "name": "qwen3:8b-q4_K_M",
                    "digest": A01_MODEL_DIGEST,
                }
            ]
        }

    generator = OllamaGenerator(info_transport=info_transport)
    assert asyncio.run(generator.health()) is True
    assert checks == [("http://127.0.0.1:11434/api/tags", 60.0)]
    assert generator.calls == 0


def test_health_rejects_wrong_model_digest() -> None:
    generator = OllamaGenerator(
        info_transport=lambda url, timeout: {
            "models": [{"name": "qwen3:8b-q4_K_M", "digest": "wrong"}]
        }
    )
    assert asyncio.run(generator.health()) is False


def test_invalid_json_is_not_retried() -> None:
    calls = 0

    def transport(url, payload, timeout):
        nonlocal calls
        calls += 1
        return {"response": "not-json"}

    generator = OllamaGenerator(transport=transport)
    with pytest.raises(InvalidGeneration):
        asyncio.run(generator.generate(task()))
    assert calls == 1
    assert generator.calls == 1


def test_mixed_union_fields_are_rejected_without_retry() -> None:
    calls = 0

    def transport(url, payload, timeout):
        nonlocal calls
        calls += 1
        return {
            "response": json.dumps(
                {
                    "action": "clarify",
                    "missing_fact": "role",
                    "question": "Вы поставщик?",
                    "source_ids": ["not-allowed-on-clarify"],
                }
            )
        }

    with pytest.raises(InvalidGeneration):
        asyncio.run(OllamaGenerator(transport=transport).generate(task()))
    assert calls == 1


def test_runtime_config_pins_only_the_verified_a01_model() -> None:
    root = Path(__file__).parents[1]
    config = json.loads(
        (root / "config" / "runtime" / "a02.json").read_text(encoding="utf-8")
    )
    assert config["generator"]["model"] == A01_MODEL_NAME
    assert config["generator"]["manifest_digest"] == A01_MODEL_DIGEST
    assert config["generator"]["thinking"] is False
    assert config["generator"]["automatic_generation_retries"] == 0
    assert "4b" not in json.dumps(config, ensure_ascii=False).lower()
