# TenderHack — единая спецификация и задания для новых чатов

Версия 2.1 · 12.09.2026 · Статус: спецификация будущей реализации, не отчёт о готовом коде.

**Строим законченный локальный сервис поддержки: проверяемые источники → ответ или уточнение → передача человеку → его ответ в том же чате → оценка конкретного ответа. Один генератор в runtime; четыре агента помогают разрабатывать один продукт.**

**Одна задача с отдельным ID = один новый чат.** Завершив задачу, агент сдаёт commit/patch и handoff и останавливается. Следующий ID запускается в новом чате даже у того же участника. Новый агент получает документы и состояние репозитория, а не должен помнить переписку.

## 1. Основания и разрешение противоречий

Источники: S1 — TENDER_HACK_IMPLEMENTATION_SPEC_PARALLEL_v1.md; S2 — TenderHack_specification_team4.md; R — Сравнение спецификаций.md.

Эта версия заменяет конфликтующие положения S1/S2. Старые четыре больших стартовых промпта не запускать: там различаются роли и остаются исключённые функции. Оригинальные регламент, KB, история, репозиторий и веса в этой работе не проверялись. Распределение баллов 40/20/10/20/10 и окно 34 часа перенесены из документов, а не повторно подтверждены организаторами. H0 — начало доступного окна команды; прошедшие часы не возвращаются.

| Область | Что берём | Итог v2 |
|---|---|---|
| Продуктовый процесс | S2 | Полный цикл, включая реальный ответ человека |
| Вычислительная простота | S1 + R | Один узел, один тяжёлый worker, 0–1 generation на обработку |
| Evidence gate | S1 + S2 | ANSWER_ALLOWED / CLARIFY / ESCALATE / OUT_OF_SCOPE; модель может дополнительно отказаться |
| Источники | S1 + S2 | Приоритет по типу утверждения; роль, условия, версия, неполнота, реальные ссылки |
| Индекс | S2 + R | Сохранить пригодный Qdrant Local; если его нет — NumPy. Один выбор в A00 |
| Человек и авторство | S2 | Защищённый reply, автор от backend, без кабинета оператора |
| Состояния/API | R | Минимальные Case/Request/Ticket, девять операций |
| Feedback | Смысл S2 + R | Полезность и решение в одном endpoint, но разные показатели |
| Маршруты | S1 + S2 | Правила/metadata, отдельные линия и адресат, unknown; L3 консервативно |
| Методика | S2 | 20 dev + 40 final; отдельно 30 исторических пар и две человеческие оценки |
| Карточки | S2 + R | 8–10 reviewed; обычный RAG важнее количества карточек |
| Аналитика | S1 + S2 + R | Детерминированный отчёт, один итоговый экран; негативные tags — гипотезы |
| Команда | S2 + v2 | Один владелец файла, небольшие commits, отдельный чат на каждый ID |

Не переносим: обязательный классификатор 86 подтем; 100 обязательных RAG-кейсов; персональный category-adjusted ranking без данных; генеративный retry; публичный PATCH тикета; обязательный dashboard; отдельные outcome/retry/status endpoints; 19 событий; ACL на каждую публичную статью; 15–20 обязательных карточек.

## 2. Цель и приоритеты

Автоматизируем типовые вопросы L1/L2 Портала поставщиков, объясняем основания ответа, собираем контекст для человека при недостатке знаний. Не выполняем операции в Портале. Локальный тикет не выдаём за реальную интеграцию со службой Портала.

**P0:** чат и история; обычный RAG; источник и условия; одно уточнение; отказ; маршрутизация; profanity до поиска; настоящий защищённый reply; feedback конкретного ответа; методика и реальные результаты; Linux/offline/restart.

**P1 после первого E2E:** 8–10 reviewed-карточек, dev-улучшения retrieval, компактный итоговый экран, полировка UI. Ранний источник входит в контракт, но его оформление не задерживает первый сквозной путь.

**Вне версии:** операторский кабинет, CRM, KB-редактор, автоматическое доверие ответам оператора, внешний AI/search runtime, LLM-критик, глобальные reranker/RRF/BM25, распределённые сервисы, fine-tuning, голос, vision, массовый OCR. Только точечное извлечение действительно нужной страницы при подтверждённой необходимости.

Облачные coding-инструменты допустимы как помощь разработке в пределах правил конкурса. Это не разрешает облачный runtime продукта или загрузку закрытой истории без оснований. Материалы разметки обезличиваются.

## 3. Ноутбуки и размещение нагрузки

Характеристики восстановлены из предыдущего контекста команды. **Соответствие владельцев ноутбукам не установлено.** Не утверждаем, что RTX принадлежит Артёму или Mac — Стасу. Разделяем владельца кода и место запуска. Фактическую привязку имён и машин фиксирует A00; работа на mocks не ждёт этого.

| Профиль | Известно | Нагрузка по плану | Ограничения |
|---|---|---|---|
| G — GPU | i7-12650H; RTX 3070 Laptop, 8 ГБ VRAM; RAM и установленная ОС не подтверждены | Все реальные generation/embedding, сборка индекса, Linux runtime, E2E, демонстрация | Без одновременного ingest/inference. Проверить RAM, Linux, драйвер и вместимость моделей |
| M — Mac | MacBook Air M2, 8 ГБ; версия ОС не зафиксирована | Предпочтительно frontend/Vite, браузерные проверки, лёгкий backend с fakes | Не планировать 8B, обязательный Docker и перенос ARM-окружения на x86 Linux |
| N — Azerty | RB-1551; Celeron N5095, 4 ядра, 2 ГГц; Intel UHD; 16 ГБ DDR4; SSD, ранее 180 ГБ свободно; ОС неизвестна | CPU-нормализация KB, SQLite, правила, unit-тесты, отчётные скрипты | Ограничить параллелизм; полный embedding build на G |
| W — WindowsPC | i5-4210U 1,70/2,40 ГГц; Intel HD; 12 ГБ RAM; SSD, ранее 87 ГБ свободно; Windows | Источники, ручная разметка, рубрика, отчёты, BPMN, browser client | Без CUDA/8B. Прежние «113 МБ» не трактовать как всю GPU-память; свободное место проверить заново |

Назначение профилей — размещение вычислений, не обязательная перестановка людей. Участник пишет свой лёгкий код на собственном ноутбуке, а GPU-владелец запускает его commit на G в выделенный слот. GPU-владелец не становится вторым редактором модуля.

| Участник / агент | Ответственность | Где выполняет |
|---|---|---|
| Артём / A / Codex | Контракты, backend, состояние, generation, интеграция, релиз | Разработка на доступной машине; настоящий runtime на G |
| Стас / B / Codex | Frontend; вторая независимая историческая оценка | Предпочтительно M, иначе собственная машина с Vite без ML; E2E обращается к G |
| Эдуард / C / Claude Code | Policy, KB, retrieval, gate, taxonomy/маршруты, импорт карточек | CPU-код на своей машине/N/M; embedding build и real smoke на G |
| Егор / D / Manus Lite + ручная работа | Evaluation, первая историческая оценка, расчёты, BPMN, защита | W/N/своя машина; final runner вызывает G |

Manus без Git возвращает файлы/patch разрешённых путей; Егор применяет и проверяет в своей ветке. Для исторической оценки люди подтверждают содержание самостоятельно.

### GPU-слоты

A ведёт docs/integration/gpu_slots.md: задача, точный SHA, команда, начало/окончание, результат.

1. A01 — ранний Linux/model smoke, память, short/long, restart.
2. C03 — embedding build после C02; демо в это время не работает.
3. A03 — настоящий сквозной ответ.
4. C07 — ограниченный dev-прогон; A05 — нагрузка/offline/restart.
5. D07 — final на замороженном RC.
6. A07/D08 — репетиция и демонстрация; тяжёлые фоновые программы на G закрыты.

Другие ноутбуки могут обращаться к G по локальной сети; весь ML/runtime остаётся на G. Для финального запуска интернет не требуется. Reply-ключ не попадает в браузерный UI.

## 4. Стек и бюджет

| Компонент | Решение |
|---|---|
| UI | React + TypeScript + Vite, локальные assets |
| API | FastAPI + Pydantic, один процесс, workers=1 |
| Данные приложения | app.sqlite; единственный writer — backend |
| KB | Read-only knowledge.sqlite + один локальный индекс |
| Embedding | Qwen3-Embedding-0.6B, 1024 измерения, закреплённые revision/adapter |
| Generator | Qwen3-8B GGUF Q4_K_M через локальный Ollama; thinking выключен и проверен |
| Индекс | Пригодный рабочий Qdrant Local, иначе NumPy exact cosine; без сервера Qdrant |
| Поиск | Dense top 10; условный exact/FTS5, обычно 3–5 evidence |
| Конкурентность | Один тяжёлый участок embedding → retrieval → generation; до 3 ожидающих |
| ОС сдачи | Linux; WSL2 только при подтверждённой допустимости |

Версии библиотек, digest весов, quantization, параметры и ОС фиксируются по фактическому запуску, не по предположению документа. p95 короткого ответа ≤15 с при одном прогретом клиенте — ориентир, не замер и не обещание.

Обычная обработка: 1 query embedding, 0–1 generation. **Автоматического повторного generation нет**, в том числе для невалидного JSON. Пользовательский retry после технического сбоя — отдельная принятая попытка. Profanity/человек используют 0 embedding и 0 generation; reviewed-карточка — 0 generation, embedding может понадобиться для поиска.

Начальный контекст 8192 токена: 600 reserve output и 300 служебных; input с chat template ≤7292. Обычно input 2600–5000, ответ 120–250. Условия не обрезаются ради длины. Бюджет считать tokenizer генератора, не embedding-модели.

Первые технические пределы: retrieval 10 с, generation 60 с, ожидание очереди 180 с. Уточнить по A01/A05. Блокирующие вычисления не работают в event loop. Workers=1 не заменяет общий GPU scheduler, охватывающий и embedding.

Если 8B не проходит smoke: проверить контекст/нагрузку; CPU embedding — только после измерения. Один закреплённый 4B-резерв допустим после провала ранней проверки и новой dev-оценки. Не держать несколько генераторов, не менять стек после H22. Разрушительная установка ОС/разметка диска не входит в автоматический bootstrap.

## 5. Репозиторий, владение и C0

| Пути | Единственный владелец записи |
|---|---|
| contracts/**, backend/**, tools/**, infra/**, config/runtime/** | A |
| Root README, AGENTS, pyproject/lock, .env.example, Makefile, CI | A |
| docs/integration/** | A |
| frontend/**, включая generated TS и frontend lock | B |
| knowledge/**, config/knowledge/** | C |
| evaluation/**, кроме annotations/stas/** | D |
| evaluation/annotations/stas/** | B |
| reports/**, presentation/**, docs/process/** | D |
| content/cards/<participant>/**, content/reviews/<participant>/**, docs/coordination/<participant>/** | Соответствующий участник |
| data/raw/** | Неизменные входы; никто не переписывает |
| var/**, artifacts/**, веса, индексы | Сборки вне Git, без параллельной записи |

C реализует profanity в knowledge/policy, routing и gate; A вызывает их, применяет state/budget/verifier и публикует результат. D считает показатели из экспорта, не читает работающую app.sqlite.

**C0 — результат A00**, tag bootstrap-contracts-v2. В первый час: структура/AGENTS, минимальные DTO/Protocol, OpenAPI, fixtures, EvaluationExport schema, test fakes, health/minimal run, inventory, выбор индекса. Это каркас, не весь backend. B00/C00/D00 до C0 работают автономно, не создавая общие API.

Канон — Pydantic в contracts/python. A генерирует OpenAPI/JSON Schema; B — TypeScript без ручной правки generated. Root Python-зависимости меняет A по заявке, frontend — B.

Каждая задача: task/<ID>-<slug> от опубликованного интеграционного SHA, отдельный clone/worktree. Одна активная задача на рабочий каталог. A последовательно интегрирует небольшие commits. Следующая зависимая задача стартует от SHA с уже принятыми зависимостями, не автоматически от старого C0.

CR: docs/coordination/<participant>/CR-<ID>.md с проблемой, точным изменением, потребителями, тестом. A принимает решение внутри команды и обновляет DTO/fixtures/changelog вместе. После первого E2E только небольшие необходимые изменения; после H22 — исправление подтверждённых дефектов. Передача владения файлом фиксируется до редактирования.

## 6. Сущности

UUID-строки для новых ID; original_id сохраняется. UTC ISO 8601; длительности ms; страницы PDF с единицы. Неизвестное null, массивы всегда массивы. Материал неизменен внутри snapshot_id; source_id уникален между снимками, например включает snapshot.

| Сущность | Минимум полей |
|---|---|
| Session | session_id, created_at, expires_at |
| Case | case_id, session_id, status, case_version, active_request_id, clarification_count, confirmed_facts, topic_id, subtopic_id, route, is_demo, created_at, updated_at |
| Message | message_id, case_id, seq, role, kind, responder_type, author_id, answer_origin, content, source_ids[], created_at |
| Request | request_id, case_id, user_message_id, accepted_case_version, status, result_message_ids[], error_code, trace_id, timings_ms, created_at, finished_at |
| Ticket | ticket_id, case_id UNIQUE, status, route, reason_codes[], missing_information[], context_snapshot, created_at, updated_at, resolved_by |
| Feedback | feedback_id, session_id, message_id, useful, solved, specialist_rating, reason_codes[], comment, updated_at; UNIQUE(session_id,message_id) |

Message.role=user/assistant/system; kind=question/answer/clarification/notice; responder_type=ai/operator/system/null; answer_origin=rag/card/operator/system/null. Автор от сервера.

Достаточно шести таблиц + компактное хранение receipt идемпотентности chat/retry/handoff/reply. Не универсальная платформа событий. Демонстрационный оператор сопоставляется ключу в защищённой config.

confirmed_facts: ограниченные slots роли supplier/customer/unknown, явных кодов/объекта и подтверждённых выполненных шагов. Для факта value + user_message_id. Исправление пользователя заменяет старый факт. AI-текст не становится evidence; неоднозначное извлечение даёт unknown. Новая тема — новый Case без предметных фактов прежнего.

## 7. HTTP-контракт: девять операций

| Операция | Вход | Выход/семантика |
|---|---|---|
| POST /api/v1/sessions | {} | 201 новая / 200 действующая Session, HttpOnly-cookie |
| POST /api/v1/chat | ChatInput | 202 AcceptedRequest, вопрос и Request сохранены |
| GET /api/v1/requests/{id} | — | RequestView: status/progress/candidates/final IDs/error |
| GET /api/v1/cases/{id} | — | CaseView: Case, Ticket/null, ограниченная полная история |
| POST /api/v1/cases/{id}/handoff | request_key, expected_case_version | 201 новый / 200 существующий Ticket |
| GET /api/v1/sources/{id} | — | Карточка источника, реальный excerpt/version/page/file URL |
| POST /api/v1/feedback | FeedbackInput | 201/200 feedback + outcome_applied |
| GET /api/v1/health | — | ready/degraded; 503 если нельзя принимать/сохранять |
| POST /internal/tickets/{id}/reply | OperatorReplyInput + Bearer | Operator Message + простой status одной транзакцией |

### Формы

~~~json
{"case_id":null,"expected_case_version":null,"request_key":"UUID","text":"Как подписать контракт?","retry_of":null}
~~~

Новый вопрос: text непустой, retry_of=null. Retry: text=null, retry_of=Request ID, новый ключ; прежнее user Message не дублируется. Existing case требует expected_case_version. Новый case_id=null требует version=null.

AcceptedRequest: request_id, case_id, user_message_id, case_version, status, trace_id. Быстрый Request к моменту ответа уже может быть terminal; 202 означает приём, не решение проблемы.

RequestView: request_id, case_id, status, progress, candidate_sources[], result_message_ids[], error:null|{code,message,retryable}, timings_ms. Status=queued/processing/final/error/cancelled. Progress=queued/retrieving/sources_found/generating/null. Progress может жить в памяти; приём и terminal сохраняются.

CaseView: case, ticket/null, messages[], limit_reached. MVP ограничивает Case 100 сообщениями; приём резервирует место для финального результата, избыток отклоняется с просьбой начать тему. Не обрезать историю молча. Пагинация вне обязательной версии.

~~~json
{"message_id":"UUID","useful":true,"solved":null,"specialist_rating":null,"reason_codes":[],"comment":null}
~~~

Feedback: первый клик сразу сохраняется. Пропущенное поле при обновлении сохраняется, явный null очищает nullable. При создании хотя бы одна оценка непуста. specialist_rating=1–5 только для настоящего operator answer, AI → 422. Максимум два reason_codes: NOT_RELEVANT/UNCLEAR/MISSING_INFORMATION/POSSIBLY_OUTDATED; comment ≤2000. Notice/policy не оцениваются как answer. Поля автора от клиента отвергаются.

FeedbackResponse: feedback_id, message_id, case_version, case_status, outcome_applied, outcome_reason. Solved меняет текущий Case только для последнего answer без более позднего user Message/передачи/закрытия и без active Request. Иначе оценка сохраняется, outcome_applied=false. Повтор того же solved не повышает version повторно. Старый отзыв не переоткрывает resolved.

~~~json
{"request_key":"UUID","expected_case_version":5,"text":"Ответ специалиста","next_status":"waiting_user"}
~~~

OperatorReplyInput: next_status=waiting_user/resolved, text ≤6000, только existing Ticket. Author от ключа. CLI читает текст из файла; не имитирует operator через mock браузера.

### Доступ и ошибки

HttpOnly, SameSite=Strict cookie; Secure при HTTPS, локальное HTTP-исключение в config. Один origin, Vite proxy для dev. Browser mutations проверяют Origin. Секреты не в localStorage/Git/bundle. Private Case/Request/Message/Feedback проверяют session; чужое и отсутствующее — одинаковый 404.

Internal reply защищён даже на localhost. Публичные официальные KB доступны без CaseSourceLinks ACL. Приватная история/вложения не раздаются статикой. Реальные публичные PDF — только по manifest-карте разрешённых файлов, не произвольному filesystem path. Нет PDF — показываем имеющийся текст, не изображаем оригинал.

Ошибки: 401 UNAUTHORIZED; 404 NOT_FOUND; 409 STALE_CASE_VERSION/CASE_BUSY/CASE_CLOSED/IDEMPOTENCY_CONFLICT/INVALID_TRANSITION; 422 VALIDATION_ERROR; 429 QUEUE_FULL; 503 STORAGE_UNAVAILABLE. Envelope: error={code,message,retryable,trace_id,current_case_version:null|int}. 429/503 до приёма не подтверждают сохранение. Сбой модели после 202 хранится в Request.

## 8. Состояния и восстановление

Case: open/awaiting_clarification/awaiting_feedback/handoff_offered/handed_off/resolved/closed_policy. Ticket: new/waiting_user/resolved/closed_policy. Реализация обычными функциями, без workflow framework.

| Событие | Переход |
|---|---|
| Вопрос принят | Case open, Request queued |
| Один неизвестный факт, count=0 | awaiting_clarification, count=1 |
| Ответ на уточнение | open, новое retrieval; count не сбрасывать |
| Проверенный AI/card answer | awaiting_feedback |
| Нет evidence/конфликт/invalid generation | handoff_offered, Ticket ещё нет |
| OUT_OF_SCOPE | Notice о границах сервиса, open, без автоматического тикета |
| Подтверждение/недвусмысленная просьба человека | handed_off, один Ticket new, active Request инвалидирован |
| Operator reply waiting_user | handed_off, Ticket waiting_user |
| Пользователь отвечает человеку | Message сохранено, Ticket new как ожидание следующего ответа; AI не запускается |
| Operator reply resolved | Case/Ticket resolved, resolved_by=operator |
| Актуальный solved=true | Case resolved; Ticket при наличии resolved, resolved_by=user |
| Актуальный solved=false | AI Case open либо Ticket new/Case handed_off; inference сам не запускается |
| Profanity в незакрытом Case | closed_policy, отмена актуальности Request, незавершённый Ticket closed_policy |
| Технический сбой | Request error; не resolved |
| Новая проблема после закрытия | Новый Case, старый не переоткрывается |

Продолжение resolved/closed_policy через chat — 409. Старый answer можно оценивать, но нельзя переписать терминальный исход. Точный успешный повтор запроса возвращает receipt и после закрытия.

Гарантии:

- Chat/retry/handoff/reply: scope=(actor,operation,request_key), hash тела; точный повтор возвращает результат, другое тело — 409. Receipt атомарен с записью, сохраняется при restart, проверяется до stale-version.
- Один active AI Request на Case. Policy и явный handoff проверяются до CASE_BUSY/GPU admission, могут инвалидировать прежний результат.
- Один тяжёлый выполняемый + три ожидающих; вместимость резервируется атомарно с приёмом, 429 до user Message. Быстрые ветки не ждут GPU.
- Перед публикацией в транзакции проверяются active_request_id, accepted_case_version и допустимость Case. При несовпадении cancelled, поздний AI-текст не публикуется.
- Final Message/sources/trace, terminal Request и Case записываются атомарно. Во время inference нет SQLite-транзакции.
- Отмена Request не освобождает GPU-слот до фактического завершения/остановки вычисления.
- Restart: queued/processing → error RESTART_INTERRUPTED, active_request_id очищаются; вопрос и receipts остаются.
- Retry через chat: только свой error/cancelled Request, незакрытый Case без Ticket, без более позднего user Message/active Request. Новый Request к старому Message, не дубль вопроса.
- Handoff/reply требуют version. Existing Ticket не создаётся снова. Feedback не инвалидирует generation; при active Request solved outcome не применяется.

## 9. Policy и KnowledgePort

DTO в contracts/python не зависят от backend/knowledge. C реализует порты, A внедряет зависимости. C не пишет app DB, A не читает внутренние таблицы KB.

~~~python
class PolicyPort(Protocol):
    def check(self, text: str) -> PolicyResult: ...

class KnowledgePort(Protocol):
    async def retrieve(self, query: QueryContext) -> KnowledgeResult: ...
    async def get_source(self, source_id: str) -> SourceRecord | None: ...
    async def get_card(self, card_id: str) -> ScenarioCard | None: ...
    async def health(self) -> KnowledgeHealth: ...

class GeneratorPort(Protocol):
    async def generate(self, task: GenerationInput) -> GenerationProposal: ...
~~~

PolicyResult: profanity, explicit_human_request, matched_rule_ids[]. Profanity приоритетен; неоднозначная фраза не является согласием на передачу.

QueryContext: text, confirmed_facts, recent_user_messages, clarification_count, trace_id. AI-текст не становится evidence.

KnowledgeResult: snapshot_id, candidates:EvidenceItem[], selected_evidence_ids[], decision, missing_fact:null|{key,question}, reason_codes[], card_id/null, route:RoutingResult, timings_ms.

EvidenceItem: evidence_id, source_id, original_ids[], parent_id, source_type, title, version/null, source_date/null, section_path/null, page_from/null, page_to/null, text, conditions[], audience_raw/null, applicable_roles[], role_verified, content_status=complete/pointer/incomplete, eligibility_reason/null, retrieval_method=dense/exact/fts, score. Score внутренний, не вероятность.

RoutingResult: topic_id/null, subtopic_id/null, support_line=null/L1/L2/L3, recommended_recipient/null, basis_source_ids[], rule_id/null, is_probable_defect, is_ambiguous, reason_codes[]. Не содержит назначенного реального оператора.

KnowledgeHealth: available, mode=semantic/lexical_only/unavailable, snapshot_id, reason. Нет подходящего содержания → ESCALATE; техническая невозможность поиска → KnowledgeUnavailable и SEARCH_UNAVAILABLE. Эти причины не смешиваются.

### Profanity

Детерминированный русский словарь/regex, Unicode/регистр/простые разделители/маскировка/замены только для поиска совпадений. Исходник хранится. Проверять false positives на обычных словах/технических строках.

При срабатывании 0 routing, 0 embedding, 0 retrieval, 0 generation. Notice: «Обращение завершено: в сообщении обнаружена нецензурная лексика. Пожалуйста, соблюдайте правила общения». Policy-closure не считается решением проблемы.

### Routing

Первый проход — дешёвые признаки, второй — проверенная metadata evidence без второго embedding. Taxonomy из реального справочника, 9/86 не выдумываются. В историческом вводе исключить встроенную метку «Подтема запроса: …», чтобы не измерять утечку ответа.

L1: навигация/вход/регистрация/простой how-to. L2: методология, договоры/УПД, сложное заполнение. L3: сочетание признаков воспроизводимого технического дефекта/инцидента; «не работает» само по себе недостаточно.

Неопределённость L1/L2 → L2 triage; L2/L3 без технических оснований → L2 triage с ambiguity. При отсутствии оснований вообще — null, не автоматически L2. Адресат отдельно от линии. Missing attachment не означает L3. Gold line берётся из реальных пригодных данных.

## 10. KB, retrieval и gate

### Подготовка

Имеющийся локальный снимок, без пересборки Портала из сети. Trusted: применимый Регламент, официальные инструкции, официальный KB snapshot. Регламент включается при реальном наличии; отсутствие ограничивает соответствующие ответы.

История «Описание → Решение» используется для формулировок/taxonomy/оценки. Решение, operator reply и положительный feedback не становятся trusted evidence.

C02:

1. Фиксирует входы/хеши. Ранее заявленные 1468 chunks, 480 article_id, 6 PDF — ожидания, не текущие замеры.
2. Удаляет TOC/номера/служебные fragments с причинами, сохраняет короткие полезные ответы.
3. Восстанавливает части/parent статьи. Near-duplicates разных версий автоматически не схлопывает.
4. Сохраняет audience_raw; instruction не является пользовательской ролью; unknown не означает все роли.
5. Помечает pointer/incomplete/missing attachment; ссылка на приложение не обосновывает его отсутствующее содержание.
6. Не выдумывает даты актуальности и URL статьи из URL API.
7. Связывает PDF/страницы при наличии; отсутствующие скриншоты не считает прочитанными.

Статья/секция — parent. При пригодных children сохраняем существующий chunking. Ориентир child 220–400 токенов, overlap 30–50 внутри секции, parent 600–1000; смысл и условия важнее длины.

Manifest: snapshot_id, created_at, input_files[{name,sha256}], normalizer_version, embedding_model/revision/dim/adapter_version, index_type, counts{raw,included,excluded,articles,cards_reviewed}, files[{path,sha256}]. Смена embedding adapter/весов требует пересборки. Runtime KB read-only.

### Поиск

Корректная query instruction Qwen, документы без неё; pooling/normalization закреплены и сверены с адаптером. E5-префиксы не переносить. Заголовок включён в embedding.

Exact IDs выделяются до морфологии. Условный exact/FTS для кодов/полей/аббревиатур и иных подтверждённых dev-сценариев. Безопасные FTS-токены, одинаковая русская нормализация; английский Porter не выдаётся за русскую. Проверить контракт/контракта/контракту и похожие разные коды.

Dense top 10 → dedup → применимость/роль/версия → parent expansion → 3–5 evidence. Тема мягкая, неверный topic не закрывает правильный источник. Подтверждённая несовместимость роли блокирует материал. A упаковывает по generator tokenizer; важные условия не обрезаются.

### Приоритет источников

| Утверждение | Приоритет при применимости |
|---|---|
| Нормативное правило | Регламент → официальная инструкция → KB |
| UI/how-to | Актуальная применимая инструкция → KB; Регламент не выдумывает кнопку |
| FAQ | Проверенная применимая KB с учётом нормативных ограничений |

Приоритет не отменяет роль/объект/версию/полноту. Unknown date не значит новее. Неразрешимый конфликт применимых материалов → ESCALATE. Authority-число само по себе ничего не доказывает.

### Gate

ANSWER_ALLOWED означает разрешение попытки, не доказательство истинности.

| Условие | Решение |
|---|---|
| Нет пригодного evidence, только pointer, существенное missing attachment | ESCALATE с причиной |
| Один необходимый неизвестный факт, count=0 | CLARIFY |
| Уточнение исчерпано | ESCALATE |
| Неизвестный exact ID | CLARIFY/ESCALATE без подмены |
| Несовместимая роль/конфликт | CLARIFY при одном разрешимом факте, иначе ESCALATE |
| Явно посторонняя тема | OUT_OF_SCOPE |
| Применимые полные evidence без известного конфликта | ANSWER_ALLOWED |

Пороги только по dev. Малый margin двух chunks одной статьи не означает плохой ответ; несколько chunks не независимые подтверждения. Нет confidence «90%». Непокрытая существенная часть multipart-вопроса не получает выдуманного ответа.

Reason codes: NO_EVIDENCE, ROLE_REQUIRED, ROLE_MISMATCH, MISSING_ATTACHMENT, KNOWN_CONFLICT, UNKNOWN_IDENTIFIER, UNSUPPORTED_OPERATION, EXPLICIT_HUMAN_REQUEST, UNRESOLVED_AFTER_STEPS, INVALID_GENERATION, MODEL_UNAVAILABLE, SEARCH_UNAVAILABLE, POLICY_LANGUAGE, OUT_OF_SCOPE. Backend хранит понятный reason_text.

## 11. Generation и reviewed-карточки

Генератор получает вопрос, подтверждённые факты, упакованные eligible evidence и allowed IDs. Не получает raw scores, исторические ответы, весь корпус. Инструкции внутри KB — данные, не system instructions. У модели нет инструментов управления Порталом/тикетами.

~~~text
GenerationProposal =
 {action:"answer", summary:string, conditions:string[], steps:string[], source_ids:string[]}
 | {action:"clarify", missing_fact:string, question:string}
 | {action:"escalate", reason_code:string, reason_text:string}
~~~

Union без смешанных полей. Answer имеет непустые summary/source_ids. Clarify после лимита превращается в предложение человека. Модель не создаёт Ticket и не выбирает автора.

Verifier: JSON/schema; непустой ограниченный ответ; только переданные source IDs; сохранение известных обязательных условий/кодов; проверяемые числа/даты/URL; запрет «я разблокировал/отправил/подписал». Нумерация шагов не считается содержательным числом. Число, встречающееся в источнике, не доказывает верность его использования. Метаданные citations формирует backend.

Invalid/unsupported proposal → handoff_offered INVALID_GENERATION, без повторной генерации. Это не универсальная семантическая проверка: содержание оценивается людьми.

ScenarioCard: card_id, intent_id, status=draft/reviewed/disabled, title, utterances[], applicable_roles[], required_facts[{key,expected_value}], source_ids[], content{summary,conditions,steps}, handoff_required, route, author_id, reviewer_id, reviewed_at, snapshot_id.

Применение только reviewed, другой reviewer, источники текущего snapshot, проверенный intent, все условия. Один similarity недостаточен. Handoff_required=true → предложение передачи, не выдача шагов как решения. Missing fact → общий CLARIFY; нет точного match → обычный RAG.

Каждый готовит 2 кандидата, итого 8; до 10 только после успешного RAG. Ревью A↔C и B↔D: автор редактирует своё, reviewer пишет замечания у себя. C06 импортирует одобренные. Если пригодных меньше восьми, сообщить факт, не снижать критерии.

## 12. UI

Чат, ввод, «Новая тема», этап, источник, условия перед шагами, одно уточнение, передача, тикет, человек, feedback. Нет операторского кабинета.

| Ситуация | Текст/поведение |
|---|---|
| Очередь/поиск | «Запрос в очереди» / «Ищу подходящую инструкцию» |
| Кандидат источника | «Найден материал. Проверяю, подходит ли он к вашей ситуации» |
| RAG/card | «Ответ по инструкции» / «Проверенный сценарий», источник и условия |
| Недостаточно evidence | Чего не хватает + «Передать специалисту» |
| Ticket | «В очереди специалиста нашего сервиса. Рекомендуемый адресат на Портале: …» |
| Неизвестный адресат | «Адресат требует уточнения» |
| Сбой | Ввод/принятый вопрос сохранён, допустимый retry или передача |

Не писать «Передано в службу Портала» без интеграции. Scores/prompt/VRAM не часть UX. Санитизация Markdown/HTML, локальные assets, без внешних CDN.

Request polling 750–1000 мс; Ticket Case каждую секунду; после terminal перечитать Case. В фоне 3 с; таймеры отменять. Дедуп по message_id; поздний ответ старого case_id не меняет текущий экран. Cookie + сохранённый case_id восстанавливают диалог; localStorage не даёт прав. При 409 обновить Case и сохранить ввод без слепого повтора.

Полезность отдельно от solved в одной форме. Рейтинг сотрудника только у operator. Старый отзыв с outcome_applied=false не изображает закрытие Case.

## 13. Экспорт и оценка

### Один экспорт

A: python -m tools.export_data --output <file.json>. Один JSON-конверт из согласованного read snapshot/backup: schema_version, export_id, created_at, as_of, app_commit, kb_snapshot_id, rows:EvaluationRow[]. Без секретов, не семь независимо выгруженных файлов.

**Одна EvaluationRow на Case**, включая случаи без ответа:

- case_id, cohort=demo/live, created_at, case_status, topic_id, subtopic_id, policy_closed;
- route{support_line,recommended_recipient,reason_codes};
- ticket:null|{ticket_id,status,created_at,resolved_by};
- messages[{message_id,seq,kind,responder_type,author_id,answer_origin,text,source_ids,created_at}];
- requests[{request_id,user_message_id,status,result_message_ids,error_code,timings_ms}];
- feedback[{message_id,useful,solved,specialist_rating,reason_codes,comment,updated_at}] — актуальные записи;
- current_resolution:null|{message_id,confirmed_by:user/operator,answer_origin,confirmed_at}.

AI-test/history отдельны от live/demo. D соединяет их в отчёте с явным происхождением, не смешивает знаменатели.

Timings ms: queue, retrieval, generation_total, time_to_first_source, total, prompt_eval, decode; неизвестные null. Total от приёма до terminal с очередью; answer latency отдельно от прочих исходов; вложенные интервалы не суммировать дважды.

### Три массива

1. AI: 20 dev, 40 final, многоходовые случаи допустимы. test_id, group_id, split, messages/actions, answerable, expected_outcome, role, gold_source_ids, required_conditions, forbidden_claims, gold_line/allowed_lines, recipient, evidence_refs.
2. История: 30 реальных пар, две независимые человеческие оценки Стаса/Егора, отдельное согласование. До 10 отдельных учебных примеров для якорей, не в итоговых 30.
3. Live/demo: отзывы/traces. Demo маркируется на сервере и не выдаётся за реальные пользовательские наблюдения.

Final хранит D вне общего checkout до RC. Перефразировки группируются до split. Карточки не создаются из скрытого final. После раскрытия исправления — post-test fixes, повтор не новый независимый тест.

Историческую оценку подтверждают люди, не «два независимых LLM». Нет истории — методика возможна, выполненные 30 пар нет. Нет author_id — оценка службы/ответов без выдуманного персонального рейтинга.

### Рубрика

| Измерение | 0 | 1 | 2 |
|---|---|---|---|
| Правильность | Существенно неверно | Частично верно | Существенные проверяемые утверждения верны |
| Полнота | Нет необходимого | Часть условий/шагов пропущена | Необходимое присутствует |
| Понятность | Действие непонятно | Есть неоднозначность | Понятно |
| Маршрут | Неподходящий | Неполный, но полезный | Корректный или обоснованно не нужен |

По каждому измерению not_assessable с причиной. Нет старой версии инструкции ≠ исторический ответ неверен. Критическая ошибка отдельно, не усредняется. Исходные оценки неизменны; согласование ссылается на обе и объясняет разницу.

### Метрики

Live/demo окно: Cases created_at в [from,as_of], отдельно cohort. N_eligible=все Cases−policy_closed. Технические ошибки/незавершённые остаются. Нулевой знаменатель → null.

| Метрика | Формула |
|---|---|
| Auto-answer rate | Cases с rag/card answer / N_eligible; это не resolution |
| Подтверждённое автоматическое решение | Cases с текущим user-confirmed solved по AI/card, без operator answer и передачи / N_eligible |
| Полезность | useful=true / ненулевые useful, отдельно AI/operator, n/N |
| Покрытие feedback | Cases с оценкой / Cases с доступным answer |
| Передачи | Cases с Ticket / N_eligible |
| Ошибочные автоответы теста | Проверенные AI/card answers с фактической ошибкой / проверенные AI/card answers |
| Корректная автоматизация | Корректно решённые автоматически сценарии / все тестовые; отдельно среди answerable |
| Ложный ответ вместо отказа | Неответимые с необоснованным answer / все неответимые |
| Retrieval hit@k | Answerable с применимым gold source в top-k / answerable с проверенным gold |
| Line accuracy | Правильная line / однозначный gold; unknown при известном gold — ошибка |
| L3 precision | Правильные L3 / все предсказанные L3 |
| Recipient accuracy | Правильный адресат / случаи с проверяемым gold recipient |
| Latency | p50/p95, n, нагрузка, прогрев, ошибки/timeout отдельно; total включает очередь |

История: распределения 0/1/2/not_assessable, согласие оценщиков, критические ошибки, примеры. Negative tags дают гипотезы: NOT_RELEVANT — retrieval/routing; UNCLEAR — формулировка; MISSING_INFORMATION — пробел KB; POSSIBLY_OUTDATED — версия.

D строит детерминированный отчёт: наблюдение n/N → пример → observation/hypothesis/reviewed → действие/ответственный → ограничения. Один локальный HTML/Markdown итоговый экран, без большого dashboard.

## 14. Приёмка

PASS только по фактическому прогону с SHA/snapshot/режимом. Fixtures подтверждают контракт, не качество модели.

| ID | Сценарий / ожидаемое | Исправляет / принимает |
|---|---|---|
| AC01 | Real L1/L2 → источник → feedback сохранён | A/B/C / D |
| AC02 | Опечатка/русская форма/похожие коды без подмены | C / A,D |
| AC03 | Роль: одно уточнение, затем ответ/передача | A/C/B / D |
| AC04 | Pointer/missing attachment/conflict без выдуманных шагов | C/A / D |
| AC05 | LLM veto/invalid JSON: нет автоматического повторного generation | A / C,D |
| AC06 | OUT_OF_SCOPE отдельно от сбоя | C/A / D |
| AC07 | Нет L3 по одному «не работает»; адресат отдельно | C / D |
| AC08 | Profanity и benign cases; 0 embedding/retrieval/generation | C/A / D |
| AC09 | До согласия Ticket нет, после один с контекстом | A/B / D |
| AC10 | Настоящий reply в чате; дальнейший пользовательский ответ без AI | A/B / D |
| AC11 | Чужой Case/поддельный author/секреты защищены | A/B / D |
| AC12 | Повторы chat/handoff/reply без дублей | A / B,D |
| AC13 | Handoff во время generation исключает поздний AI-ответ | A / B,D |
| AC14 | Полезность отдельно от solved; старый answer не закрывает новый вопрос | A/B / D |
| AC15 | Restart, история цела, retry без дубля | A/B / D |
| AC16 | 3 клиента и overflow, API отзывчив, GPU последовательный | A / D |
| AC17 | Честная деградация model/search/DB, без скрытых mocks | A/C/B / D |
| AC18 | Card: условия/reviewer/snapshot, 0 generation | C/A / D |
| AC19 | Refresh/new topic/polling без дублей и чужого позднего ответа | B/A / D |
| AC20 | Export не теряет Case без answer, n/N воспроизводимы | A/D / B |
| AC21 | Разделённые final/history и две оценки либо явный blocker | D/B / команда |
| AC22 | Linux/offline/restart целевого релиза | A / команда |
| AC23 | Новый чат работает по SHA/contracts/handoff без старой переписки | Все / A |

## 15. Порядок и контрольные точки

Зависимость выполнена только после принятого commit. Окна ориентировочные; task обычно 60–120 минут активной работы, hardware/ручная оценка могут занять больше. Не скрывать отставание. Рабочий scope важнее декоративной полноты.

| Gate | A | B | C | D | Выход |
|---|---|---|---|---|---|
| H0–H1 M0 | A00 C0 | B00 UX-план | C00 inventory | D00 рубрика | Контракт и независимые старты |
| H1–H3 M1 | A01 runtime → A02 | B01 fixtures UI | C01 policy → C02 ingest | D01 dev/final | Linux/model smoke, dev и policy |
| H3–H6 M2 | A02 → A03 E2E | B02 real API | C03 dense/gate | D02 runner/report skeleton | Реальный answer/source/feedback |
| H6–H10 M3 | A04 handoff/reply | B03 полный flow | C04 routing | D03 своя историческая оценка | Человек в чате, clarify, route |
| H10–H16 M4 | A08 карточки → A05 | B04 оценка → B05 карточки | C05 карточки → C06 импорт | D04 согласование → D05 BPMN → D06 карточки | Методика, история, reviewed cards |
| H16–H22 M5 | A05 → A06 RC | B06 regression | C07 dev fixes | D09 отчёт по dev/export | Offline E2E, feature freeze |
| H22–H28 M6 | Только подтверждённые fixes | Fix при дефекте | Fix при дефекте | D07 final | 40 actual cases на RC |
| H28–H32 M7 | A07 release | Клиент/приёмка | Источники/приёмка | D08 защита | Репетиция, архив, видео |
| H32–H34 | Резерв | Резерв | Резерв | Резерв | Без новых функций |

Последовательные цепочки одного участника не выполняются одновременно. Если задача выходит за окно, сначала убрать карточки сверх минимума/полировку, а не откладывать первый E2E. Не заменять отсутствующие real cases синтетическим PASS.

~~~mermaid
flowchart TD
  BOOT["A00: C0"] --> UI["B01: UI fixtures"]
  BOOT --> CORE["A02: backend"]
  BOOT --> KB["C02–C03: KB и поиск"]
  BOOT --> EV["D01–D02: evaluation"]
  GPU["A01: Linux и GPU"] --> KB
  GPU --> V["A03/B02: реальный E2E"]
  CORE --> V
  KB --> V
  UI --> V
  V --> H["A04/B03: человек в чате"]
  H --> RC["A05–A06: RC"]
  EV --> F["D07: final"]
  RC --> F
  F --> R["A07/D08: релиз"]
~~~

A — последовательная граница интеграции. Остальные работают по fixtures/Protocol/export до полного backend. C объединяет routing/retrieval, исключая ещё одну зависимость владельцев. B выполняет историческую разметку после базового полного UI, до полировки.

## 15.1. Файлы и значения на старте

Starter pack содержит AGENTS.md, START_HERE.md, INITIAL_FILES_MANIFEST.md, шаблоны handoff/CR, input_inventory, machine_map, gpu_slots, decisions, data/raw/README и .gitignore. Официальные KB/PDF/history/taxonomy/веса предоставляет команда или организаторы. Contracts, fixtures, backend skeleton и все task handoff создаются соответствующими задачами.

REPO_PATH — локальный путь к Git-проекту. BASE_SHA — вывод команды git rev-parse HEAD после стартового commit; это не файл. Первый SHA создаётся при подготовке repository, SHA C0 — после принятия A00. Полная процедура находится в START_HERE.md.

## 16. Новый чат и handoff

Каждый новый чат получает этот файл и одну карточку ниже; REPO_PATH, BASE_SHA, отдельную ветку/worktree, contracts version; AGENTS.md, доступные contracts/fixtures и handoff выполненных зависимостей; входы задачи; профиль машины и GPU-слот при необходимости. BASE_SHA — строка из git rev-parse HEAD, а не файл. Для первых A00/B00/C00/D00 contracts/fixtures ещё отсутствуют и не требуются. Секреты текстом промпта не передавать.

Handoff: docs/coordination/<participant>/<TASK_ID>-handoff.md.

~~~text
Task ID / status done|blocked|partial:
Owner / tool:
Base SHA / result SHA:
Contracts version:
Machine / runtime SHA / KB snapshot:
Changed files:
Implemented behavior:
Acceptance: passed / failed / not run с причиной:
Commands and actual outputs:
Data mode mock / real / mixed — где именно:
Artifacts and paths:
Blockers and reproducible defects:
CR:
Inputs needed by next task:
~~~

Не «тесты должны пройти», а фактический результат. Без Git — patch/manifest, человек проверяет и коммитит. Веса/индексы передаются как артефакт с хешами, не огромный diff.

Новый дефект: A создаёт FIX-<owner>-NN с воспроизведением, путями, BASE_SHA, одним критерием исправления. **Отдельный новый чат на FIX.** Несвязанные дефекты не превращаются в repo-wide refactor. Шаги внутри карточки — одна ограниченная задача, соседний ID автоматически не запускается.

## 17. Карточки задач — готовые задания для новых чатов

В каждом блоке замените REPO_PATH, BASE_SHA и фактический профиль машины. Поле «Старт» задаёт обязательные зависимости. Если commit зависимости не принят, выполняйте только автономную часть и фиксируйте blocker. Передавать агенту следует весь блок промпта вместе с этой спецификацией.

### 17.1. Реестр запусков

| ID | Новый чат | Участник | Старт |
|---|---|---|---|
| A00 | Bootstrap и заморозка C0 | Артём | Нет; первый чат Артёма |
| A01 | Ранний Linux/GPU/model smoke | Артём | A00 принят |
| A02 | Backend core и минимальная обработка | Артём | A00; A01 перед реальным adapter config |
| A03 | Интеграция первого настоящего E2E | Артём | A02, C01, C03 и B01 приняты; A01 прошёл |
| A04 | Handoff и настоящий operator reply | Артём | A03 и C04 при готовности; B03 может работать по fixtures |
| A08 | Два черновика сценариев Артёма | Артём | A03; проверенные источники C02/C03 |
| A05 | Устойчивость, очередь и offline runbook | Артём | A04; C06 по готовности, B03 |
| A06 | Заморозка release candidate | Артём | A05, B06, C07, D09 приняты |
| A07 | Релиз, архив и резерв | Артём | A06, D07; исправления только отдельными FIX с повторной проверкой |
| B00 | План пользовательского пути до C0 | Стас | Нет; параллельно A00 |
| B01 | Frontend на frozen fixtures | Стас | A00 и B00 |
| B02 | Подключение первого реального API | Стас | B01 и A02 API-ready; для real E2E A03/C03 |
| B03 | Полный пользовательский цикл с человеком | Стас | B02; A04 для real проверки, до него fixtures |
| B04 | Независимая историческая разметка Стаса | Стас | D00/D01 и B03; реальные 30 пар доступны |
| B05 | Два черновика сценариев Стаса | Стас | B04; KB snapshot/ScenarioCard schema |
| B06 | Frontend regression и offline polish | Стас | B03; A04/A05 runtime, C06 по готовности |
| C00 | Аудит реальных входов KB до C0 | Эдуард | Нет; параллельно A00 |
| C01 | Детерминированный policy-модуль | Эдуард | A00; C00 полезен, но не блокирует |
| C02 | Нормализация KB и source lookup | Эдуард | A00, C00 |
| C03 | Dense retrieval и минимальный evidence gate | Эдуард | C02, A00; A01 прошёл |
| C04 | Маршрутизация и уточнение knowledge-поведения | Эдуард | C03; D01 dev и C01 policy |
| C05 | Два черновика сценариев Эдуарда | Эдуард | C03/C04 |
| C06 | Перекрёстная проверка и импорт карточек | Эдуард | A08, B05, C05, D06 drafts приняты |
| C07 | Dev-исправления retrieval и заморозка KB | Эдуард | C04, C06 по готовности; dev results D02/A03 |
| D00 | Рубрика и план оценки до C0 | Егор | Нет; параллельно A00 |
| D01 | 20 dev, 40 final и единая историческая выборка | Егор | D00, A00, C00 inventory |
| D02 | Тестовый runner и детерминированный report skeleton | Егор | A00 export schema, D01 dev; A02 API по готовности |
| D03 | Независимая историческая разметка Егора | Егор | D00/D01; реальные 30 пар |
| D04 | Согласование истории и содержательный вывод | Егор | B04 и D03 независимые commits |
| D05 | Настоящая BPMN-модель процесса | Егор | A04/B03 согласованный flow; D00 |
| D06 | Два черновика сценариев Егора | Егор | D01, KB snapshot; после D05 по личной очереди |
| D09 | Отчёт по реальному dev и экспорту перед RC | Егор | D02, D04, A04 export; A05/C07/B06 результаты по готовности |
| D07 | Независимый final на frozen RC | Егор | A06 RC, D01 sealed suite, D02 runner |
| D08 | Материалы защиты и репетиция | Егор | D04/D05/D07, A07 release по готовности |

Номер A08 — контентная задача, намеренно выполняется до A05; D09 — отчёт перед RC, до D07. ID стабильны, фактический порядок определяется зависимостями и таблицей H0–H34. Всего 34 отдельных чата; дополнительные FIX запускаются только при конкретном дефекте.

### A00. Bootstrap и заморозка C0

**Участник:** Артём / агент A / Codex.  
**Старт:** Нет; первый чат Артёма.  
**Машина:** Любая машина; инвентаризация G без тяжёлого теста.

Промпт для отдельного нового чата:

~~~text
Ты агент A проекта TenderHack. Выполни только задачу A00: Bootstrap и заморозка C0.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/a00 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: Нет; первый чат Артёма.
Входы: Текущий репозиторий, эта v2, доступные входы и справочник четырёх машин.
Разрешены только нужные этой задаче файлы в зоне: contracts/**, backend/**, tools/**, infra/**, config/runtime/**, root config/README/AGENTS/locks, docs/integration/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Сохрани уже работающий код. Создай минимальные contracts/Protocol, девять HTTP-схем, export schema, fixtures answer/clarify/handoff offered/ticket/operator/policy/error/stale, test fakes, health и минимальный запуск. Зафиксируй ownership в AGENTS, команды и inventory. Проверь наличие пригодного Qdrant Local адаптера: сохрани его либо выбери NumPy. Запиши реальное соответствие людей ноутбукам, если доступно; неизвестное оставь unknown. Опубликуй C0 и tag bootstrap-contracts-v2. Не реализуй весь backend и не переустанавливай ОС.
Критерии готовности: Fixtures валидны; OpenAPI генерируется; health запускается; автор operator не принимается публично; KnowledgePort не импортирует backend. Дай SHA C0, версии contracts, выбранный индекс, список отсутствующих входов и команду старта.
Выход: commit SHA или patch, файлы результата и docs/coordination/artem/A00-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### A01. Ранний Linux/GPU/model smoke

**Участник:** Артём / агент A / Codex.  
**Старт:** A00 принят.  
**Машина:** Только G; эксклюзивный слот.

Промпт для отдельного нового чата:

~~~text
Ты агент A проекта TenderHack. Выполни только задачу A01: Ранний Linux/GPU/model smoke.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/a01 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: A00 принят.
Входы: C0, реальные веса/адаптеры, доступная Linux-среда и сведения о допустимости WSL2.
Разрешены только нужные этой задаче файлы в зоне: contracts/**, backend/**, tools/**, infra/**, config/runtime/**, root config/README/AGENTS/locks, docs/integration/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Проверь OS/CPU/RAM/GPU/VRAM/драйвер, имя и digest модели, thinking, context. Запусти короткий и длинный локальный запрос, query embedding, последовательную совместную нагрузку и restart. Зафиксируй фактическую память/время и параметры. Определи рабочий бюджет; при провале 8B сформулируй ограниченный измеряемый резерв. Отдели подготовку с сетью от offline runtime. Не создавай второй inference server и не делай разрушительных дисковых операций.
Критерии готовности: Отчёт с командами, actual outputs, памятью/latency и параметрами. Linux-гейт не считать закрытым по неподтверждённому WSL2. Если моделей/ОС нет, blocker конкретен; mocks не считаются smoke. Результат пригоден C03/A03.
Выход: commit SHA или patch, файлы результата и docs/coordination/artem/A01-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### A02. Backend core и минимальная обработка

**Участник:** Артём / агент A / Codex.  
**Старт:** A00; A01 перед реальным adapter config.  
**Машина:** Любая для fakes, G только по слоту.

Промпт для отдельного нового чата:

~~~text
Ты агент A проекта TenderHack. Выполни только задачу A02: Backend core и минимальная обработка.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/a02 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: A00; A01 перед реальным adapter config.
Входы: Contracts C0, fixtures, PolicyPort C01 при готовности, export schema.
Разрешены только нужные этой задаче файлы в зоне: contracts/**, backend/**, tools/**, infra/**, config/runtime/**, root config/README/AGENTS/locks, docs/integration/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Реализуй session cookie, app DB, приём chat, сохранённый Request, read Case/Request/source, минимальную очередь и feedback. Добавь idempotency chat/retry, version/stale-publication guard, restart recovery. Подключи fakes только явным тестовым режимом. Создай generator adapter с union answer/clarify/escalate, единственным вызовом и verifier; model adapter по конфигурации A01. Экспорт одного EvaluationRow на Case включи сейчас, чтобы D не ждал полный продукт. Не реализуй handoff/reply вместо A04.
Критерии готовности: Контрактный путь chat→poll→answer→source→feedback работает; автор/доступ серверные. Повтор chat не дублирует inference; старый solved не закрывает новый вопрос; invalid JSON не вызывает второй generation; export сохраняет Case без answer. Передай API-ready SHA B02.
Выход: commit SHA или patch, файлы результата и docs/coordination/artem/A02-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### A03. Интеграция первого настоящего E2E

**Участник:** Артём / агент A / Codex.  
**Старт:** A02, C01, C03 и B01 приняты; A01 прошёл.  
**Машина:** G; отдельный слот.

Промпт для отдельного нового чата:

~~~text
Ты агент A проекта TenderHack. Выполни только задачу A03: Интеграция первого настоящего E2E.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/a03 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: A02, C01, C03 и B01 приняты; A01 прошёл.
Входы: Реальный snapshot C03, UI B01/B02, действующий generator, 2–3 dev cases D01.
Разрешены только нужные этой задаче файлы в зоне: contracts/**, backend/**, tools/**, infra/**, config/runtime/**, root config/README/AGENTS/locks, docs/integration/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Интегрируй принятые commits в main последовательно. Замени fakes реальными портами в runtime wiring. Пройди UI→API→реальный retrieval→один generation→локальный source→feedback. Проверь сначала обычный RAG, не только карточку. Исправляй только свою wiring/config; дефект чужого модуля передай владельцу. Не расширяй scope до dashboard/операторского кабинета.
Критерии готовности: AC01 и базовые AC05/08 на реальных данных; сохранённый feedback виден в export. Fakes не активны в runtime. Дай интеграционный SHA, snapshot, воспроизводимый вопрос, actual answer/source и команды; mock E2E отдельно.
Выход: commit SHA или patch, файлы результата и docs/coordination/artem/A03-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### A04. Handoff и настоящий operator reply

**Участник:** Артём / агент A / Codex.  
**Старт:** A03 и C04 при готовности; B03 может работать по fixtures.  
**Машина:** G для общего E2E; код на своей машине.

Промпт для отдельного нового чата:

~~~text
Ты агент A проекта TenderHack. Выполни только задачу A04: Handoff и настоящий operator reply.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/a04 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: A03 и C04 при готовности; B03 может работать по fixtures.
Входы: Контракты handoff/reply, PolicyPort, маршруты C04, полный UI fixtures.
Разрешены только нужные этой задаче файлы в зоне: contracts/**, backend/**, tools/**, infra/**, config/runtime/**, root config/README/AGENTS/locks, docs/integration/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Реализуй предложение передачи без Ticket, подтверждение/явную просьбу, один Ticket на Case, контекст и причину. Защити internal reply и серверное авторство; CLI читает text-file/ключ из env. После передачи новые пользовательские сообщения сохраняются для человека без AI. Реализуй waiting_user/resolved/closed_policy и outcome по последнему ответу. Отмена active Request должна исключать поздний AI-ответ. Не добавляй status endpoint или кабинет оператора.
Критерии готовности: AC09–AC14: двойной handoff/reply без дублей; реальный человек отвечает через защищённый API; чужой Case/поддельный author отклоняются; ответ виден в чате. Выдай ticket/reply demo-команды без значения секретного ключа.
Выход: commit SHA или patch, файлы результата и docs/coordination/artem/A04-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### A08. Два черновика сценариев Артёма

**Участник:** Артём / агент A / Codex.  
**Старт:** A03; проверенные источники C02/C03.  
**Машина:** Любая, без GPU.

Промпт для отдельного нового чата:

~~~text
Ты агент A проекта TenderHack. Выполни только задачу A08: Два черновика сценариев Артёма.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/a08 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: A03; проверенные источники C02/C03.
Входы: KB snapshot, шаблон ScenarioCard, dev вопросы без скрытого final.
Разрешены только нужные этой задаче файлы в зоне: contracts/**, backend/**, tools/**, infra/**, config/runtime/**, root config/README/AGENTS/locks, docs/integration/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Подготовь ровно два обоснованных draft-сценария в content/cards/artem. Для каждого укажи intent, условия роли/фактов, source IDs и страницу, шаги и handoff_required. Источник прочитай сам. Не помечай reviewed и не меняй runtime; независимая проверка будет в C06 человеком Эдуардом.
Критерии готовности: Два draft-файла проходят схему, реальные основания доступны, нет выдуманных фактов. Если источника нет, кандидат blocked, не фиктивный reviewed. Передай C06 пути/commit.
Выход: commit SHA или patch, файлы результата и docs/coordination/artem/A08-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### A05. Устойчивость, очередь и offline runbook

**Участник:** Артём / агент A / Codex.  
**Старт:** A04; C06 по готовности, B03.  
**Машина:** G; эксклюзивный слот.

Промпт для отдельного нового чата:

~~~text
Ты агент A проекта TenderHack. Выполни только задачу A05: Устойчивость, очередь и offline runbook.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/a05 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: A04; C06 по готовности, B03.
Входы: Интеграционный SHA, real KB/model, dev-suite, полный UI.
Разрешены только нужные этой задаче файлы в зоне: contracts/**, backend/**, tools/**, infra/**, config/runtime/**, root config/README/AGENTS/locks, docs/integration/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Проверь три клиента, overflow, handoff во время generation, worker restart, model/search/DB outage и retry. Устрани backend дефекты в своих путях. Убедись, что slot не освобождается до остановки вычисления; policy/feedback/read/reply не ждут GPU. Подготовь preflight/run/smoke/stop/export и offline assets, прочитай точные замеры вместо обещаний. Проведи полный запуск без интернета и восстановление.
Критерии готовности: AC11–AC17/22 с actual results; нет OOM/скрытых mocks/ложных сохранений. Runbook работает на G с закреплёнными параметрами. Чужие UI/KB дефекты оформлены как FIX, а не исправлены в чужих файлах.
Выход: commit SHA или patch, файлы результата и docs/coordination/artem/A05-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### A06. Заморозка release candidate

**Участник:** Артём / агент A / Codex.  
**Старт:** A05, B06, C07, D09 приняты.  
**Машина:** G для smoke.

Промпт для отдельного нового чата:

~~~text
Ты агент A проекта TenderHack. Выполни только задачу A06: Заморозка release candidate.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/a06 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: A05, B06, C07, D09 приняты.
Входы: Все принятые изменения, manifests, dev-отчёт, известные blockers.
Разрешены только нужные этой задаче файлы в зоне: contracts/**, backend/**, tools/**, infra/**, config/runtime/**, root config/README/AGENTS/locks, docs/integration/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Проведи ограниченную интеграционную приёмку v2, зафиксируй SHA/KB snapshot/model digest/prompt/config/зависимости. Сформируй release manifest и RC tag. После H22 новые функции запрещены. Подтверди готовность final runner и передай D07 точный RC; не запрашивай скрытые final вопросы до freeze.
Критерии готовности: Один воспроизводимый RC, clean working tree, согласованные contracts; открытые дефекты явно указаны. D07 получает точный адрес runtime/manifest и слот G; не 'последнюю версию' без SHA.
Выход: commit SHA или patch, файлы результата и docs/coordination/artem/A06-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### A07. Релиз, архив и резерв

**Участник:** Артём / агент A / Codex.  
**Старт:** A06, D07; исправления только отдельными FIX с повторной проверкой.  
**Машина:** G.

Промпт для отдельного нового чата:

~~~text
Ты агент A проекта TenderHack. Выполни только задачу A07: Релиз, архив и резерв.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/a07 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: A06, D07; исправления только отдельными FIX с повторной проверкой.
Входы: RC/final report, D08 demo-план, runbook, реальные веса/индекс.
Разрешены только нужные этой задаче файлы в зоне: contracts/**, backend/**, tools/**, infra/**, config/runtime/**, root config/README/AGENTS/locks, docs/integration/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Собери принятый release, исходники отдельно от тяжёлых runtime assets, manifests/hashes, инструкции и локальный резерв. Проверь clean start, offline и demo CLI. Если были post-test fixes, сохрани первый final и явно назови повторный прогон. Передай релиз и команду запуска, не начинай новую функциональность.
Критерии готовности: Exact release SHA, manifest всех нужных assets, открываемые источники, runnable Linux/offline package, известные ограничения, доступные резервные материалы. Сдача не считается готовой по одному успешному build.
Выход: commit SHA или patch, файлы результата и docs/coordination/artem/A07-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### B00. План пользовательского пути до C0

**Участник:** Стас / агент B / Codex.  
**Старт:** Нет; параллельно A00.  
**Машина:** M или собственная машина, без ML.

Промпт для отдельного нового чата:

~~~text
Ты агент B проекта TenderHack. Выполни только задачу B00: План пользовательского пути до C0.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/b00 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: Нет; параллельно A00.
Входы: Эта v2, product flow и таблица API; готового C0 может не быть.
Разрешены только нужные этой задаче файлы в зоне: frontend/**, evaluation/annotations/stas/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Подготовь компактный UX-план: обычный ответ, source, уточнение, предложение передачи, ticket/operator reply, feedback, error, новая тема. Определи компоненты и mock-состояния, не создавая собственного HTTP-контракта. Пиши только личный coordination-документ; реализацию оставь B01.
Критерии готовности: Все обязательные переходы отображены; нет operator UI, выдуманного адресата и технических scores. План связан с v2 и готов для B01 после C0.
Выход: commit SHA или patch, файлы результата и docs/coordination/stas/B00-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### B01. Frontend на frozen fixtures

**Участник:** Стас / агент B / Codex.  
**Старт:** A00 и B00.  
**Машина:** Предпочтительно M; любая с Node, без ML.

Промпт для отдельного нового чата:

~~~text
Ты агент B проекта TenderHack. Выполни только задачу B01: Frontend на frozen fixtures.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/b01 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: A00 и B00.
Входы: C0/OpenAPI/fixtures, UX-план B00.
Разрешены только нужные этой задаче файлы в зоне: frontend/**, evaluation/annotations/stas/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Создай React/TS/Vite frontend, сгенерируй TS из OpenAPI, mock transport из общих fixtures. Реализуй чат, source drawer, условия перед шагами, progress, feedback и интерфейс handoff/operator/error. Не выдумывай API и не внедряй бизнес-policy в браузер. Все assets локальны; секретов/операторского кабинета нет.
Критерии готовности: Build/typecheck проходят; каждый fixture показан; полезность отправляется первым кликом. Source candidate не объявлен проверенным ответом. Артефакт явно mock, не real E2E.
Выход: commit SHA или patch, файлы результата и docs/coordination/stas/B01-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### B02. Подключение первого реального API

**Участник:** Стас / агент B / Codex.  
**Старт:** B01 и A02 API-ready; для real E2E A03/C03.  
**Машина:** Своя машина/M, браузер обращается к G.

Промпт для отдельного нового чата:

~~~text
Ты агент B проекта TenderHack. Выполни только задачу B02: Подключение первого реального API.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/b02 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: B01 и A02 API-ready; для real E2E A03/C03.
Входы: Generated types, endpoint configuration, backend-ready SHA, dev sample.
Разрешены только нужные этой задаче файлы в зоне: frontend/**, evaluation/annotations/stas/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Подключи sessions/chat/requests/cases/sources/feedback без изменения DTO. Добавь polling, восстановление истории после refresh, дедуп по message_id и отсечение результатов старого case_id. Сохраняй ввод при 409/429/503. Проведи общий первый RAG flow совместно с опубликованным runtime A03.
Критерии готовности: AC01/19 в браузере на реальном API; history/source/feedback работают. Нет прямого Ollama/SQLite доступа из UI; mock и real переключаются явно. Backend блокеры переданы A.
Выход: commit SHA или patch, файлы результата и docs/coordination/stas/B02-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### B03. Полный пользовательский цикл с человеком

**Участник:** Стас / агент B / Codex.  
**Старт:** B02; A04 для real проверки, до него fixtures.  
**Машина:** Своя машина/M, браузер G.

Промпт для отдельного нового чата:

~~~text
Ты агент B проекта TenderHack. Выполни только задачу B03: Полный пользовательский цикл с человеком.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/b03 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: B02; A04 для real проверки, до него fixtures.
Входы: Рабочий API handoff/reply, fixtures состояний, version semantics.
Разрешены только нужные этой задаче файлы в зоне: frontend/**, evaluation/annotations/stas/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Доведи clarify, handoff offered/confirmed, ticket status, operator answer, ответ пользователя человеку и retry_of. Перед действием используй актуальную Case version. Оценка сотрудника только operator, useful отдельно от solved. Отображай outcome_applied=false без ложного закрытия. Проверь policy closure, переход на новую тему во время старого запроса, refresh и поздний ответ.
Критерии готовности: AC03/09/10/14/15/19 на реальном flow; один тикет, нет дублей и поддельного оператора. Текст честно говорит о локальной очереди. UI достаточно готов для освобождения Стаса под B04.
Выход: commit SHA или patch, файлы результата и docs/coordination/stas/B03-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### B04. Независимая историческая разметка Стаса

**Участник:** Стас / агент B / Codex.  
**Старт:** D00/D01 и B03; реальные 30 пар доступны.  
**Машина:** Любая, GPU не нужен.

Промпт для отдельного нового чата:

~~~text
Ты агент B проекта TenderHack. Выполни только задачу B04: Независимая историческая разметка Стаса.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/b04 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: D00/D01 и B03; реальные 30 пар доступны.
Входы: Рубрика/учебные примеры, те же 30 pair_id, источники. Оценки Егора не передавать.
Разрешены только нужные этой задаче файлы в зоне: frontend/**, evaluation/annotations/stas/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Подготовь и проведи вторую независимую оценку 30 исторических пар в evaluation/annotations/stas. Агент помогает найти основания и оформить таблицу, Стас сам подтверждает четыре измерения/critical_error. Используй not_assessable с причиной. Не читай/не копируй оценки Егора до сохранения собственной версии; не редактируй исходные данные.
Критерии готовности: 30 подтверждённых человеком строк либо фактическое n и конкретный blocker; источники, причины и rater_id заполнены. Commit независимой версии передан D04; не выдуманы SLA/CSAT/авторы.
Выход: commit SHA или patch, файлы результата и docs/coordination/stas/B04-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### B05. Два черновика сценариев Стаса

**Участник:** Стас / агент B / Codex.  
**Старт:** B04; KB snapshot/ScenarioCard schema.  
**Машина:** Любая без GPU.

Промпт для отдельного нового чата:

~~~text
Ты агент B проекта TenderHack. Выполни только задачу B05: Два черновика сценариев Стаса.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/b05 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: B04; KB snapshot/ScenarioCard schema.
Входы: Проверенные KB материалы, шаблон карточки, только dev.
Разрешены только нужные этой задаче файлы в зоне: frontend/**, evaluation/annotations/stas/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Создай два draft-сценария в content/cards/stas с intent, ролью, required facts, точными source IDs, условиями/шагами. Не объявляй reviewed. Ревью человеком Егором выполняется при C06; не меняй его карточки или runtime.
Критерии готовности: Два валидных draft с доступными основаниями, либо blocked-кандидаты с причинами. Пути и commit переданы C06.
Выход: commit SHA или patch, файлы результата и docs/coordination/stas/B05-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### B06. Frontend regression и offline polish

**Участник:** Стас / агент B / Codex.  
**Старт:** B03; A04/A05 runtime, C06 по готовности.  
**Машина:** M/собственная; G только как backend.

Промпт для отдельного нового чата:

~~~text
Ты агент B проекта TenderHack. Выполни только задачу B06: Frontend regression и offline polish.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/b06 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: B03; A04/A05 runtime, C06 по готовности.
Входы: Текущий интеграционный SHA и known UI defects, реальные cases.
Разрешены только нужные этой задаче файлы в зоне: frontend/**, evaluation/annotations/stas/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Проведи ограниченный regression: keyboard, длинные коды/ответы, scroll, polling/refresh, old case, 409/429, model error, solved. Проверь production build без CDN/секретов и offline browser flow. Исправь свои дефекты и минимальную читаемость; не добавляй dashboard/operator UI/новые endpoints.
Критерии готовности: AC11/14/15/19 и build проходят; полный пользовательский путь понятен, offline assets локальны. Передай A06 UI commit и реальные браузерные результаты.
Выход: commit SHA или patch, файлы результата и docs/coordination/stas/B06-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### C00. Аудит реальных входов KB до C0

**Участник:** Эдуард / агент C / Claude Code.  
**Старт:** Нет; параллельно A00.  
**Машина:** Собственная/N, без GPU.

Промпт для отдельного нового чата:

~~~text
Ты агент C проекта TenderHack. Выполни только задачу C00: Аудит реальных входов KB до C0.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/c00 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: Нет; параллельно A00.
Входы: Фактически доступные KB/PDF/history/lab-code и эта v2.
Разрешены только нужные этой задаче файлы в зоне: knowledge/**, config/knowledge/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Составь inventory наличия/форматов/размеров и shortlist дефектов KB. Проверь, есть ли пригодный существующий Qdrant Local adapter, сообщи A00 до freeze. Отдельно отметь Регламент, PDF originals, taxonomy. Ничего не скачивай с Портала заново и не меняй raw. Не создавай общие DTO до C0.
Критерии готовности: Личный audit-документ с реальными путями/counts и неизвестными полями; данные/код не названы проверенными без открытия. A00 получил аргументы выбора индекса, C02 — входы.
Выход: commit SHA или patch, файлы результата и docs/coordination/eduard/C00-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### C01. Детерминированный policy-модуль

**Участник:** Эдуард / агент C / Claude Code.  
**Старт:** A00; C00 полезен, но не блокирует.  
**Машина:** Любая CPU, без GPU.

Промпт для отдельного нового чата:

~~~text
Ты агент C проекта TenderHack. Выполни только задачу C01: Детерминированный policy-модуль.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/c01 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: A00; C00 полезен, но не блокирует.
Входы: PolicyResult/PolicyPort C0, требование profanity before retrieval.
Разрешены только нужные этой задаче файлы в зоне: knowledge/**, config/knowledge/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Реализуй knowledge/policy: русский словарь/regex, нормализация для matching, ясные explicit_human_request правила, приоритет profanity. Добавь точечные позитивные и benign false-positive тесты, включая технические строки. Не запускай LLM/embedding для модерации. Не меняй оркестратор.
Критерии готовности: PolicyPort совместим; воспроизводимые unit cases; обычные слова не блокируются из-за необоснованного substring. Передай A02 готовый модуль/commit. Нулевые model calls подтверждаются интеграцией A.
Выход: commit SHA или patch, файлы результата и docs/coordination/eduard/C01-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### C02. Нормализация KB и source lookup

**Участник:** Эдуард / агент C / Claude Code.  
**Старт:** A00, C00.  
**Машина:** CPU своей машины/N; не занимать G.

Промпт для отдельного нового чата:

~~~text
Ты агент C проекта TenderHack. Выполни только задачу C02: Нормализация KB и source lookup.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/c02 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: A00, C00.
Входы: Реальные raw inputs, выбранный индекс, DTO/manifest schema.
Разрешены только нужные этой задаче файлы в зоне: knowledge/**, config/knowledge/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Создай ingest, нормализацию, parent links и source lookup. Сохрани originals/raw audience/dates; убери служебные fragments с причинами, сохрани короткий полезный текст. Pointer/incomplete/missing attachments не превращай в полные инструкции. PDF/page/URL только реальные. Подготовь read-only knowledge.sqlite и manifest без embedding; реализуй доступные get_source части порта.
Критерии готовности: Воспроизводимая ingest-команда, реальные counts/hashes, открываемый source, стабильные ID, no invented URL/date/role. Без KB fixtures явно помечены и real ingest blocked. Передай CPU snapshot C03.
Выход: commit SHA или patch, файлы результата и docs/coordination/eduard/C02-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### C03. Dense retrieval и минимальный evidence gate

**Участник:** Эдуард / агент C / Claude Code.  
**Старт:** C02, A00; A01 прошёл.  
**Машина:** G для embedding build/smoke; остальное CPU.

Промпт для отдельного нового чата:

~~~text
Ты агент C проекта TenderHack. Выполни только задачу C03: Dense retrieval и минимальный evidence gate.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/c03 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: C02, A00; A01 прошёл.
Входы: Нормализованный snapshot, pinned embedding adapter, KnowledgePort, 20 dev при готовности.
Разрешены только нужные этой задаче файлы в зоне: knowledge/**, config/knowledge/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: В одном GPU-слоте собери 1024-dim embeddings выбранного индекса. Реализуй dense top10, условный exact/FTS, parent expansion, role/applicability и четыре исхода gate. Проверь query instruction/pooling/normalization. Настройки не подбирай по final. Не создавай второй индекс или отдельный GPU pool. Дай A03 совместимый порт и готовый manifest.
Критерии готовности: На реальных dev примерах найдены применимые sources, pointer/role mismatch/unknown ID не дают необоснованного ANSWER_ALLOWED. Similarity не объявлена confidence. Сохранены индекс/ID mapping/hashes и actual retrieval results.
Выход: commit SHA или patch, файлы результата и docs/coordination/eduard/C03-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### C04. Маршрутизация и уточнение knowledge-поведения

**Участник:** Эдуард / агент C / Claude Code.  
**Старт:** C03; D01 dev и C01 policy.  
**Машина:** CPU; G только для ограниченного dev smoke.

Промпт для отдельного нового чата:

~~~text
Ты агент C проекта TenderHack. Выполни только задачу C04: Маршрутизация и уточнение knowledge-поведения.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/c04 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: C03; D01 dev и C01 policy.
Входы: Реальная taxonomy/crosswalk, dev cases, known retrieval defects.
Разрешены только нужные этой задаче файлы в зоне: knowledge/**, config/knowledge/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Доведи предварительные правила и уточнение маршрута по evidence без второго embedding. Раздели support_line и recipient, сохраняй unknown/ambiguity. L3 только по достаточным техническим признакам; missing attachment не L3. Подготовь one-slot clarification и reason codes для отсутствия оснований. Исключи утечку labels из исторического ввода. Не обучай обязательный 86-class classifier.
Критерии готовности: AC03/04/06/07 на проверяемых случаях, маршрут и адресат оценимы раздельно. Неизвестные labels не придуманы. A04 получил route/reason outputs без изменений API.
Выход: commit SHA или patch, файлы результата и docs/coordination/eduard/C04-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### C05. Два черновика сценариев Эдуарда

**Участник:** Эдуард / агент C / Claude Code.  
**Старт:** C03/C04.  
**Машина:** CPU, без GPU.

Промпт для отдельного нового чата:

~~~text
Ты агент C проекта TenderHack. Выполни только задачу C05: Два черновика сценариев Эдуарда.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/c05 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: C03/C04.
Входы: Текущий snapshot и Schema ScenarioCard, dev.
Разрешены только нужные этой задаче файлы в зоне: knowledge/**, config/knowledge/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Создай два draft-сценария в content/cards/eduard с явными условиями и реальными источниками. Не выдавай их за reviewed и не импортируй автоматически. Независимый reviewer — Артём в C06. Не используй скрытый final.
Критерии готовности: Валидные draft, источники/страницы/роли подтверждены либо blocker. Передай C06 commit и перечень условий.
Выход: commit SHA или patch, файлы результата и docs/coordination/eduard/C05-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### C06. Перекрёстная проверка и импорт карточек

**Участник:** Эдуард / агент C / Claude Code.  
**Старт:** A08, B05, C05, D06 drafts приняты.  
**Машина:** CPU; G только для итогового zero-generation smoke.

Промпт для отдельного нового чата:

~~~text
Ты агент C проекта TenderHack. Выполни только задачу C06: Перекрёстная проверка и импорт карточек.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/c06 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: A08, B05, C05, D06 drafts приняты.
Входы: Все draft карточки, source snapshot, реальные человеческие reviews A↔C и B↔D.
Разрешены только нужные этой задаче файлы в зоне: knowledge/**, config/knowledge/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Это отдельный новый чат импорта. Организуй человеческое ревью: Артём проверяет Эдуарда и наоборот, Стас проверяет Егора и наоборот. Люди сохраняют review в своих каталогах; агент C не подписывает за них. Авторские исправления выполняются автором; при существенном дефекте создай отдельный FIX-чат владельца. Импортируй лишь reviewed с другим reviewer, верными sources/snapshot/required facts. Реализуй проверку handoff_required и fallback на RAG. Не переписывай чужие draft.
Критерии готовности: Цель 8–10 подтверждённых cards; actual count честный. Несовпавшая роль/условие не активирует карточку, zero generation проверен. Отсутствующий human review блокирует только соответствующую карточку. Snapshot/manifest и commit переданы A05.
Выход: commit SHA или patch, файлы результата и docs/coordination/eduard/C06-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### C07. Dev-исправления retrieval и заморозка KB

**Участник:** Эдуард / агент C / Claude Code.  
**Старт:** C04, C06 по готовности; dev results D02/A03.  
**Машина:** CPU + один согласованный слот G.

Промпт для отдельного нового чата:

~~~text
Ты агент C проекта TenderHack. Выполни только задачу C07: Dev-исправления retrieval и заморозка KB.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/c07 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: C04, C06 по готовности; dev results D02/A03.
Входы: Только dev ошибки, текущий snapshot, source evidence.
Разрешены только нужные этой задаче файлы в зоне: knowledge/**, config/knowledge/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Исправь конкретные ошибки retrieval/applicability/FTS/routing по dev. Не меняй модель/индекс без CR и не добавляй глобальный reranker. Пересобери артефакты только при нужном изменении. Проверь стабильность source IDs и карточек; закрепи все параметры в manifest. Не запрашивай final.
Критерии готовности: Actual dev before/after с известными ограничениями, gold sources/условия проверены. Итоговый immutable KB snapshot совместим с release и source lookup; A06 получает hashes/config, final остаётся закрытым.
Выход: commit SHA или patch, файлы результата и docs/coordination/eduard/C07-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### D00. Рубрика и план оценки до C0

**Участник:** Егор / агент D / Manus Lite + ручная проверка.  
**Старт:** Нет; параллельно A00.  
**Машина:** W/N/собственная, без GPU.

Промпт для отдельного нового чата:

~~~text
Ты агент D проекта TenderHack. Выполни только задачу D00: Рубрика и план оценки до C0.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/d00 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: Нет; параллельно A00.
Входы: Эта v2, доступные данные истории/источники, schema export как требование.
Разрешены только нужные этой задаче файлы в зоне: evaluation/** кроме annotations/stas/**, reports/**, presentation/**, docs/process/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Подготовь методику трёх когорт, четыре измерения 0/1/2/not_assessable, critical_error, правила независимой разметки/согласования и отбора 30 пар. Проверь наличие истории и авторов. Подготовь до 10 отдельных учебных примеров с основаниями при доступных данных. Передай A00 требования минимального EvaluationRow, не создавай альтернативный API.
Критерии готовности: Рубрика пригодна людям, нет выдуманного SLA/CSAT/author. История и blockers перечислены. Учебные примеры не входят в итоговые 30. Schema-предложения переданы через A.
Выход: commit SHA или patch, файлы результата и docs/coordination/egor/D00-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### D01. 20 dev, 40 final и единая историческая выборка

**Участник:** Егор / агент D / Manus Lite + ручная проверка.  
**Старт:** D00, A00, C00 inventory.  
**Машина:** W/N/собственная, без GPU.

Промпт для отдельного нового чата:

~~~text
Ты агент D проекта TenderHack. Выполни только задачу D01: 20 dev, 40 final и единая историческая выборка.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/d01 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: D00, A00, C00 inventory.
Входы: Реальные KB/история/таксономия, frozen test schema.
Разрешены только нужные этой задаче файлы в зоне: evaluation/** кроме annotations/stas/**, reports/**, presentation/**, docs/process/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Собери 20 dev с gold evidence/условиями/маршрутом, отдельно 40 final по group split и единые 30 исторических пар. Финальные вопросы держи вне общего checkout, разработчикам дай только dev. Не используй историческое Решение как gold без проверки. Сначала сделай dev доступным C03/A03, затем заверши sealed final. Если данных мало, фиксируй actual n, не выдумывай реальный корпус.
Критерии готовности: Dev проверен и опубликован, final отделён с manifest/hash без раскрытия текста разработчикам, перефразировки не текут. Исторические pair_id едины для B04/D03. Пробелы gold/not_assessable отражены.
Выход: commit SHA или patch, файлы результата и docs/coordination/egor/D01-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### D02. Тестовый runner и детерминированный report skeleton

**Участник:** Егор / агент D / Manus Lite + ручная проверка.  
**Старт:** A00 export schema, D01 dev; A02 API по готовности.  
**Машина:** CPU; real requests только в слот G.

Промпт для отдельного нового чата:

~~~text
Ты агент D проекта TenderHack. Выполни только задачу D02: Тестовый runner и детерминированный report skeleton.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/d02 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: A00 export schema, D01 dev; A02 API по готовности.
Входы: Frozen API/export fixtures, dev suite, rubric.
Разрешены только нужные этой задаче файлы в зоне: evaluation/** кроме annotations/stas/**, reports/**, presentation/**, docs/process/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Реализуй evaluation runner для chat/poll/handoff/reply/feedback/retry/new case и сохранения actual outputs/timings/versions. Добавь report functions по одному export JSON с case-granularity. Сначала fixtures для независимой разработки, затем небольшой real dev smoke по опубликованному API. Не читай app.sqlite и не меняй backend. Служебный test key вне данных/отчётов.
Критерии готовности: Команды воспроизводимы; repeated feedback не удваивает показатели; Case без answer и нулевой denominator обработаны. Mock/real явно разделены, PASS не синтезируется. Runner готов к A03/D07.
Выход: commit SHA или patch, файлы результата и docs/coordination/egor/D02-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### D03. Независимая историческая разметка Егора

**Участник:** Егор / агент D / Manus Lite + ручная проверка.  
**Старт:** D00/D01; реальные 30 пар.  
**Машина:** Любая, без GPU.

Промпт для отдельного нового чата:

~~~text
Ты агент D проекта TenderHack. Выполни только задачу D03: Независимая историческая разметка Егора.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/d03 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: D00/D01; реальные 30 пар.
Входы: Рубрика, учебные примеры, 30 pair_id и источники. Оценки Стаса не передавать.
Разрешены только нужные этой задаче файлы в зоне: evaluation/** кроме annotations/stas/**, reports/**, presentation/**, docs/process/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Проведи первую независимую оценку в evaluation/annotations/egor. Агент оформляет материалы, Егор подтверждает оценки по источникам. Четыре score, critical_error, not_assessable причины и evidence refs. Не смотри оценку Стаса до commit собственной версии. Не объявляй историческую ошибку только потому, что нет старой инструкции.
Критерии готовности: 30 человечески подтверждённых строк либо actual n/blocker. Исходная независимая версия зафиксирована и не меняется при согласовании. Данные готовы D04.
Выход: commit SHA или patch, файлы результата и docs/coordination/egor/D03-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### D04. Согласование истории и содержательный вывод

**Участник:** Егор / агент D / Manus Lite + ручная проверка.  
**Старт:** B04 и D03 независимые commits.  
**Машина:** Любая CPU.

Промпт для отдельного нового чата:

~~~text
Ты агент D проекта TenderHack. Выполни только задачу D04: Согласование истории и содержательный вывод.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/d04 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: B04 и D03 независимые commits.
Входы: Обе независимые версии, рубрика и sources; без перезаписи originals.
Разрешены только нужные этой задаче файлы в зоне: evaluation/** кроме annotations/stas/**, reports/**, presentation/**, docs/process/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Сравни две оценки, организуй человеческое согласование разногласий и сохрани третью запись с ссылками/причинами. Посчитай распределения/согласие/not_assessable/critical errors. Напиши вывод с реальными примерами, ограничениями и действиями. Без author_id не создавай рейтинг конкретных сотрудников. Не подменяй этап окончательным AI final report.
Критерии готовности: Исходные оценки сохранены; каждое расхождение объяснено; все числа пересчитываются и имеют n/N. Есть конкретные observation/hypothesis/action и честные ограничения.
Выход: commit SHA или patch, файлы результата и docs/coordination/egor/D04-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### D05. Настоящая BPMN-модель процесса

**Участник:** Егор / агент D / Manus Lite + ручная проверка.  
**Старт:** A04/B03 согласованный flow; D00.  
**Машина:** Любая, без GPU.

Промпт для отдельного нового чата:

~~~text
Ты агент D проекта TenderHack. Выполни только задачу D05: Настоящая BPMN-модель процесса.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/d05 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: A04/B03 согласованный flow; D00.
Входы: Итоговые состояния/API v2 и реальный пользовательский процесс.
Разрешены только нужные этой задаче файлы в зоне: evaluation/** кроме annotations/stas/**, reports/**, presentation/**, docs/process/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Создай BPMN 2.0 файл с пользователем, сервисом, человеком: вопрос, policy, поиск, gate, одно уточнение, подтверждение передачи, ожидание/ответ человека, feedback и разные завершения. Сделай читаемый SVG/PNG экспорт. Mermaid не заменяет .bpmn. Не добавляй кабинет оператора или автоматическую публикацию KB.
Критерии готовности: .bpmn открывается/валидируется доступным средством, переходы соответствуют реализации, изображение читаемо. Передай BPMN+экспорт для защиты; если визуальная проверка не выполнена, отметь её явно.
Выход: commit SHA или patch, файлы результата и docs/coordination/egor/D05-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### D06. Два черновика сценариев Егора

**Участник:** Егор / агент D / Manus Lite + ручная проверка.  
**Старт:** D01, KB snapshot; после D05 по личной очереди.  
**Машина:** Любая, без GPU.

Промпт для отдельного нового чата:

~~~text
Ты агент D проекта TenderHack. Выполни только задачу D06: Два черновика сценариев Егора.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/d06 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: D01, KB snapshot; после D05 по личной очереди.
Входы: Реальные sources и ScenarioCard schema, dev без sealed final.
Разрешены только нужные этой задаче файлы в зоне: evaluation/** кроме annotations/stas/**, reports/**, presentation/**, docs/process/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Создай два draft-сценария в content/cards/egor. Проверяемые intent/условия/источники/шаги, никакой выдуманной инструкции. Reviewer Стас проверит в C06; сам reviewed не ставь. Подготовь источники так, чтобы человеку было быстро их проверить.
Критерии готовности: Два валидных draft либо конкретный blocker, пути и commit переданы C06. Скрытый final не использован.
Выход: commit SHA или patch, файлы результата и docs/coordination/egor/D06-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### D09. Отчёт по реальному dev и экспорту перед RC

**Участник:** Егор / агент D / Manus Lite + ручная проверка.  
**Старт:** D02, D04, A04 export; A05/C07/B06 результаты по готовности.  
**Машина:** CPU; runner только в GPU-слот.

Промпт для отдельного нового чата:

~~~text
Ты агент D проекта TenderHack. Выполни только задачу D09: Отчёт по реальному dev и экспорту перед RC.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/d09 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: D02, D04, A04 export; A05/C07/B06 результаты по готовности.
Входы: Реальный dev run/export, независимая история, версии кода/KB.
Разрешены только нужные этой задаче файлы в зоне: evaluation/** кроме annotations/stas/**, reports/**, presentation/**, docs/process/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: В отдельном новом чате пересчитай отчёт по реальным данным до RC. Раздели dev/history/live/demo, auto-answer и resolution, errors/timeouts и latency. Подготовь один итоговый HTML/Markdown экран и список конкретных дефектов с владельцами. Нет final данных — не подставляй их. Передай A06 отчёт и blockers.
Критерии готовности: Каждое число выводится из actual input с n/N, пустые выборки null. Есть методика/пример/действие, отчёт воспроизводится без LLM/GPU. Готовность к final сформулирована по evidence.
Выход: commit SHA или patch, файлы результата и docs/coordination/egor/D09-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### D07. Независимый final на frozen RC

**Участник:** Егор / агент D / Manus Lite + ручная проверка.  
**Старт:** A06 RC, D01 sealed suite, D02 runner.  
**Машина:** G эксклюзивно для inference; расчёт CPU.

Промпт для отдельного нового чата:

~~~text
Ты агент D проекта TenderHack. Выполни только задачу D07: Независимый final на frozen RC.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/d07 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: A06 RC, D01 sealed suite, D02 runner.
Входы: Точный release SHA, model/prompt/config/KB hashes, закрытые 40 final cases.
Разрешены только нужные этой задаче файлы в зоне: evaluation/** кроме annotations/stas/**, reports/**, presentation/**, docs/process/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Проверь совпадение runtime manifest с RC. Запусти sealed final, сохрани все actual outputs, источники, transitions, times и ошибки. Проведи содержательную проверку по gold/источникам, посчитай n/N и ограничения. Не меняй пороги/prompt/model во время прогона. Дефекты передай A как FIX; исходные результаты не стирай. Повтор после фикса обозначь post-test rerun.
Критерии готовности: 40 выполненных случаев либо actual n с причинами; отчёт включает ошибочные ответы, abstention, routing/recipient и latency. Версии и raw outputs сохранены; нет заявления нового независимого теста после настройки по final.
Выход: commit SHA или patch, файлы результата и docs/coordination/egor/D07-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

### D08. Материалы защиты и репетиция

**Участник:** Егор / агент D / Manus Lite + ручная проверка.  
**Старт:** D04/D05/D07, A07 release по готовности.  
**Машина:** Своя машина для материалов, G для реального демо.

Промпт для отдельного нового чата:

~~~text
Ты агент D проекта TenderHack. Выполни только задачу D08: Материалы защиты и репетиция.
Репозиторий: <REPO_PATH>. База: <BASE_SHA>. Фактическая машина: <MACHINE_PROFILE>.
Создай/используй отдельную ветку task/d08 от принятого BASE_SHA и отдельный worktree.
Прочитай AGENTS.md и TenderHack_UNIFIED_SPEC_v2.md. Contracts/fixtures и handoff читай только если они уже созданы выполненными обязательными зависимостями. В A00/B00/C00/D00 их изначально нет и создавать чужой результат нельзя. Старые чаты не являются входом; конфликтующие S1/S2 не реализуй.
Обязательные зависимости: D04/D05/D07, A07 release по готовности.
Входы: Final report, история, BPMN, exact release, известные ограничения.
Разрешены только нужные этой задаче файлы в зоне: evaluation/** кроме annotations/stas/**, reports/**, presentation/**, docs/process/** и собственные content/coordination.
Не меняй чужие файлы/общие DTO без владельца. Изменение контракта предложи через CR; продолжай независимую часть по действующему контракту. Не добавляй облачный runtime, операторский кабинет, второй генератор или repo-wide refactor. GPU только по выделенному слоту; не загружай модели на слабой машине.
Что сделать: Подготовь пяти минутный сценарий и резерв на десять: обычный RAG с source/условием, no-answer, подтверждение handoff, живой reply другого человека, feedback, методика/реальные метрики, короткий profanity, BPMN. Один спикер и один исполнитель демо. Собери материалы/локальный итоговый экран и запись настоящего прогона. Не подменяй сбой заранее заготовленным AI-ответом.
Критерии готовности: Репетиция укладывается в 5 минут, источники и реальные числа доступны, reply показывает настоящего человека. Локальный резерв/видео явно обозначены как запись; ограничения не скрыты. Передай окончательный порядок и список файлов A07/команде.
Выход: commit SHA или patch, файлы результата и docs/coordination/egor/D08-handoff.md по разделу 16. Проверки выполняй по реальным критериям этой задачи, укажи команды и actual results, mock/real и ограничения. Отсутствующие реальные данные не выдумывай.
После сдачи остановись. Не начинай следующий ID: для него участник создаст отдельный новый чат.
~~~

## 18. Пакет сдачи и демонстрация

| Результат | Владелец | Проверяемая готовность |
|---|---|---|
| Release source и manifest | A | Один SHA, согласованные contracts, hashes/config |
| Локальное приложение | A/B/C | Полный реальный пользовательский цикл на G |
| KB/индекс/cards | C | Read-only snapshot, реальные источники, reviewed count |
| Методика/историческая оценка | D/B | 30 пар или честный фактический объём, две исходные оценки и согласование |
| AI dev/final | D | Raw outputs, split, версии, n/N, ошибки, latency |
| Содержательный итоговый экран | D | Воспроизводимые метрики и конкретные действия |
| BPMN | D | Открываемый .bpmn и читаемый экспорт |
| Runbook/offline/CLI | A | Реальный preflight/start/restart/reply/export |
| Демо и резерв | D/A | Пятиминутная репетиция, локальные материалы, видео реального прогона |

Демо: 0:00–0:25 цель; 0:25–1:15 обычный RAG с опечаткой/ролью и точным источником; 1:15–2:05 недостаток основания; 2:05–2:55 подтверждение передачи и живой reply; 2:55–3:20 feedback; 3:20–4:15 методика/реальные результаты; 4:15–4:40 profanity; 4:40–5:00 BPMN и пределы автоматизации. Это план репетиции, не измеренный хронометраж.

Обычный RAG-пример не заменять карточкой: жюри должно увидеть реальный поиск и генерацию. При задержке показываем найденный материал с честным статусом; при сбое — деградацию/человека. Запись реального демо допускается как явно названный резерв, не как скрытая имитация live.

## 19. Что проверить до запуска задач

1. A00 фиксирует фактическое соответствие имён четырём ноутбукам, RAM/ОС G и доступность Linux. Роли кода сохраняются независимо от владельца G.
2. Команда подтверждает реальное оставшееся время относительно исходных 34 часов; таблица не обещает ещё 34 часа после уже прошедшей части.
3. C00/D00 отмечают наличие raw KB, Регламента, PDF originals, taxonomy, истории и весов. Отсутствие блокирует только зависимый результат.
4. A01 снимает hardware-риск в начале, не перед сдачей. WSL2 без подтверждённой допустимости остаётся риском соответствия.
5. Не запускать четыре общих чата «сделай весь frontend/backend/RAG». Первые четыре запуска: A00, B00, C00, D00. После C0 — новые чаты по очередям и зависимостям.

Эта спецификация не утверждает, что код написан, модели помещаются, тесты пройдены или источники доступны. Готовность появляется только после соответствующей задачи, принятого commit и фактической проверки.
