"""Плотный (dense) слой поиска C03: чтение векторов и cosine top-k.

Подпакет намеренно вынесен из плоского `knowledge/kb/*.py`: тест
`knowledge/kb/tests/test_no_model_calls.py` сканирует только файлы прямо в
`knowledge/kb/` (`os.listdir`, без рекурсии) и запрещает там `numpy`/`torch`
и т.п. Здесь запрета нет, но математика cosine всё равно реализована на
чистом stdlib (`array`, `struct`, `math`) — реальный forward-pass модели
(torch/transformers) в этот пакет не входит и не импортируется: он живёт в
`knowledge/kb/gpu/` (профиль G, отдельный скрипт, см. README там).
"""

from __future__ import annotations
