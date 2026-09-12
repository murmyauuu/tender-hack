# D02 — handoff

- Status: done
- Owner / tool: Егор / opencode (big-pickle)
- Base SHA: c5d093c1d7ccc373fd87163cd7f0573ea62a88d5 (main + D01 `task/d01-dataset`)
- Result SHA: 25e57c3
- Contracts version: 2.0.0-c0
- Machine profile: локальный Windows, Python 3.14.5, pytest 9.0.3, fastapi 0.128.0, pydantic 2.12.5
- Runtime SHA / KB snapshot: не требуется (runner работает на C0 fixtures без runtime)
- Changed files:
  - `evaluation/__init__.py` — маркер пакета зоны E (D)
  - `evaluation/runner/__init__.py`, `evaluation/runner/records.py`, `evaluation/runner/driver.py`,
    `evaluation/runner/fixture_driver.py`, `evaluation/runner/http_driver.py`, `evaluation/runner/suite.py`,
    `evaluation/runner/__main__.py` — runner
  - `evaluation/report/__init__.py`, `evaluation/report/export_io.py`, `evaluation/report/metrics.py`,
    `evaluation/report/report.py`, `evaluation/report/demo_export.py`, `evaluation/report/__main__.py` — report-функции
  - `evaluation/tests/__init__.py`, `evaluation/tests/test_runner_fixture.py`,
    `evaluation/tests/test_report_metrics.py`, `evaluation/tests/test_report_integration.py`, `evaluation/tests/README.md`
  - `evaluation/README.md` — дополнено разделами runner/report и командами D02

## Implemented behavior

### Runner (evaluation/runner)

- Операции контракта: `session`, `new_case` (chat с case_id=null), `poll_request`, `case`, `source`,
  `feedback`, `handoff`, `reply` (operator), `retry` (chat text=null, retry_of), `chat`.
- Драйверы одной операции вызываются по интерфейсу `RunnerDriver` (async).
- `fixture_driver.py` — детерминированный провайдер на frozen C0 fixtures: фиксированные UUID и timestamps,
  стадийный поллинг (processing→final / error), слоты новых case: answer → handoff → error → retry.
  Все ответы помечены `mock=True`. Это НЕ реальные пользовательские данные.
- `http_driver.py` — реальный API-driver поверх HTTP (не читает app.sqlite). Ошибки оборачиваются в
  `DriverError` из envelope; `TENDERHACK_REPLY_KEY` берётся из env и никогда не логируется/не пишется в трассу.
- `suite.py` — полный сценарий `full-v1`: session → new_case(answer) → poll → case → source → feedback(solved)
  → new_case(no-answer) → poll → case → handoff (идемпотентность) → reply → case → feedback(operator) →
  new_case(error) → poll → case → retry → poll → case.
- Трасса: `SuiteReport` (`tenderhack.d02_suite_trace/v1`) с OperationRecord: outcome ok/error/skipped,
  input/output/error, elapsed_ms, attempts, statuses_seen. При 501/неготовности A02 runner корректно
  записывает ошибку и помечает `meta.not_run_reason` (smoke = not run, не blocker).
- Guard'ы: STALE_CASE_VERSION, POLL_TIMEOUT (после max_attempts), retry только для error-запроса,
  retry переиспользует user_message_id.

### Report-функции (evaluation/report)

- Вход — один `EvaluationExport` JSON (модель C0 из `contracts/python`), выход — детерминированные метрики
  и Markdown-отчёт. LLM/GPU не используются.
- Метрики по cohort (demo/live раздельно, знаменатели не смешиваются):
  auto_answer, confirmed_auto_resolution, usefulness_ai/usefulness_operator, solved_rate,
  feedback_coverage, handoffs, no_answer, errors (case с error Request), timeouts (total ≥ 120000 ms),
  latency total/answer p50/p95 (nearest-rank).
- Границы: `policy_closed` исключается из N_eligible; пустой знаменатель → value=null;
  repeated feedback дедуплицируется по message_id (max updated_at) и не считает Case дважды;
  repeated solved не увеличивает версию повторно; dangling feedback — в issues; AC20 (дубли case_id) —
  в issues.
- `demo_export.py` — детерминированный mock EvaluationExport (7 demo + 2 live), покрывающий все границы;
  mock помечается явно, числа в тестах — реальные значения этой фикстуры.

## Acceptance: passed (fixtures) / not run (real API smoke)

| Проверка | Результат |
|---|---|
| Все 9+ операций runner-а в трассе | Да — ops: session, new_case, poll_request, case, source, feedback, handoff, reply, retry (19 ops) ✓ |
| Fixture full scenario: 0 ошибок | `operations_error: 0` ✓ |
| Итоговые состояния драйвера | auto→resolved v3; handoff→resolved v5 (ticket operator); error→retry→awaiting_feedback v2 ✓ |
| Детерминизм: 2 прогона runner-а | summary/ops/states идентичны ✓ |
| Детерминизм: 2 прогона report | metrics JSON и bytes идентичны ✓ |
| Ожидаемые метрики demo-фикстуры | совпадают с записью meta["expected"] ✓ |
| Null при пустом знаменателе | auto_answer/usefulness/handoffs/latency → null ✓ |
| Dedup repeated feedback | solved_rate n=3 (не 4) ✓ |
| AC20 duplicate case_id | обнаруживается ✓ |
| p50/p95 nearest-rank | demo 2850/5400; live 60000/134000 ✓ |
| Секреты в артефактах | отсутствуют (в т.ч. TENDERHACK_REPLY_KEY) ✓ |
| pytest | `python -m pytest tests evaluation/tests -q` → 48 passed ✓ |
| Реальный API smoke на A02 | **not run**: backend (A02) не реализован — все endpoints 501, работает только `/health`. По условию D02 real smoke «not run» при неготовности API, не blocker |

## Commands and actual outputs

```powershell
$env:PYTHONPATH = "D:\tender-hack-d02-d02-runner"
python -m pytest tests evaluation/tests -q
# 48 passed
python -m evaluation.runner --driver fixture --out var/evaluation/d02/suite_fixture.json
# {"operations_total": 19, "operations_ok": 19, "operations_error": 0,
#  "operations_skipped": 0, "...": "resolved v3", "not_run_reason": null}
python -m evaluation.report --demo --out var/evaluation/d02/report_demo.md --json-out var/evaluation/d02/metrics_demo.json
# demo: auto 0.5, confirmed 1/6, useful_ai 1.0, useful_operator 1.0, solved 2/3,
#       coverage 0.75, handoffs 1/6, no_answer 2/6, latency 2850/5400
# live: auto 0.5, confirmed 0.5, errors 0.5, timeouts 0.5, latency 60000/134000
# (deterministic mock fixture)
python -m evaluation.report var/evaluation/d02/demo_export.json --mock --source "deterministic demo/live fixture (D02)"
```

## Data mode: mock (fixtures) + real smoke not run

- Frontend dev: runner проверен на `contracts/fixtures` (mock=True).
- Real API smoke: не выполнялся (A02 501). Для запуска после готовности A02:
  `python -m evaluation.runner --driver http --base-url http://127.0.0.1:8000 --out var/evaluation/d02/suite_http.json`
  — read-only HTTP, app.sqlite не читается.

## Artifacts and paths

| Артефакт | Путь | Статус в Git |
|---|---|---|
| Runner | `evaluation/runner/*.py` | tracked (этот коммит) |
| Report-функции | `evaluation/report/*.py` | tracked |
| Тесты D02 | `evaluation/tests/*.py`, `README.md` | tracked |
| Trailing suite (fixture) | `var/evaluation/d02/suite_fixture.json` | gitignored (`var/`) |
| Demo export (mock) | `var/evaluation/d02/demo_export.json` | gitignored |
| Demo metrics JSON | `var/evaluation/d02/metrics_demo.json` | gitignored |
| Demo report MD | `var/evaluation/d02/report_demo.md` | gitignored |

## Known blockers and reproducible defects

- **D01 не влит в origin/main** (main на `dddb724f`, D01-ветка `origin/task/d01-dataset` на `c5d093c`).
  Работа велась от `c5d093c` (main + D01). Интегратору A нужно решить мерж D01; для D02 это не блокер
  (D02 не зависит от деплоя D01, но handoff D01 уже зафиксировал «Acceptance: passed»).
- **A02 API отсутствует**: backend — скелет C0, все endpoints 501. Демонстрационный real smoke = not run.
- Bare `pytest` не видит `evaluation/tests` (testpaths=["tests"] в pyproject — зона A); используем
  `python -m pytest tests evaluation/tests`.
- My fixture-драйвер поддерживает максимум 3 новых case на слот (QUEUE_FULL) — это лимит демо-сценария.

## Contract change requests

- Нет. Report-функции используют канонические модели C0 без изменения контракта.

## Inputs required by next tasks

- D09/D07: `python -m evaluation.report <export.json> --out report.md` (экспорт EvaluationExport от A через
  `tools/export_data`); runner для live-трасс: `python -m evaluation.runner --driver http ...`.
- B03: фикстуры состояний и версии Case покрыты fixture_driver (можно использовать как эталон).