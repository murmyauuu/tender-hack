# C03 — handoff

- **Task ID / status:** C03 — Dense retrieval и минимальный evidence gate / **partial (done на M, blocked-on-G для реального embedding forward-pass)**
- **Owner / tool:** Эдуард / агент C / Claude Code
- **Base SHA:** `7988174aa1af7e2fbebc8a4980f43f84fa10e1e8` (тот же SHA, что зафиксирован в задании; совпадает с `origin/main` на момент старта — 1c3c6ae/dc277e5/8da0dcc = C01/C02/CR-EDUARD-001 уже внутри)
- **Result SHA:** `16875ec966b11535191cf900156ff2088286330b` (`task/c03`; предыдущий коммит `ea03c888` на этой ветке содержал регресс — два уже отредактированных трекаемых файла, `store.py` и `test_port_and_fts.py`, остались нестейджены при `git add` и попали в коммит в старом виде; исправлено следующим коммитом `16875ec`, независимо перепроверено `git worktree add --detach` в чистый каталог + `uv run pytest` → 392 passed)
- **Ветка / worktree:** `task/c03` / `/Users/gunter/Desktop/tenderhack-c03` (отдельный, worktree C00/C01/C02 не тронуты)
- **Contracts version:** `2.0.0-c0`, контракты **не изменялись** (KnowledgePort/EvidenceItem/KnowledgeResult/QueryContext/GateDecision/ReasonCode использованы как есть)
- **Machine:** M — MacBook Air M2 (arm64), 8 GiB RAM, macOS, без GPU. `torch`/`transformers`/`numpy` на этой машине не установлены и не добавлялись как зависимости (`pyproject.toml` — файл A, не в зоне C; не редактировался).
- **KB snapshot:** `kb-4918a97f0874d1e8` (от C02, без изменений) — `var/knowledge/knowledge.sqlite` SHA-256 `6d1555777d9bbf9ae7f2df93a69cf61f53dd04263877a8ebaf7fc35e16a4bdf8`, `var/knowledge/manifest.json` SHA-256 `e0d01a74dcfe43f8a562a10837793fa04a052e775e60877115dce7785f24d061` — **идентичен C02**, C03 не переписывал реальный manifest (embedding-поля стамповать некому — весов на M нет).

A01 (эмбеддинг-адаптер) и D01 (20 dev) прочитаны напрямую с неслитых веток `origin/task/a01` и `origin/task/d01-dataset` (`git show`), не скопированы файлами и не пересозданы.

---

## 1. Changed files

Только зона C (`knowledge/**`, `config/knowledge/**`, `docs/coordination/eduard/**`):

| Файл | Назначение | Строк |
|---|---|---|
| `knowledge/kb/retrieval.py` | пайплайн: dedup → роль/применимость → parent expansion → four-outcome gate | 529 |
| `knowledge/kb/lexical.py` | условный exact/FTS: детект кодов/аббревиатур до морфологии | 63 |
| `knowledge/kb/index_build.py` | приёмка индекса от G: валидация формы/порядка/L2-нормы + штамповка manifest | 120 |
| `knowledge/kb/dense/vectors.py` | чтение/запись `.npy` и точный (brute-force) cosine top-k — **без пакета numpy** (stdlib `struct`/`array`) | 185 |
| `knowledge/kb/dense/encoder.py` | `QueryEncoder` протокол, `MockQueryEncoder` (честно помечен `is_mock=True`), пины A01 | 101 |
| `knowledge/kb/dense/__init__.py` | пакет | 12 |
| `knowledge/kb/gpu/real_encoder.py` | реальный forward-pass Qwen3-Embedding (torch/transformers) — **только для G** | 97 |
| `knowledge/kb/gpu/embed_and_smoke.py` | единственный скрипт, требующий GPU: build embeddings + dev retrieval smoke | 301 |
| `knowledge/kb/gpu/README.md` | точные команды и ожидаемый вывод для оператора G | — |
| `knowledge/kb/gpu/__init__.py` | пакет | 10 |
| `knowledge/kb/store.py` | **изменён**: `retrieve()` больше не `NotImplementedError` — реальный CPU-пайплайн + подключаемый encoder/индекс; `health()` различает `semantic`/`lexical_only`/`unavailable` честно | +131/-32 |
| `knowledge/kb/tests/test_dense_vectors.py` | 11 тестов: `.npy` round-trip, cosine, top-k, ошибки формата | — |
| `knowledge/kb/tests/test_dense_encoder.py` | 7 тестов: mock детерминирован/L2/dim, пины A01, query-инструкция буквально | — |
| `knowledge/kb/tests/test_lexical_exact_ids.py` | 8 тестов: детект аббревиатур/кодов/номеров пунктов | — |
| `knowledge/kb/tests/test_retrieval_pipeline.py` | 27 тестов: dedup/роль/конфликт/gate (синтетика) + 8 интеграционных на реальном снимке | — |
| `knowledge/kb/tests/test_index_build.py` | 6 тестов: валидация индекса, штамповка manifest на синтетике | — |
| `knowledge/kb/tests/test_port_and_fts.py` | **изменён**: `test_retrieve_does_not_pretend_to_search` заменён на `test_retrieve_returns_a_real_knowledge_result` (retrieve() больше не заглушка) | +14/-8 |
| `config/knowledge/retrieval.json` | конфиг: пины embedding-адаптера, тип индекса, структурные константы пайплайна | 37 |

Чужого не трогал: `pyproject.toml`, `contracts/**`, `backend/**`, `tools/**`, `tests/**`, `docs/integration/**`, `config/runtime/**` — без изменений (проверено `git diff --stat` — пусто). Зона C01 (`knowledge/policy/**`, `config/knowledge/policy_rules.json`) и зона C00 (`knowledge/audit/**`) не затронуты. `knowledge/kb/ingest.py`, `normalize.py`, `classify.py`, `schema.py`, `pdf_text.py` (файлы C02) — без изменений, снимок собирается тем же кодом с тем же `snapshot_id`.

---

## 2. Implemented behavior

### 2.1. Query instruction / pooling / normalization — реализовано буквально по A01

`knowledge/kb/dense/encoder.py`: `EMBEDDING_MODEL="Qwen/Qwen3-Embedding-0.6B"`, `EMBEDDING_REVISION="97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"`, `EMBEDDING_DIM=1024`, `EMBEDDING_SAFETENSORS_SHA256="0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd"`, `POOLING="last_token"`, `NORMALIZATION="l2"`, `QUERY_INSTRUCTION_TEMPLATE` — ровно строка A01, без E5-префиксов (`test_query_instruction_matches_a01_pin_exactly`). Документы инструкцию НЕ получают (`build_query_instruction` применяется только в `encode_query`, никогда не в `embed_and_smoke.py`'s `encode_documents`).

### 2.2. Dense top10 → dedup → применимость/роль/версия → parent expansion → 3–5 evidence

Реализовано в `knowledge/kb/retrieval.py::run_pipeline`, одним и тем же кодом что на M (mock encoder), что на G (реальный) — меняется только объект `encoder`/`dense_index`, сам пайплайн не ветвится по mock/real:

1. `collect_raw_hits` — dense top-10 через `DenseIndex.top_k` (точный cosine, `knowledge/kb/dense/vectors.py`), либо, если реального индекса нет (сегодня на M его нет — G ещё не собрал), честный лексический fallback (`bm25` через `chunks_fts`) — **не имитация dense**, а другой явно промаркированный метод (`retrieval_method=fts`). Параллельно — условный exact-поиск кодов/аббревиатур (`knowledge/kb/lexical.py`).
2. `dedup_hits` — один `source_id`, приоритет `exact > fts > dense`; при коллизии на одном и том же exact-термине relative-ранжирование внутри exact сохраняется через bm25-добавку (`_EXACT_MATCH_SCORE + bm25`), иначе все exact-хиты по частой аббревиатуре получили бы одинаковый score и порядок среди них стал бы произвольным — найдено и исправлено во время тестирования на реальных dev-запросах (см. §7).
3. `apply_role_gate` — роль/применимость по данным C02 (`applicable_roles`, `role_verified`); `role_verified=false` не считается «все роли» (передано дальше как unverified, не блокирует).
4. `expand_to_evidence_groups` — группировка retrieved chunks по `parent_id`, текст evidence — `parents.text` (полный восстановленный текст статьи/секции, а не обрезанный chunk), `content_status` группы — худший статус среди РЕАЛЬНО найденных в этой группе chunks (не всех детей parent). Несколько chunks одной статьи схлопываются в одно evidence — не считаются независимыми подтверждениями (§10 Gate).
5. `detect_known_conflict` — конфликт версий одного `source_key` среди финалистов → `KNOWN_CONFLICT`.
6. `decide_gate` — четыре исхода (см. §2.3).

### 2.3. Четыре исхода gate с reason_codes (§10, раздел «Gate»)

| Условие (реальный код, не гипотеза) | Decision | reason_codes |
|---|---|---|
| Запрос без единого содержательного токена (приветствие) | `OUT_OF_SCOPE` | `OUT_OF_SCOPE` |
| Неизвестный exact ID/код, `clarification_count<1` | `CLARIFY` | `UNKNOWN_IDENTIFIER` |
| Тот же неизвестный ID, уточнение исчерпано | `ESCALATE` | `UNKNOWN_IDENTIFIER`, `UNRESOLVED_AFTER_STEPS` |
| Конфликт версий среди применимых финалистов | `ESCALATE` | `KNOWN_CONFLICT` |
| Ни одного пригодного evidence | `ESCALATE` | `NO_EVIDENCE` |
| Только pointer/incomplete (нет complete) | `ESCALATE` | `NO_EVIDENCE` и/или `MISSING_ATTACHMENT` |
| Роль нужна, но неизвестна, `clarification_count<1` | `CLARIFY` | `ROLE_REQUIRED` (+`missing_fact.key="role"`) |
| Та же ситуация, уточнение исчерпано | `ESCALATE` | `ROLE_REQUIRED`, `UNRESOLVED_AFTER_STEPS` |
| Роль известна и не совпадает — единственные найденные candidates | `ESCALATE` | `ROLE_MISMATCH` (без цикла clarify — это не «один разрешимый факт») |
| Применимые complete evidence без конфликта | `ANSWER_ALLOWED` | `[]`, `selected_evidence_ids` = 3–5 (cap 5) |

`GateDecision`/`ReasonCode` — из `tenderhack_contracts.models`, не изобретены заново. `route` в `KnowledgeResult` — нейтральный пустой `RoutingResult()`: топик/линия поддержки — зона C04, здесь не выдумывается.

### 2.4. Условный exact/FTS для кодов/аббревиатур

`knowledge/kb/lexical.py::detect_exact_identifiers` находит в тексте запроса кириллические/латинские аббревиатуры (≤6 прописных букв — ИНН, СТЕ, УПД, КЭП, МЧД, ОГРН…), составные коды через дефис (`YML-12`, `РДИК_0474`* — см. сноску), номера пунктов (`1.2`, `10.3.1`). Каждый такой токен ищется точным FTS-запросом (`AND` всех нормализованных слов термина) в `chunks_fts` — той же нормализацией, что и остальной текст (`knowledge/kb/normalize.py`, единая для C02/C03). Если ни одного совпадения — `UNKNOWN_IDENTIFIER`, без подмены на общий ответ (проверено интеграционным тестом на реальном снимке с придуманным кодом `ZQXPRT-99`, которого в снимке гарантированно нет).

*Примечание: коды вида `РДИК_0474` используют `_` как разделитель, который FTS-токенайзер (`unicode61`) не разбивает — они ловятся как единый непрерывный токен через `is_abbreviation_or_code`'s hyphen-паттерн лишь частично; фактическая проверка (§7, dev-кейсы DEV-009…013) показала, что они всё равно находятся — не через `detect_exact_identifiers`, а штатным dense/FTS top-10, поскольку сам код входит в текст статьи как искомое слово. Формальный regex под `_`-коды отдельно не добавлялся, чтобы не плодить точечные паттерны без второго подтверждённого сценария (§10: «иных подтверждённых dev-сценариев» — этот один уже покрыт без отдельного паттерна).

### 2.5. `store.py`: `NotImplementedError` заменён на настоящий `retrieve()`

- `SqliteKnowledgeStore.__init__` принимает `encoder: QueryEncoder | None` (по умолчанию `MockQueryEncoder`) — точка внедрения реального encoder для A03, без изменений в этом файле.
- При старте пытается загрузить `var/knowledge/index.npy` + `index_ids.json` (если G их уже прислал) — отсутствие не ошибка.
- `health()` — `mode='semantic'` только если ОБА условия реальны (реальный корпус векторов И реальный, не mock, encoder); если корпус реальный, но encoder mock — честно `lexical_only`, не выдаётся за semantic.
- `retrieve()` — реальный вызов `knowledge.kb.retrieval.run_pipeline`.

---

## 3. Acceptance — по критериям задачи

| Критерий | Результат |
|---|---|
| На реальных dev примерах найдены применимые sources | **passed, честно как FTS-fallback, не dense**: 20/20 реальных dev-кейсов D01 находят gold source среди candidates (`gold_in_candidates=20/20`), 18/20 — среди финально выбранных 3–5 evidence (`gold_in_selected=18/20`, см. §7) |
| pointer/role mismatch/unknown ID не дают необоснованный ANSWER_ALLOWED | **passed**: покрыто и синтетическими юнит-тестами (`test_gate_pointer_only_escalates_without_answering`, `test_gate_role_mismatch_always_escalates_no_clarify_loop`, `test_gate_unknown_identifier_clarifies_then_escalates`), и интеграционными на реальном снимке (`test_integration_role_mismatch_or_incomplete_never_answers_on_real_kb`, `test_integration_unknown_identifier_clarifies_then_escalates`) |
| Similarity не объявлена confidence | **passed**: `EvidenceItem.score` — bm25/cosine/константа exact, диапазон явно вне [0,1] для fts/exact (тест `test_integration_retrieve_never_invents_confidence_from_score`); нигде в коде/DTO score не преобразуется в проценты/вероятность |
| Индекс/ID mapping/manifest с хешами сохранены | **partial**: механизм готов и протестирован (`knowledge/kb/index_build.py` — 6 тестов, `knowledge/kb/dense/vectors.py` — 11 тестов, на синтетике), но **реального индекса ещё нет** — сборка требует GPU/torch (профиль G), которого на M нет. `var/knowledge/manifest.json` остаётся с `embedding_*: null`, как оставил C02 |
| Actual retrieval results приложены, а не «должно работать» | **passed для CPU-части (FTS-fallback)**: полный лог 20/20 реальных dev-запросов приведён в §7 с фактическими decision/reason_codes/candidates; **not run для dense-части** — реальный embedding forward-pass не выполнялся на этой сессии (нет GPU), явно помечено blocked-on-G |

---

## 4. Commands and actual outputs

### Git-контекст

```
$ git rev-parse 7988174aa1af7e2fbebc8a4980f43f84fa10e1e8^{commit}
7988174aa1af7e2fbebc8a4980f43f84fa10e1e8
$ git log --oneline -3 origin/main
7d7b44c ev(D01): publish 20 dev AI-test cases, seal 40 final cases, finalize history manifest
573b151 docs(a01): Record real GPU model smoke
7988174 style(knowledge): Remove trailing whitespace
$ git worktree add ../tenderhack-c03 task/c03   # branch task/c03 создана от 7988174
HEAD is now at 7988174 style(knowledge): Remove trailing whitespace
```

### Сборка снимка C02 (без изменений — воспроизводимость подтверждена)

```
$ python3 -m knowledge.kb.ingest --out var/knowledge
snapshot_id kb-4918a97f0874d1e8, raw 1468, included 1528, excluded 44, articles 480
$ shasum -a 256 var/knowledge/knowledge.sqlite
6d1555777d9bbf9ae7f2df93a69cf61f53dd04263877a8ebaf7fc35e16a4bdf8  var/knowledge/knowledge.sqlite
```
Совпадает с C02-handoff.md буквально.

### Тесты

```
$ uv run pytest
392 passed in 17.76s

$ uv run pytest knowledge/kb/tests/test_retrieval_pipeline.py knowledge/kb/tests/test_dense_vectors.py \
    knowledge/kb/tests/test_dense_encoder.py knowledge/kb/tests/test_lexical_exact_ids.py \
    knowledge/kb/tests/test_index_build.py
59 passed in 4.45s   # 27 pipeline + 11 vectors + 7 encoder + 8 lexical + 6 index_build

$ uv run pytest knowledge/kb/tests
138 passed in 17.17s
```

Проверено напрямую (`git stash` на BASE_SHA-состоянии этой ветки, полный прогон, затем `git stash pop`): было **327 passed**, стало **392 passed** — чистая разница **+65** (59 из 5 новых тестовых файлов C03 + 6 дополнительных из уже существующего `test_no_model_calls.py`, который параметризован по списку файлов `knowledge/kb/*.py` и автоматически подхватил 3 новых файла верхнего уровня — `lexical.py`, `retrieval.py`, `index_build.py` — по 2 параметризованных теста на файл). `pyproject.toml`/`testpaths` не менялся — CR-EDUARD-001 уже закрыт интегратором, `uv run pytest` без флагов покрывает `knowledge/kb/tests` и `knowledge/policy/tests`.

### Проверка: подпакеты C03 импортируются как установленный пакет (без sys.path-хака)

```
$ uv run python3 -c "
import knowledge.kb.dense.vectors as v
import knowledge.kb.gpu.real_encoder as r
import knowledge.kb.retrieval as p
import knowledge.kb.lexical as l
import knowledge.kb.index_build as i
print('all imports OK (installed package, no sys.path hack)')
"
all imports OK (installed package, no sys.path hack)
```

### Проверка: `dense/` и `gpu/` не подпадают под сканирование «0 model calls» C02 (не рекурсивное `os.listdir`)

```
$ uv run python3 -c "
from knowledge.kb.tests.test_no_model_calls import _module_files
import os
for f in _module_files(): print(os.path.basename(f))
"
__init__.py classify.py index_build.py ingest.py lexical.py normalize.py
pdf_text.py retrieval.py schema.py store.py
$ uv run pytest knowledge/kb/tests/test_no_model_calls.py -v
25 passed in 8.26s
```
9 файлов верхнего уровня (было 4 у C02: `ingest.py`, `normalize.py`, `store.py`, `pdf_text.py`) — все проверены на 0 forbidden imports, включая новые `lexical.py`, `retrieval.py`, `index_build.py`, `classify.py`. `torch`/`transformers`/`numpy` нигде в этих 9 файлах не импортированы — только в `knowledge/kb/gpu/real_encoder.py` (не сканируется, реален только на G).

### `git diff --stat` — чужие файлы не тронуты

```
$ git diff --stat -- pyproject.toml config/runtime/ contracts/ backend/ tools/ tests/
(пусто)
$ uv run python -m tools.generate_contracts   # A's tool, sanity check
(no tracked diff)
$ uv run python -m tools.validate_fixtures
valid: 8/8 fixtures
```

---

## 5. §7 — Реальный прогон 20 dev-кейсов D01 (FTS-fallback, честно НЕ dense)

D01 (`evaluation/ai_test/dev/ai_test_dev.jsonl`, ветка `origin/task/d01-dataset`) прочитан командой:

```
git show origin/task/d01-dataset:evaluation/ai_test/dev/ai_test_dev.jsonl > /tmp/ai_test_dev.jsonl
wc -l /tmp/ai_test_dev.jsonl
20 /tmp/ai_test_dev.jsonl
```

Прогон через реальный `SqliteKnowledgeStore.retrieve()` с `MockQueryEncoder` (пометка `is_mock=True`, следовательно dense недоступен) — пайплайн использует настоящий лексический fallback (`bm25` через `chunks_fts`, реальная C02-нормализация), НЕ имитацию dense. `gold_source_ids` из D01 (сырые id снимка) сопоставлены с внутренними `source_id` через `chunks.original_ids` (0 missing, как и заявил D01).

Полный лог по всем 20:

```
DEV-001  role=supplier   decision=ANSWER_ALLOWED  in_cand=True  in_sel=True   n_cand=9
DEV-002  role=supplier   decision=ANSWER_ALLOWED  in_cand=True  in_sel=True   n_cand=8
DEV-003  role=supplier   decision=ANSWER_ALLOWED  in_cand=True  in_sel=True   n_cand=5
DEV-004  role=supplier   decision=ANSWER_ALLOWED  in_cand=True  in_sel=True   n_cand=8
DEV-005  role=supplier   decision=ANSWER_ALLOWED  in_cand=True  in_sel=True   n_cand=12
DEV-006  role=supplier   decision=ANSWER_ALLOWED  in_cand=True  in_sel=True   n_cand=17
DEV-007  role=supplier   decision=ANSWER_ALLOWED  in_cand=True  in_sel=False  n_cand=11
DEV-008  role=supplier   decision=ANSWER_ALLOWED  in_cand=True  in_sel=True   n_cand=7
DEV-009  role=supplier   decision=ANSWER_ALLOWED  in_cand=True  in_sel=True   n_cand=10
DEV-010  role=supplier   decision=ANSWER_ALLOWED  in_cand=True  in_sel=True   n_cand=10
DEV-011  role=supplier   decision=ANSWER_ALLOWED  in_cand=True  in_sel=True   n_cand=14
DEV-012  role=supplier   decision=ANSWER_ALLOWED  in_cand=True  in_sel=True   n_cand=5
DEV-013  role=supplier   decision=ANSWER_ALLOWED  in_cand=True  in_sel=True   n_cand=9
DEV-014  role=supplier   decision=ANSWER_ALLOWED  in_cand=True  in_sel=True   n_cand=11
DEV-015  role=supplier   decision=ANSWER_ALLOWED  in_cand=True  in_sel=False  n_cand=19
DEV-016  role=supplier   decision=ANSWER_ALLOWED  in_cand=True  in_sel=True   n_cand=10
DEV-017  role=customer   decision=ANSWER_ALLOWED  in_cand=True  in_sel=True   n_cand=8
DEV-018  role=supplier   decision=ANSWER_ALLOWED  in_cand=True  in_sel=True   n_cand=16
DEV-019  role=supplier   decision=ANSWER_ALLOWED  in_cand=True  in_sel=True   n_cand=7
DEV-020  role=supplier   decision=ANSWER_ALLOWED  in_cand=True  in_sel=True   n_cand=10

TOTAL: 20
gold_in_candidates: 20/20
gold_in_selected:   18/20
ANSWER_ALLOWED (по реальному gate, все 20 корректно применимых supplier/customer вопросов): 20/20
```

**Честная интерпретация, не приукрашена:**

- Все 20 кейсов — реальные, применимые (не CLARIFY/ESCALATE ожидались по D01) вопросы с известной ролью → `ANSWER_ALLOWED` на всех 20 корректен по замыслу датасета.
- Gold source физически присутствует среди найденных candidates во ВСЕХ 20 случаях — FTS/exact fallback находит правильный документ.
- В 2/20 (DEV-007, DEV-015) gold source НЕ попал в финальные 3–5 selected evidence:
  - **DEV-015** — гарантированно ожидаемое поведение, не дефект: gold source `portal:563264:1` имеет `content_status='incomplete'` в реальном снимке C02 (ссылка на отсутствующий рисунок), и gate по замыслу §10 никогда не включает incomplete в `ANSWER_ALLOWED`-набор, даже если он лидирует по score. Другие complete-источники того же вопроса выбраны вместо него.
  - **DEV-007** — реальное ограничение лексического (bm25) fallback, не dense: вопрос про МЧД встречается в ~11-17 chunks снимка (частая аббревиатура), exact-поиск находит их все с близкими bm25-весами, и топ-5 по bm25 не всегда совпадает с топ-5 по СМЫСЛОВОЙ близости к конкретному под-вопросу. Это именно тот разрыв, который должен закрыть реальный dense (semantic) поиск на G — не тюнинг весов на этом наборе (что запрещено заданием), а другой, семантический сигнал.
- Во время этого честного прогона найден и исправлен реальный баг ранжирования: exact-хиты изначально получали одинаковый плоский score, из-за чего проигрывали bm25/dense score по абсолютной величине и терялись из топ-5 (открыто на DEV-013 до фикса — `portal:588040:1` был в candidates, но не в selected; после фикса — в selected). Исправление: `_EXACT_MATCH_SCORE + bm25(term)`, сохраняет и приоритет exact, и относительное ранжирование внутри exact-хитов. Тест не добавлялся отдельно на этот конкретный регресс (покрыт интеграционными dev-тестами и синтетическими `test_dedup_*`), но зафиксирован здесь как найденный и закрытый дефект собственной реализации.

**Это НЕ подмена реального dense-результата.** Числа выше — FTS/exact, а не dense; `health().mode` в этом состоянии — `lexical_only`. Реальный dense top-10/gate прогон по этим же 20 dev-кейсам с реальными embeddings — задача `knowledge/kb/gpu/embed_and_smoke.py`, не выполнена в этой сессии (нет GPU).

---

## 6. Data mode mock / real / mixed — где именно

| Часть | Режим | Где |
|---|---|---|
| KB снимок (chunks/parents/FTS) | **real** | не изменялся, тот же `kb-4918a97f0874d1e8` от C02 |
| dedup / роль-применимость / версия-конфликт / parent expansion / gate | **real** | `knowledge/kb/retrieval.py`, чистый детерминированный код, без модели |
| Условный exact/FTS | **real** | `knowledge/kb/lexical.py` + реальный `chunks_fts` (bm25) |
| Query encoder (dense) | **mock** | `MockQueryEncoder` (`knowledge/kb/dense/encoder.py`), явно `is_mock=True`, hash-based, НЕ семантический — использован только чтобы прогнать CPU-логику через тот же код-путь, что и реальный encoder будет использовать |
| Dense corpus векторы | **отсутствуют** | `var/knowledge/index.npy` не существует — G не собирал; `health().mode` честно `lexical_only`, а не `semantic` |
| 20 dev retrieval smoke в §5 | **real KB + real FTS/exact + mock dense** (dense не участвовал, т.к. недоступен — использован fallback) | помечено явно, не выдано за dense |
| Реальный embedding forward-pass (веса Qwen3-Embedding-0.6B) | **не выполнялся** | `knowledge/kb/gpu/embed_and_smoke.py` написан и готов, но не запущен — нет GPU на M |
| `.npy` reader/writer, cosine top-k (`knowledge/kb/dense/vectors.py`) | **real код, синтетические тестовые данные** | 11 тестов на сгенерированных векторах — код реален и корректен, входные числа для тестов не претендуют на семантику |
| `index_build.py` (валидация индекса + manifest stamping) | **real код, синтетические тестовые данные** | то же — механизм готов, реального индекса для прогона на нём ещё нет |

Ни один mock не выдан за real. Ни один тест не переименован/удалён ради зелёного результата — старый `test_retrieve_does_not_pretend_to_search` заменён на новый, отражающий реальное поведение (retrieve больше не заглушка), с той же строгостью проверки.

---

## 7. Artifacts and paths

Вне Git (`var/` — `AGENTS.md`), не изменены C03 (идентичны C02):

| Артефакт | Путь | SHA-256 |
|---|---|---|
| KB snapshot | `var/knowledge/knowledge.sqlite` | `6d1555777d9bbf9ae7f2df93a69cf61f53dd04263877a8ebaf7fc35e16a4bdf8` |
| Manifest | `var/knowledge/manifest.json` | `e0d01a74dcfe43f8a562a10837793fa04a052e775e60877115dce7785f24d061` |

**Не существуют** (blocked-on-G, честно не выдуманы):

| Ожидаемый артефакт | Путь | Кто создаёт |
|---|---|---|
| Dense index | `var/knowledge/index.npy` | `knowledge/kb/gpu/embed_and_smoke.py` на G |
| ID mapping | `var/knowledge/index_ids.json` | то же |
| Manifest (обновлённый) | `var/knowledge/manifest.json` (embedding-поля станут не-null) | то же, `knowledge.kb.index_build.stamp_manifest` |
| Dev retrieval log | `var/knowledge/retrieval_log_dev20.json` | то же |

В Git (эта сессия, зона C):

- `knowledge/kb/retrieval.py`, `knowledge/kb/lexical.py`, `knowledge/kb/index_build.py`
- `knowledge/kb/dense/` (vectors.py, encoder.py, __init__.py)
- `knowledge/kb/gpu/` (real_encoder.py, embed_and_smoke.py, README.md, __init__.py)
- `knowledge/kb/store.py` (изменён)
- `config/knowledge/retrieval.json`
- 5 новых тестовых файлов + 1 изменённый (`test_port_and_fts.py`) в `knowledge/kb/tests/`

---

## 8. Blockers and reproducible defects

### BL-C03-1 (не блокер C03, зависимость от инфраструктуры) — реальный embedding build не выполнен

**Владелец: тот, у кого физический доступ к профилю G (Артём или пользователь лично).** Причина: агент этой сессии выполняется на M (MacBook Air M2, без GPU); `torch`/`transformers` не установлены и не могут быть установлены как часть этой задачи (не в зоне C — `pyproject.toml` принадлежит A, и даже если бы был в зоне C, задача явно запрещает загружать модели на слабой машине).

Воспроизведение/устранение: выполнить `knowledge/kb/gpu/embed_and_smoke.py` по инструкции `knowledge/kb/gpu/README.md` на машине с GPU и локально скачанной моделью (A01 её уже скачал на Windows CUDA venv). Ожидаемый результат — 4 файла в `var/knowledge/` (см. §7) + полный stdout лог, который нужно вернуть агенту C03/интегратору.

### Ограничения C03 (не блокеры, зафиксированы явно)

1. **`route: RoutingResult` — нейтральный.** Топик/линия поддержки (L1/L2/L3) — зона C04. C03 не выдумывает тему: `RoutingResult()` со всеми `None`/`[]`/`False` полями. `KnowledgeResult.route` обязателен по контракту, поэтому не может быть `None` — заполнен пустым, а не подделанным значением.
2. **OUT_OF_SCOPE — узкий сигнал, не полная классификация темы.** Реализовано только «нет ни одного содержательного токена» (приветствие/пустой ввод). Полноценная классификация «явно посторонняя тема» по смыслу — зона C04 (routing/taxonomy), здесь не имитируется тестами на выдуманной taxonomy.
3. **Версия/конфликт** проверяется только там, где в снимке вообще есть непустое поле `version` (в основном Регламент; у портала/PDF оно почти всегда `None` — искусственно не заполнялось, BL-C00-5 остаётся открытым за A/C02). При отсутствии `version` конфликт не может быть обнаружен — это честное ограничение входных данных, не логики C03 (покрыто тестом `test_no_conflict_when_versions_agree_or_are_null`).
4. **`РДИК_XXXX`-коды** (частый класс кодов интеграционного контроля в реальных dev-вопросах DEV-009…013) не получили отдельного regex-паттерна в `is_abbreviation_or_code` — они и так надёжно находятся штатным FTS/exact по вхождению термина в текст статьи (подтверждено §5: все find в candidates). Отдельный паттерн не добавлен, чтобы не плодить точечные правила без второго независимого сценария, требующего именно `_`-нотацию exact ID (§10: «иных подтверждённых dev-сценариев»).
5. **DEV-007/DEV-015 не в топ-5 finalists** — задокументировано честно в §5, не скрыто и не подогнано.

---

## 9. CR

**Новых CR нет.** CR-EDUARD-001 (`knowledge` в `packages.find`, `testpaths` включает `knowledge/kb/tests`) уже закрыт интегратором в базовом коммите — подтверждено: все новые подпакеты (`knowledge.kb.dense`, `knowledge.kb.gpu`) импортируются как установленный пакет без sys.path-хака (§4). `knowledge/kb/tests/conftest.py`'s sys.path-вставка оставлена как есть (не обязательна, но безвредна) — не моя зона для удаления чужого решения без необходимости.

Контракты (`KnowledgePort`, `EvidenceItem`, `KnowledgeResult`, `QueryContext`, `GateDecision`, `ReasonCode`, `RoutingResult`) использованы БЕЗ изменений — ни одного нового поля, ни одного нового enum-значения не потребовалось.

---

## 10. Inputs needed by next task

**Для завершения C03 (не для C04!) — вернуть в эту же зону как артефакт:**

Кто угодно с доступом к профилю G должен выполнить `knowledge/kb/gpu/embed_and_smoke.py` (см. `knowledge/kb/gpu/README.md` за точными командами) и вернуть:

1. `var/knowledge/index.npy`
2. `var/knowledge/index_ids.json`
3. `var/knowledge/manifest.json` (обновлённый, со stamped embedding-полями)
4. `var/knowledge/retrieval_log_dev20.json`
5. Полный stdout запуска

После получения — интеграция тривиальна: `SqliteKnowledgeStore` уже умеет их подхватить (`_load_dense_index`, проверено на синтетике), `health().mode` автоматически станет `semantic`, как только encoder тоже станет реальным (внедряется извне, не в этом коммите).

**Для C04 (маршрутизация):**

- `route: RoutingResult` в `retrieve()` сейчас нейтрален — C04 может либо расширить `run_pipeline` (добавив вызов routing до/после gate), либо реализовать отдельный слой поверх `KnowledgeResult.candidates`. И то, и другое совместимо с текущим кодом без изменения контракта.
- `OUT_OF_SCOPE` сейчас триггерится только на пустой/приветственный ввод — если C04 реализует полноценную topic-классификацию, ему может понадобиться расширить или заменить `_is_out_of_scope` в `knowledge/kb/retrieval.py` (моя зона, потребуется координация, не блокирует независимую разработку C04 поверх текущего поведения).

**Для C07 (dev retrieval run / заморозка KB):** после того как §10 (dense build на G) выполнен, `retrieval_log_dev20.json` — готовый вход для сравнения dense vs FTS-fallback качества по всем 20 dev.

---

## 11. Остановка

C03 завершён в части, доступной на M (partial: done по CPU-логике, blocked-on-G по реальному embedding forward-pass). C04 в этом чате не начинаю — для него участник создаёт отдельный новый чат.
