# C04 — handoff

- **Task ID / status:** C04 — Маршрутизация и уточнение knowledge-поведения / **done** (CPU-only, G не требовался)
- **Owner / tool:** Эдуард / агент C / Claude Code
- **Base SHA:** `7d7b44c41f6996478105534ec933aa920f6fc1f1` (`origin/main`, совпадает с BASE_SHA из задания)
- **Result SHA:** см. финальное сообщение чата (HEAD ветки `task/c04` после этого handoff-коммита)
- **Ветка / worktree:** `task/c04` / `/Users/gunter/Desktop/tenderhack-c04`

## 0. Важная оговорка про базу — почему в истории есть merge-коммит

На момент старта C03 (`knowledge/kb/retrieval.py`, `dense/**`, `lexical.py`) **ещё не был смёржен
интегратором в `origin/main`** — подтверждено фактически:

```
$ git ls-tree -r origin/main --name-only | grep '^knowledge/kb/'
knowledge/kb/__init__.py
knowledge/kb/classify.py
knowledge/kb/ingest.py
knowledge/kb/normalize.py
knowledge/kb/pdf_text.py
knowledge/kb/schema.py
knowledge/kb/store.py
knowledge/kb/tests/...           # НЕТ retrieval.py/lexical.py/dense/
```

C04 по заданию обязан **реализовать** `route: RoutingResult` внутри `retrieve()` — то есть физически
редактировать `knowledge/kb/retrieval.py`, файл, которого в `main` ещё нет. Задание разрешает читать
C03 «напрямую с ветки origin/task/c03» для контекста (как A01/D01 до их мержа), но здесь этого
недостаточно: нужен САМ файл для правки, не только чтение для справки.

Решение: `task/c04` создана от `origin/main` (BASE_SHA), затем **один явный merge-коммит**
`git merge origin/task/c03` (тот же паттерн, что уже используется в истории `main` —
`feat(integration): Merge C01/C02/B01 …`). Это не копирование файлов вручную и не пересоздание чужого
результата: обычная git-операция интеграции зависимости, конфликтов не было (`Merge made by the 'ort'
strategy`, файлы C04 в diff отсутствовали на тот момент). После A примет C03 в `main` этот merge-коммит
станет тривиально сводимым (fast-forward-совместимым) с уже интегрированной версией C03.

```
$ git merge-base origin/task/c03 origin/main
7988174aa1af7e2fbebc8a4980f43f84fa10e1e8    # общий предок — до D01/A01-докс коммитов
$ git merge origin/task/c03 --no-edit
Merge made by the 'ort' strategy.
 19 files changed, 2768 insertions(+), 32 deletions(-)   # ровно файлы C03, ни одного конфликта
```

Все изменения ЭТОЙ задачи (C04) находятся **поверх** этого merge-коммита и видны отдельно:

```
$ git diff --stat <merge-commit-sha>
 knowledge/kb/retrieval.py | 86 +++++++++++++++++++++++++++++++++++++++--------
 1 file changed, 72 insertions(+), 14 deletions(-)
$ git status --short   # + untracked новые файлы C04
 M knowledge/kb/retrieval.py
?? config/knowledge/routing_lines.json
?? config/knowledge/taxonomy.json
?? knowledge/kb/routing.py
?? knowledge/kb/taxonomy_build.py
?? knowledge/kb/tests/test_routing.py
```

- **Contracts version:** `2.0.0-c0`, **не менялся** (`RoutingResult`/`KnowledgeResult`/`ReasonCode` использованы как есть).
- **Machine / runtime:** M — MacBook Air M2 (arm64), 8 GiB RAM, macOS, Python 3.13.12. GPU не использовался и не требовался (задание: «G только для ограниченного dev smoke» — dev smoke здесь целиком CPU, dense по-прежнему недоступен, см. §6 ниже).
- **KB snapshot:** `kb-4918a97f0874d1e8` — идентичен C02/C03 (не пересобирался):
  `var/knowledge/knowledge.sqlite` SHA-256 `6d1555777d9bbf9ae7f2df93a69cf61f53dd04263877a8ebaf7fc35e16a4bdf8`,
  `var/knowledge/manifest.json` SHA-256 `e0d01a74dcfe43f8a562a10837793fa04a052e775e60877115dce7785f24d061`.

---

## 1. Changed files

Только зона C (`knowledge/**`, `config/knowledge/**`, `docs/coordination/eduard/**`):

| Файл | Назначение | Строк |
|---|---|---|
| `knowledge/kb/taxonomy_build.py` | Разбор реального `НН 2026/Темы_подтемы_обращений.xlsx` (zip+XML, stdlib) → канонический `config/knowledge/taxonomy.json` | 156 |
| `config/knowledge/taxonomy.json` | Сгенерированный справочник: 9 тем / 86 строк / 82 уникальные подтемы, `theme_id`(TH1-9)/`subtopic_id`(ST01-86) — стабильная нумерация самого файла, не выдуманная | 611 |
| `config/knowledge/routing_lines.json` | Baseline L1/L2 по теме + 3 subtopic-override с обоснованием (rationale в самом файле) | 42 |
| `knowledge/kb/routing.py` | `match_topic`, `detect_defect_signals`, `extract_recipient`, `decide_support_line`, `build_routing_result` — вся логика C04 | 421 |
| `knowledge/kb/retrieval.py` | **изменён** (поверх C03): `route=RoutingResult()` → `route=build_routing_result(...)`; `_is_out_of_scope` расширен (см. §4); `_STOPWORDS` дополнен предлогами | +72/-14 |
| `knowledge/kb/tests/test_routing.py` | 32 теста: unit (topic/defect/recipient/line) + интеграционные на реальном снимке | 460 |
| `docs/coordination/eduard/C04-handoff.md` | этот файл | — |

Чужого не трогал: `pyproject.toml`, `contracts/**`, `backend/**`, `tools/**`, `tests/**`,
`docs/integration/**`, `config/runtime/**`, `knowledge/policy/**` (C01), `knowledge/audit/**` (C00),
`config/knowledge/policy_rules.json` — без изменений (проверено ниже). Файлы C03 (`lexical.py`,
`dense/**`, `index_build.py`, `store.py`, `gpu/**`) не редактировались вообще — только
`retrieval.py`, и только в местах, явно относящихся к routing/OOS.

```
$ git diff --stat -- pyproject.toml config/runtime/ contracts/ backend/ tools/ tests/ knowledge/policy/ knowledge/audit/ config/knowledge/policy_rules.json
(пусто)
```

---

## 2. Implemented behavior

### 2.1. Taxonomy — реальный справочник, 9/86 не выдуманы

`НН 2026/Темы_подтемы_обращений.xlsx` — Office Open XML, разобран через stdlib `zipfile` +
`xml.etree.ElementTree` (без openpyxl/pandas, та же линия «только stdlib», что и весь `knowledge/kb/**`).
Тема указана только в первой строке своего блока (объединённые ячейки в источнике) — реализовано
вперёд-заполнение (`current_theme`). Проверено фактически, совпадает с C00 буквально:

```
$ uv run python -m knowledge.kb.taxonomy_build
themes=9 subtopic_rows=86 subtopics_distinct=82 -> config/knowledge/taxonomy.json
```

`theme_id`/`subtopic_id` — НЕ выдуманы: `theme_id` = порядковый номер темы по первому появлению в
файле (TH1..TH9), `subtopic_id` = буквально колонка «№» источника (ST01..ST86). Справочника
линий/адресатов эта таблица не содержит и не притворяется, что содержит (см. §7 blockers).

### 2.2. Routing — два прохода (§10)

`knowledge/kb/routing.py`:

1. **Первый проход (дешёвые признаки самого запроса):**
   - `match_topic(query_text)` — нормализованное (`fts_normalize`, та же C02-нормализация/стемминг,
     что и FTS-индекс — не второй способ разбора текста) точное совпадение ВСЕХ ключевых слов
     подтемы. Резервное правило — только для токенов, которые сами являются
     аббревиатурой/кодом (`is_abbreviation_or_code` из `lexical.py`, не второй парсер) и уникальны для
     всей taxonomy (`РДИК`→ST75, `YML`→ST50, `ЕИС`→ST77) — покрывает случаи, когда вопрос называет
     только код, а не остальные слова описательной подтемы. **Обычные существительные, даже редкие
     в taxonomy** (например «поставщик»), в резерв не попадают — найдено и исправлено во время
     разработки как источник ложных совпадений (regression-тест
     `test_match_topic_generic_common_word_is_not_a_distinctive_fallback`).
   - `detect_defect_signals(query_text)` — категории A (цитируемая ошибка рядом со словом «ошибка»),
     B (явный язык воспроизводимости/инцидента: «постоянно», «каждый раз», «зависает», …), C (голая
     формула «не работает»). РДИК-подобные коды явно исключены как признак дефекта (документированный
     валидационный контроль, не баг — C03-handoff §2.4/§8).
   - `decide_support_line` — L1/L2 baseline из `config/knowledge/routing_lines.json` (по теме, с 3
     subtopic-override), L3 — **только** при сочетании категорий B+(A или C); неопределённость L1/L2 →
     L2 triage (не ambiguous); неопределённость L2/L3 без recurrence → L2 triage + `is_ambiguous=true`;
     нет topic-совпадения вообще → `support_line=null` (НЕ автоматический L2).
2. **Второй проход (проверенная metadata уже найденных evidence, БЕЗ второго embedding):**
   - `match_topic(..., evidence=...)` — подтверждает совпадение через `basis_source_ids` (title/text
     кандидатов, уже найденных C03's `retrieve()`).
   - `extract_recipient(evidence, selected_ids)` — деterministic поиск буквальной фразы «обратитесь в /
     направьте обращение в …» **только в тексте наивысшего по score SELECTED evidence** (не во всём
     selected-наборе и тем более не в остальных candidates — см. §5, найденная и исправленная проблема
     с посторонним referral). Это не выдуманный справочник (которого нет, BL-C00-2) — это буквальный
     текст реального источника, который уже показан пользователю как основание ответа.

`build_routing_result` собирает всё в `RoutingResult` без изменения формы контракта.

### 2.3. Wiring в `retrieval.py`

- `run_pipeline`: `route=RoutingResult()` (нейтральный от C03) → `route=build_routing_result(query.text,
  evidence_items, selected_ids)`.
- `_is_out_of_scope` расширен: узкий сигнал C03 (пустой/приветственный ввод) сохранён буквально;
  добавлено осторожное расширение — содержательные токены есть, но НИ dense/exact-хиты, НИ
  содержательный (без стоп-слов) FTS-хит, НИ `match_topic` не находят вообще ничего общего с запросом →
  `OUT_OF_SCOPE`. Дешёвая, отдельная от основного retrieval FTS-проверка ТОЛЬКО по не-стоп-словным
  токенам — реальный поиск по всем токенам запроса (включая предлоги) даёт по редкому предлогу
  искусственно высокий bm25 из-за обратной частотности документа (найдено и исправлено, см. §5).
  `_STOPWORDS` дополнен предлогами/частицами (`про`, `о`, `об`, `от`, `до`, `из`, `за`, `под`, `над`,
  `при`, `для`, `не`, `ли`, `же`, …), которых не хватало в исходном C03-наборе.
- `decide_gate`/`_is_out_of_scope` получили новый keyword-only параметр `conn: sqlite3.Connection | None
  = None` (по умолчанию — не ломает существующие 9 синтетических unit-тестов C03, которые вызывают
  `decide_gate` без реального соединения).

---

## 3. Acceptance — AC03/AC04/AC06/AC07 (реальный прогон)

| Критерий | Что проверено | Результат |
|---|---|---|
| **AC03** — роль: одно уточнение, затем ответ/передача | `test_integration_role_clarify_still_works_route_is_still_present` — C03's role-clarify (CLARIFY→ROLE_REQUIRED→ANSWER_ALLOWED после подтверждения) не сломан добавлением routing; `route` присутствует (не Optional по контракту) даже во время CLARIFY | **passed** |
| **AC04** — pointer/missing attachment/conflict без выдуманных шагов | `test_integration_missing_attachment_never_forces_l3_on_real_kb` — DEV-015-подобный реальный вопрос (gold source `content_status=incomplete`) не создаёт необоснованный L3; `is_probable_defect=False` | **passed** |
| **AC06** — OUT_OF_SCOPE отдельно от сбоя | `test_integration_out_of_scope_extended_for_genuinely_unrelated_query` («Расскажи анекдот про программиста и кота» → `OUT_OF_SCOPE`, не `ESCALATE`/`SEARCH_UNAVAILABLE`); `test_integration_greeting_out_of_scope_regression_not_broken` (узкий сигнал C03 не сломан) | **passed** (оба) |
| **AC07** — нет L3 по одному «не работает»; адресат отдельно от линии | `test_integration_bare_ne_rabotaet_on_real_kb_never_yields_l3` (реальный снимок); `test_bare_ne_rabotaet_alone_is_not_a_defect_signal` (unit); `support_line`/`recommended_recipient` — независимые поля, независимые функции (`decide_support_line`/`extract_recipient`), заполняются раздельно (видно в §6 — L1/L2/L3 без recipient и наоборот) | **passed** |

Полный прогон:

```
$ uv run pytest knowledge/kb/tests/test_routing.py -v
32 passed in ~0.2s (без snapshot_dir fixture) / полный файл с интеграционными ~4s
$ uv run pytest
428 passed in 17.30s   # было 392 до C04 (C03 baseline) -> +36 (32 в test_routing.py + 4 доп.
                       # параметризации в test_no_model_calls.py от 2 новых top-level файлов)
```

---

## 4. Commands and actual outputs

### Git preflight

```
$ git fetch --prune origin && git switch main && git pull --ff-only origin main && git status --short
Already on 'main'. Already up to date. (пусто)
$ git rev-parse HEAD
7d7b44c41f6996478105534ec933aa920f6fc1f1
$ git ls-tree -r origin/main --name-only | grep 'knowledge/kb/retrieval\|knowledge/kb/lexical\|knowledge/kb/dense'
(пусто — C03 ещё не в main, см. §0)
$ git worktree add ../tenderhack-c04 -b task/c04 main
$ git merge origin/task/c03 --no-edit   # см. §0 — обоснование
Merge made by the 'ort' strategy.  19 files changed, 2768 insertions(+), 32 deletions(-)
```

### Сборка taxonomy (реальный вход)

```
$ uv run python -m knowledge.kb.taxonomy_build
themes=9 subtopic_rows=86 subtopics_distinct=82 -> config/knowledge/taxonomy.json
$ shasum -a 256 "НН 2026/Темы_подтемы_обращений.xlsx"
f5649e083b5f0c13cf346e26387064aca2c33edb9c9e7ceee1c3cc4641f5d05a
$ shasum -a 256 config/knowledge/taxonomy.json config/knowledge/routing_lines.json
4c95de98f5b507e6ff8a377af852c032ee6cfc81bd026df76523185c84b487ee  config/knowledge/taxonomy.json
381fc3093f1e0eaaa9aba20ae1f53a022f1aa7a3b2fe88c11138c2d2520bddb4  config/knowledge/routing_lines.json
```

Совпадает с C00 буквально (`knowledge/audit/c00_inventory.json.taxonomy`: `themes=9,
subtopic_rows=86, subtopics_distinct=82`) — не пересчитано заново с нуля, тот же реальный источник.

### Тесты

```
$ uv run pytest
428 passed in 17.30s

$ uv run pytest knowledge/kb/tests/test_routing.py -q
32 passed

$ uv run pytest knowledge/kb/tests/test_no_model_calls.py -v
29 passed   # было 25 у C03 -> +4 (routing.py, taxonomy_build.py: по 2 параметризованных теста каждый)

$ uv run python3 -c "import knowledge.kb.routing as r; import knowledge.kb.taxonomy_build as t; print('all imports OK (installed package, no sys.path hack)')"
all imports OK (installed package, no sys.path hack)

$ grep -rnE "import (torch|transformers|numpy|openai|anthropic|httpx|requests|aiohttp|socket|urllib|subprocess)" knowledge/kb/routing.py knowledge/kb/taxonomy_build.py
(no matches — exit 1)
```

### 20 dev-кейсов D01 — реальный прогон (FTS-fallback CPU, честно не dense — см. §6)

```
$ uv run python /tmp/run_dev20.py   # store.retrieve() по evaluation/ai_test/dev/ai_test_dev.jsonl
DEV-001  ANSWER_ALLOWED topic=TH9 sub=ST86 line=L1 defect=False recipient=службу контроля качества Портала поставщиков по форме обратной связи
DEV-002  ANSWER_ALLOWED topic=TH9 sub=ST86 line=L1 defect=False recipient=None
DEV-003  ANSWER_ALLOWED topic=None sub=None line=None defect=False recipient=Службу контроля качества Портала поставщиков по форме обратной связи
DEV-004  ANSWER_ALLOWED topic=TH1 sub=ST03 line=L2 defect=False recipient=службу технической поддержки Портал поставщиков по форме обратной связи
DEV-005  ANSWER_ALLOWED topic=None sub=None line=None defect=False recipient=None
DEV-006  ANSWER_ALLOWED topic=None sub=None line=None defect=False recipient=None
DEV-007  ANSWER_ALLOWED topic=TH1 sub=ST02 line=L1 defect=False recipient=None
DEV-008  ANSWER_ALLOWED topic=None sub=None line=None defect=False recipient=None
DEV-009  ANSWER_ALLOWED topic=TH8 sub=ST75 line=L2 defect=False recipient=None
DEV-010  ANSWER_ALLOWED topic=TH8 sub=ST75 line=L2 defect=False recipient=None
DEV-011  ANSWER_ALLOWED topic=TH8 sub=ST75 line=L2 defect=False recipient=None
DEV-012  ANSWER_ALLOWED topic=TH8 sub=ST75 line=L2 defect=False recipient=None
DEV-013  ANSWER_ALLOWED topic=TH8 sub=ST75 line=L2 defect=False recipient=None
DEV-014  ANSWER_ALLOWED topic=None sub=None line=None defect=False recipient=None
DEV-015  ANSWER_ALLOWED topic=TH8 sub=ST77 line=L2 defect=False recipient=None
DEV-016  ANSWER_ALLOWED topic=None sub=None line=None defect=False recipient=None
DEV-017  ANSWER_ALLOWED topic=None sub=None line=None defect=False recipient=None
DEV-018  ANSWER_ALLOWED topic=TH1 sub=ST03 line=L2 defect=False recipient=None
DEV-019  ANSWER_ALLOWED topic=None sub=None line=None defect=False recipient=None
DEV-020  ANSWER_ALLOWED topic=None sub=None line=None defect=False recipient=None

TOTAL: 20/20 ANSWER_ALLOWED (совпадает с C03-handoff §5 — все 20 корректно применимых)
topic assigned:      11/20
line assigned:       11/20
recipient assigned:   3/20  (DEV-001, DEV-003, DEV-004)
is_ambiguous=True:     0/20
is_probable_defect:    0/20 (ни один реальный dev-вопрос не является техническим дефектом — корректно)
```

**Честная интерпретация, не приукрашена:**

- **Topic/line (11/20, 55%).** Основной путь (полное совпадение стемов подтемы) точен, но
  консервативен: реальные формулировки часто используют другую словоформу, чем taxonomy
  («расторгнуть» vs «расторжение» — историческое чередование г/ж, которое простой Snowark-подобный
  стеммер C02 не сводит к одному стему; это ограничение общего нормализатора C02, не этого модуля —
  задокументировано в docstring теста `test_match_topic_exact_full_keyword_containment`). 9/20 честно
  остаются `topic=null`, а не получают угаданную тему.
- **Recipient (3/20).** Из 20 dev-кейсов только 2 вообще имеют `gold recipient` в D01 (DEV-002,
  DEV-018) — остальные 18 по замыслу датасета recipient=null. Наш `extract_recipient` нашёл реальный
  адресат в 3 случаях (DEV-001, DEV-003, DEV-004 — все три подтверждены буквальным текстом
  top-ranked selected evidence). Для DEV-002/DEV-018 (те самые 2 с gold recipient) — **честный null**:
  правильный источник с фразой-рефералом физически присутствует в KB, но при текущем CPU FTS-fallback
  (нет реального dense-индекса, см. §6) не попадает в top-5 selected для этого конкретного
  формулирования вопроса — тот же класс ограничения, что и DEV-007/DEV-015 в C03-handoff §5. Это
  сознательный компромисс precision-over-recall: расширение поиска recipient на весь selected-набор
  (не только top-1) было опробовано и **отклонено** во время разработки — оно давало посторонний,
  топически нерелевантный recipient для нескольких других вопросов (см. §5, DEV-009 regression case).
- **is_probable_defect = 0/20.** Ни один из 20 реальных dev-вопросов не является техническим дефектом
  по замыслу датасета (`answerable=true` для всех 20) — корректное поведение: L3 не сработал ложно ни
  разу, при этом DEV-004/DEV-018 (содержат цитируемую ошибку при входе) корректно получили `L2`
  (uncertain L1/L2 triage), а не `L1` и не `L3`.

---

## 5. Найденные и исправленные во время разработки проблемы (не гипотетические — реально пойманы)

| # | Проблема | Как найдена | Исправление |
|---|---|---|---|
| 1 | Резервное правило по «уникальному» ключевому слову подтемы ловило обычные частотные слова предметной области (`поставщик` — единственный раз в тексте одной подтемы taxonomy, но повсеместен в реальных вопросах) → ложно маршрутизировало вообще все supplier-вопросы в «Снятие блокировки с поставщика» | Прогон полного dev20-скрипта, ручной просмотр вывода | Резерв ограничен ТОЛЬКО токенами-аббревиатурами/кодами (`is_abbreviation_or_code`), не обычными существительными; regression-тест добавлен |
| 2 | «РДИК_0009»-подобные коды не матчились основным путём (описательная подтема содержит 6 слов, вопрос — только код) | Прогон dev20, DEV-009..013 давали `topic=None` | Резервное правило по уникальным аббревиатурам/кодам (табл. `_DISTINCTIVE_KEYWORD_TO_SUBTOPIC`) + разбор составных токенов (`рдик_0009`→`рдик`+`0009`) только для целей topic-match |
| 3 | Расширение OUT_OF_SCOPE через «zero raw hits» не срабатывало вообще: предлог «про» (отсутствовал в `_STOPWORDS`) редко встречается в корпусе → искусственно высокий bm25 из-за IDF, «расскажи анекдот про кота» матчил документ только по «про» | Целевой интеграционный тест на заведомо не по теме вопрос | `_STOPWORDS` дополнен предлогами/частицами; отдельная `_has_meaningful_lexical_hit` без стоп-слов вместо порога по score (порог по score оказался ненадёжен — редкие стоп-слова получают bm25 даже выше многих реальных совпадений) |
| 4 | `extract_recipient` искал фразу-реферал по ВСЕМ candidates (сначала selected, потом остальные) → для вопроса про РДИК_0009 нашёл посторонний referral в selected-статье про истёкший срок блокировки ЛК (она реально попала в top-5 selected из-за неточности FTS-fallback ранжирования, но не по теме вопроса) | Ручная проверка basis_source_ids/recipient на всех 20 dev после первой реализации | Сужено до ТОЛЬКО наивысшего по score selected evidence; если там рефераla нет — честный `null`, не поиск дальше |
| 5 | `decide_gate`/`_is_out_of_scope` с обязательным первым позиционным `conn` сломал 9 существующих синтетических unit-тестов C03 (`test_gate_*` в `test_retrieval_pipeline.py`, которые вызывают `decide_gate` без реального соединения) | `uv run pytest` сразу после первой версии wiring | `conn` сделан keyword-only с default `None`; `_has_meaningful_lexical_hit` возвращает `False` при `conn=None` — расширение OOS просто не участвует там, где реального снимка нет (не ломает синтетику C03) |

---

## 6. Data mode mock / real / mixed — где именно

| Часть | Режим | Где |
|---|---|---|
| KB снимок (chunks/parents/FTS) | **real** | не изменялся, тот же `kb-4918a97f0874d1e8` от C02/C03 |
| Taxonomy (9 тем/86 строк/82 подтемы) | **real** | `НН 2026/Темы_подтемы_обращений.xlsx`, разобран `taxonomy_build.py`, сверено с C00 |
| `match_topic` / `detect_defect_signals` / `decide_support_line` / `extract_recipient` | **real, детерминированный код** | `knowledge/kb/routing.py`, чистые функции без модели, вход — реальный текст запроса + реальные evidence из C03's `retrieve()` |
| Query encoder (dense) | **mock** (унаследовано от C03) | `MockQueryEncoder`, `is_mock=True` — dense corpus по-прежнему не собран (blocked-on-G, C03-handoff §8/BL-C03-1), 20 dev идут через честный FTS-fallback, как и в C03 |
| 20 dev retrieval+routing smoke в §4 | **real KB + real FTS + real routing-логика + mock dense** (dense недоступен, использован fallback, как и в C03) | явно помечено, не выдано за dense/semantic |
| `recommended_recipient` | **real, извлечён из текста реального источника** | не выдуманный справочник (которого нет) — буквальная фраза «обратитесь в …» из top-ranked selected evidence; при отсутствии такой фразы — честный `null` |

Ни один mock не выдан за real. Ни один тест не удалён/переименован ради зелёного результата.

---

## 7. Blockers and reproducible defects

### BL-C04-1 (передаётся дальше, не гипотетический) — справочника линий/адресатов не существует

Подтверждено C00 (`docs/integration/input_inventory.md`, `knowledge/audit/C00_input_audit.md §6.2`) И
A00 (`docs/coordination/artem/A00-handoff.md`: «No dedicated support-line/recipient crosswalk was found;
blocks verified C04 routing/recipient mapping»), и заново перепроверено в этой задаче: ни в одной ветке
репозитория, ни в одном входном файле (`НН 2026/Темы_подтемы_обращений.xlsx` — только тема/подтема, без
колонок линии/адресата; `TenderHack_KnowledgeBase_summary.txt:233` — дизайн-набросок «1/2/3 линия», не
данные) справочника «подтема → линия/адресат» не существует.

**Следствие:** `support_line` вычисляется из явного, но необходимо приближённого baseline
(`config/knowledge/routing_lines.json`, задокументирован по темам с обоснованием) + query-level
технических признаков (не из справочника). `recommended_recipient` — почти всегда `null` по
конструкции (3/20 на реальном dev, см. §4) — это ожидаемый, честный результат, не баг и не недоработка
экстракции. **Владелец блокера: организаторы/заказчик данных** (нужен реальный справочник
линий/адресатов, если он вообще существует у РТС Тендер вне переданного набора файлов) — это не
техническая, а входная проблема, C04 не может её обойти выдумыванием данных.

### Ограничения C04 (не блокеры, зафиксированы явно)

1. **Topic/line coverage на dev — 11/20 (55%).** Ограничение общего C02-нормализатора (Snowball-подобный
   стеммер без словаря не сводит некоторые вербальные/отглагольные формы к одному стему при
   исторических чередованиях согласных — «расторгнуть»/«расторжение», «восстановить»/«восстановление»).
   Не в зоне C04 для исправления (`knowledge/kb/normalize.py` — общий файл C02, разделяемый с FTS-индексом
   и C03's lexical.py; менять его ради частного случая routing означало бы менять поведение
   retrieval/lexical для всех потребителей без координации).
2. **Recipient recall ограничен ранжированием FTS-fallback, не логикой extraction.** Для 2/20 dev-кейсов
   с gold recipient (DEV-002/DEV-018) правильный источник физически в KB, но не в top-5 selected при
   текущем CPU-only ранжировании — тот же класс ограничения, что DEV-007/DEV-015 в C03-handoff §5.
   Ожидается улучшение после реального dense-индекса (BL-C03-1, blocked-on-G, не входит в scope C04).
3. **`is_probable_defect`/L3 — консервативен по конструкции.** Требует явного сочетания признаков
   (см. §2.2); отдельные incident-слова без recurrence-языка (например «зависает» без «постоянно»/
   «каждый раз») сознательно НЕ считаются достаточными — задокументировано в docstring
   `DefectSignals.is_probable_defect`, предпочтение отдано false negative над false positive (не
   изобретать L3 там, где оснований недостаточно, согласуется с общей философией проекта «unknown
   остаётся unknown»).
4. **OUT_OF_SCOPE расширение — узкое и консервативное.** Срабатывает только когда ОБА сигнала (dense/exact
   хиты и содержательный FTS-хит) отсутствуют И taxonomy не матчит вообще ничего. На реальных 20 dev ни
   разу не сработало ложно (все 20 остались `ANSWER_ALLOWED`).
5. **«Консультация» — подтема, буквально повторяющаяся в 5 темах** (C00 §6.2), помечается `is_ambiguous=True`
   при совпадении — намеренно не выбирает тему наугад (тест
   `test_match_topic_consultation_ambiguous_across_five_themes`).

Воспроизводимых дефектов в чужих модулях (C01/C02/C03) не найдено; полный `uv run pytest` после всех
изменений — `428 passed`, регрессий нет.

---

## 8. CR

**Новых CR нет.** Контракт (`RoutingResult`, `KnowledgeResult`, `ReasonCode`) использован БЕЗ изменений.

Рассмотрено и **отклонено** как ненужное изменение контракта: добавление отдельного `ReasonCode` для
«недостаточно оснований для маршрута» — существующих полей `RoutingResult.support_line=null` +
`is_ambiguous` достаточно, чтобы честно отразить это состояние без нового enum-значения. Если A/D
впоследствии решат, что операторскому кабинету/отчётности нужен явный machine-readable признак «маршрут
не определён по стольким-то причинам» — это отдельный, самостоятельный CR владельцу A, не блокирующий
сдачу C04.

---

## 9. Inputs needed by next task

**Для A04 (handoff/operator reply):** `KnowledgeResult.route` теперь реален и приходит через
существующий `KnowledgePort.retrieve()` без изменения API/формы контракта. Поля `support_line`/
`recommended_recipient` независимы — оба могут быть `null` одновременно (нет оснований), только один
из двух (например line есть, recipient нет — самый частый случай, 8/11 c topic-match), или (реже) оба.
`is_ambiguous=True` — сигнал показать оператору «не уверены», не автоматически выбирать резервную линию.
`recommended_recipient` **не является** назначением реального оператора/отдела (§9 спеки: «Не содержит
назначенного реального оператора») — это текстовая подсказка из источника, не структурированный ID.

**Для C05/C06 (карточки/кросс-проверка):** `config/knowledge/taxonomy.json` — канонический источник
для 9/86 labels в карточках, не выдумывать новые темы/подтемы сверх этого файла.

**Для команды/организаторов:** BL-C04-1 (справочник линий/адресатов) — реальный входной пробел, не
решаемый на уровне кода; если такой справочник существует вне переданного набора файлов, его появление
позволит заменить `config/knowledge/routing_lines.json`'s baseline-эвристику точным сопоставлением без
переписывания логики `decide_support_line` (baseline-словарь — единственное место, которое потребуется
заменить).

**Для C07 (dev fixes/заморозка KB):** topic/line coverage 11/20 и recipient 3/20 на CPU FTS-fallback —
ожидается улучшение recall (не логики) после доставки реального dense-индекса с G (BL-C03-1), поскольку
корректное ранжирование topically-релевантных источников в top-5 — единственное, что сейчас ограничивает
и `match_topic`'s second-pass corroboration, и `extract_recipient`'s top-1 restriction.

## Остановка

C04 завершён. C05 в этом чате не начинаю — для него участник создаёт отдельный новый чат.
