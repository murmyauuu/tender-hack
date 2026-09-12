import hashlib
import json
import subprocess
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).parents[1]
CANONICAL_KB_SHA256 = "71bf714a9e205a35f5d8ec0fd2d0f9bbd4ad3a8409968b754eb8de7b349d79ae"
RAW_TEXT_PATHS = (
    "TenderHack_KnowledgeBase/knowledge_base_FINAL.jsonl",
    "TenderHack_KnowledgeBase/TenderHack_KnowledgeBase_summary.txt",
    "TenderHack_KnowledgeBase/api_report.json",
)


def test_canonical_raw_kb_is_byte_stable() -> None:
    kb_path = ROOT / "TenderHack_KnowledgeBase" / "knowledge_base_FINAL.jsonl"
    kb_bytes = kb_path.read_bytes()
    records = [json.loads(line) for line in kb_bytes.decode("utf-8").splitlines()]

    assert hashlib.sha256(kb_bytes).hexdigest() == CANONICAL_KB_SHA256
    assert len(records) == 1468
    assert len({record["id"] for record in records}) == 1468

    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "TenderHack_KnowledgeBase/knowledge_base_FINAL.jsonl -text" in attributes


def test_raw_text_manifest_hashes_are_byte_stable() -> None:
    manifest_path = ROOT / "docs" / "integration" / "input_manifest.sha256"
    manifest = {
        path: digest
        for digest, path in (
            line.split("  ", 1)
            for line in manifest_path.read_text(encoding="utf-8").splitlines()
        )
    }

    attributes = set((ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines())
    for raw_path in RAW_TEXT_PATHS:
        raw_bytes = (ROOT / raw_path).read_bytes()
        blob_oid = subprocess.check_output(
            ["git", "rev-parse", f"HEAD:{raw_path}"], cwd=ROOT, text=True
        ).strip()
        blob_bytes = subprocess.check_output(
            ["git", "cat-file", "blob", blob_oid], cwd=ROOT
        )
        blob_sha256 = hashlib.sha256(blob_bytes).hexdigest()
        assert manifest[raw_path] == blob_sha256
        assert hashlib.sha256(raw_bytes).hexdigest() == blob_sha256

    for raw_path in RAW_TEXT_PATHS:
        assert f"{raw_path} -text" in attributes


def test_input_manifest_verifier_reports_success_and_failure(tmp_path: Path) -> None:
    verifier = ROOT / "tools" / "verify_input_manifest.py"
    assert verifier.is_file()

    result = subprocess.run(
        [sys.executable, str(verifier)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "14/14 OK" in result.stdout

    (tmp_path / "sample.txt").write_bytes(b"wrong bytes\n")
    (tmp_path / "manifest.sha256").write_text(
        f"{'0' * 64}  sample.txt\n",
        encoding="utf-8",
    )
    failed = subprocess.run(
        [
            sys.executable,
            str(verifier),
            "--manifest",
            str(tmp_path / "manifest.sha256"),
            "--root",
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert failed.returncode != 0
    assert "FAILED" in failed.stdout


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


def test_knowledge_package_and_tests_are_in_project_configuration() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    package_find = project["tool"]["setuptools"]["packages"]["find"]
    assert "." in package_find["where"]
    assert "knowledge*" in package_find["include"]

    testpaths = project["tool"]["pytest"]["ini_options"]["testpaths"]
    assert "knowledge/policy/tests" in testpaths
    assert "knowledge/kb/tests" in testpaths


def test_installed_knowledge_modules_import_outside_repository(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from knowledge.policy import build_policy; "
                "from knowledge.kb.store import open_store; "
                "assert build_policy().check('тест').profanity is False; "
                "assert callable(open_store)"
            ),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
