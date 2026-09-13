# Review — CARD-STAS-002

- **Task / milestone:** C06 — независимый review B05 сценариев Стаса
- **Reviewer:** egor
- **Author:** stas
- **Reviewed card:** `content/cards/stas/card-stas-002.json`
- **Verdict:** approved
- **Verdict origin:** автономный verdict reviewer-агента по явной инструкции Егора
  («сделай ревью полностью самостоятельно, без human approved, именно ты сам»);
  отдельное human-подтверждение не выполнялось.
- **Verdict comment (reviewer-agent):** карточку одобряю. Источник найден в frozen
  C07 snapshot, все факты/условия/шаги прослеживаются до источника, invented facts
  отсутствуют, route `TH8/ST75/L2` воспроизведён фактическим исполнением
  `knowledge/kb/routing.py` на всех трёх utterances карточки. Найденные risks —
  non-blocking observations, правок автору не требуется.
- **Reviewed at:** 2026-09-13 (UTC+3)

## Профиль карточки

| Поле | Значение |
|---|---|
| card_id | `CARD-STAS-002` |
| intent_id | `resolve_rdik_0474_outdated_oktmo` |
| title | Устранение интеграционного контроля РДИК_0474 |
| status | draft (не импортирована и не provides review/approved до C06) |
| snapshot_id | `kb-4918a97f0874d1e8` (совпадает с frozen C07) |

## Проверка источника

- **source_ids:** `portal:588559:1`.
- **Проверка source в frozen C07 snapshot:** запись `id=25646aa5d0332dac13b7`
  (`source_key=portal_api:588559:1`) найдена в canonical input
  `TenderHack_KnowledgeBase/knowledge_base_FINAL.jsonl`; локальный
  SHA-256 файла `71bf714a9e205a35f5d8ec0fd2d0f9bbd4ad3a8409968b754eb8de7b349d79ae`
  совпадает с canonical input C07 freeze. **Source существует**.
- **content_status:** `complete` (в тексте нет ссылок на «Рисунок» и на
  «Приложение/см.» → `attachment_status` возвращает complete).
- **role_verified:** audience=`supplier,customer` → `applicable_roles=
  [customer, supplier]`, `role_verified=true`.
- Page/section/source date/URL в frozen SourceRecord — `null`; в карточку не
  переносились и не выдумывались (в схеме ScenarioCard этих полей нет).

## Независимая перепроверка содержания

- **role/applicability:** `customer`, `supplier` — совпадает с audience источника.
- **required facts:** `rdik_code=РДИК_0474`, `organization_oktmo_state=outdated`
  — прямо в тексте источника.
- **conditions (2):**
  1. сработал именно РДИК_0474 — из источника;
  2. в ЛК организации неактуальный ОКТМО — из источника.
- **steps (5):** «Управление профилем» → «Профиль компании»; «Заявка на
  изменение данных»; «Статистические коды» — корректный ОКТМО (8 цифр);
  отправка заявки; после обновления — повтор подписания. Пункт-в-пункт
  соответствуют 5 шагам источника.
- **routing:** `TH8` / `ST75` / `L2`, rule `ROUTE.LINE.THEME_DEFAULT`,
  `recommended_recipient=null`. Воспроизведено фактическим исполнением
  `knowledge/kb/routing.py` на всех трёх utterances карточки: код «рдик» —
  уникальный abbreviation/код-токен taxonomy (встречен ровно в `ST75»
  «Формирование УПД (вопросы по ошибкам РДИК)`) → `subtopic_id=ST75`,
  `theme_id=TH8` (Электронное исполнение (ЕИС)); признаков L3-дефекта нет
  (упоминание валидационного кода РДИК само по себе не является признаком
  дефекта); line = L2 (theme default TH8); фразы «обратитесь в…» в главном
  evidence нет → `recommended_recipient=null`; `basis_source_ids=[]` (текст
  источника не содержит полного keyword-set ST75).
- **handoff_required:** `false` — подтверждается.

## Defects / risks (не блокеры)

- R1 (observation): метаданные статьи («Работа с контрактами / Исполнение
  контракта») расходятся с маршрутом TH8; это следствие детерминированной
  РДИК→ST75-таксономии. Карточка хранит ровно то, что возвращает retrieval,
  маршрут воспроизводим. Возможный CR по taxonomy — вне scope C06.
- R2: другой РДИК-код технически попадает в ST75 по токену «рдик», но карточка
  закрыта точным required fact `rdik_code=РДИК_0474` — на другие коды не
  применится.
- R3: формулировка «повторить подписание документа» сохранена буквально как в
  источнике; сужение до «документа=УПД» не производилось (нет оснований),
  изобретения нет.

## Invented facts

**Нет.** Все факты прослеживаются до frozen SourceRecord / intention;
неизвестное оставлено `null`.

## Вывод

Карточка подтверждена независимым review. Reviewer: `egor`. Verdict определён
автономно reviewer-агентом по явной инструкции владельца; human-approved
отсутствует. Не менять `status`/`reviewer_id` карточки в этом task: смена
статуса — шаг владельца после интеграции review.