CR-A-01 — DEV20 line ending reconciliation

Initiator / task: FIX-D-01 / DEV20 manifest SHA reconciliation
Base SHA / contracts version: 7d7b44c (ev(D01): publish 20 dev AI-test cases)

Problem:
- Manifest SHA (7dff9fc14660e1f938208987400dd65ec70bde164f1c91168b1e91350084cda2) does not match canonical Git blob SHA (af04729dd3f708b2ec16e043486c06dbbf54e76003dd12e2e91e62d202aff786)
- Root cause: ai_test_dev.jsonl has CRLF line endings (Windows-style) but should have LF line endings (Unix-style) for canonical Git blob hashing
- The binary content of the 20 JSONL cases is unchanged — only CRLF→LF conversion performed

Current contract:
- evaluation/ai_test/dev/manifest.json currently declares SHA: 7dff9fc14660e1f938208987400dd65ec70bde164f1c91168b1e91350084cda2
- Canonical Git blob SHA for the JSONL file: af04729dd3f708b2ec16e043486c06dbbf54e76003dd12e2e91e62d202aff786

Proposed change:
- Update manifest SHA from 7dff9fc14660e1f938208987400dd65ec70bde164f1c91168b1e91350084cda2 to af04729dd3f708b2ec16e043486c06dbbf54e76003dd12e2e91e62d202aff786
- JSONL content preserved identically (20 rows, all test IDs, groups, gold source IDs unchanged)
- Add .gitattributes entry for evaluation/ai_test/dev/ai_test_dev.jsonl to enforce LF line endings

Touch consumers:
- C07, C03, A03 — all have validated this dataset and confirmed content preservation

Can continue independent part: Yes — only metadata (manifest SHA) changed, not data

Proposed test: Run evaluate_pairs.py / verify_eval.py to confirm 20/20 JSONL rows valid and manifest hash matches canonical bytes

Decision A: pending — need owner A approval for .gitattributes addition

Decision SHA: pending