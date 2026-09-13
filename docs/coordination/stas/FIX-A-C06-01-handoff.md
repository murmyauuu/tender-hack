# FIX-A-C06-01 — deterministic reviewed ScenarioCard path

## Status and pins

- Status: **implemented and regression-tested**; C06 was not continued in this chat.
- Branch: `fix/a-c06-zero-generation-card`.
- BASE_SHA: `83a85d822e09e1c893cf2dbd8899ccdc8e8ecb99` (`origin/main`, fetched and fast-forwarded before work).
- Implementation commit: `364a0cac87c190e4af927d488f3640a1be04b600`.
- GPU: not used or required.
- Contracts, frontend, ScenarioCard drafts, C06 review/import files, retrieval architecture, and evaluation were not changed.

## Temporary ownership transfer

The project lead explicitly transferred temporary ownership of the minimum A-owned backend files needed only for FIX-A-C06-01. The transfer was used for `backend/tenderhack_backend/service.py` and the A-owned backend regression tests in `tests/test_service.py`. No C-owned implementation was edited.

## Reproduced before the fix

A regression test supplied an imported runtime card through `KnowledgePort.get_card()` and returned its ID in an `ANSWER_ALLOWED` `KnowledgeResult`. Before changing the service, the desired zero-generation assertion failed with an actual generator call:

```text
FAILED tests/test_service.py::test_reviewed_imported_card_does_not_call_generator
E       assert 1 == 0
E        +  where 1 = <tenderhack_backend.fakes.FakeGenerator ...>.calls
```

Command (the local worktree venv did not include pytest, so the pinned sibling venv was used with this worktree first on `PYTHONPATH`):

```powershell
$env:PYTHONPATH = "$PWD\backend;$PWD\contracts\python;$PWD"
..\c06-transfer-stas\.venv\Scripts\python.exe -m pytest tests/test_service.py::test_reviewed_imported_card_does_not_call_generator -q --basetemp var/pytest-fix-repro
```

## Root cause

`BackendService._process()` handled retrieval decisions and then always entered evidence packing and generation for `ANSWER_ALLOWED`. It never inspected `KnowledgeResult.card_id` and never called `KnowledgePort.get_card()`. Therefore a successful reviewed-card match was indistinguishable from ordinary RAG at the backend boundary and invoked the generator.

## Changed A-owned files

- `backend/tenderhack_backend/service.py`
  - resolves `KnowledgeResult.card_id` before the generation branch;
  - defensively requires a runtime-imported card with matching ID and snapshot, `status=reviewed`, `reviewed_at`, non-empty sources, and an independent non-empty reviewer;
  - requires confirmed applicability role when the card declares roles;
  - requires every executable condition represented by `required_facts` to be present and equal;
  - publishes deterministic content with `answer_origin=card`, reviewed source IDs and route, `generation_total=0`, without calling the generator;
  - applies `handoff_required`: status becomes `handoff_offered`, response is a notice, and solution steps are withheld as required by section 11 of the unified spec.
- `tests/test_service.py`
  - adds the reproduced zero-generation regression and all required positive/fail-closed cases;
  - extends profanity coverage with an explicit embedding counter.

## After behavior and generation-call evidence

For a matched imported/reviewed card with independent reviewer, current snapshot, real reviewed source IDs, applicable confirmed role, and all required facts:

```text
knowledge.retrieve_calls = 1
generator.calls = 0
request.timings_ms["generation_total"] = 0
message.answer_origin = "card"
message.source_ids = card.source_ids
```

The deterministic summary, conditions and (for a non-handoff card) steps come directly from the card. A handoff card remains zero-generation, preserves its sources and `answer_origin=card`, produces `handoff_offered`, and does not present steps as a completed resolution.

Fail-closed tests show wrong role, absent required fact, mismatched condition fact, unreviewed card, self-review, or a card absent from the imported runtime registry do not use card content and continue through the existing RAG path (`generator.calls=1`, `answer_origin=rag` in the controlled fixture). Profanity still closes before embedding/retrieval/generation with `0/0/0` calls.

## Tests

Passed:

```text
tests/test_service.py
24 passed in 5.64s

Relevant backend suite excluding the known generated-OpenAPI baseline failure
52 passed, 1 deselected in 19.49s

python -m compileall -q backend contracts/python tests/test_service.py
exit 0

git diff --check
exit 0 (only Windows LF/CRLF checkout warnings)
```

The full Python suite was run and collected 499 tests. Actual result: **493 passed, 6 failed**. None of the failures touches the two changed files:

1. `tests/test_app.py::test_generated_openapi_matches_runtime` — committed generated OpenAPI differs from the current runtime app on the synced base.
2. Five immutable-input/hash tests fail because three tracked raw KB text files are checked out with CRLF on this Windows worktree while the committed manifests/blob hashes expect LF:
   - three failures in `tests/test_bootstrap_docs.py`;
   - two failures in `knowledge/kb/tests/test_inputs_and_hashes.py`.

These baseline failures were not repaired because contracts/generated artifacts, raw inputs, manifests, and knowledge files are outside this FIX scope.

## Blockers

- No blocker for FIX-A-C06-01 implementation or its relevant backend acceptance.
- The repository-wide suite cannot be reported fully green in this Windows worktree for the six pre-existing/base issues listed above.
- Real C06 zero-generation acceptance still depends on C06 completing its independently reviewed import manifest; this FIX does not continue or approve C06.
