# D00 — handoff

- Status: done
- Owner / tool: Егор (D) / Manus-агент + ручная проверка; Python 3.14.5, pandas 3.0.3, openpyxl 3.1.5 — только чтение данных
- Base SHA: `ab2c182` (origin/main HEAD; `TenderHack_UNIFIED_SPEC_v2.1_prefilled.md`)
- Result SHA: `26f44dd0a75b3f1c9283b9ce17a40a352802ee57` (контентный commit D00; финальный tip с фиксацией SHA в handoff — см. ветку `task/d00-rubric-eval-plan`)
- Contracts version: v2.1 (контракты отсутствуют — до C0); предложен CR-D-001
- Machine profile: N — Azerty RB-1551, Celeron N5095, 16 ГБ RAM, Intel UHD; GPU не использовался
- Runtime SHA / KB snapshot: KB локально: `TenderHack_KnowledgeBase/knowledge_base_FINAL.sqlite` (1468 документов, документ с FTS5); `knowledge_base_FINAL.jsonl` закоммичен
- Changed files:
  - `evaluation/README.md` (новый)
  - `evaluation/rubric.md` (новый)
  - `evaluation/cohorts.md` (новый)
  - `evaluation/history_selection_plan.md` (новый)
  - `evaluation/training_examples.md` (новый)
  - `evaluation/schema/evaluationrow_requirements.md` (новый)
  - `docs/coordination/egor/CR-D-001-evaluationrow.md` (новый)
  - `docs/coordination/egor/D00-handoff.md` (этот, новый)
- Implemented behavior:
  - Рубрика 4 измерений 0/1/2/not_assessable с причинами (`N_REASON_*`), critical_error (`CE_01..CE_06`),
    правила независимой разметки/согласования, порядок оценщика, перечень метрик из рубрики;
  - Методика трёх массивов (AI-test 20 dev + 40 final; История 30 пар + до 10 учебных; Live/demo)
    с правилами разделения знаменателей и этапами;
  - План отбора 30 исторических пар с фактическим аудитом реальной выгрузки
    (`НН 2026/Выгрузка СТП за 2026.xlsx`), схемой pair_id (HIST-0001..0030 + резерв HIST-R01..R10);
  - 8 учебных примеров (якоря, НЕ итоговые 30) с обоснованием всех четырёх измерений, CE
    и статусом проверки по KB (substring-сверка с `knowledge_base_FINAL.sqlite`);
  - Требования минимального EvaluationRow для A00 + CR-D-001 (не альтернативный API).
- Acceptance: passed (критерии D00 — см. ниже «Проверки»). Человеческое подтверждение некоторых значений — см. «Что подтвердить вручную».
- Commands and actual outputs:
  - `git rev-parse HEAD` → `ab2c182` (base); `git rev-parse origin/main` → `ab2c182`; `git status --short` → пусто (до работы);
    ветка создана: `git switch -c task/d00-rubric-eval-plan ab2c182`.
  - Аудит истории: `pd.read_excel('НН 2026/Выгрузка СТП за 2026.xlsx')` → shape `(24960, 6)`;
    колонки: Влияние, Заявитель, Тема, Статус, Описание, Решение; nulls 0; дублей (Описание,Решение) 192;
    Решений <10 симв. 304; префикс «Подтема запроса:» 23508/24960; Тема unique 795;
    Влияние=RFI 24719/24960; Статус и Заявитель — константы («Завершено», «Заявитель»).
  - SHA-256: выгрузка `8159199e23214439ba26554d821c7c37b087f3188bc02949d989e8fbc63d83c9`;
    таксономия `f5649e083b5f0c13cf346e26387064aca2c33edb9c9e7ceee1c3cc4641f5d05a`.
  - KB: `SELECT COUNT(*) FROM documents` → 1468; FTS5 присутствует;
    subset-сверки для учебных примеров: «новое исполнение» — найдено; «исправительн» — найдено
    (в т.ч. «11.5.8 Формирование УПД»); «МЧД»/«DIT_PP» — найдено (3+);
    «5б» — 0 совпадений (KB snapshot старше события: строка 5б ± апрель 2026).
- Data mode: **real**. История и KB — реальные файлы команды в репозитории; учебные примеры — реальные
  пары (обезличены, сокращены) с честным статусом проверки; mock/fixtures не использовались. PASS по D00
  — содержательный, не синтетический.
- Artifacts and paths: файлы раздела «Changed files»; артефакты наших данных не изменялись
  (`data/raw`, `НН 2026`, `TenderHack_KnowledgeBase` — только чтение).
- Known blockers and reproducible defects:
  - В выгрузке истории **нет author_id, таймстампов, линий/адресатов, SLA/CSAT-полей** → персональные
    рейтинги, SLA и CSAT не вычислимы и не заявляются; для истории `author_id=null`.
  - «Тема» шумная (795 значений), подтема — неканоническая строка внутри «Описания»; сверять с
    таксономией `Темы_подтемы_обращений.xlsx`.
  - KB snapshot не содержит контекст «5б» (новые правила УПД) → для таких пар до появления нового
    источника возможна только `not_assessable` (не 0).
  - 30 пар реально отберет и подтвердит **D01**; D00 даёт только методику и правила.
  - `input_inventory.md` — зона A; D00 не правит её (запрос на фиксацию истории ушёл в CR-D-001/этот handoff).
- Contract change requests: `docs/coordination/egor/CR-D-001-evaluationrow.md` — минимальная схема
  EvaluationRow в A00 (Status: pending).
- Inputs required by next task:
  - **D01**: принять этот D00-handoff; A00 C0 (contracts/export schema + fixtures); C00 inventory;
    реальные файлы: `НН 2026/Выгрузка СТП за 2026.xlsx` (SHA выше) и `НН 2026/Темы_подтемы_обращений.xlsx`;
    правила отбора 30 пар и pair_id схему — из `evaluation/history_selection_plan.md`; рубрику —
    `evaluation/rubric.md`; НЕ использовать учебные примеры как итоговые пары.
  - **B04/D03**: рубрика, учебные примеры, единый манифест pair_id (из D01).

## Проверки по критериям D00 (фактические)

| Критерий готовности (v2.1) | Факт |
|---|---|
| Рубрика пригодна людям | да: 0/1/2/not_assessable с причинами, границы, порядок оценщика, CE, независимость/согласование |
| Нет выдуманного SLA/CSAT/author | да: аудит показал отсутствие полей; документально запрещено (rubric.md, requirements) |
| История и blockers перечислены | да: `history_selection_plan.md` + блокеры выше |
| Учебные примеры не входят в итоговые 30 | да: 8 TRN явно отделены, ссылка на 30 пар — D01 |
| Schema-предложения переданы через A | да: CR-D-001 (pending) + `evaluation/schema/evaluationrow_requirements.md` |
| Не создан альтернативный API | да: только требования и CR; реализация — одна команда A, её нет в этой задаче |

## Что Егор подтверждает вручную

1. Расчёты аудита истории (24 960 строк, колонки, «Заявитель»/«Статус» — константы, отсутствие авторов/дат).
2. Содержание учебных примеров: обезличивание текстов (нет ФИО/номеров контрактов/ссылок), полнота выдержек.
3. Демонстрационные оценки TRN-01..08 пересмотрены; расхождения с будущей разметкой не изменяют эти файлы,
   а фиксируются отдельно.
4. Согласие с передачей требований EvaluationRow в A00 через CR-D-001.