"""Доказательство: 0 model calls и 0 сетевых обращений.

Проверка фактическая, а не декларативная: модуль разбирается через AST и
проверяется каждый импорт и каждый вызов. Дополнительно сетевой слой
блокируется на уровне сокета, и снимок собирается заново с этой блокировкой —
если бы ingest куда-то ходил, тест упал бы.
"""

from __future__ import annotations

import ast
import os
import socket

import pytest

KB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(os.path.dirname(KB_DIR))

FORBIDDEN_IMPORTS = {
    # ML / embeddings
    "torch", "transformers", "sentence_transformers", "sklearn", "numpy",
    "onnxruntime", "tokenizers", "llama_cpp", "faiss", "qdrant_client",
    "openai", "anthropic", "huggingface_hub",
    # сеть
    "requests", "httpx", "aiohttp", "urllib", "urllib2", "urllib3",
    "http", "ftplib", "telnetlib", "smtplib", "websockets", "socket",
    "xmlrpc", "webbrowser",
    # чужая зона
    "backend",
}

FORBIDDEN_CALL_NAMES = {"urlopen", "urlretrieve", "download", "from_pretrained"}


def _module_files() -> list[str]:
    return sorted(
        os.path.join(KB_DIR, name)
        for name in os.listdir(KB_DIR)
        if name.endswith(".py")
    )


def test_module_files_are_discovered():
    files = _module_files()
    assert files, "модули C02 не найдены"
    names = {os.path.basename(f) for f in files}
    assert {"ingest.py", "normalize.py", "store.py", "pdf_text.py"} <= names


@pytest.mark.parametrize("path", _module_files(), ids=os.path.basename)
def test_no_forbidden_imports(path):
    tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append(node.module.split(".")[0])
    offending = sorted(set(found) & FORBIDDEN_IMPORTS)
    assert not offending, f"{os.path.basename(path)} импортирует {offending}"


@pytest.mark.parametrize("path", _module_files(), ids=os.path.basename)
def test_no_network_or_model_calls(path):
    tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
    offending: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name in FORBIDDEN_CALL_NAMES:
            offending.append(f"{name} (строка {node.lineno})")
    assert not offending, f"{os.path.basename(path)}: {offending}"


def test_knowledge_port_does_not_import_backend():
    """Критерий A00: KnowledgePort не зависит от backend."""
    for path in _module_files():
        source = open(path, encoding="utf-8").read()
        tree = ast.parse(source, filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("backend"):
                pytest.fail(f"{path} импортирует backend")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("backend")


def test_ingest_runs_with_the_network_disabled(tmp_path, monkeypatch):
    """Снимок собирается при полностью заблокированном сокете."""

    def blocked(*args, **kwargs):  # pragma: no cover - срабатывать не должен
        raise AssertionError("сетевое обращение во время ingest запрещено")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)

    from knowledge.kb import ingest as ingest_mod

    manifest = ingest_mod.run(str(tmp_path / "offline"))
    assert manifest["counts"]["raw"] == 1468
    assert manifest["embedding_model"] is None


def test_no_model_weights_or_index_are_produced(snapshot_dir):
    """C02 не строит ни весов, ни индекса — только sqlite и manifest."""
    produced = sorted(os.listdir(snapshot_dir))
    assert produced == ["knowledge.sqlite", "manifest.json"], produced
    for name in produced:
        assert not name.endswith((".npy", ".bin", ".safetensors", ".pt"))


def test_snapshot_carries_no_embedding_column(conn):
    columns = {row[1] for row in conn.execute("PRAGMA table_info(chunks)")}
    for suspicious in ("embedding", "vector", "embeddings"):
        assert suspicious not in columns
