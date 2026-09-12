"""Общие фикстуры тестов C02.

Пакет `knowledge` не входит в packages.find в pyproject.toml (файл A),
поэтому корень репозитория добавляется в sys.path здесь. Отдельный CR на
это не заводится — действует уже открытый CR-EDUARD-001.
"""

from __future__ import annotations

import os
import sys

import pytest

REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from knowledge.kb import ingest as ingest_mod  # noqa: E402


@pytest.fixture(scope="session")
def snapshot_dir(tmp_path_factory) -> str:
    """Собрать снимок один раз на сессию во временном каталоге."""
    out = str(tmp_path_factory.mktemp("kb-snapshot"))
    ingest_mod.run(out)
    return out


@pytest.fixture(scope="session")
def manifest(snapshot_dir) -> dict:
    import json

    with open(os.path.join(snapshot_dir, "manifest.json"), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="session")
def conn(snapshot_dir):
    import sqlite3

    db = os.path.join(snapshot_dir, "knowledge.sqlite")
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    yield c
    c.close()


@pytest.fixture(scope="session")
def raw_rows() -> list[dict]:
    import json

    path = os.path.join(REPO_ROOT, "TenderHack_KnowledgeBase", "knowledge_base_FINAL.jsonl")
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
