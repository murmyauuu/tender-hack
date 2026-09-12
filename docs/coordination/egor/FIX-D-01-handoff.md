FIX-D-01 — DEV20 manifest SHA reconciliation

BASE_SHA: 7d7b44c

Old SHA: 7dff9fc14660e1f938208987400dd65ec70bde164f1c91168b1e91350084cda2
Canonical SHA: af04729dd3f708b2ec16e043486c06dbbf54e76003dd12e2e91e62d202aff786

Root cause:
ai_test_dev.jsonl had CRLF (Windows-style) line endings. The canonical Git blob hashes file content as-stored, and CRLF adds extra bytes (\r) that change the SHA256 digest. Converting CRLF→LF (Unix line endings) produces the correct canonical SHA while preserving all 20 JSONL case contents identically.

Changed files:
- evaluation/ai_test/dev/ai_test_dev.jsonl: CRLF → LF line ending conversion (binary content preserved, 20 rows unchanged)
- evaluation/ai_test/dev/manifest.json: sha256 updated from 7dff9fc... to af04729d...

Content preservation confirmation:
- All 20 JSONL rows present and valid (DEV-001 through DEV-020)
- All test_ids, group_ids, gold_source_ids unchanged
- All case content preserved — only \r characters removed from line endings
- Binary SHA of converted file matches canonical intended value: af04729dd3f708b2ec16e043486c06dbbf54e76003dd12e2e91e62d202aff786

Tests:
- verify_eval.py / evaluate_pairs.py should pass with 20/20 valid JSONL rows
- Manifest hash now matches canonical intended bytes

CR to owner A — .gitattributes needed:
- Add: evaluation/ai_test/dev/ai_test_dev.jsonl -text eol=lf
- This prevents future CRLF↔LF conversions from changing the manifest SHA
- Does not change existing content; only enforces correct line endings going forward

Historical evidence preserved:
- A03 handoff, C03 runtime acceptance, C07 handoff not rewritten — old SHA documented in this reconciliation
- Dataset content fully preserved; only metadata (manifest SHA) corrected