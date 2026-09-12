"""Делает корень репозитория импортируемым.

``knowledge`` намеренно не входит в ``[tool.setuptools.packages.find]``
(pyproject — файл зоны A, C01 его не меняет). Тесты запускаются явным путём:
``uv run pytest knowledge/policy/tests -q``.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest  # noqa: E402

from knowledge.policy import build_policy  # noqa: E402


@pytest.fixture(scope="session")
def policy():
    return build_policy()
