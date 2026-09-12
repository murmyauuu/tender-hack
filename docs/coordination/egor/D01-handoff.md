# D01 — handoff

- Status: done
- Owner / tool: Егор / opencode (big-pickle)
- Base SHA: dddb724f454c986a60c6b3243db41f22bfbfabea
- Result SHA: (pending commit)
- Contracts version: 2.0.0-c0
- Machine profile: local, Python 3.14.5, pandas 3.0.3, openpyxl 3.1.5, PowerShell 5.1
- Runtime SHA / KB snapshot: knowledge_base_FINAL.jsonl (1 468 records), SHA-256 71bf714a9e205a35f5d8ec0fd2d0f9bbd4ad3a8409968b754eb8de7b349d79ae
- Changed files:
  - `evaluation/history/pairs_manifest.json` — единый манифест 30+10 исторических пар (ранее создан в ходе D01)
  - `evaluation/history/build_pairs_manifest.py` — скрипт генерации манифеста
  - `evaluation/ai_test/build_ai_test.py` — генератор 20 dev + 40 final AI-test cases
  - `evaluation/ai_test/dev/ai_test_dev.jsonl` — 20 dev cases (published, для C03/A03)
  - `evaluation/ai_test/dev/manifest.json` — dev manifest с хэшами
  - `evaluation/ai_test/final_manifest.json` — final manifest (хэши только, sealed content в final_private)
  - `evaluation/final_private/ai_test_final.jsonl` — 40 sealed final cases (gitignored, в репозиторий не входит)

## Implemented behavior

### 1. История: 30 подтем-стратифицированных пар + 10 резервных

- Исходные данные: история 24 960 строк; после дедупа и исключения TRN — 19 501 допустимых кандидатов.
- Учебные исключения (из постановки D00): rows 0, 4452, 2677, 11957, 12574, 24029, 17047, 22653.
- Метод: стратификация по 17-тематическому axial-коду, под TopicsApprox 分层 отбор вниз (60 кандидатов → отбор ближайших пары с расстоянием ≥8, исключение парафраз) → финальные 30 + 10 резервных.
- Все 30+10 пар сгруппированы pair_id HIST-0001..0030 (selected) и HIST-R01..R10 (reserve), pair_status зафиксирован; pair_id пересечения отсутствуют.
- Манифест `evaluation/history/pairs_manifest.json` не содержит текста (хэши SHA-256, row_index, sanitized labels).

### 2. AI-test: 20 dev + 40 final cases

- Все `gold_source_ids` и `evidence_refs` проверены против реальных записей KB (0 missing).
- Each case содержит: test_id, group_id, split, messages/actions, answerable, expected_outcome, role, gold_source_ids, required_conditions, forbidden_claims, gold_line/allowed_lines, recipient, evidence_refs.
- Paraphrase-группы: group_id выделена до split. Все группы dev и final строго разделяются (нет пересечений).
- В dev наборе продемонстрирована пара-парафраз (GRP-D01 и GRP-D04 — по два test_id на группу для использования multi-turn и вариаций).
- answerable=false тесты (FIN-037, FIN-038, FIN-039, FIN-040) проверяют корректный отказ/transfer.

### 3. Хранение

- Dev: опубликован полностью в `evaluation/ai_test/dev/` (git-tracked).
- Final: `evaluation/final_private/ai_test_final.jsonl` (gitignored) + `evaluation/ai_test/final_manifest.json` (только хэши, git-tracked).

## Acceptance: passed

| Проверка | Результат |
|---|---|
| Dev cases count | 20 ✓ |
| Final cases count | 40 ✓ |
| gold_source_ids в KB | 0 missing (0/60×N) ✓ |
| Paraphrase group leak dev↔final | None (gdev ∩ gfin = ∅) ✓ |
| group_id до split | Да ( все группы уникальны, dev группы не разбиты на split) ✓ |
| final_private gitignored | Да (.gitignore строка `evaluation/final_private/`) ✓ |
| Рабочее дерево чистое до D01 | Да (ветка task/d01-dataset, SHA dddb724) ✓ |

## Commands and actual outputs

```
python -X utf8 evaluation/ai_test/build_ai_test.py
# OK dev=20 final=40
# dev sha 7dff9fc14660e1f938208987400dd65ec70bde164f1c91168b1e91350084cda2
# final sha 317faca18abce7632020d89af4adb16a91630c1693dc6f295ac3bcdd3ce670f4
```

## Data mode: real

- KB: 1 468 записей (527 portal_knowledge_base_api + 941 organizer_pdf), SHA-256 совпадает с обязательным из A00/D00.
- Все gold_source_ids относятся к реальным записям portal_knowledge_base_api (id верифицированы).
- Исторические пары: реальные строки истории (xlsx), 30 подтем-стратифицированных, без synth.

## Artifacts and paths

| Артефакт | Путь | Статус в Git |
|---|---|---|
| Исторический манифест | `evaluation/history/pairs_manifest.json` | tracked (committed ранее) |
| Генератор манифеста | `evaluation/history/build_pairs_manifest.py` | tracked |
| Генератор AI-test | `evaluation/ai_test/build_ai_test.py` | tracked |
| Dev AI-test | `evaluation/ai_test/dev/ai_test_dev.jsonl` | tracked |
| Dev manifest | `evaluation/ai_test/dev/manifest.json` | tracked |
| Final manifest (хэши) | `evaluation/ai_test/final_manifest.json` | tracked |
| Final AI-test (sealed) | `evaluation/final_private/ai_test_final.jsonl` | gitignored |

## Known blockers and reproducible defects

- Нет.
- Ключевые ошибки PowerShell (ошибки NativeCommandError через stderr) — это нормальное поведение; они не являлись сбоями Python и не влияли на результат.
- Депрекация `codecs.open` — исправлена; аналогичные предупреждения не влияют на результат.

## Contract change requests

- Нет.

## Inputs required by next tasks

- B04 (Стас): `evaluation/history/pairs_manifest.json` (30 pair_id + hash/row refs)
- D03 (Егор): `evaluation/history/pairs_manifest.json` (30 pair_id + hash/row refs)
- C03/A03: `evaluation/ai_test/dev/ai_test_dev.jsonl` (20 cases, tuning retrieval/evidence)
- D02/D07/D09: `evaluation/ai_test/final_manifest.json` + `evaluation/final_private/ai_test_final.jsonl` (40 sealed final)
