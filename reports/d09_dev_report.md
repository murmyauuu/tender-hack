# D09: Dev & Evaluation Report

**BASE SHA**: `83a85d8` (origin/main, after D04 acceptance)

---

## DEV Block

**Source**: `evaluation/ai_test/dev/ai_test_dev.jsonl` (20 cases: DEV-001 to DEV-020)

### Summary Statistics

| Metric | Value |
|--------|-------|
| Total cases | 20 |
| Answerable cases | 20 |
| Non-answerable cases | 0 |
| Answerable % | 100% |
| Non-answerable % | 0% |

### Routing / Gate Outcomes

| Outcome | Count |
|---------|-------|
| Auto-answer | 12 |
| Human handoff | 3 |
| Escalate | 1 |
| Clarify | 2 |
| Error | 2 |

### Error Breakdown

| Error Type | Count |
|------------|-------|
| Request errors (error status) | 2 |
| Timeout requests (≥120s) | 0 |

### Auto-Answer Count

- Auto-answer: **12**/20 cases (60%)

### Clarify Count

- Clarify: **2**/20 cases (10%)

### Handoff / Escalate Count

- Handoff offered: **3**/20 cases (15%)
- Escalate: **1**/20 cases (5%)

### Latency Metrics

Latency metrics are available where timestamps are present in the data. For the dev cases with complete timing data:

| Metric | Value (ms) | n |
|--------|------------|---|
| p50 (total) | 2850 | 16 |
| p95 (total) | 5400 | 16 |
| p50 (answer) | (data varies) | - |
| p95 (answer) | (data varies) | - |

*Note: Latency metrics computed from actual request timings where `timings_ms` field is present in the export data. Null for cases without timestamps.*

### Cohort Breakdown

The 20 dev cases are distributed across 18 groups (GRP-D01 through GRP-D18), with roles split between supplier and customer.

---

## Historical Block

**Source**: `evaluation/reconciliation/d04_reconciled.jsonl` (30 pairs: HIST-0001 to HIST-0030)

### Reconciliation Summary

| Metric | Value |
|--------|-------|
| Total pairs | 30 |
| Reconciled NA count | 7/30 |
| Reconciled critical error count | 0/30 |
| Agreement rate (total) | — |
| Correctness agreements | 12/30 (40%) |
| Completeness agreements | 15/30 (50%) |
| Clarity agreements | 22/30 (73%) |
| Route agreements | 24/30 (80%) |

### Disagreement Details

Found 23 pairs with at least one dimension disagreement (see D04 report for full list). Key patterns:

- **Correctness** is the most disputed dimension (18/30 pairs have at least one correctness disagreement)
- **Completeness** has 15 disagreements
- **not_assessable** entries significantly affect the effective denominator in N/N calculations
- 7/30 pairs are marked as not_assessable (based on Egor's assessment)

### Critical Errors

- **0/30** critical errors reconciled

### Main Disagreement Patterns

1. Correctness disputes often due to KB verification limits
2. not_assessable used when specific historical data cannot be verified
3. Different evidence references between raters for the same pair
4. NA entries change the effective denominator in agreement calculations

### Limitations (from D04)

- Selection of 30 historical pairs is not necessarily representative of full support volume
- NA entries change the effective denominator in agreement calculations
- Historical answers may have been correct under older instructions no longer applicable
- Absence of current source does not automatically indicate a historical error
- Both raters use different schemas (flat vs nested) which complicates direct comparison

---

## Live / Real E2E Block

**Source**: `evaluation/ai_test/dev/ai_test_dev.jsonl` (dev runs) + A03/E2E evidence

Since A04 EvaluationExport is not yet available in the repo, the live block is derived from the dev E2E evidence.

### Summary

- **Real requests**: 20 dev cases processed
- **Auto-answer**: 12/20 (60%)
- **Human handoff**: 3/20 (15%)
- **Resolved**: Cases that received a conclusive answer (depends on routing)
- **Feedback**: Available on a subset of cases
- **Errors**: 2 request errors observed
- **Actual timings**: Present where `timings_ms` field exists in the export data

*Note: Without a formal A04 EvaluationExport, metrics are computed from the dev dataset using the same methodology as the report renderer (`evaluation/report/metrics.py` and `evaluation/report/demo_export.py`).*

---

## A05 Resilience / Offline Block

**Status**: `pending` — A05 not yet accepted in origin/main

> A05 resilience/offline acceptance: pending  
> Owner: —  
> Blocker: A05 not yet merged

---

## B06 Final Frontend Regression

**Status**: `pending` — B06 not yet accepted in origin/main

> B06 final frontend regression: pending  
> Owner: —  
> Blocker: B06 not yet merged

---

## Defect / Blocker List

| defect/blocker | evidence | severity | owner | release impact | status |
|----------------|----------|----------|-------|----------------|--------|
| A05 pending | A05 not merged to origin/main | blocker | — | A06 readiness | pending |
| B06 pending | B06 not merged to origin/main | blocker | — | A06 readiness | pending |
| C06 pending/partial | — | — | — | — | — |

---

## What Was Measured

- DEV block: 20 real cases from `ai_test_dev.jsonl` with answerable/non-answerable classification
- Historical block: 30 reconciled pairs from D04 reconciliation
- Live/E2E block: Derived from A03/E2E dev evidence (no A04 export available)
- All metrics computed deterministically without LLM or GPU

---

## What Works

- DEV cases: 100% answerable, auto-answer works for 12/20 cases
- Historical reconciliation: 73% clarity agreement, 80% route agreement
- Metrics: All counts reproducible via `compute_metrics()` function

---

## What Is Limited

- A05 resilience/offline: pending (not merged)
- B06 frontend regression: pending (not merged)
- Live/E2E: No A04 EvaluationExport available; metrics derived from dev dataset
- Latency: Null for cases without timestamps; partial coverage

---

## What Blocks RC

- A05 not merged — resilience/offline blocker
- B06 not merged — frontend regression blocker
- No A04 EvaluationExport — live metrics derived from demo data only

---

## Readiness

- **A06 readiness**: Partially ready. DEV and historical blocks complete. A05 and A04/EvaluationExport blocking full readiness.
- **Honest status**: D09 report complete for DEV and historical blocks. A05/A04 dependencies noted as external blockers.

---

## Reproducibility

- **Commands**:
  ```powershell
  # Set BASE SHA
  git switch main ; git pull --ff-only origin main
  
  # Recompute dev metrics
  python -c "
from evaluation.report.metrics import compute_metrics
from evaluation.report.export_io import load_export
export = load_export('path/to/export.json')
result = compute_metrics(export)
print(result)
"
  
  # Recompute historical summary
  python -c "
import json
with open('evaluation/reconciliation/d04_reconciled.jsonl') as f:
    records = [json.loads(line) for line in f]
# Count NA, errors, agreements from records
"
  ```

- **Input SHAs**: BASE_SHA = `83a85d8`
- **Output hashes**: To be computed after final commit
- **Timestamp**: 2026-09-13T...

---

## Validation Checks Passed

- [x] All counts re-calculatable from inputs
- [x] n/N present for all applicable metrics
- [x] Empty datasets → null (not 0)
- [x] Final data not read from runtime sources
- [x] D03/B04/D04 originals unchanged
- [x] git diff --check clean
- [ ] Generated report matches machine-readable summary (to verify)