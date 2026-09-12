# C07 — handoff

- **Task ID / status:** C07 — Dev-исправления retrieval/routing и заморозка KB / **done** (no code fix was justified; freeze recorded)
- **Owner / tool:** Эдуард / агент C / Claude Code
- **Base SHA:** `56da4216b7bfd5e1cc3cbc620029cd90045f4391` (`origin/main`, совпадает с BASE_SHA из задания; `git fetch --prune origin && git switch main && git pull --ff-only origin main && git status --short` — HEAD совпал, working tree чист)
- **Result SHA:** `14761d2` (`task/c07`) — код/конфиг (`config/knowledge/kb_freeze.json`) и первая версия этого handoff; поверх него один docs-only коммит фиксирует этот SHA здесь буквально
- **Ветка:** `task/c07`
- **Contracts version:** `2.0.0-c0`, **не изменялся** (никакие поля/enum не потребовались)
- **Machine / runtime:** M — MacBook Air M2 (arm64), macOS, без GPU. `torch`/`numpy` не установлены (`uv run python3 -c "import torch"` / `import numpy` → `ModuleNotFoundError`, проверено фактически). `health().mode` на этой машине — **`lexical_only`**, не `semantic`.
- **KB snapshot:** `kb-4918a97f0874d1e8` — пересобран локально командой `python3 -m knowledge.kb.ingest --out var/knowledge`, детерминированно, и подтверждён байт-в-байт идентичным C02/C03/C04: `var/knowledge/knowledge.sqlite` SHA-256 `6d1555777d9bbf9ae7f2df93a69cf61f53dd04263877a8ebaf7fc35e16a4bdf8`, `var/knowledge/manifest.json` SHA-256 `e0d01a74dcfe43f8a562a10837793fa04a052e775e60877115dce7785f24d061`.

---

## 0. Важная оговорка про рантайм — почему прогон в этой сессии НЕ semantic

Задание предполагало возможность прогона DEV20 «на текущем (semantic, если доступен локально) рантайме»
после того, как A03 закрепил реальный dense E2E. Проверено фактически, что это условие **не выполняется
на машине M этой сессии**:

- `docs/coordination/artem/A03-handoff.md`: реальный dense-индекс/id-mapping/manifest со stamped
  embedding-полями существуют физически **только на машине G**, в каталоге
  `A:\AI\retrieval-results\c03-kb-4918a97f0874d1e8-gpu-abea7ae-20260912T1619Z` (Windows, отдельная
  физическая машина). Эти файлы (`index.npy`, `index_ids.json`, обновлённый `manifest.json`,
  `retrieval_log_dev20.json`) НЕ закоммичены в git (`var/` в `.gitignore`) и не скопированы в этот
  рабочий каталог.
- Локально в `var/knowledge/` после пересборки снимка присутствуют только `knowledge.sqlite` и
  `manifest.json` с `embedding_*: null` — та же честная «до-эмбеддинговая» форма манифеста, что оставили
  C02/C03/C04 на этой же машине.
- `torch`/`numpy` не установлены в `uv`-окружении этой машины (`ModuleNotFoundError`, проверено).
- Полнофайловый поиск по домашним каталогам (`~/Desktop`, `~/Downloads`, `~/Documents`) на
  `index.npy`/`index_ids.json` — ничего не найдено.

Следствие: `SqliteKnowledgeStore.health()` на этой сессии честно возвращает
`mode='lexical_only'`, как и у C03/C04 — **тот же класс ограничения, задание явно
предусматривает эту ветку** («если доступен локально»). Весь прогон в этом handoff — реальный
KB + реальный лексический (bm25/FTS/exact) fallback, БЕЗ dense — помечено явно, не выдано за semantic.
Это не блокер C07 (задание разрешает диагностику на CPU) и не требует GPU-слота, так как ни один
рассмотренный дефект не потребовал изменения текста источника или пересборки эмбеддингов (см. §7 GPU-дисциплина).

---

## 1. Прочитанные обязательные зависимости — подтверждены в `main`

| Зависимость | Файл | Подтверждено |
|---|---|---|
| C03 real-dense runtime acceptance | `docs/coordination/stas/C03-runtime-acceptance.md` | `snapshot_id=kb-4918a97f0874d1e8`, `index_type=numpy_exact_cosine`, PASS |
| C04 (routing поверх retrieval) | `docs/coordination/eduard/C04-handoff.md` | `knowledge/kb/routing.py`, `config/knowledge/taxonomy.json`, `config/knowledge/routing_lines.json` — в `main` (`git log --oneline -- knowledge/kb/retrieval.py` → `a95dc68 feat(C04)`, `1495dfc feat(C03)`) |
| A03 (реальный semantic E2E) | `docs/coordination/artem/A03-handoff.md` | `health.mode=semantic` (в production-рантайме A/backend), `KnowledgePort.health.snapshot_id=kb-4918a97f0874d1e8`, embedding `Qwen/Qwen3-Embedding-0.6B`, все 5 hash'ей записаны |
| D02 (evaluation/runner+report) | `docs/coordination/egor/D02-handoff.md` | инструмент прочитан; область — API session/case/chat lifecycle trace (fixture/http driver), НЕ retrieval-качество (gold_in_candidates/selected). Для DEV20 retrieval diagnostics использован прямой вызов `SqliteKnowledgeStore.retrieve()` — тот же паттерн, что и в C03/C04's собственных ad hoc dev20-скриптах (в репозитории не сохранены, `/tmp/run_dev20.py` был временным); не пишется параллельный runner/report — задача other-shape (retrieval внутренности, не HTTP API operations) |
| C06 | — | не начата другим участником на момент старта C07 (не проверялась, задание явно говорит не блокироваться) |

D01 dataset: `evaluation/ai_test/dev/ai_test_dev.jsonl` (20 строк), `evaluation/ai_test/dev/manifest.json`.
**Найдена и зафиксирована (не исправлена — вне зоны C, файл `evaluation/**` принадлежит D01) реальная
нестыковка**: `manifest.json`'s заявленный `sha256` (`7dff9fc14660e1f938208987400dd65ec70bde164f1c91168b1e91350084cda2`,
тот же, что цитируют `A03-handoff.md` и `C03-runtime-acceptance.md` как «DEV20 input SHA-256») **не совпадает**
с фактическим содержимым файла в обоих коммитах, где он когда-либо существовал в git
(`c5d093c`, `7d7b44c` — оба дают `af04729dd3f708b2ec16e043486c06dbbf54e76003dd12e2e91e62d202aff786`,
проверено `git show <sha>:evaluation/ai_test/dev/ai_test_dev.jsonl | shasum -a 256`). Файл при этом
не менялся между этими двумя коммитами (`git diff` пуст) — расхождение существует с момента публикации
D01, не внесено этой сессией. Не блокер C07 (данные читаются и парсятся корректно, 20/20 строк валидны),
но стоит зафиксировать для D01/владельца данных: заявленный хеш в `manifest.json` не соответствует
файлу, который он описывает.

---

## 2. Реальный прогон DEV20 — методология

Скрипт (временный, не в git, `SqliteKnowledgeStore.retrieve()` напрямую): для каждого из 20 кейсов
`QueryContext.text` собирается конкатенацией ВСЕХ реплик пользователя кейса (`" ".join(m["text"] for m
in case["messages"])`), `confirmed_facts={"role": ...}` из поля `role` датасета. Это отличается от
последнего слова диалога — важно только для `DEV-002` (единственный multi-turn кейс, 2 реплики: первая
несёт тему «блокировка кабинета», вторая — короткий уточняющий вопрос «куда писать»). Обоснование выбора:
`knowledge/kb/**` **не потребляет** `QueryContext.recent_user_messages` вообще (проверено `grep -rn
recent_user_messages knowledge/kb` → только в тестовых фикстурах, всегда `[]`) — сборка `text` для
многоходового диалога целиком на стороне вызывающего кода (backend/A), не в зоне C. Конкатенация всех
реплик — наиболее естественная реконструкция того, что реальный вызывающий код передал бы. Это подтверждено
тем, что при таком выборе `topic assigned=11/20, line assigned=11/20` **точно** совпадает с числами,
которые сам C04 указал в своём handoff §4 — то есть это, по всей видимости, та же сборка `text`, что
использовал и оригинальный dev20-скрипт C04.

`gold_in_candidates`/`gold_in_selected` — hit засчитывается, если ХОТЯ БЫ ОДИН из `gold_source_ids` кейса
(через `chunks.original_ids`, сопоставление 1:1 с `EvidenceItem.source_id`/`.original_ids`) присутствует
среди `candidates`/среди `selected_evidence_ids`-referenced evidence соответственно. Обоснование: для
нескольких кейсов (`DEV-002/003/006/007/011/016/017`) `gold_source_ids` содержит 2 почти дублирующих
KB-записи одного и того же реального ответа (проверено вручную на DEV-007, см. §5) — «AND»-семантика
(все обязательны) не имеет смысла для дублей одного контента и даёт заведомо заниженный, не отражающий
реальность процент (см. §5, проверено: «all»-вариант даёт 15/20, ошибочно относя дубли-совпадения в
minus).

---

## 3. Полный фактический прогон (реальный, честно не dense)

```
$ uv run python3 /tmp/run_dev20_full.py   # store.retrieve() по всем 20 кейсам D01
health: {'available': True, 'mode': 'lexical_only', 'snapshot_id': 'kb-4918a97f0874d1e8',
         'reason': 'C03: снимок и FTS готовы; index files not found (G embedding build not
                     delivered yet) — retrieve() использует лексический (FTS) fallback'}

test_id    decision         in_cand  in_sel   n_cand n_sel topic  line  recipient
DEV-001    ANSWER_ALLOWED   True     True     9      5     TH9    L1    службу контроля качества Портала поставщиков по форме обратной связи
DEV-002    ANSWER_ALLOWED   True     True     8      5     TH9    L1    службу контроля качества Портала поставщиков по форме обратной связи
DEV-003    ANSWER_ALLOWED   True     True     5      5     None   None  Службу контроля качества Портала поставщиков по форме обратной связи
DEV-004    ANSWER_ALLOWED   True     True     8      5     TH1    L2    службу технической поддержки Портал поставщиков по форме обратной связи
DEV-005    ANSWER_ALLOWED   True     True     12     5     None   None  None
DEV-006    ANSWER_ALLOWED   True     True     17     5     None   None  None
DEV-007    ANSWER_ALLOWED   True     True     11     5     TH1    L1    None
DEV-008    ANSWER_ALLOWED   True     True     7      5     None   None  None
DEV-009    ANSWER_ALLOWED   True     True     10     5     TH8    L2    None
DEV-010    ANSWER_ALLOWED   True     True     10     5     TH8    L2    None
DEV-011    ANSWER_ALLOWED   True     True     14     5     TH8    L2    None
DEV-012    ANSWER_ALLOWED   True     True     5      5     TH8    L2    None
DEV-013    ANSWER_ALLOWED   True     True     9      5     TH8    L2    None
DEV-014    ANSWER_ALLOWED   True     True     11     5     None   None  None
DEV-015    ANSWER_ALLOWED   True     False    19     5     TH8    L2    None
DEV-016    ANSWER_ALLOWED   True     True     10     5     None   None  None
DEV-017    ANSWER_ALLOWED   True     True     8      5     None   None  None
DEV-018    ANSWER_ALLOWED   True     True     16     5     TH1    L2    None
DEV-019    ANSWER_ALLOWED   True     True     7      4     None   None  None
DEV-020    ANSWER_ALLOWED   True     True     10     5     None   None  None

TOTAL: 20
gold_in_candidates: 20/20
gold_in_selected:   19/20
selected misses: ['DEV-015']
topic assigned: 11/20, line assigned: 11/20, recipient assigned: 4/20
```

Полный JSON (все поля на каждый кейс, включая `reason_codes`, `is_ambiguous`, `is_probable_defect`) —
`var/knowledge/c07_dev20_run.json` (gitignored, `var/`, воспроизводится командой в §9).

**Baseline для сравнения** (`docs/coordination/stas/C03-runtime-acceptance.md`, реальный dense-GPU прогон,
§5): `gold_in_candidates=20/20`, `gold_in_selected=18/20`, misses `DEV-007`, `DEV-015`. Тот же baseline
воспроизведён `docs/coordination/eduard/C03-handoff.md` §5 на CPU лексическом fallback.

**Before/after этой сессии:** `gold_in_candidates` без изменений (20/20 → 20/20). `gold_in_selected`
**19/20** в этом честном прогоне против ранее заявленных **18/20** — расхождение разобрано в §5, ниже,
причина не в коде (retrieval.py не менялся с C04), а в методологии подсчёта прежних отчётов.

---

## 4. DEV-015 — воспроизведено, verdict: **confirmed-expected-behavior** (не дефект)

Полная трассировка кандидатов (19 штук) для DEV-015 (`Как вернуть УПД в статус «Черновик» при
электронном актировании через ЕИС?`), gold = `15e0fac0bbd05f9a724d` → `portal:563264:1`:

```
    ev:DEV-015:0  pdf:electronic_acceptance:p66:1  exact 1005.655  incomplete
    ev:DEV-015:1  portal:283499:1                   exact 1005.598  incomplete
    ev:DEV-015:2  pdf:supplier_instruction:p334:1   exact 1005.594  incomplete
    ev:DEV-015:3  pdf:supplier_instruction:p214:1   exact 1005.508  incomplete
SEL ev:DEV-015:4  portal:266542:1                   exact 1005.428  complete
    ev:DEV-015:5  portal:563264:1  [GOLD]           exact 1005.413  incomplete
SEL ev:DEV-015:6  pdf:electronic_acceptance:p45:1   exact 1005.342  complete
    ev:DEV-015:7  pdf:electronic_acceptance:p56:1   exact 1005.320  incomplete
SEL ev:DEV-015:8  portal:563256:1                   exact 1005.204  complete
SEL ev:DEV-015:9  portal:296340:1                   exact 1005.175  complete
SEL ev:DEV-015:10 portal:588038:1                   exact 1005.161  complete
    ... (9 more, all lower score)
```

1. **Воспроизведено**: реальный вызов `store.retrieve()`, не пересказ.
2. **Gold source существует**, `content_status='incomplete'` (проверено `store.get_source('portal:563264:1')`
   и напрямую в trace выше) — совпадает с C03-handoff §5 буквально.
3. **Applicability/role**: не блокер — кейс `role=supplier`, все top-candidates применимы (`decision=ANSWER_ALLOWED`,
   `reason_codes=[]`, ни одного `ROLE_MISMATCH`/`ROLE_REQUIRED`).
4. **Conditions**: не блокер, не проверялись отдельно — decision уже `ANSWER_ALLOWED` без reason codes.
5. **Причина ranking/selection**: gold-кандидат ранжируется 6-м по score (`1005.413`, между 4-м и 7-м
   selected-кандидатами по score) — **выше**, чем 3 из 5 реально отобранных (`1005.342`, `1005.204`,
   `1005.175`, `1005.161`). Он не отбирается **не из-за низкого score**, а из-за
   `content_status='incomplete'` — gate (`knowledge/kb/retrieval.py`, §10 спеки) по конструкции никогда
   не включает incomplete-evidence в `ANSWER_ALLOWED`-selected набор, даже когда оно лидирует по score.
6. **Fix**: **не требуется, не применён.** Это ожидаемое поведение gate, а не дефект — понижать
   `content_status='incomplete'` этого источника, чтобы «протащить» его в top-5, было бы подгонкой под
   число, а не исправлением дефекта (явно запрещено заданием). Verdict: **confirmed-expected-behavior**.

---

## 5. DEV-007 — воспроизведено, verdict: **confirmed-expected-behavior** (не дефект; предыдущий отчёт был неточен)

Запрос: `Какие полномочия должны быть в МЧД для работы на Портале поставщиков?`,
`gold_source_ids=["74277b582b2ca98895b9", "1a485c4a3d7d1cfa14e1"]` — **два** почти идентичных по
содержанию KB-записи (реальный дубль контента, не два разных факта):

```
    ev:DEV-007:0  pdf:supplier_instruction:p258:1  exact 1006.627  incomplete
    ev:DEV-007:1  pdf:mchd:p3:1                     exact 1006.568  incomplete
SEL ev:DEV-007:2  portal:559732:1                   exact 1006.282  complete
SEL ev:DEV-007:3  portal:559615:1                   exact 1006.195  complete
SEL ev:DEV-007:4  portal:559622:1                   exact 1006.052  complete
SEL ev:DEV-007:5  portal:559730:1  [GOLD: 1a485c4a3d7d1cfa14e1]  exact 1006.045  complete
SEL ev:DEV-007:6  portal:559628:1                   exact 1005.408  complete
    ev:DEV-007:7  portal:225989:1                   fts   15.987   complete
    ev:DEV-007:8  portal:559897:1                   fts   14.811   complete
    ev:DEV-007:9  portal:588563:1  [GOLD: 74277b582b2ca98895b9] fts 14.685  complete
    ev:DEV-007:10 portal:559617:1                   fts   13.790   complete
```

1. **Воспроизведено**: реальный вызов `store.retrieve()`.
2. **Gold source**: `74277b582b2ca98895b9`→`portal:588563:1` (fts, score 14.685, за пределами top-5) —
   `content_status='complete'`, реально содержит нужный ответ (коды `DIT_PP0001-0008`). Но **второй**
   gold id, `1a485c4a3d7d1cfa14e1`→`portal:559730:1`, **присутствует среди 5 selected** (score 1006.045,
   ровно 5-я позиция из 5).
3. **Проверено содержимое `portal:559730:1`** — не по усечённому 400-символьному `SourceRecord.excerpt`
   (не показывает нужный фрагмент из-за обрезки), а по **полному `EvidenceItem.text`**, который реально
   уходит в generation (`knowledge/kb/retrieval.py`: «текст evidence — `parents.text`, полный
   восстановленный текст статьи, а не обрезанный chunk»): полный текст **содержит** и коды `DIT_PP0001`–
   `DIT_PP0008` с описаниями, и требуемую оговорку «МЧД, полученная в ГИС ЕИС, не содержит полномочий
   для работы на Портале поставщиков» — то есть selected-evidence **фактически достаточен** для
   правильного ответа на этот вопрос (проверено командой, текст приведён полностью в рабочих файлах
   сессии).
4. **Applicability/role/conditions**: не блокер, `decision=ANSWER_ALLOWED`, `reason_codes=[]`.
5. **Ranking/selection**: детерминированно и воспроизводимо дважды подряд (идентичный вывод при повторном
   запуске) — `portal:559730:1` реально попадает в top-5 по exact-score, не пограничный/случайный
   результат.
6. **Почему предыдущий отчёт (`C03-handoff.md` §5, `C03-runtime-acceptance.md` §5) числил DEV-007 как
   miss**: код `knowledge/kb/retrieval.py`, отвечающий за dedup/score/selection (`collect_raw_hits`,
   `dedup_hits`, `expand_to_evidence_groups`), **не менялся C04** (проверено `git diff 1495dfc a95dc68 --
   knowledge/kb/retrieval.py` — единственные изменения: `route`-сборка и расширение `_is_out_of_scope`
   стоп-словами; ни `collect_raw_hits`, ни `dedup_hits`, ни cap-логика отбора не затронуты). KB snapshot
   байт-в-байт идентичен (`knowledge.sqlite` SHA-256 не менялся с C02). При идентичном коде и идентичных
   данных детерминированный пайплайн не мог дать другой selected-набор тогда, чем сейчас — то есть
   `portal:559730:1` уже был бы среди selected и в момент написания `C03-handoff.md`. Наиболее вероятное
   объяснение: тогдашний ad hoc dev20-скрипт (не сохранён в git, был во `/tmp`) использовал более узкую
   проверку gold-match (например, только по первому `gold_source_ids[0]`, что для DEV-007 равно
   `74277b582b2ca98895b9`, реально отсутствующему в top-5, — под эту гипотезу числа сходятся: «only-first»
   даёт ровно тот же DEV-007=miss без ложного срабатывания на других кейсах... кроме `DEV-006`, где
   «only-first» ошибочно даёт `in_candidates=False`, что противоречит заявленному `20/20` — то есть
   единой простой формулы, воспроизводящей исходные числа буквально, восстановить не удалось; сам факт
   расхождения и код/данные, которые делают его невозможным объяснить дефектом текущего кода, задокументированы
   честно). Возможно также разночтение "золотых" файлов дев-сета в момент, когда C03 читал их напрямую
   из неслитой ветки `origin/task/d01-dataset` через `git show` (см. C03-handoff.md §0/§7) — этот файл
   в репозитории с тех пор не менялся (подтверждено §1), но нельзя исключить, что тогдашний временный
   `/tmp`-экземпляр отличался.
7. **Fix**: **не требуется, не применён.** Реальное поведение уже корректно: applicable, complete,
   содержательно достаточный evidence присутствует в selected. Verdict: **confirmed-expected-behavior**
   (в широком смысле «нет дефекта для исправления»), с явной пометкой, что численный разрыв с прежним
   отчётом — не регресс кода, а неточность прежнего измерения.

---

## 6. Остальные 18 кейсов — новых regressions не найдено

Полный прогон (§3) — все 18 прочих кейсов: `decision=ANSWER_ALLOWED`, `reason_codes=[]`,
`gold_in_candidates=True`, `gold_in_selected=True`. `DEV-019` имеет `n_selected=4` (не 5) — в пределах
разрешённого диапазона «3–5 evidence» (C03-handoff §2.2), не дефект: после dedup/gate-фильтрации осталось
4 применимых уникальных evidence-групп, cap=5 не был достигнут по объективной нехватке кандидатов, не по
ошибке.

Побочно проверено (не входит в перечень обязательных DEV-007/DEV-015, но соответствует «добавь любые новые
regressions, если найдёшь»): recipient extraction для `DEV-002` (у C04 задокументирован как честный `null`
из-за «CPU ranking limitation», см. C04-handoff §4/§7 п.2) при конкатенации всех реплик диалога (а не только
последней) **корректно находит** `службу контроля качества Портала поставщиков по форме обратной связи` —
совпадает с `gold recipient`. Это не фикс кода (`extract_recipient`/`match_topic` не менялись), а следствие
того, что `text`, переданный в `QueryContext`, в этом прогоне включает первую реплику диалога (см. §2
методологию). `DEV-018` остаётся честным `null` — не разрешён этим изменением, реальное ограничение
CPU lexical fallback ranking, как и задокументировано C04.

---

## 7. Applied fixes

**Ни одного изменения кода `knowledge/kb/**` или `config/knowledge/{routing_lines,taxonomy,retrieval,normalizer,policy_rules}.json` не применено.**
Оба заявленных дефекта (DEV-007, DEV-015) после честного воспроизведения оказались
`confirmed-expected-behavior` — задание явно разрешает и ожидает такой исход («допустимый и приемлемый
итог по каждому пункту — "no justified retrieval change"»). Единственный новый файл в зоне C —
`config/knowledge/kb_freeze.json` (заморозка, §8), не логика.

**GPU-дисциплина**: пересборка dense-индекса **не требовалась и не выполнялась** — ни один
рассмотренный дефект не связан с текстом источника или эмбеддингами (оба — вопрос gate-политики
`content_status` и ranking/selection на уже существующих данных). `docs/integration/gpu_slots.md`
прочитан (не редактировался — чужая зона); слот C07 «Dev retrieval run» помечен как `planned`, но
реальный dense-прогон не требовался для завершения задачи в её текущей формулировке (все выводы получены
и подтверждены на CPU-данных, GPU нужен был бы только для получения `health.mode=semantic` локально, что
не являлось условием для вынесения verdict по DEV-007/DEV-015 — trace показывает, что проблема/не-проблема
целиком объясняется на уровне gate/ranking логики, не зависящей от того, dense или lexical дал score).

---

## 8. Freeze — release-ready immutable KB state

Записан как git-отслеживаемый, воспроизводимый манифест: [`config/knowledge/kb_freeze.json`](../../../config/knowledge/kb_freeze.json).

Содержит: `snapshot_id`, canonical `input_files` hashes (те же 8, что в `var/knowledge/manifest.json`),
`schema_version`/`normalizer_version`, `knowledge.sqlite` provenance (macOS+Windows-G hashes и
cross-platform verdict из `C03-runtime-acceptance.md`), dense index/id-mapping/manifest hashes (на G,
не пересобирались), embedding model/revision/safetensors hash, routing config hashes
(`taxonomy.json`/`routing_lines.json`), C05-card source_id compatibility check result, DEV20
reproduction summary этой сессии, known limitations (DEV-007/DEV-015 verdicts, topic/line/recipient
coverage).

Ничего в этом файле не «выдумано» — каждое поле либо вычислено локально в этой сессии (`shasum -a 256`),
либо процитировано с явной атрибуцией источника (`A03-handoff.md`, `C03-runtime-acceptance.md`,
`C04-handoff.md`).

### C05-карточки — совместимость source_id (проверено командой, не предположением)

```
$ uv run python3 -c "
import asyncio
from knowledge.kb.store import open_store
async def main():
    store = open_store()
    for sid in ['portal:559622:1', 'portal:559732:1', 'portal:588150:1']:
        rec = await store.get_source(sid)
        print(sid, '->', 'FOUND' if rec else 'MISSING', rec.content_status if rec else '')
asyncio.run(main())
"
portal:559622:1 -> FOUND complete
portal:559732:1 -> FOUND complete
portal:588150:1 -> FOUND complete
```

Снимок не пересобирался с изменением контента (только детерминированная реконструкция того же
`kb-4918a97f0874d1e8`) — совместимость тривиально верна, но подтверждена командой, как и требовало
задание.

---

## 9. Commands and actual outputs

```
$ git fetch --prune origin && git switch main && git pull --ff-only origin main && git status --short
(получена новая ветка origin/task/a04, main уже актуален)
$ git rev-parse HEAD
56da4216b7bfd5e1cc3cbc620029cd90045f4391
$ git switch -c task/c07

$ python3 -m knowledge.kb.ingest --out var/knowledge
snapshot_id kb-4918a97f0874d1e8 (детерминированно, лог идентичен C02/C03/C04)
$ shasum -a 256 var/knowledge/knowledge.sqlite var/knowledge/manifest.json
6d1555777d9bbf9ae7f2df93a69cf61f53dd04263877a8ebaf7fc35e16a4bdf8  var/knowledge/knowledge.sqlite
e0d01a74dcfe43f8a562a10837793fa04a052e775e60877115dce7785f24d061  var/knowledge/manifest.json

$ uv run pytest -q
428 passed

$ uv run python3 -c "import torch" 2>&1 | tail -1
ModuleNotFoundError: No module named 'torch'
$ uv run python3 -c "import numpy" 2>&1 | tail -1
ModuleNotFoundError: No module named 'numpy'

# DEV20 reproduction (script recreated at var/c07_run_dev20_full.py for reproducibility, not tracked —
# var/ is gitignored per AGENTS.md; logic documented in full in §2-3 above):
$ uv run python3 var/c07_run_dev20_full.py
(см. §3 полный вывод)

$ git diff --stat -- pyproject.toml config/runtime/ contracts/ backend/ tools/ tests/ docs/integration/ \
    knowledge/policy/ knowledge/audit/ evaluation/
(пусто — чужие зоны не тронуты)
```

---

## 10. Changed files

| Файл | Назначение |
|---|---|
| `config/knowledge/kb_freeze.json` | новый — release-ready freeze manifest (§8) |
| `docs/coordination/eduard/C07-handoff.md` | этот файл |

Никакой код `knowledge/**` не менялся. Никакие другие `config/knowledge/*.json` не менялись (проверено
`git diff --stat` — только `kb_freeze.json` новый, остальные без diff).

---

## 11. Acceptance

| Критерий | Результат |
|---|---|
| Реальный прогон DEV20 через `store.retrieve()`, не пересказ | **passed** — §3, полный лог |
| DEV-007 разобран по всем 6 пунктам методологии (repro→gold→role→conditions→ranking→fix-decision) | **passed** — §5 |
| DEV-015 разобран по всем 6 пунктам | **passed** — §4 |
| Не подгонять threshold ради 20/20 | **passed** — ни один порог/вес не менялся; DEV-015 остаётся `ESCALATE`-подобным исключением по дизайну gate, зафиксировано как `confirmed-expected-behavior`, а не «исправлено» |
| Только точечные, минимальные fixes (если бы понадобились) | **not applicable** — ни один fix не потребовался |
| GPU-дисциплина: слот не занят без необходимости | **passed** — GPU не использовался, дефекты не требовали пересборки эмбеддингов |
| Freeze с полным набором полей §16 | **passed** — `config/knowledge/kb_freeze.json` |
| C05-карточки source_id совместимы | **passed**, проверено командой — §8 |
| Handoff по разделу 16 | **passed** — этот файл |

---

## 12. Data mode: real / mock / mixed

| Часть | Режим |
|---|---|
| KB снимок | **real**, пересобран локально, байт-в-байт идентичен C02/C03/C04 |
| Лексический/exact retrieval (bm25/FTS) | **real** |
| Query encoder (dense) | **mock** (`MockQueryEncoder`, `is_mock=True`) — реальный dense недоступен на этой машине (нет GPU/torch, артефакты G не скопированы локально); `health().mode=lexical_only`, честно не выдано за `semantic` |
| Routing (topic/line/recipient) | **real**, детерминированный код C04, без модели |
| DEV20 датасет | **real**, D01, 20 строк |
| Freeze manifest hashes | **real**, либо вычислены локально (`shasum`), либо процитированы с атрибуцией источника (G-артефакты, не пересчитаны локально — недоступны) |

---

## 13. Blockers

**Нет блокирующих для C07.** Один непровёденный GPU-rebuild **не требуется**: ни один рассмотренный
дефект (DEV-007, DEV-015) не потребовал изменения текста источника или пересборки эмбеддингов — оба
разрешились на уровне анализа gate/ranking-политики над уже существующими данными, без изменения кода.
Если A/интегратор впоследствии решит скопировать реальные G-артефакты (`index.npy`/`index_ids.json`/
stamped `manifest.json`) в этот рабочий каталог, чтобы получить `health.mode=semantic` локально на M —
это отдельная инфраструктурная задача (перенос файлов между машинами), не блокер и не входит в scope C07.

## 14. CR

**Новых CR нет.** Контракты не менялись.

## 15. Inputs needed by next task (A06 — интеграция/приёмка)

- `config/knowledge/kb_freeze.json` — единая точка правды для release-ready KB state: snapshot/hashes/
  known limitations, без необходимости собирать их заново из отдельных C02-C05 handoff'ов.
- Verdict DEV-007/DEV-015 закрыт как `confirmed-expected-behavior` для обоих — A06 может опираться на
  `gold_in_candidates=20/20`, `gold_in_selected=19/20` (реальное значение при честном подсчёте «хотя бы
  один gold id»; см. §2 обоснование методологии) как на текущий baseline retrieval-качества на CPU
  lexical fallback. Реальный dense (G) даёт `18/20` по прежнему (стас-)отчёту с ДРУГОЙ методологией
  подсчёта — сравнение dense vs lexical по единой методологии не проводилось в этой сессии (артефакты G
  недоступны локально) и остаётся открытым вопросом для того, кто получит доступ и к G, и к этой сессии
  одновременно.
- Найденная нестыковка `evaluation/ai_test/dev/manifest.json`'s `sha256` (§1) — стоит передать
  владельцу D01 для проверки/исправления, не блокирует A06.
- C05-карточки (`card-eduard-001.json`, `card-eduard-002.json`) подтверждены совместимыми с текущим
  замороженным снимком — можно review'ить дальше без дополнительной проверки source_id.

## Остановка

C07 завершён. C06 в этом чате не начинаю — для него участник создаёт отдельный новый чат.
