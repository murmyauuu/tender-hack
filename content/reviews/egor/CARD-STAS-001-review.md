# Review — CARD-STAS-001

- **Task / milestone:** C06 — независимый review B05 сценариев Стаса
- **Reviewer:** egor
- **Author:** stas
- **Reviewed card:** `content/cards/stas/card-stas-001.json`
- **Verdict:** approved
- **Verdict origin:** автономный verdict reviewer-агента по явной инструкции Егора
  («сделай ревью полностью самостоятельно, без human approved, именно ты сам»);
  отдельное human-подтверждение не выполнялось.
- **Verdict comment (reviewer-agent):** карточку одобряю. Источник найден в frozen
  C07 snapshot, все факты/условия/шаги прослеживаются до источника, invented facts
  отсутствуют, route `null` воспроизведён фактическим исполнением
  `knowledge/kb/routing.py`. Найденные risks — non-blocking observations, правок
  автору не требуется.
- **Reviewed at:** 2026-09-13 (UTC+3)

## Профиль карточки

| Поле | Значение |
|---|---|
| card_id | `CARD-STAS-001` |
| intent_id | `upload_mchd_to_user_profile` |
| title | Загрузка МЧД в профиль пользователя |
| status | draft (не импортирована и не provides review/approved до C06) |
| snapshot_id | `kb-4918a97f0874d1e8` (совпадает с frozen C07) |

## Проверка источника

- **source_ids:** `portal:559615:1`.
- **Проверка source в frozen C07 snapshot:** запись `id=2d53e6247ffba83f77e1`
  (`source_key=portal_api:559615:1`) найдена в canonical input
  `TenderHack_KnowledgeBase/knowledge_base_FINAL.jsonl`; локальный
  SHA-256 файла `71bf714a9e205a35f5d8ec0fd2d0f9bbd4ad3a8409968b754eb8de7b349d79ae`
  совпадает с canonical input C07 freeze. **Source существует**.
- **content_status:** `complete` (в тексте нет ссылок на «Рисунок» и на
  «Приложение/см.» → `attachment_status` возвращает complete).
- **role_verified:** audience=`supplier` → `applicable_roles=[supplier]`,
  `role_verified=true`.
- Page/section/source date/URL в frozen SourceRecord — `null`; в карточку не
  переносились и не выдумывались (в схеме ScenarioCard этих полей нет).

## Независимая перепроверка содержания

- **role/applicability:** `supplier` — совпадает с audience-metadata источника.
- **required facts:** `role=supplier`, `mchd_action=upload_to_user_profile`,
  `mchd_file_format=xml` — выводимы из intent и текста источника.
- **conditions (3):**
  1. роль поставщика — gate по доказанной audience-metadata (не из текста статьи);
  2. требуется добавить МЧД в профиль — intent;
  3. доступен XML-файл МЧД — из текста источника («добавить файлы xml доверенности»).
- **steps (3):** два подтверждённых пути источника (сам пользователь через
  «Операции с МЧД» в профиле; администратор ЮЛ через «Управление профилем» →
  «Профиль компании» → «Сведения о пользователях» → «Операции с МЧД») +
  заключительный шаг загрузки XML. Дополнительных шагов нет.
- **routing:** пуст (все route-поля `null`) — воспроизведено фактическим
  исполнением `knowledge/kb/routing.py` на всех трёх utterances карточки:
  `match_topic` пуст (в `config/knowledge/taxonomy.json` нет подтемы, полный
  keyword-set которой входит в токены utterances, и нет уникального
  кода/аббревиатуры для этой подтемы) → `support_line=null` (не автоматический
  L2). Соответствует live retrieval B05.
- **handoff_required:** `false` — подтверждается: простой how-to, адресата
  источник не называет, оснований для operator handoff нет.

## Defects / risks (не блокеры)

- R1: условие «роль поставщика» взято из audience-metadata, а не из текста
  статьи; подтверждено metadata (`role_verified=true`), не выдумано.
- R2: у по сути L1-вопроса route остаётся `null` из-за отсутствия покрытия в
  taxonomy — это осознанный детерминированный выбор, а не пропуск; runtime
  должен принимать пустые route-поля (схема допускает `null`).
- R3: ложный матч на вопросы «нужна ли МЧД / полномочия» не возникает: карточка
  ограничена required fact `mchd_action=upload_to_user_profile`; fallback
  зафиксирован в B05-handoff (не поле карточки).

## Invented facts

**Нет.** Все факты прослеживаются до frozen SourceRecord / intent; неизвестное
оставлено `null`.

## Вывод

Карточка подтверждена независимым review. Reviewer: `egor`. Verdict определён
автономно reviewer-агентом по явной инструкции владельца; human-approved
отсутствует. Не менять `status`/`reviewer_id` карточки в этом task: смена
статуса — шаг владельца после интеграции review.