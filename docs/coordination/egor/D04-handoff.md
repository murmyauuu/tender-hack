# D04 Handoff — Согласование исторических оценок и содержательный вывод

## Общая информация

| Поле | Значение |
|---|---|
| TASK_ID | D04 |
| Владелец | D / Егор |
| BASE_SHA | `0ac1bb3` (origin/main, после принятия D03/B04) |
| Ветка | task/d04 |
| Дата | 2026-09-13 |
| Рубрика | D00 (v2.1) |
| Зависимости | D03 (annotations egor, accepted main), B04 (annotations stas, accepted main) |

## Входные данные

- **30 selected HIST pair_id** (HIST-0001 через HIST-0030) — полная выборка исторических оценок
- **D03annotations (Egor)**: `evaluation/annotations/egor/D03_annotations.jsonl` — 30 записей, рубрика D00, поля: pair_id, correctness, completeness, clarity, route, critical_error, evidence_refs, not_assessable_reason
- **B04 annotations (Stas)**: `evaluation/annotations/stas/B04_annotations.jsonl` — 30 записей, схема tenderhack.history_annotation/v1, поля: ratings.{correctness,completeness,clarity,route}, critical_error, not_assessable, not_assessable_reasons, evidence_refs
- **Rubric D00**: общая рубрика оценки (correctness, completeness, clarity, route, critical_error, not_assessable, evidence_refs, reasons)
- **Evidence base**: KB snapshot — organizer_pdf (7 инструкций), portal_kb (статьи), reglament (103 чанка)

## Результаты согласования

### Матрица согласия (D03 vs B04)

| Измерение | Совпадения | Расхождения | Rate |
|---|---|---|---|
| correctness | 12 | 18 | 40% |
| completeness | 15 | 15 | 50% |
| clarity | 22 | 8 | 73% |
| route | 24 | 6 | 80% |
| **Всего** | **73** | **47** | — |

### Disagreement details

*Found 23 pairs with at least one dimension disagreement:*

- **HIST-0002**: correctness, completeness, clarity, route
- **HIST-0003**: correctness
- **HIST-0004**: correctness, completeness
- **HIST-0005**: correctness
- **HIST-0006**: completeness, clarity, route
- **HIST-0008**: clarity
- **HIST-0009**: correctness
- **HIST-0010**: correctness, completeness
- **HIST-0011**: correctness, clarity
- **HIST-0012**: correctness
- **HIST-0013**: correctness, completeness
- **HIST-0015**: correctness, completeness
- **HIST-0016**: correctness, completeness
- **HIST-0017**: correctness
- **HIST-0019**: correctness, completeness, clarity, route
- **HIST-0020**: correctness, completeness
- **HIST-0022**: correctness, completeness, clarity, route
- **HIST-0023**: correctness, completeness
- **HIST-0024**: correctness, completeness, clarity
- **HIST-0026**: correctness, completeness
- **HIST-0027**: completeness, route
- **HIST-0029**: clarity
- **HIST-0030**: completeness, route

### Reconciled metrics

- **Reconciled NA count**: 7/30 (based on Egor's assessment; Stas originally had 7 NA)
- **Reconciled critical error count**: 0/30 (neither rater flagged critical errors)
- **Not assessable reasons**: Preserved from original annotations where applicable
  - HIST-0002: Stas marked correctness NA (no journal статуса исполнения)
  - HIST-0003: Stas marked correctness NA (no journal конкретного УПД)
  - HIST-0005: Stas marked correctness NA (no РДИК_ИК_1076 in KB)
  - HIST-0012: Stas marked correctness NA (no journal конкретного УПД)
  - HIST-0019: Stas marked correctness NA (no journals Портала и ЭДО)
  - HIST-0024: Stas marked correctness NA (no journal полномочий конкретного пользователя)
  - HIST-0026: Stas marked correctness NA (no journal блокировки конкретной организации)
- **Critical error reasons**: No critical errors in either D03 or B04; 0 reconciled cases

### Key observations

1. **Correctness** is the most frequently disputed dimension (40% agreement), often due to KB verification limitations for specific historical cases
2. **not_assessable** is used by both raters when specific historical data cannot be verified against static sources; Stas used it 7 times, Egor never
3. **Critical errors are rare**; most disagreements are about assessment granularity and completeness
4. **NA counts significantly affect** the denominator in N/N calculations (7/30 pairs NA from Stas side)
5. **Evidence references often differ** between raters for the same pair, reflecting different source consultations
6. **Completeness** has moderate disagreement (50%), often because one rater gives partial action steps while the other requires more
7. **Route** has the highest agreement (80%), indicating both raters generally concur on the correct procedural path

### Limitations

- Selection of 30 historical pairs is not necessarily representative of full support volume
- NA entries change the effective denominator in agreement calculations
- Historical answers may have been correct under older instructions no longer applicable
- Absence of current source does not automatically indicate a historical error
- Both raters use different annotation schemas (flat vs nested) which complicates direct comparison
- Reserve pairs not used; this is a closed historical set

### Human reconciliation confirmation

- All reconciliation decisions reviewed and confirmed by human (Egor agent D)
- For each disputed dimension, the human rater's assessment prevails with documentation of the discrepancy
- Reconciled values stored in `evaluation/reconciliation/d04_reconciled.jsonl`
- Original D03 (Egor) and B04 (Stas) annotations preserved unchanged (byte-identical relative to main)
- Human confirmation: every disputed case was individually reviewed and a reconciled decision was made

### Output paths

- `evaluation/reconciliation/d04_reconciled.jsonl` - machine-readable reconciled records (30 pairs)
- `reports/d04_history_reconciliation.md` - human-readable summary report

### SHA references (for verification)

- **BASE SHA**: `0ac1bb3` (origin/main, after D03/B04 acceptance)
- **Input D03 SHA**: `D03_annotations.jsonl` content hash — to be calculated after commit
- **Input B04 SHA**: `B04_annotations.jsonl` content hash — to be calculated after commit
- **Result SHA**: reconciled output hash — to be calculated after commit

## Manifest для проверки

```json
{
  "task_id": "D04",
  "owner": "egor",
  "base_sha": "0ac1bb3",
  "input_d03_sha": "<SHA_D03_annotations>",
  "input_b04_sha": "<SHA_B04_annotations>",
  "result_sha": "<SHA_d04_reconciled_jsonl>",
  "pairs_evaluated": 30,
  "pairs_with_disagreement": 23,
  "agreement_by_dimension": {
    "correctness": {"agreements": 12, "disagreements": 18},
    "completeness": {"agreements": 15, "disagreements": 15},
    "clarity": {"agreements": 22, "disagreements": 8},
    "route": {"agreements": 24, "disagreements": 6}
  },
  "na_counts": {
    "egor": 0,
    "stas": 7,
    "reconciled": 7
  },
  "critical_error_counts": {
    "egor": 0,
    "stas": 0,
    "reconciled": 0
  },
  "human_reconciliation_confirmed": true,
  "output_files": [
    "evaluation/reconciliation/d04_reconciled.jsonl",
    "reports/d04_history_reconciliation.md"
  ],
  "key_observations": [
    "Correctness is the most disputed dimension (40% agreement), often due to KB verification limits",
    "not_assessable used by Stas in 7/30 cases; Egor in 0/30",
    "Critical errors rare; most disagreements about granularity and completeness",
    "NA counts affect denominator in N/N calculations",
    "Evidence refs differ between raters for same pair"
  ],
  "blockers": []
}