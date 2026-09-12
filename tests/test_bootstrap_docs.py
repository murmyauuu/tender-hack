import json
from pathlib import Path


ROOT = Path(__file__).parents[1]


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
