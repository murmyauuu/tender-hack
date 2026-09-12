# B05 — два draft-сценария Стаса

- **Status:** done
- **Owner / tool:** Стас / агент B / Codex
- **BASE_SHA:** `d9ebc5b41d892b00338e88db8ac1b296b512860c` (`origin/main` после `fetch --prune` и `pull --ff-only`)
- **Result SHA:** `c71ab4820273f32bae52771e4a49537506c98c4d` (коммит с двумя карточками; этот handoff добавлен следующим docs-only коммитом)
- **Branch:** `task/b05`
- **Contracts version:** `2.1.0-a02`; `ScenarioCard` не изменялся
- **Machine profile:** Windows, CPU-only; generation/GPU не использовались
- **Runtime SHA / KB snapshot:** runtime не изменялся; frozen C07 logical snapshot `kb-4918a97f0874d1e8`

## Preflight и inputs

`B04` принята в `main`: merge commit `31ce916` содержит commits `f1bff9a` и
`6c383ed`; `git branch -r --contains origin/task/b04` вернул `origin/main`.

C07 ещё не смержена в `origin/main` на BASE_SHA, поэтому его чужой конфиг не переносился в
B05. Frozen identity проверена по `origin/task/c07:config/knowledge/kb_freeze.json`:

- `snapshot_id=kb-4918a97f0874d1e8`;
- SHA-256 всех восьми canonical input files совпали с C07;
- локальная детерминированная сборка имеет `raw=1468`, `included=1528`, `articles=480`,
  `cards_reviewed=0`;
- оба source ID карточек найдены в этом snapshot и имеют `content_status=complete`.

Использованы только `evaluation/ai_test/dev/ai_test_dev.jsonl`, frozen KB и обычные
verified source records. Sealed final не использовался и не изменялся.

## Changed files

- `content/cards/stas/card-stas-001.json`
- `content/cards/stas/card-stas-002.json`
- `docs/coordination/stas/B05-handoff.md`

Карточки A08/C05 не дублируются: в B05 нет сценариев банковских реквизитов,
привязки сертификата, освобождения ИП от МЧД или РДИК_0009.

## Карточки и evidence

### CARD-STAS-001 — `upload_mchd_to_user_profile`

- **Intent:** загрузить XML-файл МЧД в профиль пользователя.
- **Role / audience:** `supplier`; `role_verified=true` в retrieval evidence.
- **Source ID:** `portal:559615:1`, `content_status=complete`.
- **Page / section / source date / URL:** в frozen SourceRecord все `null`; не выдумывались.
- **Required facts:** `role=supplier`, `mchd_action=upload_to_user_profile`,
  `mchd_file_format=xml`.
- **Required conditions:** роль поставщика; цель — добавить МЧД в профиль; доступен
  XML-файл МЧД. Все три условия подтверждены audience/text источника и DEV-008.
- **Steps:** разделены два подтверждённых пути — самостоятельная загрузка в
  профиле и загрузка администратором ЮЛ через «Сведения о пользователях»; затем
  добавляется XML-файл.
- **Handoff:** `false`.
- **Routing:** фактический retrieval вернул пустой route; все route-поля `null`,
  а не заполнены по догадке.
- **Fallback:** при отсутствии/несовпадении role или требуемых facts карточку не
  применять; использовать общий `CLARIFY`/обычный RAG.

### CARD-STAS-002 — `resolve_rdik_0474_outdated_oktmo`

- **Intent:** устранить контроль `РДИК_0474`, вызванный неактуальным ОКТМО.
- **Role / audience:** `customer`, `supplier`; обе роли подтверждены source audience и
  `role_verified=true`.
- **Source ID:** `portal:588559:1`, `content_status=complete`.
- **Page / section / source date / URL:** в frozen SourceRecord все `null`; не выдумывались.
- **Required facts:** `rdik_code=РДИК_0474`, `organization_oktmo_state=outdated`.
- **Required conditions:** сработал именно `РДИК_0474`; в личном кабинете организации
  указан неактуальный ОКТМО. Оба условия прямо указаны в source text и DEV-010.
- **Steps:** `Управление профилем` → `Профиль компании` → `Заявка на изменение
  данных`; корректный восьмизначный ОКТМО в «Статистических кодах»; отправка заявки;
  после обновления — повтор подписания.
- **Handoff:** `false`.
- **Routing:** подтверждён live retrieval: `topic_id=TH8`, `subtopic_id=ST75`,
  `support_line=L2`, `rule_id=ROUTE.LINE.THEME_DEFAULT`; `recommended_recipient=null`.
- **Fallback:** если код не `РДИК_0474` или не подтверждёно условие о неактуальном
  ОКТМО, карточку не применять; использовать `CLARIFY`/обычный RAG. Адресата не
  предлагать: evidence его не подтверждает.

## Status и runtime

Обе карточки:

- `status=draft`;
- не reviewed и не approved;
- `reviewer_id=null`, `reviewed_at=null`;
- `author_id=stas`;
- не импортированы в runtime: поиск по backend/knowledge/config/frontend/tools/tests не
  нашёл `CARD-STAS` или `content/cards/stas`.

В ScenarioCard-схеме нет отдельных полей `fallback`, `page` и `section`; fallback и доступность
page/section поэтому зафиксированы в handoff, не выданы за несуществующие поля контракта.

## Validation / acceptance

- `ScenarioCard.model_validate_json()` — **2/2 passed**; схема с `extra=forbid`.
- Ровно два JSON-файла в `content/cards/stas/` — **passed**.
- Draft/reviewer/snapshot assertions — **passed**.
- `store.get_source()` на оба source IDs — **passed**, records complete.
- Live retrieval на первую utterance каждой карточки — `ANSWER_ALLOWED`; карточный route
  побитово совпал с retrieval route — **passed**.
- Frozen snapshot compatibility по `snapshot_id`, canonical input hashes, counts и source IDs —
  **passed**.
- `git diff --check` — **passed**.
- Sealed final diff относительно BASE_SHA пуст — **passed**.

## Known limitations

1. Frozen C07 файл конфига на BASE_SHA находится только в `origin/task/c07`, а не в `main`; B05 не
   мержит и не копирует чужие C07-файлы.
2. Локальные Windows-байты SQLite/manifest имеют SHA-256 `971a0d66...` / `a22c30a9...` и не
   совпадают с macOS/G container hashes C07. C07 уже фиксирует platform-specific SQLite
   serialization; B05 поэтому проверил logical snapshot identity, input hashes, counts и сами records,
   но не заявляет байтовую идентичность локального DB-контейнера.
3. Для `CARD-STAS-001` routing-таксономия не даёт подтверждённый route, поэтому route пуст.
4. Portal SourceRecord обеих карточек не содержит page/section/date/URL. PDF-чанк по МЧД
   найден, но помечен `incomplete` из-за отсутствующих рисунков, поэтому в source IDs карточки
   он не включён.

## Что должен проверить Егор в C06

1. Независимо перечитать `portal:559615:1` и `portal:588559:1` в том же frozen snapshot.
2. Подтвердить roles/audience, все required facts и каждое condition отдельно от steps.
3. Проверить, что `CARD-STAS-001` не матчится на вопросы о необходимости/полномочиях
   МЧД, а только на intent загрузки XML в профиль.
4. Проверить точный match `РДИК_0474` и не путать карточку с другими РДИК-кодами.
5. Повторно вычислить routes и сохранить `recommended_recipient=null`, если evidence не изменился.
6. Проверить fallback: при недостающем/несовпавшем fact карточка не должна обходить
   `CLARIFY`/обычный RAG.
7. Только после положительной независимой проверки можно менять status/reviewer и
   импортировать; B05 этого не делала.

## Blockers / CR

- **Blockers:** нет.
- **Contract change requests:** нет; текущая ScenarioCard schema достаточна.
