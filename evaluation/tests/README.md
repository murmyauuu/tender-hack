# Тесты D02 (runner + report functions)

Локальные тесты зоны `evaluation` (владелец D). Репозиторный `pyproject.toml`
задаёт `testpaths = ["tests"]` (зона A), поэтому bare `pytest` их не подхватывает.
Запуск обязателен из корня:

```
python -m pytest tests evaluation/tests -q
```

Покрытие:

- `test_runner_fixture.py` — полный сценарий runner-а на C0 fixtures (session,
  new_case, chat, poll_request, case, source, feedback, handoff, reply, retry),
  без A02; проверки версий Case, идемпотентности feedback/handoff, retry,
  guard STALE_CASE_VERSION, POLL_TIMEOUT, детерминизма.
- `test_report_metrics.py` — детерминированные метрики по EvaluationExport:
  auto-answer, confirmed_auto_resolution, usefulness (AI/operator), solved_rate,
  feedback_coverage, handoffs, no-answer, нулевой знаменатель → null,
  dedup repeated feedback, перцентили nearest-rank.
- `test_report_integration.py` — export → проверки (AC20) → metrics → Markdown;
  round-trip сохранения/загрузки; отсутствие секретов в артефактах.

Примечания:

- Все numerical ожидания — реальные значения demo-фикстуры
  (`evaluation/report/demo_export.py`), помечены mock и не выдуманы.
- Real API smoke (A02) выполняется отдельной командой
  `python -m evaluation.runner --driver http ...` после готовности A02;
  при 501 прогон корректно помечается «not run» (см. D02-handoff).