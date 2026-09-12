import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
CANONICAL_KB_SHA256 = "71bf714a9e205a35f5d8ec0fd2d0f9bbd4ad3a8409968b754eb8de7b349d79ae"


def test_canonical_raw_kb_is_byte_stable() -> None:
    kb_path = ROOT / "TenderHack_KnowledgeBase" / "knowledge_base_FINAL.jsonl"
    kb_bytes = kb_path.read_bytes()
    records = [json.loads(line) for line in kb_bytes.decode("utf-8").splitlines()]

    assert hashlib.sha256(kb_bytes).hexdigest() == CANONICAL_KB_SHA256
    assert len(records) == 1468
    assert len({record["id"] for record in records}) == 1468

    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "TenderHack_KnowledgeBase/knowledge_base_FINAL.jsonl -text" in attributes


def test_runtime_config_freezes_numpy_index_and_contract_version() -> None:
    config = json.loads((ROOT / "config" / "runtime" / "c0.json").read_text(encoding="utf-8"))
    assert config["contracts_version"] == "2.0.0-c0"
    assert config["index"]["type"] == "numpy_exact_cosine"
    assert config["index"]["server_required"] is False


def test_repository_rules_point_to_canonical_v21_spec() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "TenderHack_UNIFIED_SPEC_v2.1_prefilled.md" in agents


def test_readme_has_reproducible_c0_commands() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for command in (
        "uv sync",
        "uv run python -m tools.generate_contracts",
        "uv run python -m tools.validate_fixtures",
        "uv run pytest",
        "uv run uvicorn tenderhack_backend.app:app",
    ):
        assert command in readme
