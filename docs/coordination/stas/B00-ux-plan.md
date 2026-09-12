# B00 — UX-план пользовательского пути до C0

Основание: `TenderHack_UNIFIED_SPEC_v2.1_prefilled.md`, разделы 2, 6–8, 12, 14 и карточка B00. Это план, а не реализация. До принятия C0 названия полей, схемы и fixtures не фиксируются клиентом: единственный канон для B01 — OpenAPI и fixtures, опубликованные A00.

## 1. Рамка продукта

- Один пользовательский экран: чат, история, ввод, статус текущего запроса и действие «Новая тема».
- Источник и условия показываются рядом с конкретным ответом. Условия идут до шагов.
- Передача человеку происходит только после явного согласия/просьбы. До этого Ticket нет.
- После передачи ответ специалиста появляется в том же чате. Отдельного operator UI нет.
- Интерфейс не показывает retrieval score, prompt, VRAM и другие технические оценки; не утверждает, что локальный Ticket передан в службу Портала.
- Профиль W используется только для лёгкой клиентской разработки/браузерной проверки; ML и локальные тяжёлые сервисы не планируются.

## 2. Карта основного пути

1. **Вход/восстановление.** Клиент получает сессию, а при наличии сохранённого `case_id` загружает диалог. HttpOnly-cookie даёт доступ; `localStorage` — лишь указатель на Case.
2. **Новый вопрос.** Ввод показывается в чате сразу после принятия. Прогресс меняется по данным Request: «Запрос в очереди» → «Ищу подходящую инструкцию» → «Найден материал. Проверяю, подходит ли он к вашей ситуации». Кандидат ещё не называется ответом.
3. **Обычный ответ.** В сообщении маркер «Ответ по инструкции» или «Проверенный сценарий». Порядок: summary → условия применимости → шаги → источник(и) → feedback.
4. **Источник.** Клик по источнику открывает карточку/выдвижную панель с фактическими title, excerpt, version/date, section/page и file URL, если они есть. Неизвестные значения не додумываются; при отсутствии PDF показывается доступный текст.
5. **Одно уточнение.** Вопрос системы показывается как clarification, а ответ пользователя — как обычное user message. Затем идёт новый retrieval без сброса лимита. Ещё одного цикла clarification нет: предлагается передача.
6. **Предложение передачи.** Показываются понятная причина/чего не хватает и основное действие «Передать специалисту». Это состояние `handoff_offered`, не созданный Ticket. Отмена/продолжение не имитирует согласие.
7. **Ticket.** После успешного handoff показываются Ticket status и текст «В очереди специалиста нашего сервиса». Рекомендуемый адресат на Портале показывается отдельно, только если пришёл от backend. Иначе: «Адресат требует уточнения». Клиент не выбирает и не выдумывает адресата.
8. **Ответ специалиста.** Он добавляется в историю с пометкой «Ответ специалиста» и серверным автором. При `waiting_user` поле ввода остаётся доступным: следующее сообщение идёт человеку без запуска AI. При `resolved` продолжение Case недоступно, но можно начать новую тему.
9. **Feedback конкретному answer.** Первый клик «Полезно/нет» сразу сохраняется. В той же форме, но отдельно, указывается `solved`. У operator answer может быть рейтинг 1–5; у AI/card его нет. Если `outcome_applied=false`, UI показывает сохранённую оценку, но не изображает закрытие Case.
10. **Новая тема.** Явное действие создаёт новый Case. Прежняя история не переносит предметные факты; поздний ответ/поллинг старого `case_id` не меняет текущий экран.

## 3. Состояния и переходы UI

| Стартовое состояние | Событие/ответ | Что видит пользователь | Следующее состояние |
|---|---|---|---|
| Нет Case / новая тема | Вопрос принят | User message + прогресс | `open`, Request queued/processing |
| `open` | Найден кандид | Нейтральная фраза о проверке применимости | `open`, Request processing |
| `open` | AI/card answer | Ответ, условия, шаги, источник, feedback | `awaiting_feedback` |
| `open` | Нужен один факт | Один точный clarification-вопрос | `awaiting_clarification` |
| `awaiting_clarification` | User answer | Новый прогресс | `open`; после него answer или handoff offer |
| `open`/`awaiting_clarification` | Evidence нет, конфликт, invalid generation, лимит clarification | Причина + CTA передачи | `handoff_offered`; Ticket `null` |
| `handoff_offered` | Явное подтверждение | Подтверждённая очередь и Ticket status | `handed_off`, Ticket `new` |
| `handed_off` + Ticket `new` | Operator reply | Новое operator message, feedback | Ticket `waiting_user` или `resolved` |
| `handed_off` + Ticket `waiting_user` | User message | Сообщение человеку, без AI-прогресса | Ticket `new` |
| Актуальный answer | `solved=true` применён | Оценка сохранена, вопрос решён | `resolved` |
| Актуальный AI answer | `solved=false` применён | Оценка сохранена; ввод доступен | `open`, без автозапуска inference |
| Актуальный operator answer | `solved=false` применён | Оценка сохранена; ожидание человека | `handed_off`, Ticket `new` |
| Любой незакрытый Case | Profanity | Policy notice, без source/feedback/retry | `closed_policy` |
| `open` | OUT_OF_SCOPE | Notice о границах сервиса, без Ticket | `open` |
| Request processing | Технический сбой после приёма | Вопрос остаётся; retry, если `retryable`, или передача | Request `error`, Case не `resolved` |
| Любой Case | «Новая тема» | Пустой чат/новый Case; старая история не переносится | Новый Case |

## 4. Компоненты B01

Эти названия — границы UI, а не типы сетевого контракта.

- `ChatShell`: текущий Case, история, прогресс, ввод и новая тема.
- `MessageList` / `MessageCard`: роль, kind/responder/origin и дедупликация по `message_id`.
- `RequestProgress`: только человеко-понятные queued/retrieving/sources-found/generating/error состояния.
- `AnswerCard`: summary, условия перед шагами, ссылки на источники и feedback к этому `message_id`.
- `SourceTrigger` / `SourceDrawer`: загрузка канонической карточки источника; loading/not-found/degraded.
- `ClarificationPrompt`: один недостающий факт без клиентской догадки о нём.
- `HandoffOffer`: причина, чего не хватает, явное подтверждение и состояние stale/error без слепого повтора.
- `TicketStatus`: локальная очередь, status, support line и recommended recipient только из Case/Ticket; пустое значение — «Адресат требует уточнения».
- `FeedbackForm`: мгновенное useful, отдельное solved, дополнительные reason/comment; specialist rating только для operator answer.
- `ErrorNotice`: понятная ошибка, факт сохранения/несохранения, допустимые retry/handoff/new topic.
- `PolicyNotice` и `OutOfScopeNotice`: отделяют policy closure и границу сервиса от технического сбоя.

## 5. Привязка к каноническим операциям v2.1

| Операция v2.1 | Роль в пути B01 |
|---|---|
| `POST /api/v1/sessions` | Начало/восстановление browser session |
| `POST /api/v1/chat` | Новый вопрос, ответ на clarification, сообщение человеку или явный retry в рамках канона |
| `GET /api/v1/requests/{id}` | Поллинг этапа, кандидатов, terminal/error |
| `GET /api/v1/cases/{id}` | История, Case/Ticket status, восстановление и перечитывание после terminal/409 |
| `POST /api/v1/cases/{id}/handoff` | Только явное подтверждение передачи |
| `GET /api/v1/sources/{id}` | Карточка источника из answer |
| `POST /api/v1/feedback` | Useful/solved/reasons/comment и operator-only rating к конкретному message |
| `GET /api/v1/health` | Честный ready/degraded статус, не скрытый mock |
| `POST /internal/tickets/{id}/reply` | Не вызывается frontend; его результат приходит в Case через поллинг |

Других HTTP-операций план не добавляет. Фактические request/response-типы B01 получает из generated C0 OpenAPI.

## 6. Каталог mock-состояний для B01

B01 не описывает форму этих данных вручную. Каждое состояние должно быть воспроизведено только из frozen C0 fixture через generated TS и mock transport.

| Mock-состояние | Проверяемый UX-результат |
|---|---|
| Accepted + queued/processing/progress | Принятый user message не дублируется, этап обновляется |
| Candidate source | Материал пока не объявлен проверенным ответом |
| RAG answer | Summary, условия, шаги, source, AI feedback |
| Reviewed card answer | Тот же каркас, маркер «Проверенный сценарий» |
| Clarification | Один вопрос; ответ user запускает следующий этап |
| Handoff offered | Причина + CTA; Ticket ещё не показан |
| Ticket with known recipient | Локальная очередь и отдельно рекомендованный адресат |
| Ticket with unknown recipient | «Адресат требует уточнения», без догадки |
| Operator reply: waiting_user | Серверный автор, operator feedback/rating, ввод идёт человеку |
| Operator reply: resolved | Терминальный Case, feedback доступен, CTA новой темы |
| Feedback applied/not applied | Полезность и solved не смешаны; stale feedback не меняет видимый исход |
| Retryable accepted-request error | Вопрос сохранён, один явный retry без дубля user message |
| Rejected-before-acceptance 409/429/503 | Ввод сохранён; Case перечитан при 409; нет слепого retry |
| Source unavailable/not found | Нет выдуманного PDF/URL; основной ответ остаётся в истории |
| OUT_OF_SCOPE | Notice о границах, без error/Ticket |
| Policy closure | Policy notice, Case закрыт, без feedback и AI-прогресса |
| Refresh/current Case + stale old Case result | История восстанавливается; поздний чужой результат не меняет экран |

## 7. Поведение клиента на границах

- Polling Request: 750–1000 мс; Ticket/Case: 1 с; в фоне: 3 с. После terminal Request перечитать Case. Все таймеры отменять при смене Case/размонтировании.
- Входящую историю дедуплицировать по `message_id`; ответ применять только если его `case_id` всё ещё текущий.
- На mutation использовать ключ идемпотентности и актуальную Case version только в форме, которую закрепит C0. При 409 перечитать Case, сохранить ввод и предложить повторное явное действие.
- Если запрос не был принят (429/503), UI не утверждает, что вопрос сохранён. Если ошибка пришла после 202, показать сохранённый вопрос и разрешённые сервером действия.
- Markdown/HTML санитизировать; assets локальные; секреты и operator reply key никогда не попадают в browser storage, bundle или fixture.

## 8. Definition of Ready для B01 после C0

B01 может начаться только из нового чата и от принятого SHA, содержащего A00 и B00. Нужны:

1. A00 handoff с точным C0 SHA, tag `bootstrap-contracts-v2`, contracts version и командой проверки fixtures/OpenAPI.
2. Сгенерированный C0 OpenAPI для девяти операций и generated TypeScript; generated-код не правится вручную.
3. Frozen fixtures как минимум для answer, clarify, handoff offered, ticket, operator reply, policy, error и stale; точный перечень/имена берутся из A00.
4. Команда запуска test fake/mock transport и пример разрешённого dev origin/cookie потока.
5. Подтверждённое правило отображения source URL/PDF и поведение для `null`/unknown полей.

До C0 блокируются только контрактная реализация и fixture-прогон B01; UX-план B00 завершён автономно.

## 9. Чек-лист приёмки плана

- [x] Обычный RAG/card answer, source и условия до шагов.
- [x] Одно clarification, затем answer или handoff offer.
- [x] Handoff offer без Ticket; Ticket только после согласия.
- [x] Ticket, известный/unknown recommended recipient и operator reply в том же чате.
- [x] Feedback к конкретному answer; useful отдельно от solved; operator-only rating.
- [x] Технический error, stale/overflow/storage, retry без дубля.
- [x] Refresh, polling cleanup, dedup и изоляция позднего результата прежнего Case.
- [x] Новая тема не переносит confirmed facts.
- [x] OUT_OF_SCOPE и policy closure отделены от technical error.
- [x] Нет operator UI, выдуманного адресата, scores и секретов в браузере.
- [x] План не вводит десятую HTTP-операцию и не фиксирует альтернативные DTO.
