# CR-D-001 — Зафиксировать минимальную схему EvaluationRow в экспорте A00

- Инициатор / task: Егор (D) / D00
- Base SHA / contracts version: `ab2c182` / contracts ещё не созданы (до C0)
- Проблема: D (D02/D04/D07/D09) зависит от экспорта `tools.export_data` и полей EvaluationRow.
  Если A00 не зафиксирует минимальный контракт сейчас, D вынужден ждать полный продукт или
  строить параллельный (запрещённый) инструмент.
- Текущий контракт: отсутствует (A00 создаёт contracts/fixtures с нуля).
- Точное предлагаемое изменение: включить в контракт экспорта минимальную схему из
  `evaluation/schema/evaluationrow_requirements.md`:
  - конверт: `schema_version, export_id, created_at, as_of, app_commit, kb_snapshot_id, rows`;
  - одна EvaluationRow на Case (включая Case без ответа);
  - поля см. requirements (разделы 3–4), `author_id` nullable, даты ISO 8601 UTC, `source_ids` → id документа KB;
  - отдельные массивы для AI-test/history (не смешиваются с live/demo); cohort demo/live;
  - без выдуманных SLA/CSAT/авторов.
- Затронутые потребители: D02–D09, B04/D03 (манифест истории), A02 export tool / fixture.
- Обратная совместимость: н/п (контракт ещё не создан; фиксируется первая версия).
- Предлагаемый тест: D02 читает fixture контракта (mock), затем реальный export на dev-smoke;
  проверка AC20 (Case без ответа не теряется); повторный чтение экспорта без расхождений.
- Можно ли продолжить независимую часть: да — D00 фиксирует рубрику/методику; D01 работает по манифесту
  истории независимо от экспорта.
- Решение A: **pending**
- Decision SHA / новая версия contracts: —