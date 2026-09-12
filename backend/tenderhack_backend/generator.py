from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from urllib.request import Request, urlopen

from pydantic import TypeAdapter, ValidationError
from tenderhack_contracts import GenerationInput, GenerationProposal

from .verifier import InvalidGeneration

A01_MODEL_NAME = "qwen3:8b-q4_K_M"
A01_MODEL_DIGEST = "a0a5ad8024dd21401f07634d0c71393b9c9d37aa57a6b594e02b86ab72c450b4"
A01_GGUF_SHA256 = "d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785"

Transport = Callable[[str, dict, float], dict]
_PROPOSAL_ADAPTER = TypeAdapter(GenerationProposal)


def _http_transport(url: str, payload: dict, timeout: float) -> dict:
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class OllamaGenerator:
    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        timeout_seconds: float = 60.0,
        transport: Transport = _http_transport,
    ) -> None:
        self.url = f"{base_url.rstrip('/')}/api/generate"
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def generate(self, task: GenerationInput) -> GenerationProposal:
        prompt = self._prompt(task)
        payload = {
            "model": A01_MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "format": "json",
            "options": {"num_ctx": 8192, "temperature": 0.1, "seed": 42},
            "keep_alive": "5m",
        }
        try:
            envelope = await asyncio.to_thread(
                self.transport, self.url, payload, self.timeout_seconds
            )
            raw = envelope["response"]
            return _PROPOSAL_ADAPTER.validate_json(raw)
        except InvalidGeneration:
            raise
        except (KeyError, TypeError, json.JSONDecodeError, ValidationError) as exc:
            raise InvalidGeneration("generator returned invalid JSON") from exc

    @staticmethod
    def _prompt(task: GenerationInput) -> str:
        evidence = [
            {
                "source_id": item.source_id,
                "title": item.title,
                "text": item.text,
                "conditions": item.conditions,
            }
            for item in task.evidence
        ]
        return (
            "/no_think\n"
            "Верни только один JSON-объект: answer, clarify или escalate. "
            "Не утверждай, что выполнил действие. Используй только allowed_source_ids.\n"
            + json.dumps(
                {
                    "question": task.question,
                    "confirmed_facts": task.confirmed_facts,
                    "allowed_source_ids": task.allowed_source_ids,
                    "evidence": evidence,
                },
                ensure_ascii=False,
            )
        )
