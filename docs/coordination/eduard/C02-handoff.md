# C02 — handoff

- **Task ID / status:** C02 — Нормализация KB и source lookup / **done**
- **Owner / tool:** Эдуард / агент C / Claude Code
- **Base SHA:** `27d45b1675cc884350e6b06aba431d5d867fb76c` (тег `bootstrap-contracts-v2`)
- **Result SHA:** `39b29f65cf156e7521e0680f95a063bd4b21a694`
- **Ветка / worktree:** `task/c02` / `/Users/gunter/Desktop/tenderhack-c02` (отдельный, worktree C00 и C01 не тронуты)
- **Contracts version:** `2.0.0-c0`, контракты не изменялись
- **Machine:** M — MacBook Air M2 (arm64), 8 GiB RAM, macOS 14.4.1, без GPU. Python 3.13.12, uv 0.11.27.
  Свободно на диске **62 GiB** (замер `df -h .` в ходе задачи) — блокер BL-C00-3 в части места **неактуален**.
- **KB snapshot:** `kb-4918a97f0874d1e8`

`origin/main` (ab2c182) сознательно не использовался как база: контрактов там ещё нет.
Синхронизации с `origin/main` не выполнялось, `git fetch origin --prune` выполнен, незакоммиченных
изменений не было и не уничтожалось.

---

## 1. Changed files

Только зона C (`knowledge/**`, `config/knowledge/**`, `docs/coordination/eduard/**`):

| Файл | Назначение |
|---|---|
| `knowledge/kb/__init__.py` | пакет C02 |
| `knowledge/kb/pdf_text.py` | извлечение текстового слоя PDF, только stdlib (zlib + свой парсер) |
| `knowledge/kb/normalize.py` | `clean_text`, `rebuild_title`, русская нормализация для FTS |
| `knowledge/kb/classify.py` | служебные fragments, pointer/incomplete, роли |
| `knowledge/kb/schema.py` | DDL read-only снимка |
| `knowledge/kb/ingest.py` | воспроизводимый ingest, parent links, manifest |
| `knowledge/kb/store.py` | `SqliteKnowledgeStore` — доступная часть KnowledgePort |
| `knowledge/kb/tests/conftest.py` + 4 тестовых модуля | 73 теста |
| `config/knowledge/normalizer.json` | конфигурация нормализации |
| `docs/coordination/eduard/C02-handoff.md` | этот файл |

Чужого не трогал: `pyproject.toml`, `contracts/**`, `backend/**`, `tools/**`, `tests/**`,
`docs/integration/**` — без изменений. Зона C01 (`knowledge/policy/**`,
`config/knowledge/policy_rules.json`) не создавалась и не перезаписывалась; логика policy
не менялась и не вызывалась. Зона C00 (`knowledge/audit/**`) не изменялась. raw-входы неизменны
(только чтение). Артефакты сборки в Git не коммитились — `.gitignore:14 var/` это подтверждает.

---

## 2. Implemented behavior

Ingest, нормализация, parent links и source lookup по разделу 10 спецификации v2.1.

1. **Входы и хеши зафиксированы** фактическим замером; counts взяты из файла, а не из `api_report.json`.
2. **Служебные fragments удалены с причиной** (44), короткие полезные записи сохранены (57 из 57).
3. **Parent/части восстановлены:** портал — по `article_id`; PDF — секции из оглавления самого
   документа; near-duplicates не схлопнуты.
4. **`audience_raw` сохранён**, `instruction` ролью не считается, `general`/пусто ≠ «все роли».
5. **pointer/incomplete/missing attachment помечены** с `eligibility_reason`.
6. **Даты и URL не выдуманы:** `updated_at → collected_at`, `source_url → collection_endpoint`,
   в DTO `url`/`source_date` = `None`.
7. **Регламент загружен** отдельным `source_type` (103 чанка, 82 секции) — закрывает BL-C00-1.
   Дочитана пропущенная стр. 3 «Инструкции по электронному актированию».
8. **`title` пересобран** там, где он не был заголовком (35 записей).
9. **Trusted-состав:** Регламент, официальные инструкции, KB snapshot. История, operator reply
   и feedback в снимок **не попадают** — в ingest нет ни одного пути к `Выгрузка СТП за 2026.xlsx`.
10. **Единая русская FTS-нормализация** — словоформы сведены.

Порт: `get_source` / `health` / `get_card` реализованы; `retrieve` намеренно не реализован.

---

## 3. Counts

Все числа — фактический замер, воспроизводятся `python3 -m knowledge.kb.ingest`.

| Показатель | Значение | Сверка |
|---|---|---|
| raw | **1468** | = C00; `api_report.json` (1468) совпадает только здесь |
| included | **1528** | 527 portal + 898 organizer_pdf + 103 reglament |
| excluded | **44** | 43 из снимка + 1 дочитанная пустая страница |
| articles (портал) | **480** | = C00; `api_report.json` заявлял 483 — **не используется** |
| parents | **636** | 480 портал + 74 PDF-секции + 82 секции Регламента |

**Исходный снимок:** 941 organizer_pdf + 527 portal = 1468 — совпадает с C00 и с `summary.txt`;
`api_report.json` (530/483/944) расходится и как источник counts **отвергнут** (BL-C00-7).

### Что именно удалено и почему

| Причина | Записей | Обоснование |
|---|---|---|
| `content_is_table_of_contents` | 27 | строка/страница оглавления с точками-лидерами (≥4 точки) |
| `content_is_page_number_only` | 17 | `content` — только номер страницы (16 из снимка + 1 дочитанная стр. 3) |
| **Итого** | **44** | все сохранены в таблице `excluded` вместе с причиной и исходным текстом |

Порог по длине единственным критерием **не является**: 57 коротких портальных записей (<200
символов) сохранены полностью, ни одна портальная запись не удалена (527 → 527).
Строка «и т.д.» содержанием оглавления не считается — критерий ≥4 точек, а не ≥3
(при ≥3 в мусор попали бы 8 содержательных записей; проверено и покрыто тестом).

Отдельно снято **799 строк** повторяющегося колонтитула КонсультантПлюс в Регламенте
(«Документ предоставлен КонсультантПлюс», «Страница N», «www.consultant.ru» и т. п.).

### Уточнение к C00 (два расхождения, оба в пользу C02)

1. **44 = 43.** C00 получил 44 сложением классов 17 + 27. Фактически один и тот же чанк входит в
   оба класса: `title` — строка оглавления `10.3. Страница контракта .....`, а `content` — `"3"`.
   Объединение классов = **43**, а не 44. Итоговые 44 в снимке C02 набираются иначе:
   43 из снимка + 1 дочитанная пустая страница.
2. **Стр. 3 «электронного актирования» не потеряна — она пустая.** Страница дочитана из PDF
   фактически: текстового слоя сверх номера страницы нет, встроенных изображений на ней **0**.
   То есть исходный ingest пропустил не содержание, а пустую страницу. Запись заведена,
   проведена через пайплайн и исключена с причиной; содержание не выдумывалось. D9 закрыт
   как объяснённый, а не как потеря данных.

### Полнота и роли

| Показатель | Значение |
|---|---|
| `content_status = complete` | 713 |
| `content_status = incomplete` (missing attachment) | **777** (C00/D6: 776 + 1 из Регламента) |
| `content_status = pointer` | 38 |
| `role_verified = true` | 1182 |
| `applicable_roles = []` (instruction/general) | остальные, `role_verified = false` |
| `titles_rebuilt` | 35 |

---

## 4. Manifest (целиком)

Файл: `var/knowledge/manifest.json` (вне Git).

```json
{
  "adapter_version": null,
  "counts": {
    "articles": 480,
    "by_source_type": {"organizer_pdf": 898, "portal_kb": 527, "reglament": 103},
    "cards_reviewed": 0,
    "content_status": {"complete": 713, "incomplete": 777, "pointer": 38},
    "excluded": 44,
    "excluded_by_reason": {"content_is_page_number_only": 17, "content_is_table_of_contents": 27},
    "included": 1528,
    "parents": 636,
    "raw": 1468,
    "role_verified": 1182,
    "titles_rebuilt": 35
  },
  "created_at": null,
  "created_at_note": "null by design: снимок детерминирован, часы в артефакт не попадают",
  "embedding_dim": null,
  "embedding_model": null,
  "embedding_revision": null,
  "index_type": null,
  "embedding_note": "C02 embeddings не строит: 0 model calls, 0 сетевых вызовов. Поля заполняются null явно. Контракт для C03: смена embedding adapter, весов или revision требует ПОЛНОЙ пересборки снимка — index_type из config/runtime/c0.json (numpy_exact_cosine) на момент C02 имеет status=not_built.",
  "files": [
    {"path": "var/knowledge/knowledge.sqlite",
     "sha256": "6d1555777d9bbf9ae7f2df93a69cf61f53dd04263877a8ebaf7fc35e16a4bdf8",
     "size_bytes": 10895360}
  ],
  "input_files": [
    {"name": "TenderHack_KnowledgeBase/knowledge_base_FINAL.jsonl",
     "sha256": "71bf714a9e205a35f5d8ec0fd2d0f9bbd4ad3a8409968b754eb8de7b349d79ae"},
    {"name": "Регламент_информационного_взаимодействия-4.pdf",
     "sha256": "ef09670556196f6acf00d78e4e3aefe688665cecbf1fd8622afaa5fb488b707b"},
    {"name": "НН 2026/Инструкция по работе с Порталом для заказчика.pdf",
     "sha256": "7355b2c39b4aa4fbac758f64aeab0bdfd4a8219cc483dd5ca52e28eacb59fcde"},
    {"name": "НН 2026/Инструкция по электронному актированию.pdf",
     "sha256": "d14f883b14f8f117842541900300901404b37d43cdddf13c3e3266cfbd9155b3"},
    {"name": "НН 2026/Инструкция по работе с машиночитаемыми доверенностями.pdf",
     "sha256": "755870a7454fd166146bfd64a7c50009fc834340798d28ff9cee3132265272b9"},
    {"name": "НН 2026/Инструкция по созданию оферты и СТЕ.pdf",
     "sha256": "ce50227cb1bb29b9145dd0fb52181c353c03bb11e00a0ab467cf544914b20159"},
    {"name": "НН 2026/Инструкция по работе с Порталом для поставщика.pdf",
     "sha256": "3c52c3633b6bc84e99ca1a23336536e9408ba83b28f160ee5c02738a2f754c6b"},
    {"name": "НН 2026/Инструкция по формированию YML.pdf",
     "sha256": "753fc58d5c7ae3b15932ef658d88f4eb2886273af2e3067389c5aa0934bd9a9c"}
  ],
  "normalizer_version": "c02-normalizer-1.0.0",
  "removed_boilerplate_lines": 799,
  "schema_version": "c02-schema-1.0.0",
  "snapshot_id": "kb-4918a97f0874d1e8"
}
```

`embedding_model` / `embedding_revision` / `embedding_dim` / `adapter_version` / `index_type`
заполнены `null` **явно**: C02 embeddings не строит. `created_at` тоже `null` намеренно — иначе
два прогона разошлись бы по хешу, а приёмка требует одинаковых артефактов.

---

## 5. Артефакты

| Артефакт | Путь | SHA-256 | Размер |
|---|---|---|---|
| CPU snapshot KB | `var/knowledge/knowledge.sqlite` | `6d1555777d9bbf9ae7f2df93a69cf61f53dd04263877a8ebaf7fc35e16a4bdf8` | 10 895 360 B |
| Manifest | `var/knowledge/manifest.json` | `e0d01a74dcfe43f8a562a10837793fa04a052e775e60877115dce7785f24d061` | 3 195 B |

Вне Git по AGENTS.md («var, artifacts, веса и индексы — локальные результаты вне Git»);
`.gitignore:14 var/` проверено. Снимок пересобирается одной командой за ~4 с.

---

## 6. Commands and actual outputs

### Git-контекст

```
git rev-parse bootstrap-contracts-v2^{commit} -> 27d45b1675cc884350e6b06aba431d5d867fb76c
git status --porcelain                        -> (пусто)
git fetch origin --prune                      -> ok
git worktree add -b task/c02 /Users/gunter/Desktop/tenderhack-c02 27d45b1
                                              -> HEAD is now at 27d45b1
df -h .  -> /dev/disk3s5 228Gi, занято 132Gi, свободно 62Gi, 69 %
```

### Ingest (воспроизводимая команда)

```
$ python3 -m knowledge.kb.ingest --out var/knowledge
real 4.2s
snapshot_id kb-4918a97f0874d1e8, raw 1468, included 1528, excluded 44, articles 480
```

### Приёмка: два прогона дают одинаковые ID и хеши

```
$ python3 -m knowledge.kb.ingest --out $S/d1 && python3 -m knowledge.kb.ingest --out $S/d2
6d1555777d9bbf9ae7f2df93a69cf61f53dd04263877a8ebaf7fc35e16a4bdf8  $S/d1/knowledge.sqlite
6d1555777d9bbf9ae7f2df93a69cf61f53dd04263877a8ebaf7fc35e16a4bdf8  $S/d2/knowledge.sqlite
1af7bf9aeaea04726fcece4af9324c002d736bdeb225663fcca6a9482784c912  $S/d1/manifest.json
1af7bf9aeaea04726fcece4af9324c002d736bdeb225663fcca6a9482784c912  $S/d2/manifest.json

$ diff <(sqlite3 d1 "select source_id from chunks order by 1") \
       <(sqlite3 d2 "select source_id from chunks order by 1")
-> (пусто) SOURCE_IDs IDENTICAL across runs
```

### Source фактически открывается

```
$ python3 -c "... open_store().get_source('reglament:s012:c01')"
{
  "source_id": "reglament:s012:c01",
  "source_type": "reglament",
  "title": "Приложение 2",
  "excerpt": "к Регламенту информационного взаимодействия с использованием автоматизированной
              информационной системы \"Портал поставщиков\" Соглашение об использовании …",
  "version": "ред. от 10.06.2025",
  "source_date": null,
  "section_path": "Приложение 2",
  "page_from": 20, "page_to": 20,
  "url": null, "file_url": null,
  "conditions": [], "applicable_roles": [],
  "content_status": "complete"
}

get_source('portal:225874:1') -> title '"Ошибка формата" при загрузке прайс-листа',
                                 applicable_roles ['supplier'], url null, source_date null
get_source('no-such-source')  -> None
get_card('any')               -> None
health()                      -> available=True, mode='lexical_only',
                                 snapshot_id='kb-4918a97f0874d1e8'
retrieve(...)                 -> NotImplementedError: «зона C03»
```

### FTS: русская нормализация сводит словоформы (закрывает D12)

```
форма         C00 unicode61      C02 ключ  C02 hits
контракт                110      контракт       474
контракта               351      контракт       474
контракту                61      контракт       474
оферта                   42         оферт       290
оферты                  183         оферт       290
```

Пять разных ключей дефолтного `unicode61` сведены к двум. Английский Porter не применяется:
`fts_normalize("running") == "running"`. Аббревиатуры и коды не стеммируются: `ИНН → инн`
(а не `ин`), `СТЕ УПД КЭП`, `YML-12` сохраняются — exact ID выделяются до морфологии.

### 0 model calls и 0 сетевых вызовов — проверкой, не декларацией

```
$ python3 - <<AST  # полный разбор импортов всех модулей knowledge/kb
classify.py      ['__future__', 're']
ingest.py        ['__future__','argparse','dataclasses','hashlib','json','os','re','sqlite3','sys']
normalize.py     ['__future__', 're', 'unicodedata']
pdf_text.py      ['__future__', 'dataclasses', 're', 'zlib']
schema.py        ['__future__']
store.py         ['__future__', 'contracts', 'json', 'os', 'sqlite3', 'typing']
ОБЪЕДИНЕНИЕ: ['__future__','argparse','contracts','dataclasses','hashlib','json','os','re',
              'sqlite3','sys','typing','unicodedata','zlib']
ЗАПРЕЩЁННЫЕ НАЙДЕНЫ: НЕТ — 0 model calls, 0 network

$ grep -rnE 'import (torch|transformers|requests|httpx|aiohttp|socket|urllib)|from_pretrained|urlopen|https?://[a-z]' knowledge/kb/*.py
-> совпадений нет
```

Дополнительно тест `test_ingest_runs_with_the_network_disabled` подменяет `socket.socket`,
`socket.create_connection` и `socket.getaddrinfo` на исключение и **собирает снимок целиком** —
проходит. `backend` не импортируется ни в одном модуле (критерий A00 не сломан).

### Тесты

```
$ uv run pytest knowledge/kb/tests
73 passed in 17.07s

$ uv run pytest            # набор A00
28 passed in 0.27s
```

Тесты C01 в этой ветке отсутствуют (C01 — отдельная ветка `task/c01`, ветки не объединены),
поэтому не запускались.

---

## 7. Матрица тестов

| Категория | Кейсы | Результат |
|---|---|---|
| Фиксация входов и хешей | манифест vs фактические файлы; хеш = git blob; хеш ≠ A00; CRLF воспроизводит A00; raw=1468; counts = C00; embedding-поля null; files с path/sha | 8 passed |
| Служебные fragments | у каждой исключённой есть причина; классы = C00 (27/17); номер страницы; оглавление; «и т.д.» не оглавление | 5 passed |
| Короткие полезные записи | 57 коротких портальных сохранены; 527 → 527 | 1 passed |
| Заголовки | имя файла не заголовок; причина пересборки записана; точки-лидеры убраны | 3 passed |
| audience / роли | `audience_raw` сохранён; instruction не роль; general/пусто не «все роли»; реальные роли verified | 4 passed |
| pointer / incomplete / attachment | incomplete ≥700; pointer помечен и не повышен; у каждой не-complete есть причина | 3 passed |
| Нет выдуманных URL/дат | endpoint не выдаётся за статью; collected_at — одна константа; в схеме нет url/source_date | 3 passed |
| Parent портала | parent по article_id (480); 36 многочанковых; нет сирот | 3 passed |
| PDF: страницы и секции | ни один чанк не пересекает страницу; секции из оглавления, иерархичны; неизвестная секция = NULL; страницы Регламента ≤57 | 4 passed |
| Near-duplicates | повторяющиеся заголовки не схлопнуты; source_id уникальны; 0 точных дублей content | 2 passed |
| Стабильность ID | два прогона: одинаковые ID и одинаковый SHA-256; ID выводятся из стабильных ключей | 2 passed |
| get_source / порт | реальный SourceRecord; url/date = None; None для неизвестного; Регламент открывается; health lexical_only; health unavailable без снимка; get_card None; retrieve не имитирует поиск; снимок read-only | 9 passed |
| FTS-нормализация | 3 группы словоформ сведены; аббревиатуры не стеммируются; не английский Porter; поиск находит другую словоформу; идемпотентность | 7 passed |
| 0 model calls | импорты всех модулей (AST); запрещённые вызовы; backend не импортируется; ingest при заблокированном сокете; нет весов/индекса; нет колонки embedding | 19 passed |
| **Итого** | | **73 passed** |

---

## 8. Data mode

**real** во всей части, которая сдана. Fixture за real не выдавалось.

| Часть | Режим | Где |
|---|---|---|
| Портальные записи (527) | **real** | локальный снимок `knowledge_base_FINAL.jsonl`, из сети ничего не запрашивалось |
| PDF-инструкции (898) | **real** | текстовый слой 6 PDF, счётчики страниц совпали с C00 |
| Регламент (103) | **real** | извлечён из `Регламент_информационного_взаимодействия-4.pdf`, 57 стр., 0 нерасшифрованных глифов |
| Карточки сценариев | **отсутствуют** | `content/cards` содержит только README; `get_card` → `None`. Это зафиксированное ограничение, а не заглушка |
| `retrieve` / dense | **не реализовано** | зона C03; поднимает `NotImplementedError`, поиск не имитируется |
| Даты актуальности, URL статьи, роли для instruction/general | **unknown** | оставлены `null`, причина записана |

Mock-данных в снимке нет.

---

## 9. Blockers

### Статус блокеров C00

| # | Блокер | Статус |
|---|---|---|
| BL-C00-1 | Регламент не загружен в KB (0 чанков) | **закрыт.** 103 чанка, 82 секции, стр. 1–57, `source_type='reglament'`, приоритет по §10 обеспечен отдельным типом. OCR не потребовался |
| BL-C00-3 | На M свободно 2.8 GiB | **закрыт в части места:** фактически 62 GiB. Часть «нет torch и весов» остаётся открытой и **передаётся C03** — для C02 она нерелевантна |
| BL-C00-5 | `source_url` = endpoint API, `updated_at` = константа | **закрыт в снимке:** поля переименованы в `collection_endpoint` / `collected_at`; в DTO `url` и `source_date` = `None`. Как дефект входных данных **остаётся открытым и передаётся A**: per-article URL и дата актуальности в снимке отсутствуют физически |
| BL-C00-6 | 776 чанков ссылаются на отсутствующие рисунки | **передан C03 помеченным:** 777 чанков `content_status='incomplete'` с `eligibility_reason` = `MISSING_ATTACHMENT: …`. Снять его C02 не может — изображений в снимке нет; gate обязан учитывать |
| BL-C00-7 | `api_report.json` расходится с файлом | **закрыт:** counts манифеста взяты из фактического замера (1468/941/527/480). `api_report.json` как источник counts отвергнут |
| BL-C00-2, BL-C00-4, BL-C00-8 | линии/адресаты, Qdrant, правила хакатона | вне C02, статус не менялся |

### Новый дефект: `docs/integration/input_manifest.sha256` (файл A) не проходит проверку

**BL-C02-1, владелец A, severity: средняя (не блокирует C02).**

Воспроизведение на M:

```
$ shasum -a 256 -c docs/integration/input_manifest.sha256
TenderHack_KnowledgeBase/api_report.json: FAILED
TenderHack_KnowledgeBase/knowledge_base_FINAL.jsonl: FAILED
TenderHack_KnowledgeBase/TenderHack_KnowledgeBase_summary.txt: FAILED
shasum: WARNING: 3 computed checksums did NOT match
```

11 бинарных входов (PDF/XLSX/PPTX) — **OK**. Падают ровно 3 текстовых файла.

**Причина установлена точно, а не предположена:** манифест A зафиксировал хеш CRLF-версии.
Побайтовое повторное CRLF-преобразование рабочего файла воспроизводит хеш A00 **для всех трёх**:

| Файл | Факт (LF, = git blob) | A00 манифест | `LF→CRLF` от факта |
|---|---|---|---|
| `knowledge_base_FINAL.jsonl` | `71bf714a…d79ae` | `439e7041…8df2c` | `439e7041…8df2c` ✔ |
| `TenderHack_KnowledgeBase_summary.txt` | `413f922d…32312` | `54d69db8…be5096` | `54d69db8…be5096` ✔ |
| `api_report.json` | `74b1ca3f…d31050` | `a94d1125…b802c` | `a94d1125…b802c` ✔ |

В рабочем дереве `\r\n` отсутствует (проверено), `git show HEAD:<file>` даёт тот же хеш, что и
рабочее дерево. C00 независимо наблюдал то же самое: `api_report.json` в архиве CRLF, в
репозитории LF.

**В снимке C02 используется фактический хеш git blob, а не значение из A00.**
`docs/integration/**` не правился — это зона A. Покрыто тестами
`test_kb_snapshot_hash_equals_git_blob` и `test_a00_manifest_hash_is_reproduced_by_crlf_conversion`.

Рекомендация A (не блокирует C02): добавить `.gitattributes` с `* text=auto eol=lf` для
текстовых входов и пересчитать манифест на LF. Отдельный CR не заводил — дефект передаётся
владельцу по правилу AGENTS.md «воспроизводимый дефект передайте владельцу».

### Ограничения C02 (не блокеры)

- 8 из 898 PDF-чанков без `section_path`: страницы идут до первого раздела оглавления. Оставлены
  `NULL` осознанно — неверная секция хуже отсутствующей.
- Собственного outline (`/Outlines`) нет ни в одном PDF (проверено) — секции восстановлены по
  оглавлению самого документа; нумерованные строки тела инструкций это шаги списка, не заголовки.
- 63 из 103 чанков Регламента короче ориентира 220 токенов: секция Регламента часто короче
  ориентира целиком, а граница секции важнее длины (§10: «смысл и условия важнее длины»).

---

## 10. CR

**Новых CR нет.**

Действует уже открытый **CR-EDUARD-001** (`docs/coordination/eduard/`, ветка `task/c01`,
статус pending): `knowledge` не входит в `packages.find` в `pyproject.toml`, поэтому пакет
импортируется только от корня репозитория. Тот же обходной путь применён здесь:

- `knowledge/kb/store.py` импортирует контракты как `contracts.python.tenderhack_contracts.models`;
- `knowledge/kb/tests/conftest.py` добавляет корень репозитория в `sys.path`.

Дубликата CR на ту же тему не создавал. Контракты не менялись: четыре метода `KnowledgePort`
(`retrieve`, `get_source`, `get_card`, `health`) — **async**, реализованы как async;
синхронный `PolicyPort.check` не затронут.

`testpaths = ["tests"]` в `pyproject.toml` (файл A) не правился; тесты C02 лежат в своей зоне и
запускаются явным путём — явный аргумент переопределяет `testpaths`.

---

## 11. Точка интеграции для C03

**Снимок:** `var/knowledge/knowledge.sqlite`, SHA-256
`6d1555777d9bbf9ae7f2df93a69cf61f53dd04263877a8ebaf7fc35e16a4bdf8`, 10 895 360 B,
`snapshot_id = kb-4918a97f0874d1e8`. Пересобирается: `python3 -m knowledge.kb.ingest --out var/knowledge`.

**Схема таблиц**

| Таблица | Назначение | Ключевые поля |
|---|---|---|
| `chunks` | 1528 дочерних единиц — вход embedding | `source_id` PK, `parent_id`, `title`, `text`, `section_path`, `page_from/page_to`, `applicable_roles`, `role_verified`, `content_status`, `eligibility_reason`, `collected_at`, `collection_endpoint`, `ord` |
| `parents` | 636 родителей для parent expansion | `parent_id` PK, `title`, `text`, `child_count`, `page_from/page_to` |
| `excluded` | 44 исключённых с причиной | `original_id` PK, `reason`, `raw_content` |
| `chunks_fts` | FTS5 по нормализованному тексту | `source_id`, `title_norm`, `text_norm` |
| `manifest` | манифест в БД | `key`, `value` (JSON) |

**Что подавать в embedding.** Ровно `chunks`: конкатенацию `title` и `text` — заголовок
включается в embedding по §10 «Поиск». Брать **`title`, а не `raw_title`**: `raw_title` у 35
записей содержал имя файла, версионный штамп или обрезанную строку оглавления, и в embedding
такой заголовок вносит шум (C00/D8). `text` уже приведён `clean_text`. **`text_norm` из
`chunks_fts` в embedding не подавать** — это лексический ключ со снятыми окончаниями, он для FTS,
не для dense.

**Что учесть.**
- Порядок: `ORDER BY ord, source_id` — детерминирован, совпадает между прогонами.
- 777 чанков `content_status='incomplete'` и 38 `pointer` — gate обязан их учитывать
  (BL-C00-6 передан помеченным, не закрытым).
- `role_verified=false` (346 чанков) не означает «все роли».
- `url`/`source_date` в снимке отсутствуют физически; приоритет по свежести на этих данных
  не строится.
- Смена embedding adapter/весов/revision требует **полной пересборки снимка** — зафиксировано
  в `embedding_note` манифеста.
- `config/runtime/c0.json`: `numpy_exact_cosine`, `status=not_built`, `artifact_path
  var/knowledge/index.npy` — индекс строит C03, C02 его не создавал.
- На M нет torch и весов (остаток BL-C00-3); места достаточно — 62 GiB.

## 12. Точка интеграции для A02/A03

```python
from knowledge.kb.store import open_store, SqliteKnowledgeStore

store = open_store()                       # по умолчанию var/knowledge
store = SqliteKnowledgeStore(snapshot_dir) # явный каталог снимка

record = await store.get_source(source_id)  # SourceRecord | None
card   = await store.get_card(card_id)      # всегда None: карточек нет
health = await store.health()               # KnowledgeHealth
```

- Класс: `SqliteKnowledgeStore`; фабрика: `open_store(snapshot_dir=DEFAULT_SNAPSHOT_DIR)`.
- Все четыре метода **async** (в отличие от синхронного `PolicyPort.check`).
- `get_source` → `SourceRecord` с `url=None`, `source_date=None`, `file_url=None` — всегда;
  неизвестный `source_id` → `None`, без исключения.
- `health()` → `mode='lexical_only'` при наличии снимка, `'unavailable'` при его отсутствии
  (это не ошибка, файла может не быть), `snapshot_id` из манифеста.
- `retrieve()` поднимает `NotImplementedError` — **это намеренно**: пустой `KnowledgeResult`
  с полем `decision` выглядел бы как состоявшийся поиск и принятое решение gate. До сдачи C03
  оркестратор обязан трактовать knowledge как `lexical_only` и не вызывать `retrieve`.
- Снимок открывается `mode=ro`: runtime KB read-only, запись из runtime невозможна (покрыто тестом).
- `knowledge` не импортирует `backend` — критерий A00 сохранён.
- Импорт пакета возможен только от корня репозитория (CR-EDUARD-001).

## 13. Остановка

C02 завершён. C03 в этом чате не начинал — для него участник создаёт отдельный новый чат.
