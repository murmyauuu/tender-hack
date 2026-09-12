"""Фактическое доказательство: 0 model calls, 0 сетевых вызовов.

Проверка структурная, а не декларативная: AST всех модулей policy разбирается
и сверяется с allowlist импортов и denylist имён.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

POLICY_DIR = Path(__file__).resolve().parents[1]
MODULE_FILES = sorted(
    path for path in POLICY_DIR.glob("*.py") if path.name != "__init__.py"
)
ALL_FILES = sorted([*MODULE_FILES, POLICY_DIR / "__init__.py"])
#: Сканируются только модули policy. Сам тест использует socket/subprocess
#: намеренно — как инструмент проверки, поэтому в список не входит.

#: Единственные разрешённые верхнеуровневые импорты: stdlib + DTO контракта.
ALLOWED_TOP_LEVEL = {
    "__future__",
    "ast",
    "dataclasses",
    "json",
    "pathlib",
    "re",
    "typing",
    "unicodedata",
    "tenderhack_contracts",
}

#: Запрещённые модули: LLM, embeddings, retrieval, сеть, подпроцессы.
FORBIDDEN_MODULES = {
    "aiohttp",
    "anthropic",
    "asyncio",
    "faiss",
    "http",
    "httpx",
    "huggingface_hub",
    "llama_cpp",
    "numpy",
    "ollama",
    "openai",
    "qdrant_client",
    "requests",
    "sentence_transformers",
    "socket",
    "ssl",
    "subprocess",
    "torch",
    "transformers",
    "urllib",
    "urllib3",
    "websockets",
}

#: Запрещённые вызовы/атрибуты по имени.
FORBIDDEN_CALL_TOKENS = (
    "embed",
    "encode_query",
    "generate",
    "retrieve",
    "urlopen",
    "Popen",
    "system",
)


def _imported_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # относительный импорт внутри пакета policy
                continue
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize("path", ALL_FILES, ids=lambda p: p.name)
def test_only_stdlib_and_contracts_imported(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots = _imported_roots(tree)
    assert roots <= ALLOWED_TOP_LEVEL, f"{path.name}: {sorted(roots - ALLOWED_TOP_LEVEL)}"
    assert not roots & FORBIDDEN_MODULES


@pytest.mark.parametrize("path", ALL_FILES, ids=lambda p: p.name)
def test_no_forbidden_call_names(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Name):
            names.add(node.id)
    offenders = {
        name
        for name in names
        for token in FORBIDDEN_CALL_TOKENS
        if token.lower() in name.lower()
    }
    assert not offenders, f"{path.name}: {sorted(offenders)}"


def test_no_network_or_model_module_loaded_by_import() -> None:
    """Импорт policy не подтягивает ни одного ML/сетевого модуля."""
    before = set(sys.modules)
    import importlib

    importlib.import_module("knowledge.policy")
    added = set(sys.modules) - before
    added_roots = {name.split(".")[0] for name in added}
    assert not added_roots & FORBIDDEN_MODULES, sorted(added_roots & FORBIDDEN_MODULES)


def test_ruleset_is_plain_data() -> None:
    """Конфигурация правил — данные, без исполняемого кода и без URL."""
    config = (
        POLICY_DIR.parents[1] / "config" / "knowledge" / "policy_rules.json"
    ).read_text(encoding="utf-8")
    for token in ("http://", "https://", "model", "embedding", "api_key"):
        assert token not in config.lower(), token


def test_check_works_with_network_layer_disabled(policy, monkeypatch) -> None:
    """Поведенческое доказательство: с отключённым сокетом policy работает.

    Любой вызов LLM/embedding/retrieval по сети упал бы на этом тесте.
    """
    import socket

    def _blocked(*args, **kwargs):  # pragma: no cover - должен не вызываться
        raise AssertionError("policy попыталась открыть сетевое соединение")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)

    corpus = [
        "иди на хуй",
        "х*й",
        "соедините меня с оператором",
        "как связаться с оператором?",
        "оферта не проходит модерацию по 44-ФЗ",
        "GUID 2f8a1c3e-4b5d-4a6f-8c9e-0d1e2f3a4b5c",
        "",
    ]
    for text in corpus:
        assert policy.check(text) is not None


def test_socket_is_pulled_by_pydantic_not_by_policy() -> None:
    """`_socket`/`ipaddress` в sys.modules приходят из pydantic, не из policy."""
    import subprocess
    import sys

    code = (
        "import sys;"
        "import knowledge.policy;"
        "print('socket' in sys.modules)"
    )
    probe = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(POLICY_DIR.parents[1]),
    )
    assert probe.returncode == 0, probe.stderr
    # Модуль верхнего уровня `socket` не импортируется вообще.
    assert probe.stdout.strip() == "False", probe.stdout
