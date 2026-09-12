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
InfoTransport = Callable[[str, float], dict]
_PROPOSAL_ADAPTER = TypeAdapter(GenerationProposal)


def _ollama_schema() -> dict:
    """Keep validation limits in Pydantic without exceeding Ollama grammar limits."""

    def sanitize(value):
        if isinstance(value, dict):
            return {
                key: sanitize(item)
                for key, item in value.items()
                if key not in {"maxLength", "minLength", "maxItems"}
            }
        if isinstance(value, list):
            return [sanitize(item) for item in value]
        return value

    return sanitize(_PROPOSAL_ADAPTER.json_schema())


def _http_transport(url: str, payload: dict, timeout: float) -> dict:
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _http_info_transport(url: str, timeout: float) -> dict:
    request = Request(url, method="GET")
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class OllamaGenerator:
    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        timeout_seconds: float = 60.0,
        transport: Transport = _http_transport,
        info_transport: InfoTransport = _http_info_transport,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.url = f"{self.base_url}/api/generate"
        self.timeout_seconds = timeout_seconds
        self.transport = transport
        self.info_transport = info_transport
        self.calls = 0
        self.last_timings_ms: dict[str, float] = {}

    async def health(self) -> bool:
        try:
            envelope = await asyncio.to_thread(
                self.info_transport,
                f"{self.base_url}/api/tags",
                min(self.timeout_seconds, 60.0),
            )
        except Exception:  # noqa: BLE001 - local runtime dependency boundary
            return False
        return any(
            item.get("name") == A01_MODEL_NAME
            and item.get("digest") == A01_MODEL_DIGEST
            for item in envelope.get("models", [])
        )

    async def generate(self, task: GenerationInput) -> GenerationProposal:
        prompt = self._prompt(task)
        self.calls += 1
        self.last_timings_ms = {}
        payload = {
            "model": A01_MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "format": _ollama_schema(),
            "options": {"num_ctx": 8192, "temperature": 0.1, "seed": 42},
            "keep_alive": "5m",
        }
        try:
            envelope = await asyncio.to_thread(
                self.transport, self.url, payload, self.timeout_seconds
            )
            self.last_timings_ms = {
                key: round(float(envelope[source]) / 1_000_000, 3)
                for key, source in (
                    ("prompt_eval", "prompt_eval_duration"),
                    ("decode", "eval_duration"),
                    ("ollama_total", "total_duration"),
                )
                if envelope.get(source) is not None
            }
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
            "Верни только один JSON-объект по переданной JSON Schema: answer, clarify или "
            "escalate. Для answer: summary — краткий ответ; conditions — дословно сохрани "
            "все непустые условия evidence; steps — конкретные шаги; source_ids — только "
            "значения из allowed_source_ids. Не придумывай URL, даты или выполненные действия.\n"
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
