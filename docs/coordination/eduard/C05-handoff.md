# C05 — handoff

- **Task ID / status:** C05 — Два черновика сценариев Эдуарда / **done**
- **Owner / tool:** Эдуард / агент C / Claude Code
- **Base SHA:** `f62ce7784d4e166cab4b6015732fa8e23c1c9254` (`origin/main`, совпадает с BASE_SHA из задания)
- **Result SHA:** `f9afc86` (`task/c05`) — код/карточки; поверх него один docs-only коммит фиксирует этот SHA в handoff
- **Ветка:** `task/c05`

## 0. Оговорка про базу — почему в истории есть merge-коммит

На момент старта C05 задание C04 (`route: RoutingResult` в `knowledge/kb/retrieval.py`,
`knowledge/kb/routing.py`, `config/knowledge/taxonomy.json`, `config/knowledge/routing_lines.json`)
**ещё не было принято интегратором A в `origin/main`** — проверено фактически:

```
$ git log origin/task/c04 --oneline -5
ef44fc3 docs(C04): record result SHA in handoff
3a256db feat(C04): routing (topic/subtopic/line/recipient) and OOS/clarify tuning
4345073 merge(task/c03): bring in CPU retrieval pipeline as C04 dependency
...
$ find knowledge/kb -iname "*routing*"   # на origin/main — пусто
```

Задание C05 явно разрешает для этого случая тот же паттерн, что уже использовал C04 для C03:
`task/c05` создана от `origin/main` (BASE_SHA), затем один явный merge-коммит
`git merge origin/task/c04`. Конфликт был один — `knowledge/kb/retrieval.py` (add/add: `main` после
интеграции A02/GPU-рантайма и `task/c04` независимо модифицировали один и тот же файл от общего
предка C03). Разрешён не вручную-пересозданием, а построчным сравнением: diff показал, что версия
`origin/task/c04` — строгий суперсет версии `origin/main` в этом файле (тот же C03-код плюс
routing-хуки C04, без потерянных изменений с любой стороны):

```
$ diff <(git show HEAD:knowledge/kb/retrieval.py) <(git show origin/task/c04:knowledge/kb/retrieval.py)
# только добавления C04 (routing-импорт, build_routing_result(), расширенный _is_out_of_scope,
# OOS-стоп-слова) поверх идентичного C03-кода — ни одной строки main, отсутствующей в c04-версии
```

Итог мержа принят как версия `origin/task/c04` для этого файла (`git add` без ручного редактирования
контента).

```
$ git status --short   # сразу после merge --no-edit
A  config/knowledge/routing_lines.json
A  config/knowledge/taxonomy.json
A  docs/coordination/eduard/C04-handoff.md
M  knowledge/kb/retrieval.py
A  knowledge/kb/routing.py
A  knowledge/kb/taxonomy_build.py
A  knowledge/kb/tests/test_routing.py
```

После приёмки C04 в `main` этот merge-коммит станет тривиально сводимым.

- **Contracts version:** `2.0.0-c0`, **не менялся** — `ScenarioCard`/`RoutingResult` использованы как
  есть, ни одного поля не добавлено/не изменено.
- **Machine / runtime:** M — macOS-14.4.1-arm64, Python 3.13.12. GPU не требовался и не использовался
  (dense-индекс в `var/knowledge/` не собирался — задача целиком CPU: FTS/exact fallback).
- **KB snapshot:** `kb-4918a97f0874d1e8`.
  `var/knowledge/knowledge.sqlite` собран локально командой `python3 -m knowledge.kb.ingest --out
  var/knowledge` (сырые источники `TenderHack_KnowledgeBase/knowledge_base_FINAL.jsonl`,
  `Регламент_информационного_взаимодействия-4.pdf`, `НН 2026/*.pdf` присутствуют локально, `var/`
  вне Git по AGENTS.md). Результат детерминирован и **побитово совпадает** с тем, что зафиксировал C04:
  `knowledge.sqlite` SHA-256 `6d1555777d9bbf9ae7f2df93a69cf61f53dd04263877a8ebaf7fc35e16a4bdf8`,
  `manifest.json` SHA-256 `e0d01a74dcfe43f8a562a10837793fa04a052e775e60877115dce7785f24d061`.
  Dense-векторы (`index.npy`/`index_ids.json`, профиль G) отсутствуют → `health().mode ==
  "lexical_only"` (честный FTS/exact fallback, ожидаемо по заданию, не блокер).

---

## 1. Changed files

Только зона C (`knowledge/**` не редактировался, кроме принятого merge-коммита C04; свои файлы —
`content/cards/eduard/**` и `docs/coordination/eduard/C05-handoff.md`):

| Файл | Назначение |
|---|---|
| `content/cards/eduard/card-eduard-001.json` | Draft-карточка №1: МЧД не требуется ИП |
| `content/cards/eduard/card-eduard-002.json` | Draft-карточка №2: РДИК_0009 |
| `docs/coordination/eduard/C05-handoff.md` | этот файл |
| `knowledge/kb/retrieval.py` | принят merge-конфликт (см. §0) — не редактировался повторно вручную |

Чужого не трогал: `contracts/**` (схема `ScenarioCard`/`RoutingResult` не менялась), `backend/**`,
`tools/**`, `tests/**`, `docs/integration/**`, `config/runtime/**`, `frontend/**`,
`evaluation/ai_test/**` (final не открывался, dev использован только на чтение).

```
$ git diff --stat f62ce7784d4e166cab4b6015732fa8e23c1c9254 -- contracts/ backend/ tools/ tests/ frontend/ config/runtime/ docs/integration/
(пусто)
```

---

## 2. Implemented behavior

Две draft-карточки `ScenarioCard` (`status="draft"`, **не** `"reviewed"`), обе валидированы
pydantic-моделью из `contracts/python/tenderhack_contracts/models.py` (round-trip
`model_dump_json()` → `ScenarioCard.model_validate_json()`, извне не подделано ни одно поле схемы —
`ContractModel` с `extra="forbid"`).

### 2.1. CARD-EDUARD-001 — «МЧД не требуется индивидуальному предпринимателю»

Основа — реальные dev-кейсы `DEV-005`/`DEV-006` (`evaluation/ai_test/dev/ai_test_dev.jsonl`, роль
`supplier`, `answerable=true`). **Важно:** `gold_source_ids` из этого dev-файла (`57f55c...`,
`d5395e...`) относятся к старой схеме ID и **не существуют** в текущем снимке
(`kb-4918a97f0874d1e8`) — проверено `store.get_source()`, все три вернули `None`. Это не выдумано и
не проигнорировано: карточка использует РЕАЛЬНЫЕ source_id из фактического снимка, найденные через
живой `store.retrieve()` на тот же вопрос (см. `retrieval_method="exact"`, детектор точных
идентификаторов сработал на «МЧД»):

- `portal:559622:1` — «Нужна ли МЧД индивидуальному предпринимателю?», `content_status=complete`,
  `role_verified=True`, `applicable_roles=["supplier"]` — прямой ответ «Нет».
- `portal:559732:1` — «При каких действиях на Портале поставщиков требуется МЧД и кому?», тот же
  статус/роль — общий контекст правила (кому МЧД нужна/не нужна), опора для `steps` (не путать с
  директором филиала).

`route` — реальный вывод `store.retrieve()` → `build_routing_result()` (не заполнен вручную):
`topic_id=None, subtopic_id=None, support_line=None, recommended_recipient=None, rule_id=None`.
Причина честно нулевая, а не баг: в `config/knowledge/taxonomy.json` (9 тем/86 строк C04, реальный
источник) нет ни одной подтемы с ключевыми словами, покрывающими «МЧД» — проверено
`grep -i "мчд\|доверенн"` по `taxonomy.json`, совпадений нет. Зафиксировано ниже как blocker для
следующей задачи (не выдумываю справочник, которого нет).

`conditions` — дословно `required_conditions` из `DEV-005`/`DEV-006`: «Пользователь — индивидуальный
предприниматель».

### 2.2. CARD-EDUARD-002 — «РДИК_0009»

Основа — реальный dev-кейс `DEV-009` (роль `supplier`, точный идентификатор «РДИК_0009» в тексте
запроса). Единственный источник, реально существующий в снимке и найденный `store.retrieve()`
(`retrieval_method="fts"`, топ по score среди selected evidence):

- `portal:588150:1` — «Действия при срабатывании интеграционного контроля РДИК_0009»,
  `content_status=complete`, `role_verified=True`, `applicable_roles=["customer","supplier"]` —
  дословный текст источника совпадает с `gold_line`/`expected_outcome` DEV-009 (расхождение
  сведений о заказчике с реестром ЕИС → привести в соответствие с контрактом ЕИС).

`route` — реальный вывод `build_routing_result()`: `topic_id="TH8"` (Электронное исполнение, ЕИС),
`subtopic_id="ST75"`, `support_line="L2"`, `rule_id="ROUTE.LINE.THEME_DEFAULT"` (из
`config/knowledge/routing_lines.json`, C04 baseline: TH8→L2, «УПД/РДИК-контроли — методология, не
дефект по умолчанию»). `recommended_recipient=None` — ожидаемо честный `null` (BL-C04-1/BL-C00-2:
справочника линий/адресатов не существует, `extract_recipient()` не нашёл буквальной фразы
«обратитесь в …» в тексте источника).

`applicable_roles=["customer","supplier"]` взяты из `applicable_roles` реального evidence (не сужены
до одной роли dev-кейса вручную — источник объективно применим к обеим ролям).

### 2.3. Explicit — карточки не reviewed и не импортированы

Обе карточки `status="draft"`, `reviewer_id=null`, `reviewed_at=null`. Не добавлены ни в один индекс
рантайма (`store.get_card()` их не видит — читает только снимок, `content/cards/` не сканируется
никаким кодом на текущий момент, проверено `grep -rn "content/cards" --include="*.py"` → 0
совпадений вне этого README). Импорт — задача C06 (отдельный reviewer, Артём).

---

## 3. Acceptance

| Критерий | Результат |
|---|---|
| Обе карточки валидны по pydantic-схеме `ScenarioCard` | **passed** — `ScenarioCard.model_validate_json()` на обоих файлах без ошибок (см. §4 команды) |
| `status="draft"`, не `"reviewed"` | **passed** — оба файла |
| `source_ids` реально существуют в KB snapshot (не выдуманы) | **passed** — `store.get_source()` вернул непустую запись для всех 3 (`portal:559622:1`, `portal:559732:1`, `portal:588150:1`) |
| `applicable_roles` подтверждены `role_verified` в снимке | **passed** — оба через `EvidenceItem.role_verified=True` из реального `store.retrieve()` |
| `route` — реальный вывод `build_routing_result()`, не заполнен вручную | **passed** — оба поля `route` скопированы напрямую из `KnowledgeResult.route`, возвращённого `store.retrieve()` |
| Карточки не выданы за `reviewed`, не импортированы в рантайм | **passed** — `status="draft"`, `content/cards/` нигде не читается рантаймом |
| Не использован скрытый final-набор | **passed** — источник вопросов только `evaluation/ai_test/dev/ai_test_dev.jsonl` (DEV-005/006/009); `evaluation/ai_test/final*` не открывался |
| Существующие тесты `knowledge/**` не сломаны merge-коммитом C04 | **passed** — 395/395 |

---

## 4. Commands and actual outputs

```
$ git fetch --prune origin && git switch main && git pull --ff-only origin main
Fast-forward → f62ce7784d4e166cab4b6015732fa8e23c1c9254

$ git switch -c task/c05 origin/main
$ git merge origin/task/c04 --no-edit
Auto-merging knowledge/kb/retrieval.py
CONFLICT (add/add): Merge conflict in knowledge/kb/retrieval.py
# разрешено принятием версии origin/task/c04 (строгий суперсет, см. §0), затем:
$ git add knowledge/kb/retrieval.py && git commit --no-edit
[task/c05 62a4a51] Merge remote-tracking branch 'origin/task/c04' into task/c05

$ python3 -m knowledge.kb.ingest --out var/knowledge
...
"snapshot_id": "kb-4918a97f0874d1e8"

$ python3 -m pytest knowledge/ -q
395 passed

# построение карточек: живой store.retrieve()/get_source() + build_routing_result(),
# результат сериализован через ScenarioCard.model_dump_json(), затем round-trip
# ScenarioCard.model_validate_json() — оба файла:
wrote content/cards/eduard/card-eduard-001.json
  validated OK: card_id=CARD-EDUARD-001 status=draft route={'topic_id': None, 'subtopic_id': None, 'support_line': None, 'recommended_recipient': None, 'basis_source_ids': [], 'rule_id': None, 'is_probable_defect': False, 'is_ambiguous': False, 'reason_codes': []}
wrote content/cards/eduard/card-eduard-002.json
  validated OK: card_id=CARD-EDUARD-002 status=draft route={'topic_id': 'TH8', 'subtopic_id': 'ST75', 'support_line': 'L2', 'recommended_recipient': None, 'basis_source_ids': [], 'rule_id': 'ROUTE.LINE.THEME_DEFAULT', 'is_probable_defect': False, 'is_ambiguous': False, 'reason_codes': []}

$ python3 -c "
import asyncio, sys
sys.path.insert(0,'contracts/python'); sys.path.insert(0,'.')
from knowledge.kb.store import open_store
async def m():
    s = open_store()
    for sid in ['57f55c0bf16f7c32125b','d5395ef3de690c75b419','23994fa9015966d76043']:
        print(sid, await s.get_source(sid))
asyncio.run(m())
"
57f55c0bf16f7c32125b None
d5395ef3de690c75b419 None
23994fa9015966d76043 None
# подтверждено: старые gold_source_ids из dev-файла не существуют в текущем снимке — не используются в карточках
```

---

## 5. Data mode

**Real** (не mock) — везде:
- KB snapshot: собран локально из реальных исходников (`TenderHack_KnowledgeBase/*.jsonl`,
  `Регламент*.pdf`, `НН 2026/*.pdf`), идентичен по SHA-256 снимку C03/C04.
- Retrieval: `store.retrieve()` реальный pipeline C03 (`knowledge/kb/retrieval.py`) в режиме
  `lexical_only` (честный FTS/exact fallback — dense-индекс от G не собирался, не требовался для
  этой задачи).
- Routing: реальный `build_routing_result()` C04 (`knowledge/kb/routing.py`), не заглушка.
- Query encoder: `MockQueryEncoder` (по умолчанию на M, `is_mock=True`) — влияет только на то, что
  `health().mode` не `"semantic"`; на retrieval двух конкретных запросов карточек это не повлияло:
  оба нашли полное evidence через `exact`/`fts` без dense (см. `retrieval_method` в §2).
- Источники вопросов (`DEV-005/006/009`): реальные dev-кейсы, `evaluation/ai_test/dev/` (не final).

Ничего не mock/выдумано в самих карточках.

---

## 6. Artifacts and paths

- `content/cards/eduard/card-eduard-001.json`
- `content/cards/eduard/card-eduard-002.json`
- `var/knowledge/knowledge.sqlite` (SHA-256 `6d1555777d9bbf9ae7f2df93a69cf61f53dd04263877a8ebaf7fc35e16a4bdf8`, локальный build-артефакт, вне Git)
- `var/knowledge/manifest.json` (SHA-256 `e0d01a74dcfe43f8a562a10837793fa04a052e775e60877115dce7785f24d061`)

---

## 7. Blockers

- **BL-C05-1 (наследует BL-C04-1/BL-C00-2, не гипотетический):** в `config/knowledge/taxonomy.json`
  нет подтемы, покрывающей тему «МЧД» — `CARD-EDUARD-001.route` честно пустой
  (`topic_id=None`/`support_line=None`). Это пробел входных данных (реальный `Темы_подтемы_обращений.xlsx`
  не выделяет МЧД отдельной строкой), не дефект `routing.py`. Передаётся дальше как наблюдение, не
  создаю CR на этой задаче (вне зоны C05 — таксономия зафиксирована C04, менять её не моё право).
- Dense-индекс (`var/knowledge/index.npy`) не собран (профиль G) — обе карточки построены на
  `lexical_only` retrieval. Не блокер: обе карточки нашли полное evidence через `exact`/`fts`.

## 8. CR

Нет — контракт (`ScenarioCard`/`RoutingResult`) не потребовал изменений, обе карточки укладываются в
существующую схему.

## 9. Inputs needed by next task (C06)

- `task/c05`, result SHA — commit после этого файла.
- Обе карточки для перекрёстной проверки, условия (`content.conditions`) по каждой:
  - `CARD-EDUARD-001`: «Пользователь — индивидуальный предприниматель»; «Роль — поставщик»; «Вопрос о
    необходимости МЧД для подписания электронных документов».
  - `CARD-EDUARD-002`: «Электронное исполнение по контракту (сфера закупок ЕИС)»; «Сработал
    интеграционный контроль РДИК_0009».
- KB snapshot `kb-4918a97f0874d1e8` (пересобрать локально: `python3 -m knowledge.kb.ingest --out
  var/knowledge` — детерминировано, SHA-256 см. §6).
- BL-C05-1 (см. §7) — независимый reviewer должен знать, что `route` карточки №1 пуст по объективной
  причине, не по ошибке этой задачи.
