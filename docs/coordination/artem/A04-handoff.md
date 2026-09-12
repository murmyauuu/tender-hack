# A04 — Handoff и настоящий operator reply

## Status and pins

- Status: **PASS** for A04 backend/runtime. A05/A08 were not started.
- Branch: `task/a04`
- BASE_SHA: `56da4216b7bfd5e1cc3cbc620029cd90045f4391` (`origin/main` after A03 merge).
- Result/content SHA: `7ef5f1a0d3284c59eca5325c9d632995013482bc`
  (`f948cf531c9ebd95e8c62cb01dc3ea2b3dfb6065` implementation plus feedback coverage).
- Contracts: existing `2.1.0-a02`; no DTO or generated frontend change was required.
- Runtime class: real FastAPI + SQLite + C01 policy and protected internal HTTP endpoint;
  the repeatable A04 smoke uses controlled no-model knowledge dependencies because the handoff
  path must perform no generation. GPU was not used and no C07/G slot was occupied.

Preflight confirmed A03 (`56da421` merge / `f92d87d` handoff), C04 (`a95dc68`), B03 fixture
phase (`27f41aa` / `28dc241` handoff), and C03 real-dense acceptance (`f62ce77`) in the base.

## Implemented flow

- `handoff_offered` still has `ticket=null`. Public confirmation atomically creates one Ticket,
  moves the Case to `handed_off`, invalidates any active Request, and persists a receipt.
- An unambiguous `explicit_human_request` from C01 creates the Ticket directly, without an extra
  confirmation and without retrieval/generation.
- The database `UNIQUE(case_id)` constraint remains the final one-Ticket-per-Case guard. Exact
  repeats of handoff and reply are returned from durable receipts; changed bodies conflict.
- Internal reply requires a backend-only Bearer key. The backend assigns `author_id`,
  `responder_type=operator`, and `answer_origin=operator`; these fields are forbidden in the input.
- An operator reply moves `Ticket new -> waiting_user`. A following user Message is stored with a
  terminal Request receipt, moves the Ticket back to `new`, and never enters the AI queue. The next
  operator reply can choose `waiting_user` again or atomically resolve both Case and Ticket.
- A queued Request cancelled by policy/handoff is discarded before retrieval. An already in-flight
  result fails the publication version/active-request guard and cannot add an AI Message.
- Profanity in a handed-off Case closes the Case and every unfinished Ticket as `closed_policy`
  before knowledge/model work.

## C04 routing and Ticket context

The Ticket copies the accepted `Case.route` rather than recomputing or inventing a route. Its
context snapshot contains the Case identity/version/facts, ordered Message history, handoff reason,
topic/subtopic, `support_line`, rule/ambiguity/defect fields, and source IDs from C04 basis plus
history. `recommended_recipient` is included in the context only when non-null; the smoke kept it
absent. The controlled smoke carried `TH1 / ST01 / L2 / portal:42:1` end to end.

## Actual local smoke

Command:

```powershell
uv run python -m tools.run_a04_e2e --output-dir var/a04
```

Actual persisted run:

- Case ID: `9bd28616-c2d3-45d0-bc6d-9efd14715f96`
- Ticket ID: `df4f345a-be2c-4878-af98-7651bdd00d70`
- First operator Message: `f622ff17-7e26-477c-89c8-8677d5e54db8`
- Resolved operator Message: `2a1a4e70-1f13-48a8-9907-8a3c76e50bc9`
- SQLite evidence (gitignored):
  `var/a04/a04-dd5a118d-89bf-48d9-a30a-8bc2853c6837.sqlite`

Observed state transitions:

```text
handoff_offered / ticket:none
handed_off      / ticket:new
handed_off      / ticket:waiting_user
handed_off      / ticket:new
resolved        / ticket:resolved (resolved_by=operator)
```

The user-to-operator follow-up returned a terminal Request and measured
`retrieval_delta=0`, `generation_delta=0`. Refresh through `GET /api/v1/cases/{id}` showed the same
operator Message exactly once with server-authored identity fields.

## Security evidence

- No internal key: HTTP `401`; wrong key: HTTP `401`. Missing backend configuration is implemented
  as a fail-closed HTTP `503`.
- Forged `author_id`, `responder_type`, or `answer_origin`: HTTP `422` before domain mutation.
- Valid protected reply: HTTP `200`, `author_id=operator-smoke`,
  `responder_type=operator`, `answer_origin=operator`.
- A fresh foreign browser session reading the smoke Case: HTTP `404`.
- `npm test` captured only the public browser operations and cookie credentials. Authored browser
  transport has no internal-reply method. Exact source/bundle scan found no operator key environment
  name or test/runtime value; the production bundle contains no `/internal/tickets` URL. Browser
  storage code persists only `tenderhack.current-case-id`; it does not persist credentials.
- The real secret value is not committed, printed by the CLI, recorded here, or shown below.

## Feedback checks

- AI answer accepts normal feedback but rejects `specialist_rating` with `422`.
- Operator answer accepts `specialist_rating=1..5`; backend identity, not a client flag, decides this.
- Current operator `solved=true` resolves Case and Ticket with `resolved_by=user`.
- `solved=false` keeps the human flow active and puts the Ticket back in `new`.
- `solved=true` on an older AI or operator Message after a newer turn is saved with
  `outcome_applied=false`, `outcome_reason=ANSWER_NOT_CURRENT`, and does not close the Case.

## AC09–AC14

| AC | Result | Evidence |
|---|---|---|
| AC09 | PASS | Ticket absent at offer; confirmation `201`; exact repeat `200` with same ID; context includes C04 route/history/reason/source context. |
| AC10 | PASS | Protected operator Message appears in the same Case; user follow-up returns Ticket to `new` with retrieval/generation deltas `0/0`. |
| AC11 | PASS | Foreign Case `404`; missing/wrong key `401`; forged author/origin/type `422`; browser source/bundle/storage checks above. |
| AC12 | PASS | Durable chat/handoff/reply receipts and `UNIQUE(case_id)` prevent duplicates; exact handoff and operator reply repeats return original objects. |
| AC13 | PASS | Both pre-start cancellation (`0` retrieval/generation) and an in-flight late-generation publication race are covered; no late AI Message is persisted. |
| AC14 | PASS | AI/operator feedback separation, operator-only specialist rating, and stale solved `outcome_applied=false` are covered. |

## Verification

- `uv run pytest` -> `491 passed in 32.46s`.
- `uv run python -m compileall -q backend contracts/python tools` -> exit `0`.
- `npm run check:generated` -> PASS, four generated files checked with no diff.
- `npm run typecheck` -> PASS.
- `npm test` -> four files passed, one opt-in live file skipped; `25 passed`, `1 skipped`.
- `npm run build` -> PASS, 40 modules, JS `263.06 kB` (`80.99 kB` gzip).
- `git diff --check` -> PASS (only platform line-ending notices).

## Demo commands (no secret value)

The backend process and operator CLI must already have `TENDERHACK_OPERATOR_REPLY_KEY` in their
environment. Do not put it in shell history, browser variables, curl arguments, or files.

Start backend and create a cookie session:

```powershell
uv run uvicorn tenderhack_backend.app:app --host 127.0.0.1 --port 8000
curl.exe -sS -c var/a04/cookies.txt -b var/a04/cookies.txt -X POST http://127.0.0.1:8000/api/v1/sessions
```

User question, poll, and explicit handoff confirmation:

```powershell
$CHAT_KEY = (New-Guid).Guid
curl.exe -sS -c var/a04/cookies.txt -b var/a04/cookies.txt -H "Content-Type: application/json" -d "{`"request_key`":`"$CHAT_KEY`",`"text`":`"Нужна помощь по неизвестной операции`"}" http://127.0.0.1:8000/api/v1/chat
curl.exe -sS -b var/a04/cookies.txt http://127.0.0.1:8000/api/v1/requests/$REQUEST_ID
curl.exe -sS -b var/a04/cookies.txt http://127.0.0.1:8000/api/v1/cases/$CASE_ID
$HANDOFF_KEY = (New-Guid).Guid
curl.exe -sS -b var/a04/cookies.txt -H "Content-Type: application/json" -d "{`"request_key`":`"$HANDOFF_KEY`",`"expected_case_version`":$CASE_VERSION}" http://127.0.0.1:8000/api/v1/cases/$CASE_ID/handoff
```

Operator asks a follow-up (reply text comes from a file; key comes only from environment):

```powershell
uv run python -m tools.operator_reply --ticket-id $TICKET_ID --expected-case-version $CASE_VERSION --text-file var/a04/operator-followup.txt --next-status waiting_user
```

User follow-up, which does not launch AI:

```powershell
$FOLLOWUP_KEY = (New-Guid).Guid
curl.exe -sS -b var/a04/cookies.txt -H "Content-Type: application/json" -d "{`"case_id`":`"$CASE_ID`",`"expected_case_version`":$CASE_VERSION,`"request_key`":`"$FOLLOWUP_KEY`",`"text`":`"Номер закупки 123`"}" http://127.0.0.1:8000/api/v1/chat
```

Operator resolves:

```powershell
uv run python -m tools.operator_reply --ticket-id $TICKET_ID --expected-case-version $CASE_VERSION --text-file var/a04/operator-resolution.txt --next-status resolved
```

Replace IDs/versions only with values returned by the immediately preceding API reads. Reusing the
same request key with the exact same body demonstrates idempotency; reusing it with another body is
expected to return `409`.

## Blockers / handoff to B03

No A04 backend blocker. No frontend B03 file was edited. Stas can now run the remaining real browser
verification against this branch/result SHA, including visual refresh/polling and developer-tools
network/storage observation. The generated contract check remains clean.
