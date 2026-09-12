# evaluation — зона оценки (владелец: D)

Здесь D готовит и хранит методику и материалы оценки TenderHack.

## Карта каталога

| Путь | Содержимое | Статус |
|---|---|---|
| `rubric.md` | Рубрика: 4 измерения 0/1/2/not_assessable, critical_error, правила разметки/согласования | D00 |
| `cohorts.md` | Методика трёх массивов: AI-test (20 dev + 40 final), История (30 пар + учебные), Live/demo | D00 |
| `history_selection_plan.md` | Аудит реальной истории, правила отбора 30 пар, pair_id схема, blockers | D00 |
| `training_examples.md` | До 10 учебных якорей калибровки (не входят в итоговые 30) | D00 |
| `history/` | Рабочие материалы по исторической выборке (манифест пар — D01) | D01 |
| `schema/evaluationrow_requirements.md` | Требования к минимальному EvaluationRow для A00 (не API!) | D00 |
| `annotations/` | Разметки. `annotations/egor` — версия Егора (D03); `annotations/stas` — версия Стаса (владелец B) | D03/B04 |
| `final_private/` | Sealed final (40). НЕ коммитить (в .gitignore), открывается только после RC | D01/D07 |
| `runner/` | Evaluation runner (D02): HTTP-операции session/chat/poll/case/source/feedback/handoff/reply/retry/new_case. Драйверы: `fixture_driver.py` (frozen C0, детерминированный) и `http_driver.py` (реальный A02, без чтения app.sqlite). CLI: `python -m evaluation.runner` | D02 |
| `report/` | Report-функции по одному EvaluationExport JSON (D02): валидация/метрики/Markdown. CLI: `python -m evaluation.report`; `demo_export.py` — детерминированный mock для проверки границ (null-знаменатели, dedup feedback, latency, errors/timeouts) | D02 |
| `tests/` | Покрытие D02: runner на fixtures + report metrics/integration. Запуск: `python -m pytest tests evaluation/tests` | D02 |

## Команды D02

```powershell
$env:PYTHONPATH = "D:\tender-hack-d02-d02-runner"
python -m pytest tests evaluation/tests -q          # 48 passed (с base)
python -m evaluation.runner --driver fixture --out var/evaluation/d02/suite_fixture.json
python -m evaluation.report --demo --out var/evaluation/d02/report_demo.md --json-out var/evaluation/d02/metrics_demo.json
# real API smoke после готовности A02 (не читает app.sqlite):
python -m evaluation.runner --driver http --base-url http://127.0.0.1:8000 --out var/evaluation/d02/suite_http.json
```

Правила D02: данные — только из HTTP/fixtures, app.sqlite не читается; mock помечается
`mock`; real smoke при 501 помечается «not run», не blocker; TENDERHACK_REPLY_KEY
в артефакты не попадает.

## Правила зоны

- Исходные версии разметки после сохранения не редактируются; согласование создаёт отдельный файл со ссылками на обе.
- Любое число в отчётах: из actual input с n/N; пустая выборка → null. Мock/fixture помечаются mock.
- История: ответ оператора (Решение) НЕ является gold без проверки человеком по источникам.
- Не выдумываются: автор, SLA, CSAT, источники, даты, результаты тестов.

См. также `docs/coordination/egor/D00-handoff.md`.