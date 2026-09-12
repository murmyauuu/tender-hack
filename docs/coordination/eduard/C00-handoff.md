# C00 — handoff

- **Task ID / status:** C00 — Аудит реальных входов KB до C0 / **done**
- **Owner / tool:** Эдуард / агент C / Claude Code
- **Base SHA:** `ab2c182b45cfd9040f0d62a30574970083c15967`
- **Result SHA:** см. commit ветки `task/c00-input-audit` (проставляется после commit; фиксируется в финальном сообщении чата)
- **Contracts version:** отсутствует. C0 ещё не заморожен, A00 не принят. Contracts/fixtures/DTO в C00 не читались и не создавались.
- **Machine profile:** M — MacBook Air M2 (arm64), 8 GiB RAM, macOS 14.4.1 (23E224), свободно 2.8 GiB. GPU не использовался.
- **Runtime SHA / KB snapshot:** runtime отсутствует. Аудированный снимок KB — `TenderHack_KnowledgeBase/knowledge_base_FINAL.jsonl`, SHA-256 `71bf714a9e205a35f5d8ec0fd2d0f9bbd4ad3a8409968b754eb8de7b349d79ae`, 1468 чанков. Snapshot_id не присваивался — это работа C02.

## Changed files

Только в зоне C (`knowledge/**`) и собственной папке координации:

- `knowledge/audit/C00_input_audit.md` — audit-документ с реальными путями, counts, хешами и unknown-полями
- `knowledge/audit/audit_inputs.py` — воспроизводимый аудит-скрипт, только stdlib, только чтение
- `knowledge/audit/c00_inventory.json` — машиночитаемый отчёт (15 344 B)
- `docs/coordination/eduard/C00-handoff.md` — этот файл

Чужие файлы не менялись. `docs/integration/input_inventory.md` и `machine_map.md` принадлежат A — фактические значения переданы ниже текстом, сами файлы не трогал. raw-входы не изменялись, KB не пересобиралась, ничего не скачивалось, общих DTO не создавал.

## Implemented behavior

Аудит, не реализация. Открыл и фактически измерил все доступные входы KB/PDF/history/taxonomy; составил inventory с путями, форматами, размерами, SHA-256 и counts; собрал shortlist из 12 дефектов KB; проверил фактическое наличие Qdrant Local/lab-кода и состояние машины M. C01/C02/C03 не начинал.

## Acceptance

Критерии карточки C00 — **passed**:

| Критерий | Результат |
|---|---|
| Личный audit-документ с реальными путями/counts | passed — `knowledge/audit/C00_input_audit.md` + JSON |
| Неизвестные поля помечены | passed — §9 и §1: правила хакатона `unknown`, оставшееся время `unknown`, pptx не разбиралась, полный текст PDF не извлекался |
| Данные/код не названы проверенными без открытия | passed — каждое число получено чтением файла; §9 отделяет проверенное от непроверенного |
| Проверено наличие пригодного Qdrant Local adapter, сообщено A00 до freeze | passed — §7, фактические команды; вывод: adapter отсутствует |
| Отдельно отмечены Регламент, PDF originals, taxonomy | passed — §1, D1, §5, §6.2 |
| A00 получил аргументы выбора индекса | passed — §11 «A00», DEC-001 |
| C02 получил входы | passed — §11 «C02», 11 пунктов |
| raw не изменялся, ничего не скачивалось с Портала | passed — режим только чтение |

## Commands and actual outputs

```
git rev-parse origin/main                     -> ab2c182b45cfd9040f0d62a30574970083c15967
git status --porcelain                        -> (пусто)
git rev-list --left-right --count main...origin/main -> 0	0
git worktree add /Users/gunter/Desktop/tenderhack-c00 -b task/c00-input-audit ab2c182
                                              -> HEAD is now at ab2c182

python3 knowledge/audit/audit_inputs.py > knowledge/audit/c00_inventory.json
                                              -> exit 0, 18.0 s, 15344 B

KB JSONL: 1468 строк, 0 ошибок разбора; organizer_pdf 941 / portal 527;
          480 уникальных article_id; 533 уникальных source_key; 0 точных дублей content
PDF (7 файлов): 370 / 256 / 93 / 65 / 39 / 7 страниц инструкций + Регламент 57;
          все не зашифрованы, текстовый слой есть
          счётчики страниц совпали с max(page_start) в KB — зонд валидирован
Покрытие: пропущена только стр. 3 «Инструкции по электронному актированию»
История XLSX: 24 960 строк, все «Завершено», Описание/Решение пустых 0,
          23 508 (94 %) с префиксом «Подтема запроса: X/»
Taxonomy XLSX: 9 тем, 86 строк подтем, 82 уникальные; колонок линии/адресата НЕТ
Crosswalk: 8 из 9 тем встречаются в истории, покрытие 22 387 / 24 960 (89 %)

sqlite3 <вне Git> "PRAGMA integrity_check;"                        -> ok
sqlite3 <вне Git> "select count(*) from documents;"                -> 1468
FTS5 словоформы: контракт 110 | контракта 351 | контракту 61 | оферта 42 | оферты 183
          -> русской нормализации нет (дефолтный unicode61)

command -v qdrant                                                  -> MISSING
python3 -c "importlib.metadata.version('qdrant-client')"           -> MISSING
find /Users/gunter -maxdepth 6 -iname '*qdrant*'                   -> хранилища нет
docker info / docker ps -a / docker images                         -> зависают без вывода (>120 с, >20 с)
grep -rl -i qdrant ~/Desktop/Projects ~/Documents/GitHub ~/Downloads
          -> совпадения только в .md-спецификациях, кода нет

df -h /Users/gunter -> /dev/disk3s5 228Gi, занято 190Gi, свободно 2.8Gi, 99 %
sysctl -n hw.memsize -> 8589934592 (8 GiB)
torch / transformers / sentence-transformers / qdrant-client / faiss-cpu -> MISSING
~/.cache/huggingface (458 МБ) -> только paraphrase-multilingual-MiniLM-L12-v2
Qwen3-8B GGUF, Qwen3-Embedding-0.6B на M -> отсутствуют
```

## Data mode

**real** — все счётчики и хеши получены из фактических файлов репозитория.
Единственный объект вне Git: `knowledge_base_FINAL.sqlite` из `/Users/gunter/Downloads/TenderHack_KnowledgeBase.zip` (SHA-256 архива `2a6bfe0f…`, SQLite `6e11d6fe…`). Распакован в scratchpad вне репозитория, проверен на чтение, в Git не добавлялся. Mock-данных нет. Синтетических замен отсутствующим входам не создавалось.

## Artifacts and paths

| Артефакт | Путь | SHA-256 / размер |
|---|---|---|
| Audit-документ | `knowledge/audit/C00_input_audit.md` | в commit |
| Аудит-скрипт | `knowledge/audit/audit_inputs.py` | в commit |
| Машиночитаемый отчёт | `knowledge/audit/c00_inventory.json` | 15 344 B, в commit |
| KB JSONL (вход, не изменён) | `TenderHack_KnowledgeBase/knowledge_base_FINAL.jsonl` | `71bf714a9e205a35f5d8ec0fd2d0f9bbd4ad3a8409968b754eb8de7b349d79ae` |
| Регламент (вход, не изменён) | `Регламент_информационного_взаимодействия-4.pdf` | `ef09670556196f6acf00d78e4e3aefe688665cecbf1fd8622afaa5fb488b707b` |
| KB SQLite (вне Git) | `~/Downloads/TenderHack_KnowledgeBase.zip` → `knowledge_base_FINAL.sqlite` | `6e11d6feb9124f03f9a4fcc62afa71d00c3e34cac101921276e38458c70d48ac` |

Остальные хеши входов — в `c00_inventory.json` и §1/§5 audit-документа.

## Known blockers and reproducible defects

| # | Blocker | Блокирует | Кому |
|---|---|---|---|
| BL-C00-1 | Регламент не загружен в KB (0 чанков), PDF есть и пригоден (57 стр., текстовый слой) | нормативные ответы, приоритет источников §10 | C02 |
| BL-C00-2 | Справочник линий/адресатов отсутствует; в taxonomy только тема/подтема | маршрут остаётся `unknown` | C04, команда |
| BL-C00-3 | На M свободно 2.8 GiB, нет torch и весов моделей | локальная сборка эмбеддингов на M | C03, A00 |
| BL-C00-4 | Docker Engine не отвечает; Qdrant не найден ни в каком виде | подтверждение «рабочий Qdrant Local» для DEC-001 | A00 |
| BL-C00-5 | `source_url` = URL API коллекции, `updated_at` = одна константа на 527 записей | точные citations, приоритет по свежести | C02, A |
| BL-C00-6 | 776 чанков (53 %) ссылаются на отсутствующие рисунки | полнота evidence, `MISSING_ATTACHMENT` | C02, C03 |
| BL-C00-7 | `api_report.json` расходится с файлом: 530/483/944 против фактических 527/480/941 | counts манифеста | C02 |
| BL-C00-8 | Отдельного документа правил/регламента хакатона не найдено | заявления о соответствии требованиям | команда, A |

Воспроизводимые дефекты KB (D1–D12) с точными счётчиками — §3 и §4 audit-документа. Все воспроизводятся запуском `knowledge/audit/audit_inputs.py`.

## Contract change requests

Нет. C0 не заморожен, контракта пока не существует — менять нечего. Два замечания к будущему DTO evidence передаю как вход A00, не как CR: `source_url` в снимке не является адресом статьи, а `updated_at` не является датой актуальности; закреплять эти поля как citation-поля нельзя.

## Inputs required by next task

### Для A00 (до заморозки C0)

1. **DEC-001, выбор индекса.** Пригодного Qdrant Local adapter нет: ни `qdrant-client`, ни бинаря, ни хранилища, ни lab-кода команды; Docker Engine не отвечает, контейнеры не подтверждены. По INITIAL_FILES_MANIFEST это ветка «A00 выбирает NumPy». Масштаб корпуса — 1468 чанков (после чистки ~1424), матрица ≈1468×dim float32 порядка единиц МБ; внешний векторный сервис выигрыша не даёт, но добавляет зависимость и второй источник состояния. Со стороны владельца `knowledge/**` возражений против NumPy нет. Решение принимает A.
2. **Фактические значения для `docs/integration/input_inventory.md`** (файл A, мной не изменялся): рабочий репозиторий **yes**; локальная KB **yes** (1468 чанков); Регламент как trusted source — файл **yes**, но **в KB не загружен**; PDF originals **yes** (6 инструкций, 830 стр.); история обращений **yes** (24 960 строк); taxonomy тем/подтем **yes** (9/82); справочник линий/адресатов **no**; lab-код/Qdrant adapter **no**; Qwen3-8B GGUF **no на M**; Qwen3-Embedding-0.6B **no на M**; свободное место на M — 2.8 GiB; правила хакатона **unknown**; оставшееся время **unknown**.
3. **Фактические значения для `machine_map.md`** (файл A): профиль M — MacBook Air M2, arm64, 8 GiB RAM, macOS 14.4.1 (23E224), свободно 2.8 GiB, Python 3.13.12, ML-стек не установлен.
4. **Планирование C03:** сборка эмбеддингов на M при текущем свободном месте и отсутствии весов невозможна. Нужен слот на профиле G либо освобождение диска на M. Строку C03 в `gpu_slots.md` планирует A.
5. **DTO evidence:** не закреплять `source_url`/`updated_at` как поля citation (см. CR-замечание выше).

### Для C02 (нормализация KB и source lookup)

1. Входы и хеши брать из `knowledge/audit/c00_inventory.json`; counts манифеста — фактические (1468/941/527/480), **не** из `api_report.json`.
2. Удалить 44 служебные записи (оглавления, номера страниц) с указанием причины; порог по длине единственным критерием не делать — 57 коротких портальных записей содержательны.
3. Загрузить Регламент (57 стр., текстовый слой есть, OCR не нужен) отдельным `source_type` с приоритетом по §10.
4. Добавить пропущенную стр. 3 «Инструкции по электронному актированию».
5. Сохранить `audience_raw`; `instruction` (192 записи) ролью не считать; `general`/пусто ≠ «все роли».
6. `updated_at` → `collected_at`, актуальность статьи `unknown`; `source_url` → `collection_endpoint`, per-article URL не конструировать.
7. Parent: портал — по `article_id` из `source_key` (480 parent, 36 многочанковых статей); PDF — parent'ов нет, чанкинг строго постраничный (941 чанк, ни один не пересекает границу страницы, overlap отсутствует), секции восстанавливать по заголовкам.
8. Пометить 776 чанков «ссылка на рисунок, изображение отсутствует» и 23 pointer/приложение.
9. Пересобрать `title`: 27 записей имеют имя файла вместо заголовка, остальные — часто обрезанная первая строка; в embedding такой заголовок подавать нельзя.
10. Near-duplicates разных версий автоматически не схлопывать: точных дублей 0, но 156 заголовков повторяются.
11. Для FTS обязательна единая русская нормализация — дефолтный `unicode61` словоформы не сводит (контракт 110 / контракта 351 / контракту 61); английский Porter не подставлять.

### Прочее

- **B04 / D01 / D03:** история пригодна — 24 960 строк, 94 % с извлекаемой подтемой, 24 768 уникальных пар «Описание→Решение». В свободном тексте остаётся PII: email 196 строк, телефоны 532, «ИНН <цифры>» 584, GUID 3916. Колонка `Заявитель` обезличена (одно значение), реальной роли в истории нет.
- **C04:** crosswalk taxonomy↔история — 89 % покрытие по темам, 16 подтем истории вне taxonomy, 8 подтем taxonomy не встречаются; часть расхождений орфографические. Маршрут «подтема → линия» данных не имеет.

## Остановка

C00 завершён. C01/C02/C03 не начинал — для них участник создаёт отдельные новые чаты.
