# D09 Handoff — Отчёт по реальному dev и экспорту перед RC

## Общая информация

| Поле | Значение |
|---|---|
| TASK_ID | D09 |
| Владелец | D / Егор |
| BASE_SHA | `83a85d8` (origin/main после принятия D04) |
| Ветка | `task/d09` |
| Result SHA (branch HEAD) | `c93be1e3af9d2d4fdb119aaeeb2ca11a29d2327f` |
| Remote HEAD SHA (`origin/task/d09`) | `c93be1e3af9d2d4fdb119aaeeb2ca11a29d2327f` (local == remote, ветка опубликована) |
| Дата | 2026-09-13 |
| Машина | CPU (локальный Windows, Python 3.14); GPU не использовался |
| Статус | **done** |

Статус `done` корректен: все **обязательные** входы присутствуют — D02 (accepted в origin/main), D04 (accepted в origin/main), A04 export (воспроизведён из принятого A04 smoke/runtime и закоммичен). A05/B06 — внешние pending blockers для A06, для D09 не блокеры.

## Обязательные зависимости

| Вход | Путь | SHA-256 файла | Статус |
|---|---|---|---|
| D02 runner/report | `evaluation/report/metrics.py`, `evaluation/runner/*.py` | (в origin/main) | accepted в main |
| D04 reconciliation | `evaluation/reconciliation/d04_reconciled.jsonl` | `02403d83...66ab87` | accepted в main |
| **A04 export** | `evaluation/reports/a04_export.json` | `67eb8817...bebdb19` (git blob `e5a32915e9f2ea9eac6929c9cb43f15b365f15c6`) | воспроизведён D09 |

### A04 export — способ получения (exact command, CPU)

```powershell
$env:PYTHONPATH = "D:\tender-hack\backend;D:\tender-hack\contracts\python"
python -m tools.run_a04_e2e --output-dir var/a04
python -m tools.export_data --db var/a04/<созданный-a04-*.sqlite> --output evaluation/reports/a04_export.json --app-commit c93be1e3af9d2d4fdb119aaeeb2ca11a29d2327f
```

- Источник: принятый A04 smoke/runtime (`tools/run_a04_e2e.py`, в origin/main); экспорт через принятый `tools/export_data.py` + `backend/tenderhack_backend/export.py`.
- Классификация: **real backend / controlled no-model dependencies** (по дизайну A04; handoff/reply-путь generation не делает).
- Фактический прогон: 1 случай, Cаse `e86c357a-...`, Ticket `cafba42d-...`; переходы `handoff_offered/ticket:none → handed_off/ticket:new → handed_off/ticket:waiting_user → handed_off/ticket:new → resolved/ticket:resolved` (совпадает с A04 handoff).
- `check_export`: 1 заметка `ticket resolved without current_resolution` — ожидаемая семантика operator-resolution (в A04 smoke feedback не постился), не ошибка данных.
- Non-determinism: `export_id`/`created_at`/message ids генерируются заново (uuid4/timestamps) → байтовый дайджест файла меняется между прогонами; детерминирован сам конечный автомат smoke.

## Входные данные (прочие)

- Dev-набор D01: `evaluation/ai_test/dev/ai_test_dev.jsonl` (20 кейсов, sha `af04729d...`) + `dev/manifest.json` (sha `24f79bac...`).
- Historical: `evaluation/annotations/egor/D03_annotations.jsonl` (sha `6fd375c5...`), `evaluation/annotations/stas/B04_annotations.jsonl` (sha `bcf6c72c...`), reconcile `d04_reconciled.jsonl`.
- A03 real evidence: `docs/coordination/artem/A03-handoff.md` (accepted), pinned `retrieval_log_dev20.json` sha `47718bb1f2bf72451bcb8abd5ef2d9ba1ae2710119b154cb524732498ddd0cf0`.
- C07: accepted; snapshot `kb-4918a97f0874d1e8` — retrieval-evidence база.

## Datasets included / pending

**Included:**
- Dev-набор (20 кейсов; только факты набора; routing-исходы — null/unknown, см. ниже).
- Historical reconciliation (30 пар D04, согласия пересчитаны из аннотаций).
- Real E2E evidence A03 (retrieval smoke DEV-010/012/019; full HTTP E2E DEV-019).
- A04 export (1 real backend кейс, demo cohort, operator-resolution).
- C07 KB snapshot metadata.

**Pending (внешние, для A06, не для D09):**
- A05 resilience/offline — not in origin/main.
- B06 frontend regression — not in origin/main.

## Headline metrics — corrected, с provenance

| Блок | Метрика | Значение | Точный источник | Метод |
|---|---|---|---|---|
| DEV | Всего кейсов | 20/20 | `evaluation/ai_test/dev/manifest.json` (count), `ai_test_dev.jsonl` | count |
| DEV | answerable | 20/20 (100%) | `ai_test_dev.jsonl` (поле `answerable`) | count |
| DEV | Роли | 19 supplier / 1 customer | `ai_test_dev.jsonl` (`role`) | count |
| DEV | Routing исходы (auto-answer/handoff/escalate/clarify/errors/latency) | **null/unknown** | нет входного файла — нет реального dev-run EvaluationExport по 20 кейсам; D02 live smoke не выполнялся (A02 501) | — |
| Real E2E (A03) | retrieval smoke | DEV-010, DEV-012, DEV-019 — `ANSWER_ALLOWED` | A03 handoff + `retrieval_log_dev20.json` sha `47718bb1...` | real run |
| Real E2E (A03) | full HTTP E2E | DEV-019: resolved, answer_origin=rag, source `portal:292330:1`, generation_calls=1, e2e 15134.514 ms, no auto-retry | A03 handoff §«Accepted real E2E» | real run |
| A04 export | handoffs | 1/1 | `evaluation/reports/a04_export.json` (compute_metrics) | детерминированный расчёт |
| A04 export | auto_answer | 0/1 | там же | детерминированный расчёт |
| A04 export | errors / timeouts | 0/1 / 0/1 | там же | детерминированный расчёт |
| A04 export | usefulness/solved/feedback/latency | null (пустой знаменатель/нет данных) | там же | детерминированный расчёт |
| Historical | correctness согласия | 12/30 (40%) | D03 + B04 annotations (пересчитано) | сравнение по 4 измерениям |
| Historical | completeness согласия | 15/30 (50%) | D03 + B04 annotations (пересчитано) | сравнение |
| Historical | clarity согласия | 22/30 (73%) | D03 + B04 annotations (пересчитано) | сравнение |
| Historical | route согласия | 24/30 (80%) | D03 + B04 annotations (пересчитано) | сравнение |
| Historical | reconciled NA | 7/30 | `d04_reconciled.jsonl` (`not_assessable=true`) | count |
| Historical | reconciled critical errors | 0/30 | `d04_reconciled.jsonl` (`critical_error`=null у всех) | count |

Примечания по корректировке:
- Ранее заявленные «12/20 auto-answer, 3/20 handoff, 1/20 escalate, 2/20 clarify, 2/20 errors» — **удалены как не воспроизводимые** из файлов репозитория и ошибочно атрибутированные A03. A03 реально покрывает только DEV-010/DEV-012/DEV-019 (retrieval smoke) и DEV-019 (full E2E); DEV-* — набор D01/D02/C03 dev evaluation.
- Ранее заявленные latency 2850/5400 — это значения demo-фикстуры D02 (`demo_export`), не dev-набора; удалены.
- Роль-сплит исправлен: 19 supplier / 1 customer (не 18/2).

## Validation

| Проверка | Фактический результат |
|---|---|
| A04 export валиден | `EvaluationExport.model_validate` OK; `check_export` → 1 задокументированная ожидаемая заметка |
| d09_summary.json — валидный JSON | OK (исправлен ошибочный ключ `" cohorts"`) |
| согласия истории пересчитаны | `{correctness:12, completeness:15, clarity:22, route:24}`, NA_Stas=7 — совпадает с D04 |
| reconciled факты | NA=7, critical=0 из d04_reconciled.jsonl |
| originals D03/B04/D04 | `git diff origin/main` — пусто (не изменены) |
| sealed final | `evaluation/final_private/ai_test_final.jsonl`, `evaluation/ai_test/final_manifest.json` — `git diff origin/main` пуст, не открывались |
| mock/real | A03 real E2E и A04 real backend экспорт отделены от D02 demo-фикстуры; mock нигде не выдан за real |
| n/N и null | n/N везде, где численно возможно; пустые знаменатели → null |
| git diff --check | clean |

## Defects / blockers

| дефект/ограничение | владелец | влияние | статус |
|---|---|---|---|
| Нет закоммиченного реального dev-run EvaluationExport по 20 dev-кейсам → routing-исходы всего dev-набора не воспроизводимы | A (tools/export_data) / D07 | подтверждение dev-routing на frozen RC | открыто (не блокер D09) |
| A05 не в origin/main | A | A06 readiness | pending (внешний) |
| B06 не в origin/main | B | A06 readiness | pending (внешний) |
| Локальный env: editable `tenderhack` указывает на старый worktree `D:\tender-hack-d02-d02-runner` | — | команды требуют `PYTHONPATH` на текущий репо | note (не репо-дефект) |

## A06_INPUT_READY

**yes** — репорт, methodology, defects и A04 export готовы. A06/I дополнительно ждут принятия A05 и B06.

## Output paths

| Артефакт | Путь |
|---|---|
| Markdown репорт | `reports/d09_dev_report.md` |
| Summary JSON | `evaluation/reports/d09_summary.json` |
| A04 export (обязательный ввод) | `evaluation/reports/a04_export.json` |
| Handoff | `docs/coordination/egor/D09-handoff.md` |

## Репродукция (без LLM/GPU)

```powershell
# dev-set факты
python -c "import json,collections; rows=[json.loads(l) for l in open('evaluation/ai_test/dev/ai_test_dev.jsonl',encoding='utf-8')]; print(len(rows), collections.Counter(r['role'] for r in rows), collections.Counter(r['answerable'] for r in rows))"

# исторические согласия из аннотаций (D03 vs B04, B04 not_assessable = расхождение)
# => {correctness:12, completeness:15, clarity:22, route:24}

# reconciled факты
python -c "import json; rec=[json.loads(l) for l in open('evaluation/reconciliation/d04_reconciled.jsonl',encoding='utf-8')]; print(sum(1 for r in rec if r['not_assessable']), sum(1 for r in rec if r.get('critical_error')))"   # => 7 0

# A04 export + метрики
$env:PYTHONPATH = "D:\tender-hack\backend;D:\tender-hack\contracts\python"
python -m tools.run_a04_e2e --output-dir var/a04
python -m tools.export_data --db var/a04/<generated>.sqlite --output evaluation/reports/a04_export.json --app-commit c93be1e3af9d2d4fdb119aaeeb2ca11a29d2327f
python -m evaluation.report evaluation/reports/a04_export.json --json-out var/evaluation/d09/a04_metrics.json
```

## Contract change requests

Нет. Использованы существующие канонические контракты (C0/EvaluationExport) без изменений.

## Для следующего шага

- A06: переданы репорт и defects. Интегратор A проверяет `reports/d09_dev_report.md`, `evaluation/reports/d09_summary.json`, `evaluation/reports/a04_export.json` и этот handoff по разделу 16.
- D07 (после RC): реальный dev-run EvaluationExport по final-набору через `tools/export_data` закроет открытый дефект DEV_RUN_EXPORT_MISSING.