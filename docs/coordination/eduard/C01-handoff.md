# C01 — handoff

- **Task ID / status:** C01 — Детерминированный policy-модуль / **done**
- **Owner / tool:** Эдуард / агент C / Claude Code
- **Repo path:** `/Users/gunter/Desktop/tender-hack` (git root)
- **Worktree path:** `/Users/gunter/Desktop/tenderhack-c01`
- **Branch:** `task/c01`
- **Base SHA:** `27d45b1675cc884350e6b06aba431d5d867fb76c` (tag `bootstrap-contracts-v2`, принятый C0 от A00)
- **Result SHA:** `350b93f6bc2076028e4afb7e0877c1f51f602657` — код, ruleset, тесты и handoff. Поверх него один docs-only commit, фиксирующий этот SHA в handoff; HEAD ветки `task/c01` указан в финальном сообщении чата и содержимое кода не меняет.
- **Contracts version:** `2.0.0-c0`. Contracts не изменялись ни в одном файле.
- **Machine / runtime SHA / KB snapshot:** профиль M — MacBook Air M2 (arm64), 8 GiB RAM, macOS 14.4.1, Python 3.13.12, GPU не использовался. Runtime code = result SHA. KB snapshot **не используется**: C01 не читает KB и от C02/C03 не зависит. Новых зависимостей не добавлено — модуль на чистом stdlib.

## Changed files

Только зона C (`knowledge/**`, `config/knowledge/**`, `docs/coordination/eduard/**`):

| Файл | Назначение |
|---|---|
| `config/knowledge/policy_rules.json` | Ruleset-данные: нормализация, технические шаблоны, 13 profanity-правил, правила explicit_human_request. `ruleset_version = c01.1` |
| `knowledge/__init__.py` | Пакет зоны C |
| `knowledge/policy/__init__.py` | Публичный API: `build_policy`, `DeterministicPolicy`, `reason_codes_for`, `POLICY_CLOSURE_NOTICE` |
| `knowledge/policy/normalization.py` | Нормализация **только для матчинга**: NFKC, casefold, ё→е, zero-width, повторы, гомоглифы, цифры-как-буквы, разделители/маски, склейка коротких слов |
| `knowledge/policy/profanity.py` | Компиляция правил в анкоренные regex, проверка маскировки, исключения |
| `knowledge/policy/human_request.py` | Правила явной просьбы позвать человека + suppressors |
| `knowledge/policy/service.py` | `DeterministicPolicy` — реализация `PolicyPort`; приоритет profanity; notice |
| `knowledge/policy/tests/{conftest,test_profanity_positive,test_false_positives,test_human_request,test_priority_and_port,test_no_model_calls}.py` | 221 unit-кейс |
| `docs/coordination/eduard/C01-handoff.md` | этот файл |
| `docs/coordination/eduard/CR-EDUARD-001-knowledge-package-and-testpaths.md` | CR к A: packaging + testpaths |

Чужие файлы не менялись: `pyproject.toml`, `contracts/**`, `backend/**`, `tools/**`, `tests/**`, `docs/integration/**` — без изменений (подтверждено `git status --porcelain`, см. ниже).

## Implemented behavior

**Контракт.** Реализован ровно действующий `PolicyPort` из `contracts/python/tenderhack_contracts/ports.py`:
`def check(self, text: str) -> PolicyResult` — **синхронный**, без `async`. Возвращается настоящий
`tenderhack_contracts.models.PolicyResult` (`profanity`, `explicit_human_request`, `matched_rule_ids`).

**Нормализация — только для поиска совпадений.** Исходный текст не переписывается: `check()` принимает
`str`, строит отдельные строки-кандидаты и наружу их не отдаёт. Тест
`test_is_deterministic_and_does_not_mutate_input` проверяет, что входная строка после вызова
не изменилась, а `PolicyResult` не содержит текста вообще.

Шаги нормализации:
1. **Гашение технических конструкций** (URL, www, email, GUID, hex, стек-фреймы, пути, dotted/snake/camel идентификаторы, цифровые серии ≥3) → заменяются пробелом, чтобы гомоглифы и склейка не собрали совпадение из кода.
2. NFKC, casefold, `ё→е`, удаление zero-width, схлопывание повторов символа длиннее 3.
3. Внутри слова любой не буквенно-цифровой символ становится SENTINEL. SENTINEL трактуется и как **пропускаемый разделитель** (`х.у.й`), и как **маска одной буквы** (`х*й`) — regex решает это через backtracking.
4. **Гомоглифы и цифры-как-буквы применяются только к словам, содержащим хотя бы одну кириллическую букву.** Чисто латинские токены (`base64`, `proxy`, `oxygen`, идентификаторы) не переписываются — это главный барьер от false positives.
   Гомоглифы: `a b c e h k m o p t x y → а в с е н к м о р т х у`. Цифры: `0→о 3→з 4→ч 6→б`.
   Цифра в слове с кириллицей читается **двумя способами** и даёт двух кандидатов: цифра-как-буква (`пи3дец`) и цифра-как-маска (`п3здец`). Цифры вне карты — всегда маска (`бл9дь`).
5. **Склейка** рядов из 2..5 подряд идущих слов, где каждое слово ≤3 букв и хотя бы одно ≤2 — закрывает пробелы внутри слова (`х у й`, `бл я дь`). Длинные слова не склеиваются никогда, произвольного склеивания предложения в одну строку не происходит.

**Запрет необоснованного substring matching.** Совпадение опирается на границу слова/токена:
кандидат должен **целиком** разбираться как `^[разрешённый префикс] + корень + [окончание ≤ N]$`.
Поиск вхождения корня в произвольном месте невозможен по построению — regex анкорен `^...$` по кандидату.
Плюс per-rule список `exception_token_prefixes` (например `себ`, `теб`, `хлеб`, `требов`, `мудр`, `херсон`).
Маскировка ограничена: число атомов, закрытых маской, ≤ `max_masked` (1–2), и не менее 2 атомов должны
совпасть буквально.

**Приоритет profanity.** `check()` сначала считает profanity. При срабатывании метод **закорачивается**:
возвращается `profanity=True, explicit_human_request=False`, а `matched_rule_ids` содержит только
`POL.PROF.*`. Правила human-request в таком сообщении не вычисляются — просьба позвать человека внутри
нецензурного сообщения **не** подтверждает передачу, обращение закрывается как `closed_policy`
(спецификация §9: при срабатывании 0 routing, 0 embedding, 0 retrieval, 0 generation).

**Notice.** `POLICY_CLOSURE_NOTICE` дословно совпадает с `contracts/fixtures/policy.json`:
«Обращение завершено: в сообщении обнаружена нецензурная лексика. Пожалуйста, соблюдайте правила общения».

**Reason codes.** `PolicyResult` в C0 не содержит поля `reason_codes`, поэтому отображение вынесено в
функцию `reason_codes_for(result) -> list[ReasonCode]`, возвращающую значения **enum**
`ReasonCode.POLICY_LANGUAGE` / `ReasonCode.EXPLICIT_HUMAN_REQUEST`, а не строки. Контракт не менялся.

### Profanity rules

| rule_id | Вид | Что закрывает | Границы / исключения |
|---|---|---|---|
| `POL.PROF.HUY` | корень | `х + у + [йяеюи]` — хуй, хуйня, нахуй, охуеть, похуизм | префиксы `по на за до ни о от не пере раз рас`, окончание ≤6 |
| `POL.PROF.PIZD` | корень | `пизд` — пиздец, распиздяй, спиздить | префиксы `о по на за вы до рас раз не при от из с у`, окончание ≤6 |
| `POL.PROF.EB` | корень | `еб` — ебать, заебали, долбоеб, съебался, въебать, ёбаный | закрытый список префиксов **без одиночного `с`**; исключения `себ теб хлеб лебед ребен ребр щебен требов дебет жереб небес гребен серебр стебел плеб верб`; окончание ≤6 |
| `POL.PROF.BLYAD` | корень | `бл + я + [дт]` — блядь, блять, бляди | префиксы `о по на за не`, окончание ≤4 |
| `POL.PROF.BLYA` | корень | ровно токен `бля` (окончание 0, без префиксов) | «обляпать», «бляха» не задеваются |
| `POL.PROF.MUD` | корень | `муд + [аоие]` — мудак, мудила, мудень, мудозвон | «мудрый/мудрость» отсечены классом гласной **и** исключением `мудр` |
| `POL.PROF.PIDOR` | корень | `пид + [оа] + р` — пидор, пидорас, пидар | окончание ≤5 |
| `POL.PROF.PIDR` | корень | `пидр` — пидр, пидрила | окончание ≤3 |
| `POL.PROF.ZALUPA` | корень | залупа, залупе | окончание ≤4, `max_masked=2` |
| `POL.PROF.GANDON` | корень | гандон, гондон | «гондола» не совпадает (после `гондо` требуется `н`) |
| `POL.PROF.HER` | корень | хер, херня, похер, нахера | окончание ≤3; исключения `херсон херувим херес хером` |
| `POL.PROF.SUKA` | точный токен | сука/суки/суке/суку/сукой/сучка/сучара/сученыш/сукин (21 форма) | только полное совпадение токена → «сук», «сукно», «сучок» не блокируются |
| `POL.PROF.TRANSLIT` | точный токен, латиница | blyat, blyad, pizda, pizdec, hui, huy, xyu, ebat, suka, pidor, mudak, nahui, pohui (23 формы) | только полное совпадение чисто латинского токена |

### explicit_human_request rules

| rule_id | Условие |
|---|---|
| `POL.HUMAN.TRANSFER_REQUEST` | transfer-маркер (`соедините, переключите, переведите, подключите, свяжите, передайте, перенаправьте, эскалируйте, позовите, вызовите, пригласите, дайте`, 39 форм) + адресат в окне ≤7 токенов. Адресат — человек (`оператор, человек, специалист, сотрудник, консультант, менеджер`) **или** канал (`поддержк, техподдержк, стп, саппорт`) |
| `POL.HUMAN.NEED_PERSON` | need-маркер (`нужен, нужна, необходим, хочу, хотел, требую, требуется, прошу, можно, могу, позвольте`) + **только адресат-человек**. «Нужна поддержка» намеренно **не** срабатывает — это не просьба позвать человека |
| `POL.HUMAN.LIVE_PERSON` | «живой человек» в любой форме (`живого человека`, `живым человеком`) |
| `POL.HUMAN.NOT_BOT` | «не бот / не с ботом / не робот / не с машиной / не с автоответчиком» |
| `POL.HUMAN.TARGET_ONLY` | всё сообщение — адресат-человек плюс вежливые слова: «оператор», «оператора, пожалуйста», «человека!» |
| `POL.HUMAN.SUPPRESS.HOWTO` | **подавитель**: в предложении есть вопросительный маркер (`как, где, куда, какой, каков, есть ли, подскажите`) И контактное слово (`связат, найти, позвонит, написат, обратит, телефон, номер, контакт, почт, email, чат, адрес, график, режим работы, горяч`) → предложение считается knowledge-вопросом про контакты, не передачей |
| `POL.HUMAN.SUPPRESS.NEGATION` | **подавитель**: `не нужен / не нужна / не надо / не хочу / не требуется` → отказ от передачи |

Подавители работают **на уровне предложения**: «Как связаться с оператором? Переведите меня на
человека.» → `explicit_human_request=True` по второму предложению (проверено тестом).
Подавители не попадают в `matched_rule_ids` — там только фактически сработавшие правила.

**Неоднозначная фраза даёт `false`** — это отдельная категория тестов: общее недовольство («ужасный
сервис», «это не работает», «почему так долго», «хочу написать жалобу», «ваш бот бесполезен», «мне
нужна помощь»), упоминание человека без просьбы («оператор мне вчера ответил неправильно»), вопрос про
контакты, явный отказ, предметные запросы с маркером но без адресата-человека («дайте инструкцию по
актированию»).

## Acceptance: passed

| Критерий карточки C01 | Результат | Чем подтверждено |
|---|---|---|
| PolicyPort C0 совместим: сигнатура синхронная | **passed** | `test_signature_matches_policy_port_and_fake` (сравнение `inspect.signature(..., eval_str=True)` c `PolicyPort.check` **и** `FakePolicy.check` — совпадают), `test_check_is_synchronous` |
| Возвращается настоящий `PolicyResult` | **passed** | `test_returns_real_contract_policy_result` — `isinstance(result, PolicyResult)` + точный `model_dump()` |
| Модуль подставляется вместо `FakePolicy` без изменений в contracts/backend | **passed** | `test_drop_in_replacement_for_fake_policy` — оба порта проходят через одну функцию, аннотированную `PolicyPort`; `contracts/**` и `backend/**` не изменены |
| Воспроизводимые unit cases по всем категориям | **passed** | 221 passed, 0 failed. Матрица ниже |
| Необоснованный substring не блокирует benign text | **passed** | 91 benign-кейс в `test_false_positives.py` + `test_substring_alone_never_matches` |
| Ноль вызовов LLM/embedding/retrieval | **passed** | AST-скан импортов + поведенческий тест с отключённым сокетом + grep (вывод ниже) |
| Приоритет profanity | **passed** | `test_profanity_wins_over_human_request` (4 кейса), `test_profanity_short_circuits_human_rules` |
| A00 не сломан | **passed** | `uv run pytest` → `28 passed` |
| Не менял оркестратор / чужие файлы | **passed** | `git status --porcelain` показывает только `config/knowledge/`, `docs/coordination/eduard/`, `knowledge/` |

**Not run / вне scope:** backend orchestration (зона A), интеграция policy в `app.py` (A02), routing и
L1/L2/L3 (C04), retrieval/KB (C02/C03). Реальный end-to-end через HTTP не прогонялся — в C0 `app.py`
содержит только health и policy нигде не подключена.

### Матрица тестов

| Категория | Файл | Кейсы | Результат |
|---|---|---|---|
| explicit profanity | `test_profanity_positive.py::test_explicit_profanity_is_detected` | 27 (по одному на каждый корень/правило: хуй, хуйня, охуеть, пиздец, распиздяй, заебали, ебать, ёбаный, долбоеб, съебался, въебать, блядь, блять, бля, мудак, мудила, пидорас, пидр, залупа, гандон, гондон, херня, похер, сука, сучка, blyat, pizdec) | 27 passed |
| регистр | `::test_case_is_ignored` | 8 (`хуй, ХУЙ, ХуЙ, хУй, БЛЯДЬ, БлЯтЬ, МуДаК, СУКА`) | 8 passed |
| разделители | `::test_separators_inside_word_are_ignored` | 10 (`х у й`, `Х У Й`, `х.у.й`, `х-у-й`, `х_у_й`, `б л я д ь`, `бл я дь`, `с.у.к.а`, `п и з д е ц`, `х у й!`) | 10 passed |
| masking / гомоглифы | `::test_masking_and_homoglyphs_are_detected` | 13 (`х*й, х#й, х@й, бл*дь, бл9дь, п*здец, п3здец, пи3дец, с*ка, 6лядь, xyй, хуууй, бляяяять`) | 13 passed |
| profanity внутри длинного сообщения | `::test_profanity_inside_longer_message` | 1 | 1 passed |
| false positives (обычные слова, похожие подстроки) | `test_false_positives.py::test_ordinary_words_are_not_blocked` | 47 (страховка, сухой, ухудшение, требование, хлеб, себя, тебя, лебедь, ребенок, щебень, дебет, жеребец, небеса, серебро, верба, плебей, стебель, гребень, мудрость, мудрый, команда, гондола, пизанская, поезд, объезд, подъезд, отъезд, изъять, въезд, духи, сукно, сучок, сук, спишите, обед, надоест, херсонес, херес, херувим, Хуан, хутор, хуже, похудеть, неухоженный, блюдо, бляха-муха, суконная …) | 47 passed |
| technical strings | `::test_technical_strings_are_not_blocked` | 30 (URL, www, email, GUID, `case_id=`, hex `0x1F4AB2C9`, `case_version`, `source_ids`, `sourceIds`, стектрейс `File "app.py", line 42`, Traceback, `tenderhack_backend.app:app`, Windows-путь, unix-путь, HTTP 500, `СТЕ-1234567`, 44-ФЗ/223-ФЗ, ИНН, ОКПД2, КБК, ГОСТ, 1С, base64, proxy, oxygen, «Подтема запроса: …», `snapshot_id=mock-c0`, SHA-256, 3D) | 30 passed |
| жалобы без мата | `::test_complaints_without_profanity_are_not_blocked` | 11 | 11 passed |
| substring-граница | `::test_substring_alone_never_matches`, `::test_empty_and_whitespace_are_clean` | 2 (по 5 и 6 строк внутри) | 2 passed |
| human request positive | `test_human_request.py::test_explicit_human_request_is_detected` | 17 | 17 passed |
| ambiguous human request negative | `::test_ambiguous_phrases_do_not_confirm_handoff` | 24 | 24 passed |
| human request: предложения и подавители | `::test_request_in_second_sentence_is_detected`, `::test_howto_question_does_not_suppress_real_request_in_other_sentence` | 2 | 2 passed |
| policy priority | `test_priority_and_port.py::test_profanity_wins_over_human_request`, `::test_profanity_short_circuits_human_rules` | 5 | 5 passed |
| reason codes из enum, notice | `::test_reason_codes_come_from_enum`, `::test_closure_notice_matches_specification` | 2 | 2 passed |
| PolicyPort-совместимость | `::test_signature_matches_policy_port_and_fake`, `::test_check_is_synchronous`, `::test_returns_real_contract_policy_result`, `::test_drop_in_replacement_for_fake_policy` | 4 | 4 passed |
| детерминизм / неизменность входа | `::test_is_deterministic_and_does_not_mutate_input`, `::test_independent_instances_agree`, `::test_matched_rule_ids_are_stable_strings` | 3 | 3 passed |
| 0 model calls (структурно + поведенчески) | `test_no_model_calls.py` (все) | 14 | 14 passed |
| **Итого** | | **221** | **221 passed, 0 failed** |

## Commands and actual outputs

```
$ git rev-parse --show-toplevel
/Users/gunter/Desktop/tender-hack

$ git status --porcelain            # до начала работы
(пусто)

$ git fetch origin --prune
From https://github.com/murmyauuu/tender-hack
 * [new branch]      task/b00-user-flow-plan -> origin/task/b00-user-flow-plan

$ git rev-parse bootstrap-contracts-v2^{commit}
27d45b1675cc884350e6b06aba431d5d867fb76c        # = BASE_SHA, подтверждено

$ git rev-parse origin/main
ab2c182b45cfd9040f0d62a30574970083c15967        # origin/main отстаёт, синка НЕ делалась

$ git worktree add -b task/c01 /Users/gunter/Desktop/tenderhack-c01 27d45b167...
Preparing worktree (new branch 'task/c01')
HEAD is now at 27d45b1 docs(bootstrap): Record A00 machine and input inventory

$ uv sync
... 23 packages installed (fastapi, pydantic, uvicorn, pytest, httpx + транзитивные)
    Новых зависимостей для C01 НЕ добавлялось.
```

### Тесты C01 — фактический вывод

```
$ uv run pytest knowledge/policy/tests
........................................................................ [ 97%]
.....                                                                    [100%]
221 passed in 0.17s

$ uv run pytest knowledge/policy/tests/test_profanity_positive.py
59 passed in 0.02s
$ uv run pytest knowledge/policy/tests/test_false_positives.py
91 passed in 0.03s
$ uv run pytest knowledge/policy/tests/test_human_request.py
43 passed in 0.02s
$ uv run pytest knowledge/policy/tests/test_priority_and_port.py
14 passed in 0.01s
$ uv run pytest knowledge/policy/tests/test_no_model_calls.py
14 passed in 0.11s
```

### Регресс A00 — фактический вывод

```
$ uv run pytest
............................                                             [100%]
28 passed in 0.42s
```

**Ловушка подтверждена фактически:** общий прогон собрал 28 тестов (только `testpaths = ["tests"]`),
221 тест policy в него **не вошёл**. `pyproject.toml` не редактировался. Запуск C01 выполняется явным
путём: `uv run pytest knowledge/policy/tests -q`. Включение пути в общий прогон запрошено
в **CR-EDUARD-001**.

### Доказательство 0 model calls — фактический вывод

```
$ grep -rnE "import (torch|transformers|sentence_transformers|numpy|openai|anthropic|httpx|requests|aiohttp|socket|urllib|subprocess|qdrant_client|faiss|ollama|llama_cpp)|from (torch|transformers|...)|\.embed|embeddings?\(|urlopen|http://|https://|requests\.|client\.|await " knowledge/policy --include='*.py' | grep -v '/tests/'
(no matches — exit 1)

$ grep -rn "^\s*\(import\|from\)" knowledge/policy/*.py
knowledge/policy/__init__.py:11:from .human_request import HumanRequestMatcher
knowledge/policy/__init__.py:12:from .normalization import Normalizer
knowledge/policy/__init__.py:13:from .profanity import ProfanityMatcher
knowledge/policy/__init__.py:14:from .service import (
knowledge/policy/human_request.py:12:import re
knowledge/policy/human_request.py:13:from dataclasses import dataclass
knowledge/policy/normalization.py:14:import re
knowledge/policy/normalization.py:15:import unicodedata
knowledge/policy/normalization.py:16:from dataclasses import dataclass
knowledge/policy/profanity.py:11:import re
knowledge/policy/profanity.py:12:from dataclasses import dataclass
knowledge/policy/profanity.py:14:from .normalization import SENTINEL, MatchCandidate
knowledge/policy/service.py:14:import json
knowledge/policy/service.py:15:from pathlib import Path
knowledge/policy/service.py:17:from tenderhack_contracts import PolicyResult, ReasonCode
knowledge/policy/service.py:19:from .human_request import HumanRequestMatcher
knowledge/policy/service.py:20:from .normalization import Normalizer
knowledge/policy/service.py:21:from .profanity import ProfanityMatcher
(плюс `from __future__ import annotations` в каждом модуле)

$ grep -rn "async \|await " knowledge/policy/*.py
(none)

$ uv run python -c "import sys; import knowledge.policy; print('socket' in sys.modules)"
False
```

Итог: вся внешняя поверхность модуля — `re`, `unicodedata`, `json`, `pathlib`, `dataclasses` (stdlib) и
`tenderhack_contracts` (DTO контракта). Ни LLM, ни embeddings, ни retrieval, ни HTTP-клиента, ни
`subprocess`, ни `socket`. Ровно **0 model calls** и 0 сетевых вызовов.

Три независимых проверки в `test_no_model_calls.py`:
1. `test_only_stdlib_and_contracts_imported` — AST каждого файла, allowlist импортов из 9 имён + denylist из 24 запрещённых модулей.
2. `test_no_forbidden_call_names` — AST-скан всех `Name`/`Attribute` на `embed`, `encode_query`, `generate`, `retrieve`, `urlopen`, `Popen`, `system`.
3. `test_check_works_with_network_layer_disabled` — поведенческий: `socket.socket`, `socket.create_connection`, `socket.getaddrinfo` подменяются на падающие заглушки, после чего 7 сообщений успешно проходят `check()`. Любой сетевой вызов упал бы здесь.

`ipaddress`/`_socket` в `sys.modules` после импорта появляются из **pydantic** (через
`tenderhack_contracts`), а не из policy; модуль верхнего уровня `socket` не импортируется вообще —
подтверждено выводом `False` выше и тестом `test_socket_is_pulled_by_pydantic_not_by_policy`.

### Демонстрация работы (фактический вывод)

```
$ uv run python -c "..."
'Здравствуйте, как создать оферту?'   -> profanity=False human=False rules=[] codes=[]
'Соедините меня с оператором'         -> profanity=False human=True  rules=['POL.HUMAN.TRANSFER_REQUEST'] codes=['EXPLICIT_HUMAN_REQUEST']
'Да это же полный п*здец'             -> profanity=True  human=False rules=['POL.PROF.PIZD'] codes=['POLICY_LANGUAGE']
ruleset_version = c01.1
```

## Data mode

**real** в части кода и тестов: модуль, ruleset и 221 кейс — фактически исполняемый код, все результаты
получены реальным прогоном на машине M. Тестовый корпус — **написанный вручную набор кейсов C01**, не
выборка из реальной истории обращений: он покрывает категории задания (мат, регистр, разделители,
маскировка, benign, технические строки, human request, неоднозначность, приоритет), но **не является**
измерением precision/recall на реальных данных. Реальная история (24 960 строк, C00) в C01 не
использовалась — по карточке C01 KB и история не входят во входы. Прогон policy по реальной истории и
измерение FP-rate — задача оценки (D01/D02), не C01. Синтетических «PASS» вместо реальных прогонов нет.

## Artifacts and paths

| Артефакт | Путь |
|---|---|
| Policy-модуль | `knowledge/policy/` (5 модулей, 653 строки) |
| Ruleset (данные) | `config/knowledge/policy_rules.json` (197 строк, `ruleset_version = c01.1`) |
| Тесты | `knowledge/policy/tests/` (5 файлов, 221 кейс) |
| CR к A | `docs/coordination/eduard/CR-EDUARD-001-knowledge-package-and-testpaths.md` |
| Handoff | `docs/coordination/eduard/C01-handoff.md` |

Бинарных артефактов, весов и индексов нет — передавать по хешам нечего.

## Blockers and reproducible defects

| # | Blocker / дефект | Воспроизведение | Влияние | Кому |
|---|---|---|---|---|
| BL-C01-1 | `knowledge` не входит в `[tool.setuptools.packages.find]`, поэтому импортируется только когда cwd = корень репозитория | `cd /tmp && uv run --project <repo> python -c "import knowledge.policy"` → `ModuleNotFoundError: No module named 'knowledge'` | A02 не сможет подставить policy при запуске backend из произвольного каталога | **A**, CR-EDUARD-001 |
| BL-C01-2 | `testpaths = ["tests"]` — 221 тест policy не входит в общий прогон | `uv run pytest` → `28 passed` (не 249) | регрессии policy не видны общему CI | **A**, CR-EDUARD-001 |
| BL-C01-3 | Полная транслитерация (`ne rabotaet nihuya`, `pizdec` внутри фразы латиницей) покрыта только точным списком токенов `POL.PROF.TRANSLIT`, произвольные латинские формы не ловятся | `check("nu i piiizdec")` → `profanity=False` | осознанное ограничение: гомоглифы применяются только к словам с кириллицей, иначе английские слова и идентификаторы давали бы FP | C07 при реальном дефекте |
| BL-C01-4 | Нет реального измерения FP-rate на исторических обращениях | — | покрытие словаря оценено только на 91 benign-кейсе C01 | D01/D02, C07 |

Воспроизводимых дефектов в чужих модулях не найдено. A00 после моих изменений проходит без ошибок.

## CR

- **CR-EDUARD-001** — `docs/coordination/eduard/CR-EDUARD-001-knowledge-package-and-testpaths.md`, статус **pending**.
  Касается `pyproject.toml` (зона A), **не** `contracts/**`. Два пункта: сделать `knowledge` импортируемым
  пакетом и добавить `knowledge/policy/tests` в `testpaths`. C01 сдан по действующему контракту, CR не блокирует.
- **Contracts не менялись.** Замечание без CR: в `PolicyResult` нет поля `reason_codes`, хотя §9 связывает
  policy с `POLICY_LANGUAGE`/`EXPLICIT_HUMAN_REQUEST`. Изменение контракта **не требуется** — отображение
  сделано функцией `reason_codes_for()` на значениях enum `ReasonCode`. Если A решит добавить поле
  `reason_codes: list[ReasonCode]` в `PolicyResult`, C01 совместим: значения готовы, нужен только перенос
  в DTO. Инициатором изменения контракта остаётся A.

## Inputs needed by next task

### Точка интеграции для A02 — как подставить модуль вместо `FakePolicy`

```python
# backend: вместо FakePolicy
from knowledge.policy import build_policy, reason_codes_for

policy = build_policy()                  # -> DeterministicPolicy, реализует PolicyPort
result = policy.check(user_text)         # СИНХРОННЫЙ вызов, НЕ await
# result: tenderhack_contracts.PolicyResult(profanity, explicit_human_request, matched_rule_ids)

if result.profanity:
    # §9: 0 routing, 0 embedding, 0 retrieval, 0 generation
    # status -> TicketStatus.CLOSED_POLICY, notice -> POLICY_CLOSURE_NOTICE
    # reason code -> ReasonCode.POLICY_LANGUAGE (через reason_codes_for(result))
    ...
elif result.explicit_human_request:
    # handoff offered, reason code -> ReasonCode.EXPLICIT_HUMAN_REQUEST
    ...
```

| Что | Значение |
|---|---|
| Пакет | `knowledge.policy` |
| Фабрика | `build_policy(rules_path: str \| Path \| None = None) -> DeterministicPolicy` |
| Класс | `knowledge.policy.DeterministicPolicy` |
| Метод порта | `def check(self, text: str) -> PolicyResult` — **синхронный**, сигнатура идентична `PolicyPort.check` и `FakePolicy.check` |
| Конструктор | `DeterministicPolicy(ruleset: dict \| None = None)` — без аргументов читает `config/knowledge/policy_rules.json` |
| Reason codes | `reason_codes_for(result) -> list[ReasonCode]` (значения enum, не строки) |
| Notice | `knowledge.policy.POLICY_CLOSURE_NOTICE` (дословно из `contracts/fixtures/policy.json`) |
| Версия ruleset | `policy.ruleset_version` → `"c01.1"` (логировать вместе с trace_id) |
| Стоимость | чистый Python/stdlib; инстанс создаётся один раз, потокобезопасен на чтение (внутреннего состояния между вызовами нет) |
| Новые зависимости | нет |

Что требуется от A02:
1. Применить **CR-EDUARD-001** (или запускать backend из корня репозитория как временный обходной путь).
2. Вызывать `check()` **до** routing/retrieval/generation — приоритет profanity заложен внутри модуля, но порядок в оркестраторе определяет A.
3. Взять `matched_rule_ids` в trace/лог как есть: id стабильны, порядок детерминирован (порядок правил в ruleset).
4. Не оборачивать `check()` в `await` и не делать его async — контракт синхронный.
5. Notice и `closed_policy` формирует A: policy-модуль сам сообщения пользователю не пишет.

### Для C04 (маршрутизация)

`explicit_human_request=True` — сигнал handoff, но **не** маршрут: `support_line`, `topic_id`,
`recommended_recipient` policy не определяет. Справочника линий/адресатов по-прежнему нет (BL-C00-2).

### Для C02

C01 от C02 не зависит и ничего от него не требует. `knowledge/policy/` и
`config/knowledge/policy_rules.json` — файлы C01; при добавлении `knowledge/kb/` конфликтов не будет.

## Остановка

C01 завершён. C02 в этом чате не начинался — для него создаётся отдельный новый чат.
