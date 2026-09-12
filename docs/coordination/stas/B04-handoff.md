# B04 — Независимая историческая разметка Стаса

## Status and pins

- Status: **done**.
- Branch: `task/b04`.
- BASE_SHA: `bb2bb16a878d3638124e5da2ac4217edd55ac715` (fresh accepted `origin/main` after `git fetch --prune origin`).
- Result/content SHA: `f1bff9afe8f9388ed9b8874dd051bab7b67c1d84`.
- Rater: `stas`.
- Rubric: D00, four independent dimensions `0/1/2/not_assessable` plus `critical_error`.
- Historical pairs: **30** selected pairs, `HIST-0001`…`HIST-0030`.

## Dependency preflight

- D00: accepted content is present in `origin/main`; `docs/coordination/egor/D00-handoff.md` reports `Status: done`.
- D01: accepted manifest and real 30-pair selection are present in `origin/main`; `docs/coordination/egor/D01-handoff.md` reports `Status: done`.
- B03: remote completion handoff at `origin/task/b03` commit `23f4955` reports `Status: done` and real A04 verification. That completion commit is not yet an ancestor of `origin/main`; the older partial B03 handoff remains on main. This is an integration-state note, not a blocker for the already independent historical scoring.
- Real source workbook and taxonomy SHA-256 matched the manifest. All normalized question/answer content hashes matched for the 30 selected rows.

## Human confirmation

- Status: **confirmed, 30/30**.
- Confirmed by: Стас.
- Confirmed at: `2026-09-13T01:39:13+03:00`.
- Confirmation text: «Подтверждаю каждую из HIST-0001…HIST-0030 без изменений».
- Every annotation row records the same confirmed status, confirmer and timestamp.

## Rating distributions

| Dimension | 0 | 1 | 2 | not_assessable | Total |
|---|---:|---:|---:|---:|---:|
| correctness | 0 | 14 | 9 | 7 | 30 |
| completeness | 5 | 10 | 15 | 0 | 30 |
| clarity | 0 | 6 | 24 | 0 | 30 |
| route | 0 | 6 | 24 | 0 | 30 |

- Critical errors: **0**.
- Pairs with any `not_assessable`: **7** (`HIST-0002`, `HIST-0003`, `HIST-0005`, `HIST-0012`, `HIST-0019`, `HIST-0024`, `HIST-0026`).
- `not_assessable` dimension values: **7**, all in correctness.
- Reasons used: `VERIFICATION_NOT_POSSIBLE` for unavailable case/operator state and `NO_SOURCE` for the absent exact RDIK_ИК_1076 source/runtime evidence.

## Sources and evidence

Source types used:

- `historical_pair`: immutable row reference with source workbook SHA-256;
- `portal_knowledge_base_api`: official Portal knowledge-base articles by existing document ID;
- `organizer_pdf`: supplied official instructions with existing document ID and page;
- `NO_SOURCE`: explicit marker only where the exact source or operational state was unavailable.

All KB document IDs in `evidence_refs` were checked against `TenderHack_KnowledgeBase/knowledge_base_FINAL.jsonl`; missing IDs: **0**. No SLA, CSAT, author identity, timestamps of historical cases, or unsupported authors were invented.

## Validation results

| Check | Actual result |
|---|---|
| Annotation JSONL parsing | 30/30 rows parsed |
| Selected `pair_id` equality with manifest | exact match |
| Unique pair IDs | 30/30 |
| Missing / extra pairs | 0 / 0 |
| `row_index` mismatches | 0 |
| Missing KB evidence IDs | 0 |
| Human confirmation | 30/30 confirmed |
| Critical errors | 0 |
| Source workbook SHA-256 | `8159199e23214439ba26554d821c7c37b087f3188bc02949d989e8fbc63d83c9`, matched |
| Taxonomy SHA-256 | `f5649e083b5f0c13cf346e26387064aca2c33edb9c9e7ceee1c3cc4641f5d05a`, matched |
| Normalized content hashes | all 60 question/answer hashes matched |
| Changed paths before content commit | only `evaluation/annotations/stas/**` and `docs/coordination/stas/**` |

The raw workbook, taxonomy, manifest, KB and source pairs were read-only and were not changed.

## Independence confirmation

**D03 ratings were not read before independent commit.**

No D03 annotation content, per-pair conclusions, ratings, or reconstructable aggregates were opened before result/content commit `f1bff9afe8f9388ed9b8874dd051bab7b67c1d84`. D03 was not used to create or revise these ratings.

## Files

- `evaluation/annotations/stas/B04_annotations.jsonl` — confirmed independent ratings and evidence for all 30 pairs.
- `docs/coordination/stas/B04-human-review.md` — per-pair human review matrix and confirmation record.
- `docs/coordination/stas/B04-handoff.md` — this handoff.

## Blockers

- B04 scoring blockers: **none**.
- Integration note: merge/accept the already completed B03 remote tip separately if main must carry its final `Status: done` handoff. B04 did not alter B03 and did not start B05.
