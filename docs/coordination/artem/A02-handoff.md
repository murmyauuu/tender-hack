# A02 — Backend core и минимальная обработка

## Delivery

- Branch: `task/a02`.
- BASE_SHA: `7d7b44c41f6996478105534ec933aa920f6fc1f1` (`origin/main`).
- Result payload SHA: `4e442b6f9556bd52782290954458061808709926`.
- The delivery commit that contains this handoff is the branch tip; it intentionally follows the
  result payload so that the payload SHA is immutable and reproducible.

## Preflight and inputs

`git fetch --prune origin`, `git switch main`, and `git pull --ff-only origin main` completed with
a clean `main`; the worktree was then created from `origin/main`, not from `task/a01`.

The accepted inputs were checked on that base: A00/C0, A01, C01, C02, B01, FIX-A-01, FIX-A-02, and
D01.  The D01 source commit is not an ancestor of the integration commit, but its
`evaluation/` content and `docs/coordination/egor/D01-handoff.md` are identical on the base.
Read inputs: v2.1 unified specification, repository `AGENTS.md`, A00/A01/C01/B01/D01 handoffs,
CR-B01, D00 EvaluationRow requirements, and C0 contracts/OpenAPI/fixtures.

## What A02 delivers

- Durable `var/app.sqlite` state with session, Case, Message, Request, feedback, idempotency
  receipt, and ticket tables; WAL and startup recovery preserve cases and mark interrupted work.
- HttpOnly, SameSite=Strict session cookie; origin check for browser mutations; private Case and
  Request resources conceal other sessions with `404`.
- `POST /api/v1/chat` returns `202`; request polling, Case read, source read, and feedback are
  available.  A04 handoff/reply remain explicit `501` boundaries.
- A one-worker, capacity-four admission queue persists request state, maintains `case_version` and
  `active_request_id`, and guards final/error publication against stale requests.
- Exact chat idempotency and retry reuse the original user message.  Queue overflow rejects before
  persistence with `429`.
- C01 `PolicyPort` is production-wired before queue admission.  `KnowledgePort` remains injected
  until C03; C02 supplies source lookup/health only.
- The A01-pinned `OllamaGenerator` makes exactly one `/api/generate` call, uses
  `qwen3:8b-q4_K_M`, manifest digest
  `a0a5ad8024dd21401f07634d0c71393b9c9d37aa57a6b594e02b86ab72c450b4`, GGUF SHA-256
  `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785`, `think=false`, and
  `/no_think`.  Invalid JSON is terminal for that request: it never starts an automatic generation
  retry.  No 4B fallback exists.
- The verifier accepts only safe structured proposals backed by returned evidence; unsupported
  generation output becomes a visible failed request rather than a silent re-generation.
- `python -m tools.export_data` emits one schema-validated `EvaluationExport` row per Case,
  including unfinished/error/no-answer cases.

## CR-B01 decision for B02

CR-B01 required frozen `RequestView` progress examples, `SourceRecord`, and structured answer
sections.  The minimal backward-compatible contract update is version `2.1.0-a02`:

- optional `Message.structured_content` and `ExportMessage.structured_content` with `summary`,
  `conditions`, and `steps`;
- preserved required flat `content`/`text` as the fallback representation;
- added frozen queued/retrieving/sources-found request fixtures and one mock `SourceRecord` fixture;
- regenerated OpenAPI and EvaluationExport JSON Schema.

No existing endpoint or required field was removed.  B02 should render structured sections when
present and otherwise use the retained plain text.  See `docs/integration/contract_changelog.md`.

## Verification evidence

- `uv run python -m tools.generate_contracts` was run twice; the second run produced no diff.
  SHA-256: OpenAPI `D1EF35FF03D2060C48ED76DC16C022133E27EF341612AA16D577E92B6290D3CE`, export schema
  `CDEA45C477C854940973E7D395C4D32D7A93186B220B0A0863EC7AF0B7A4719D`.
- `uv run python -m tools.validate_fixtures` validated all 12 frozen fixtures.
- A02 Python files: `uvx ruff check ...` and `uvx ruff format --check ...` passed; the repository
  has unrelated pre-existing Ruff findings in non-A02 Python files.
- `uv run python -m compileall -q backend contracts/python tools` passed.
- `uv run pytest -q --tb=short` passed (100% exit code 0).
- Controlled real HTTP smoke with uvicorn and injected Policy/Knowledge/Generator fakes passed:
  `session (201) -> chat (202) -> poll(final) -> Case(awaiting_feedback) -> source -> feedback
  (201)`.  The received session cookie had `HttpOnly=True` and `SameSite=Strict`.
- The smoke database export succeeded with one `resolved` row and was validated as
  `EXPORT_VALID rows=1`.
- In a temporary B01-compatible frontend copy, the regenerated client passed
  `npm run typecheck`, `npm test` (8 tests), and `npm run build`.
- Acceptance behaviour is covered by controlled-dependency tests: idempotent chat, retry without a
  duplicate user message, stale success and failure publication guards, restart recovery, exactly
  one call for invalid JSON, feedback update/rules, private 404, forged-cookie 401, origin check,
  queue 429, policy short circuit, and no-answer export.

## Mock / real boundary and known limits

The HTTP smoke used only explicit fakes passed to `create_app`; production wiring never selects
them.  C01 is real production policy.  C02 source lookup is real production wiring, but retrieval
is intentionally dependency-injected until C03/A03.  A live Ollama generation smoke was not run:
the configured model/digest is the factually verified A01 runtime and GPU G was left available for
Eduard's C03 embedding build.  This task does not start A03.  A04 operator work remains out of
scope.  WSL2/Linux admission remains an organizer decision from A01.

API_READY_FOR_B02=yes
