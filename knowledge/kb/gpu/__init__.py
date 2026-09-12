"""GPU-only материалы C03 (профиль G): реальный forward-pass модели.

Этот подпакет НЕ импортируется из `knowledge/kb/*.py` верхнего уровня и не
нужен на M: он существует только для машины с GPU/torch, где реально
запускается `embed_and_smoke.py`. Тест `knowledge/kb/tests/test_no_model_calls.py`
сканирует лишь файлы прямо в `knowledge/kb/` (без рекурсии в подпакеты),
поэтому torch/transformers здесь разрешены и не нарушают «0 model calls» C02.
"""

from __future__ import annotations
