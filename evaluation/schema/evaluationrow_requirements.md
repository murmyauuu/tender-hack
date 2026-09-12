# Требования к минимальному EvaluationRow для A00

Статус: **требования D к схеме экспорта A**, переданы через A00 (карточка D00). Это НЕ альтернативный API:
реализация — одна команда `python -m tools.export_data --output <file.json>` от A. Дополнительно оформлено CR-D-001.

Канон поведения: спецификация v2.1, раздел 13 «Экспорт и оценка» (один экспорт, одна EvaluationRow на Case).

## 1. Некомпромиссные требования D

1. **Одна EvaluationRow на Case**, включая финальные случаи без ответа (незавершённые, отказанные,
   policy_closed). Один экспорт не теряет Case (проверка AC20).
2. **author_id — nullable**. В истории авторы отсутствуют (константа «Заявитель», нет ИД оператора) —
   в таких источниках `author_id = null`. Любые выдуманные авторы/идентификаторы запрещены.
3. **Нет выдуманных SLA/CSAT**: экспорт не содержит полей SLA/CSAT «по умолчанию», а только фактические
   поля (timings, statuses), из которых метрики вычисляются. Если время/статус отсутствуют — null.
4. **Даты** — ISO 8601 UTC (timestamp с Z); неизвестные — null. Никаких «найдено в будущем» и изобретённых.
5. **cohort = demo | live** — обязательно; demo помечается на сервере, не выдаётся за real.
6. **Разделение массивов**: AI-test (dev/final) и История — отдельные массивы от live/demo (см. «Три массива»,
   v2.1 §13); D соединяет в отчёте с явным происхождением и не смешивает знаменатели.
7. **source_ids ссылаются на документы KB** (id из knowledge_base_FINAL.sqlite/`documents.id`).
   Источники не придумываются; нет проверенного источника — пустой массив/null.
8. **Стабильные идентификаторы** (message_id, case_id, request_id) — строки UUID/стабильные, генерируемые
   backend; не полагаться на rowidx.
9. Запись не содержит секретов/ключей/служебных токенов.
10. Экспорт содержит версии: `schema_version`, `app_commit`, `kb_snapshot_id`, `as_of`, `created_at`,
    `export_id` — для воспроизводимости отчётов D02/D07/D09.

## 2. Структура конверта

```json
{
  "schema_version": "1.0",
  "export_id": "…",
  "created_at": "…Z",
  "as_of": "…Z",
  "app_commit": "…",
  "kb_snapshot_id": "…",
  "rows": [ EvaluationRow, … ]
}
```

## 3. Поля EvaluationRow (минимальный набор)

| Поле | Тип | null? | Примечание D |
|---|---|---|---|
| case_id | string | нет | стабильный |
| cohort | "demo"\|"live" | нет | demo server-marked |
| created_at | datetime | нет | ISO 8601 Z |
| case_status | string | нет | терминальный/активный |
| topic_id | string | да | из таксономии; unknown→null/unknown |
| subtopic_id | string | да | unknown→null/unknown |
| policy_closed | bool | нет | вычитается из N_eligible |
| route.support_line | string | да | unknown→null |
| route.recommended_recipient | string | да | зависит от C04; unknown→null |
| route.reason_codes | string[] | да | пусто если нет |
| ticket | null\|{ticket_id,status,created_at,resolved_by} | да | null если Ticket не создан |
| messages[] | array | да (пустой если нет) | см. ниже |
| requests[] | array | да | см. ниже |
| feedback[] | array | да | актуальные записи (updated_at) |
| current_resolution | null\|{message_id,confirmed_by,answer_origin,confirmed_at} | да | null=нет подтверждённого решения |

`messages[]` элемент: `message_id, seq, kind, responder_type, author_id (nullable),
answer_origin, text, source_ids[], created_at`.

`requests[]` элемент: `request_id, user_message_id, status, result_message_ids[], error_code (nullable),
timings_ms {queue, retrieval, generation_total, time_to_first_source, total, prompt_eval, decode,
все nullable}`.

`feedback[]` элемент: `message_id, useful, solved, specialist_rating (nullable), reason_codes[],
comment, updated_at`. useful и solved — раздельные; связь «полезность» ≠ «решение» сохраняется.

`current_resolution`: подтверждённое решение (user/operator), а не «передано».

## 4. Дополнительные массивы для D (предложение, решение за A)

- `dev_test`, `final_test` — технические наборы D01 с test_id/group_id/split (для отчётов D02/D07);
- `history_pairs` — только в виде манифеста вне экспорта runtime: D01 формирует `evaluation/history/pairs_manifest.json`
  (pair_id, row reference, hashes, topic/subtopic, status) — единая выдача для B04/D03.

## 5. Ограничения вычислений (передаются A как требования к данным)

- `N_eligible = все Cases − policy_closed`; нулевой знаменатель → null (`D02`).
- Полезность вычисляется отдельно для AI и operator, как `useful=true / ненулевые useful`, с n.
- Покрытие feedback = Cases с оценкой / Cases с доступным answer.
- Автоответ ≠ решение (помечается только фактом `answer_origin`).
- Лучший автор: author_id пустой/константа → персональные рейтинги не строятся.

## 6. Что D НЕ создаёт

- Альтернативного экспорта, второго API, параллельной схемы;
- значений «по умолчанию» для отсутствующих измерений;
- синтетических исторических пар вместо реальных.