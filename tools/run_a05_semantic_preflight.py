"""Print machine-G semantic runtime identity without using external network."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import platform
from pathlib import Path
from urllib.request import urlopen

from tenderhack_backend.config import Settings
from tenderhack_backend.generator import (
    A01_GGUF_SHA256,
    A01_MODEL_DIGEST,
    A01_MODEL_NAME,
)
from tenderhack_backend.runtime import build_runtime_service


EXPECTED_EMBEDDING_SHA256 = (
    "0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def run(args: argparse.Namespace) -> dict:
    knowledge_dir = Path(args.knowledge_dir).resolve()
    hf_home = Path(args.hf_home).resolve()
    settings = Settings(
        db_path=Path(args.db),
        runtime_mode="real",
        knowledge_dir=knowledge_dir,
        hf_home=hf_home,
        embedding_device=args.embedding_device,
        ollama_url=args.ollama_url,
    )
    service = build_runtime_service(settings)
    knowledge_health = await service.knowledge.health()

    with urlopen(f"{args.ollama_url.rstrip('/')}/api/tags", timeout=10.0) as response:
        tags = json.loads(response.read().decode("utf-8"))
    matching_models = [
        {"name": item.get("name"), "digest": item.get("digest")}
        for item in tags.get("models", [])
        if item.get("name") == A01_MODEL_NAME
    ]

    artifact_hashes = {}
    for name in ("knowledge.sqlite", "index.npy", "index_ids.json", "manifest.json"):
        path = knowledge_dir / name
        artifact_hashes[name] = sha256(path) if path.is_file() else None

    embedding_candidates = []
    for path in hf_home.rglob("model.safetensors"):
        actual = sha256(path)
        embedding_candidates.append(
            {
                "path": str(path),
                "sha256": actual,
                "matches_pin": actual == EXPECTED_EMBEDDING_SHA256,
            }
        )

    result = {
        "machine": {
            "node": platform.node(),
            "system": platform.system(),
            "release": platform.release(),
            "processor": platform.processor(),
        },
        "knowledge_dir": str(knowledge_dir),
        "hf_home": str(hf_home),
        "knowledge_health": knowledge_health.model_dump(mode="json"),
        "artifact_sha256": artifact_hashes,
        "embedding": {
            "model": "Qwen/Qwen3-Embedding-0.6B",
            "revision": "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3",
            "expected_safetensors_sha256": EXPECTED_EMBEDDING_SHA256,
            "candidates": embedding_candidates,
        },
        "generator": {
            "model": A01_MODEL_NAME,
            "expected_digest": A01_MODEL_DIGEST,
            "expected_gguf_sha256": A01_GGUF_SHA256,
            "matching_tags": matching_models,
            "ready": any(item["digest"] == A01_MODEL_DIGEST for item in matching_models),
        },
    }
    if knowledge_health.mode != "semantic":
        raise RuntimeError(f"semantic health required, got {knowledge_health}")
    if not result["generator"]["ready"]:
        raise RuntimeError("pinned Ollama model name/digest is unavailable")
    if not any(item["matches_pin"] for item in embedding_candidates):
        raise RuntimeError("pinned embedding model.safetensors was not found under hf-home")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--knowledge-dir", required=True)
    parser.add_argument("--hf-home", required=True)
    parser.add_argument("--db", default="var/a05/preflight.sqlite")
    parser.add_argument("--embedding-device", default="cuda")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    result = asyncio.run(run(args))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
