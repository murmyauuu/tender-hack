# A02 Backend Core Implementation Plan

> **For agentic workers:** Execute inline with the repository TDD and verification rules. Each behavior starts with a failing focused test.

**Goal:** Deliver the API-ready A02 backend core, durable SQLite state, controlled single-generation processing, and one-row-per-Case evaluation export.

**Architecture:** Keep SQL and transaction invariants in a repository, state transitions and queue admission in an application service, and HTTP/cookie/error concerns in a FastAPI factory. Inject `PolicyPort`, `KnowledgePort`, and `GeneratorPort`; production uses C01 policy, the C02 source-capable/degraded knowledge adapter until C03, and an A01-pinned Ollama adapter. The worker holds no SQLite transaction while awaiting retrieval or generation and publishes only through a version/active-request guard.

**Tech Stack:** Python 3.12, FastAPI/Pydantic, stdlib SQLite/asyncio/urllib, pytest/httpx.

---

### Task 1: Resolve CR-B01 without breaking B01

**Files:** `contracts/python/tenderhack_contracts/models.py`, `contracts/fixtures/request_*.json`, `contracts/fixtures/source.json`, `contracts/fixtures/answer.json`, `tools/validate_fixtures.py`, `tests/test_contracts.py`, generated OpenAPI/schema, `docs/integration/contract_changelog.md`.

- [x] Add failing contract tests for optional structured answer content and the four new frozen fixtures.
- [x] Run the focused tests and confirm the missing fields/files fail.
- [x] Add optional `structured_content={summary,conditions,steps}` while retaining required `content`; bump the contract version and add honest fixtures.
- [x] Regenerate OpenAPI and JSON Schema, validate every fixture, and confirm B01's existing fixtures remain valid.

### Task 2: Add durable application storage and recovery

**Files:** `backend/tenderhack_backend/storage.py`, `tests/test_storage.py`.

- [x] Add failing tests for schema creation, atomic chat receipts, private ownership, retry reuse of the user message, feedback upsert, guarded publication, restart recovery, and export of a Case without an answer.
- [x] Run the focused tests and confirm failures are caused by the absent repository.
- [x] Implement six domain tables plus idempotency receipts using short SQLite transactions, UUIDs, UTC timestamps, body hashes, JSON columns, and WAL.
- [x] Implement startup recovery from queued/processing to `RESTART_INTERRUPTED`, clearing matching active requests while preserving messages and receipts.
- [x] Run storage tests green.

### Task 3: Add orchestration, one-call verifier, and bounded queue

**Files:** `backend/tenderhack_backend/service.py`, `backend/tenderhack_backend/verifier.py`, `tests/test_service.py`.

- [x] Add failing controlled-dependency tests for answer/clarify/escalate/policy, exact chat idempotency, retry, stale publication, queue overflow, and invalid generation calling the generator exactly once.
- [x] Run tests red.
- [x] Implement policy-before-admission, capacity four (one running plus three waiting), persisted request progress, `KnowledgePort` gate handling, exactly one generator call, strict proposal verification, and guarded atomic final publication.
- [x] Run service tests green and assert policy paths make zero knowledge/generator calls.

### Task 4: Expose secure HTTP sessions and A02 endpoints

**Files:** `backend/tenderhack_backend/app.py`, `backend/tenderhack_backend/config.py`, `tests/test_a02_http.py`.

- [x] Add failing HTTP tests for session cookie flags, chat 202, poll/case/source/feedback, idempotency, private-resource 404, origin rejection, feedback rules, and 429 before persistence.
- [x] Run tests red.
- [x] Implement the app factory, lifespan worker, HttpOnly/SameSite=Strict cookie, origin guard, contract error envelope, and the six A02 operations; keep A04 handoff/reply explicitly unimplemented.
- [x] Run HTTP tests green.

### Task 5: Add the A01-pinned GeneratorPort adapter

**Files:** `backend/tenderhack_backend/generator.py`, `config/runtime/a02.json`, `.env.example`, `tests/test_generator.py`.

- [x] Add failing adapter tests for model name/digest configuration, `think=false`, `/no_think`, discriminated JSON parsing, transport failure, and invalid JSON without a second request.
- [x] Run tests red.
- [x] Implement one Ollama `/api/generate` request via a blocking call moved off the event loop; parse exactly once into `GenerationProposal` or raise a typed failure.
- [x] Run adapter tests green without loading the GPU model.

### Task 6: Add the single evaluation export

**Files:** `backend/tenderhack_backend/export.py`, `tools/export_data.py`, `tests/test_export.py`.

- [x] Add failing tests for one row per Case, nullable author/version fields, feedback/current resolution, and inclusion of unfinished/no-answer Cases.
- [x] Run tests red.
- [x] Implement a consistent SQLite read transaction and `python -m tools.export_data --output ...` JSON envelope validated by `EvaluationExport`.
- [x] Run export tests green.

### Task 7: Verify, document, commit, and push

**Files:** `README.md`, `docs/coordination/artem/A02-handoff.md`.

- [x] Run contract generation twice and require no second diff; validate fixtures.
- [x] Run backend-focused tests, the full Python suite, frontend generated-contract check/build if compatible, and a real local uvicorn HTTP smoke using controlled adapters only.
- [ ] Record exact commands, mock/real boundaries, BASE_SHA, model digest, CR-B01 decision, actual results, and `API_READY_FOR_B02=yes` only if the HTTP contract passed.
- [ ] Inspect scope/status/diff, create conventional commits on `task/a02`, push `origin task/a02`, and record the immutable result SHA.
