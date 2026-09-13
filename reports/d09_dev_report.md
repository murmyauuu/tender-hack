# D09: Dev & Evaluation Report (до RC)

**Статус**: `done` — все обязательные входы присутствуют: D02 (accepted в origin/main), D04 (accepted в origin/main), A04 export (воспроизведён из принятого A04 smoke/runtime, закоммичен в evaluation/reports/a04_export.json).

- **BASE_SHA**: `83a85d8` (origin/main после принятия D04)
- **Branch**: `task/d09`
- **Branch HEAD SHA / Result SHA**: `c93be1e3af9d2d4fdb119aaeeb2ca11a29d2327f`
- **remote HEAD SHA** (`origin/task/d09`): `c93be1e3af9d2d4fdb119aaeeb2ca11a29d2327f` (ветка опубликована, local == remote)
- **A06_INPUT_READY**: `yes` (репорт D09 готов для A06; A06 дополнительно ждёт A05/B06 как внешних blockers)

---

## 1. Входы и provenance

| Вход | Путь | SHA-256 (файла) | Git blob | Статус |
|---|---|---|---|---|
| Dev-набор (D01) | `evaluation/ai_test/dev/ai_test_dev.jsonl` | `af04729dd3f708b2ec16e043486c06dbbf54e76003dd12e2e91e62d202aff786` | — | в main |
| Dev-манифест (D01) | `evaluation/ai_test/dev/manifest.json` | `24f79bac9fa65359c03dce24f58e3fc1b67125494f536de7bbf0788393cc263a` | — | в main |
| Аннотации D03 | `evaluation/annotations/egor/D03_annotations.jsonl` | `6fd375c56b60ae0a0fd2f1cc350f78efbdcfa3cbfc21131c563c4f504e2f8e60` | — | в main, не изменены |
| Аннотации B04 | `evaluation/annotations/stas/B04_annotations.jsonl` | `bcf6c72c9a4238ee53a7ad4a68c7558c623c87f9791e4bcb3063e30d2f711821` | — | в main, не изменены (чужой файл не редактировался) |
| Reconcile D04 | `evaluation/reconciliation/d04_reconciled.jsonl` | `02403d8305f1012ecd2a4d2a2f9496031e7e226343a036e7dee09cf00866ab87` | — | в main, не изменён |
| **A04 export (обязательный ввод)** | `evaluation/reports/a04_export.json` | `67eb88178c69979fb45ce484080d7aad56d5b2ab1c981461b17b47efbeebdb19` | `e5a32915e9f2ea9eac6929c9cb43f15b365f15c6` | **этот коммит D09** |
| A03 evidence (real E2E, retrieval smoke) | `docs/coordination/artem/A03-handoff.md` (accepted в main) + pinned `retrieval_log_dev20.json` sha `47718bb1f2bf72451bcb8abd5ef2d9ba1ae2710119b154cb524732498ddd0cf0` | — | — | в main |

- D02 (runner/report) и D04 (reconciliation) — accepted в origin/main: `evaluation/report/metrics.py`, `evaluation/runner/suite.py`, `evaluation/reconciliation/d04_reconciled.jsonl` присутствуют в `origin/main`.
- C07 (KB) accepted в main; snapshot `kb-4918a97f0874d1e8` — retrieval-evidence база (по A03/C03).
- Sealed final (`evaluation/final_private/ai_test_final.jsonl`, `evaluation/ai_test/final_manifest.json`) — `git diff origin/main` пуст, не открывались.

---

## 2. DEV block (набор D01)

**Источник**: `evaluation/ai_test/dev/ai_test_dev.jsonl` (20 кейсов DEV-001..DEV-020), манифест `evaluation/ai_test/dev/manifest.json`.

| Показатель | Значение | метод / источник |
|---|---|---|
| Всего dev-кейсов | 20/20 | count по jsonl = манифест (`count: 20`) |
| answerable=true | 20/20 | поле `answerable` в jsonl; в манифесте всех 20 `answerable: true` |
| Роли | 19 supplier / 1 customer | поле `role` в jsonl |
| Группы GRP | 18 групп (GRP-D01..GRP-D18) | поле `group_id` в jsonl |

**Важно (корректировка)**: routing-исходы по всему dev-набору — auto-answer, handoff, escalate, clarify, errors, latency — **не воспроизводятся из файлов этого репозитория и отмечены как `null/unknown`**. Причина: для этого нужен реальный dev-run `EvaluationExport` по всем 20 кейсам (`python -m evaluation.report <export.json>`), а такого экспорта в репозитории нет; D02 live smoke не выполнялся (на момент D02 реальный API отсутствовал — все endpoints 501, см. D02 handoff). Ранее заявленные «12/20 auto-answer, 3/20 handoff, 1/20 escalate, 2/20 clarify, 2/20 errors» **удалены**: они не пересчитываются ни из одного файла репозитория и являлись ошибочной атрибуцией.

Реальный evidence по dev-набору есть только по тем кейсам, которые реально прогнаны (см. §3): DEV-010, DEV-012, DEV-019 (retrieval smoke) и DEV-019 (full HTTP E2E).

---

## 3. Live / real E2E block (evidence A03)

**Источник**: `docs/coordination/artem/A03-handoff.md` (accepted). Класс evidence: **real**.

### 3.1 Real retrieval smoke (A03)

| Кейс | Результат |
|---|---|
| DEV-010 | `ANSWER_ALLOWED` (dense candidates) |
| DEV-012 | `ANSWER_ALLOWED` (dense candidates) |
| DEV-019 | `ANSWER_ALLOWED` (dense candidates) |

Pinned runtime artifact: `retrieval_log_dev20.json` sha `47718bb1f2bf72451bcb8abd5ef2d9ba1ae2710119b154cb524732498ddd0cf0` (A03; dev20 — dev-набор, не «20 принятых A03 кейсов»).

### 3.2 Accepted full HTTP E2E (A03, DEV-019)

- Вопрос: «Как изменить банковские реквизиты организации на Портале поставщиков?»
- Case ID `12d8773c-6340-4b01-8b18-3dba0b044fb5`, Request ID `4829958c-2a43-4d71-8efe-f8daed9721cf`
- HTTP: session `201`, chat `202`, source `200`, feedback `201`; lifecycle `queued → processing/generating → final`
- Query embedding `1`, retrieval `1`, generation `1`; **автоматического повторного generation нет**
- Финальный статус после feedback: `resolved`; `current_resolution.confirmed_by=user`, `answer_origin=rag`
- Источник ответа: `portal:292330:1` (единственный eligible source)
- Feedback: `useful=true`, `solved=true`, `outcome_applied=true`
- Actual timings (ms): query embedding `10844.698`; retrieval `10985.834`; time to first source `10998.456`; Ollama prompt eval `27.646`; Ollama decode `3944.626`; Ollama total `4100.373`; generation total `4111.275`; end-to-end `15134.514`

---

## 4. A04 export (обязательный вход, воспроизведён)

**Путь**: `evaluation/reports/a04_export.json` · **SHA-256**: `67eb8817...ebdb19` · **git blob**: `e5a32915...`

**Exact reproduction command** (CPU; GPU не используется; требует PYTHONPATH на текущий worktree из-за editable-install старого D02 worktree в site-packages):

```powershell
$env:PYTHONPATH = "D:\tender-hack\backend;D:\tender-hack\contracts\python"
python -m tools.run_a04_e2e --output-dir var/a04
# создаёт var/a04/a04-<uuid>.sqlite — реальный backend runtime (A04 smoke)
python -m tools.export_data --db var/a04/<созданный>.sqlite --output evaluation/reports/a04_export.json --app-commit c93be1e3af9d2d4fdb119aaeeb2ca11a29d2327f
```

- Классификация: **real backend / controlled no-model dependencies** (по дизайну A04: handoff-путь не делает generation; см. A04 handoff).
- Содержимое: 1 строка `EvaluationRow`; `cohort=demo`, `case_status=resolved`, `ticket=resolved (resolved_by=operator)`; переходы состояния совпадают с A04 handoff: `handoff_offered/ticket:none → handed_off/ticket:new → handed_off/ticket:waiting_user → handed_off/ticket:new → resolved/ticket:resolved`.
- Метрики по экспорту (`compute_metrics`): `handoffs 1/1`; `auto_answer 0/1`; `confirmed_auto_resolution 0/1`; `errors 0/1`; `timeouts 0/1`; `usefulness/solved/feedback` — `null` (в A04 smoke feedback не постился); latency — `null` (total timings отсутствуют на no-model пути).
- `check_export` выводит одну задокументированную структурную заметку: `ticket resolved without current_resolution`. Это **ожидаемо** для пути A04 (resolved_by=operator без user-feedback), не является ошибкой данных; зафиксировано как ограничение.
- Non-determinism byte-level: `export_id`/`created_at`/message IDs генерируются заново (uuid4+now), поэтому точный байтовый дайджест файла меняется между прогонами; детерминирован сам конечный автомат smoke (переходы и тексты — фиксированы, подтверждены A04 handoff).

---

## 5. Historical block (D04)

**Источники**: `evaluation/annotations/egor/D03_annotations.jsonl` + `evaluation/annotations/stas/B04_annotations.jsonl` (согласия, пересчитаны), `evaluation/reconciliation/d04_reconciled.jsonl` (reconciled значения).

### 5.1 Согласия D03 vs B04 (пересчитаны из аннотаций)

| Измерение | Согласий | Расхождений (вкл. NA Stas) | Rate |
|---|---|---|---|
| correctness | 12/30 | 18 | 40% |
| completeness | 15/30 | 15 | 50% |
| clarity | 22/30 | 8 | 73% |
| route | 24/30 | 6 | 80% |

Пересчёт: сравнение по `pair_id`, по-измерение значения D03 (flat) против B04 (`ratings.*`); `not_assessable` у B04 считается расхождением. Фактический вывод скрипта: `{correctness:12, completeness:15, clarity:22, route:24}`, NA(B04)=7 по correctness, 0 по остальным. Совпадает с D04 handoff/manifest.

### 5.2 Reconciled результаты (из d04_reconciled.jsonl)

- Reconciled NA: **7/30** (`not_assessable=true` в файле)
- Reconciled critical errors: **0/30** (`critical_error` — все null)
- Все 7 NA — решения Stas, подтверждены в reconciliation (причины в D04 handoff)

### 5.3 Ограничения (из D04)

- Выборка 30 пар — не гарантия репрезентативности всего трафика поддержки
- NA меняют эффективный знаменатель
- Исторические ответы могли быть корректны при старой инструкции
- Отсутствие текущего источника не означает автоматическую ошибку
- Разные схемы аннотаций (flat vs nested) усложняют сравнение

---

## 6. A05 / C07 / B06

| Блок | Статус | Примечание |
|---|---|---|
| C07 KB | **accepted в main** | snapshot `kb-4918a97f0874d1e8` — retrieval-evidence база; результат учтён через A03/C03 evidence |
| A05 resilience/offline | **pending** | не в origin/main; внешний blocker для A06, не для D09 |
| B06 frontend regression | **pending** | не в origin/main; внешний blocker для A06, не для D09 |

---

## 7. Defects / blockers

| дефект/ограничение | evidence | владелец | влияние на RC | статус |
|---|---|---|---|---|
| Нет закоммиченного реального dev-run `EvaluationExport` по всем 20 dev-кейсам → routing-исходы всего dev-набора не воспроизводимы | отсутствие экспорта в репо; D02 live smoke не выполнен (A02 501 на тот момент) | A (tools/export_data) / D07 (получит на final) | dev-routing будет подтверждён на frozen RC | открыто/D07 |
| A05 не в origin/main | handoff отсутствует | A | A06 readiness | pending (внешний) |
| B06 не в origin/main | handoff отсутствует | B | A06 readiness | pending (внешний) |
| Environment: editable install `tenderhack` указывает на старый worktree `D:\tender-hack-d02-d02-runner` | `__editable__.tenderhack-0.0.0.pth` | — (локальная машина) | команды требуют `PYTHONPATH` на текущий репо | note (не репо-дефект) |

---

## 8. Readiness

- **A06 readiness (со стороны D09)**: репорт, methodology, defects и A04 export готовы.
- **A06_INPUT_READY**: `yes`.
- A05/B06 остаются внешними blockers для **A06/I** (feature freeze), не для D09.

---

## 9. Reproducibility commands

```powershell
# recompute dev-set facts (counts, roles, answerable)
python -c "import json,collections; rows=[json.loads(l) for l in open('evaluation/ai_test/dev/ai_test_dev.jsonl',encoding='utf-8')]; print(len(rows), collections.Counter(r['role'] for r in rows), collections.Counter(r['answerable'] for r in rows))"

# recompute historical agreements from annotations
# (скрипт: сравнение D03 vs B04 по 4 измерениям, B04 not_assessable = расхождение)
# => {correctness:12, completeness:15, clarity:22, route:24}

# recompute historical reconciled facts
python -c "import json; rec=[json.loads(l) for l in open('evaluation/reconciliation/d04_reconciled.jsonl',encoding='utf-8')]; print(sum(1 for r in rec if r['not_assessable']), sum(1 for r in rec if r.get('critical_error')))"
# => 7 0

# validate A04 export
$env:PYTHONPATH = "D:\tender-hack\backend;D:\tender-hack\contracts\python"
python -m evaluation.report evaluation/reports/a04_export.json --json-out var/evaluation/d09/a04_metrics.json
```

Репорт-функции (`evaluation/report/*.py`) детерминированы и не используют LLM/GPU.

---

## 10. Validation checks passed

- [x] Все числа пересчитаны из конкретных файлов-источников (таблица §1); не воспроизводимые значения → `null/unknown`
- [x] n/N присутствует везде, где численно возможно; пустые выборки → null (feedback/latency A04)
- [x] A04 export валиден: `EvaluationExport.model_validate` + `check_export` (1 задокументированная ожидаемая заметка про operator-resolved без feedback)
- [x] d09_summary.json — валидный JSON (исправлен ошибочный ключ `" cohorts"`)
- [x] Originals D03/B04/D04 — без diff относительно origin/main
- [x] Sealed final (`final_private/ai_test_final.jsonl`, `final_manifest.json`) — без diff относительно origin/main, не открывались
- [x] git diff --check — clean
- [x] Mock/fixture нигде не выдан за real; A03 real E2E / A04 real backend экспорт разграничены от D02 demo-фикстуры