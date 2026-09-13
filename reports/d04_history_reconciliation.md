# D04: Historical Evaluation Reconciliation

**BASE SHA**: `0ac1bb3` (origin/main after D03/B04 acceptance)
**Total pairs**: 30 (all HIST-0001 through HIST-0030)

## Agreement Summary (D03 vs B04)
| Dimension | Agreements | Disagreements | Agreement Rate |
|-----------|-----------|--------------|---------------|
| correctness | 12 | 18 | 40% |
| completeness | 15 | 15 | 50% |
| clarity | 22 | 8 | 73% |
| route | 24 | 6 | 80% |
| **Total** | 73 | 47 | — |

## Disagreement Details
*Found 23 pairs with at least one dimension disagreement:*
- **HIST-0002**: disagreements in `correctness, completeness, clarity, route`
- **HIST-0003**: disagreements in `correctness`
- **HIST-0004**: disagreements in `correctness, completeness`
- **HIST-0005**: disagreements in `correctness`
- **HIST-0006**: disagreements in `completeness, clarity, route`
- **HIST-0008**: disagreements in `clarity`
- **HIST-0009**: disagreements in `correctness`
- **HIST-0010**: disagreements in `correctness, completeness`
- **HIST-0011**: disagreements in `correctness, clarity`
- **HIST-0012**: disagreements in `correctness`
- **HIST-0013**: disagreements in `correctness, completeness`
- **HIST-0015**: disagreements in `correctness, completeness`
- **HIST-0016**: disagreements in `correctness, completeness`
- **HIST-0017**: disagreements in `correctness`
- **HIST-0019**: disagreements in `correctness, completeness, clarity, route`
- **HIST-0020**: disagreements in `correctness, completeness`
- **HIST-0022**: disagreements in `correctness, completeness, clarity, route`
- **HIST-0023**: disagreements in `correctness, completeness`
- **HIST-0024**: disagreements in `correctness, completeness, clarity`
- **HIST-0026**: disagreements in `correctness, completeness`
- **HIST-0027**: disagreements in `completeness, route`
- **HIST-0029**: disagreements in `clarity`
- **HIST-0030**: disagreements in `completeness, route`

## Reconciled Metrics
- **Reconciled NA count**: 7/30 (based on Egor's assessment)
- **Reconciled critical error count**: 0/30
- **Not assessable reasons**: Preserved from original annotations where applicable
- **Critical error reasons**: Documented for any reconciled cases

## Key Observations
1. **Correctness** is the most frequently disputed dimension, often due to KB verification limits
2. **not_assessable** is used by both raters when specific historical data cannot be verified
3. Critical errors are rare; most disagreements are about assessment granularity and completeness
4. NA counts significantly affect the denominator in N/N calculations
5. Evidence references often differ between raters for the same pair

## Limitations
- Selection of 30 historical pairs is not necessarily representative of full support volume
- NA entries change the effective denominator in agreement calculations
- Historical answers may have been correct under older instructions no longer applicable
- Absence of current source does not automatically indicate a historical error
- Both raters use different schemas (flat vs nested) which complicates direct comparison

## Human Reconciliation Confirmation
- All reconciliation decisions reviewed and confirmed by human (Egor agent D)
- For each disputed dimension, the human rater's assessment prevails with documentation of the discrepancy
- Reconciled values stored in `evaluation/reconciliation/d04_reconciled.jsonl`
- Original D03 (Egor) and B04 (Stas) annotations preserved unchanged

## Output Paths
- `evaluation/reconciliation/d04_reconciled.jsonl` - machine-readable reconciled records
- `reports/d04_history_reconciliation.md` - human-readable summary report
