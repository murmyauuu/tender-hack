# FIX-A-02 — cross-platform raw input manifest hashes handoff

- Status: done
- Owner / tool: Артём / agent A / Codex
- BASE_SHA: `dddb724f454c986a60c6b3243db41f22bfbfabea` (`origin/main` after `git fetch --prune origin`)
- Result SHA (implementation): `45b69dc219864e75728e2ef59b25f017fe7e73a0`
- Branch: `fix/a02-cross-platform-input-hashes`
- Contracts version: `2.0.0-c0`, unchanged
- Changed files: `.gitattributes`; `docs/integration/input_manifest.sha256`; `tools/verify_input_manifest.py`; `tests/test_bootstrap_docs.py`; this handoff

## Root cause and historical result

A00 computed the input manifest from a Windows working tree with system
`core.autocrlf=true`. Git stored LF blobs, but checkout converted the three raw text
inputs to CRLF because the paths were not all protected by attributes. Therefore the
A00 Windows `14/14 OK` result was honest for that checkout while Linux/macOS, which
read canonical LF bytes, rejected those three CRLF hashes.

FIX-A-01 had already canonicalized the KB manifest entry and added `-text` for that
one path before this task's BASE_SHA. At FIX-A-02 baseline the KB was therefore
already byte-stable, while the summary and API report still had CRLF manifest values.
The original A00 result remains historical; neither A00 history nor the
`bootstrap-contracts-v2` tag was rewritten.

## Canonical raw text inputs

| Tracked path | A00 / CRLF SHA-256 | Canonical blob SHA-256 | Blob / CRLF bytes |
|---|---|---|---:|
| `TenderHack_KnowledgeBase/knowledge_base_FINAL.jsonl` | `439e7041b233498a894a9eab41917e07e79109408e1f09b7cbb96668c1b8df2c` | `71bf714a9e205a35f5d8ec0fd2d0f9bbd4ad3a8409968b754eb8de7b349d79ae` | 3,021,234 / 3,022,702 |
| `TenderHack_KnowledgeBase/TenderHack_KnowledgeBase_summary.txt` | `54d69db84ef896bd5bd24a7c68595e8c14aebc5b7db83047846953b645be5096` | `413f922d1961b33dc34fcfd4450af7b4fd6472260fa5af80ed95f0952a032312` | 11,228 / 11,539 |
| `TenderHack_KnowledgeBase/api_report.json` | `a94d1125b9fd3a724ffb9dceec3a758cb9037e06f4d3a239d55728a0a58b802c` | `74b1ca3ff7c2c5cbcd74f716542f40ed9ccfb4527699525fb88b63cac5d31050` | 1,183 / 1,233 |

The canonical KB still parses as 1,468 records with 1,468 unique IDs.

## Git attributes

Only the affected tracked paths are marked; no global normalization rule was added:

```gitattributes
TenderHack_KnowledgeBase/knowledge_base_FINAL.jsonl -text
TenderHack_KnowledgeBase/TenderHack_KnowledgeBase_summary.txt -text
TenderHack_KnowledgeBase/api_report.json -text
```

The raw file entries have no content diff from BASE_SHA. Their Git blob IDs remain:

- `75981be753b31edb7e6229e5b3a437150fb10af0` — KB JSONL
- `a34d5ec170e169585410bda57c5c95f867c8d3bc` — summary
- `5df3e4002ac835a37dbce48de9fd56df404bca9a` — API report

No `git add --renormalize`, cached-index rebuild, destructive reset/clean, raw rewrite,
history rewrite, or tag move was performed.

## Windows clean-checkout verification

A new detached worktree was checked out from the implementation commit with
`core.autocrlf=true`; the pre-existing task worktree was not forcibly refreshed.

- `git ls-files --eol` for all three paths: `i/lf w/lf attr/-text`
- `git check-attr --all`: `text: unset` for all three paths
- working-tree SHA-256 equals canonical Git blob SHA-256 for all three paths
- `uv run python tools/verify_input_manifest.py`: `14/14 OK`
- canonical KB SHA-256: `71bf714a9e205a35f5d8ec0fd2d0f9bbd4ad3a8409968b754eb8de7b349d79ae`

## Tests

- Baseline before changes: `uv run pytest` — `29 passed in 1.73s`
- Regression RED: summary manifest SHA was `54d69d...`, blob SHA was `413f92...`
- Clean-checkout C0/manifest regression: `uv run pytest tests/test_bootstrap_docs.py -q` — `6 passed`
- Clean-checkout full regression: `uv run pytest` — `31 passed in 1.47s`
- Contracts/API/state machine diff against BASE_SHA: none
- Blockers: none

## Independent macOS verification

From a fresh checkout of this branch/commit, Eduard can run:

```sh
shasum -a 256 -c docs/integration/input_manifest.sha256
```

Expected result: all 14 entries report `OK`.
