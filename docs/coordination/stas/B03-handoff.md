# B03 — Полный пользовательский цикл с человеком

## Status and pins

- Status: **done**.
- Branch: `task/b03`.
- BASE_SHA: `476643812fac0ba62b545659abb4e4ffe888c186` (fresh `origin/main`).
- A04 accepted/content SHA: `7ef5f1a0d3284c59eca5325c9d632995013482bc` (`docs/coordination/artem/A04-handoff.md`: `Status: PASS`).
- B03 real-verification content SHA: `c69a13ebdb1909bb7d1ef9f0f674c42695797191`.
- Contracts: generated from accepted `contracts/openapi/openapi.json`, version `2.1.0-a02`; no DTO was invented or changed.

The earlier frozen/controlled UI implementation is retained. This run adds real browser/API
verification against the accepted A04 FastAPI service. A04's real persistence, policy, version,
receipt, feedback, handoff and protected-reply paths were used; only knowledge/generation were
controlled to select deterministic branches. No controlled answer is claimed as a real RAG result.

## Actual human-flow identifiers

- Case: `bd0afc51-9b7c-4171-b904-32c1ecbe6117`.
- Ticket: `44e41433-1882-4094-8115-f162e555a087`.
- Initial Request: `8c2b476b-55e8-4791-8f84-b4a609940875`.
- First operator Message: `d274b342-0225-4ba9-a120-09ab95d23f6c`.
- User follow-up Message: `d5069bd5-6123-4c52-baf8-0b24d2fab874`.
- Terminal user-to-operator Request: `3f6390af-70d7-4bd1-8781-702243064507`.
- Resolving operator Message: `de706909-a073-4d21-bb56-e101a1d5d7b5`.

```text
handoff_offered / ticket:null / case_version=2
handed_off      / ticket:new / case_version=3
handed_off      / ticket:waiting_user / case_version=4
handed_off      / ticket:new / case_version=5
resolved        / ticket:resolved / case_version=6 / resolved_by=operator
```

The explicit confirmation dialog preceded the public handoff mutation. Replaying the exact A04
receipt returned HTTP `200` and the original Ticket after the initial `201`; no second Ticket was
created. A black-box repeat also produced Case `57c181e3-0842-4ee5-8db4-60b1f7bc9ab8` and Ticket
`b69f2be7-4bfa-40a3-a20e-588b5b4770bd`, again `201 -> 200` with one Ticket ID.

## Browser observations

- Before confirmation the Case was `handoff_offered`, `ticket=null`; UI showed no Ticket and used a
  separate dialog saying the request enters the local queue of our service.
- The protected A04 CLI supplied the first reply from a backend-only environment. Polling rendered
  it in the same Case as `Ответ специалиста`, with a distinct operator class, Ticket `waiting_user`,
  and specialist-rating controls. AI used `Ответ по инструкции` and had no specialist rating.
- The user follow-up was present once after refresh, returned Ticket to `new`, created a terminal
  Request with all retrieval/generation timings null, and added no AI answer. The protected second
  operator reply resolved Case/Ticket with `resolved_by=operator`.
- Refresh restored both operator Messages exactly once. This run found and fixed a production issue:
  human polling now restarts on `case_version`, so operator resolution after a user follow-up appears
  without manual refresh. A regression test covers polling through resolve.
- Retry was exercised after a controlled first generation failure. UI sent `retry_of` with
  `text=null`; retry succeeded without duplicating the original user Message.
- A delayed old Request was followed by `Новая тема` and another Case. Five seconds after the old
  result completed, active UI still showed only the new Case/handoff offer and no old question/answer.
- Real stale behavior used two tabs in one browser session. Tab 2 confirmed handoff; stale Tab 1
  submitted the old version and received `409`, reread Case/Ticket, preserved
  `Не потерять этот пользовательский ввод` in the textarea, and required manual resubmit. There was
  no blind retry.
- Policy input in a handed-off browser Case produced Case/Ticket `closed_policy` and a disabled
  composer. Controlled counters were unchanged at `0/4/1` (embedding/retrieval/generation) across
  that mutation. A separate real active-Request probe ended the old Request as `cancelled`; the
  policy Request reported `retrieval=null`, `generation_total=null`.

## Feedback evidence

- AI answer: `useful=true` saved independently from `solved`; `specialist_rating` was absent in UI
  and a real API attempt was rejected with `422`.
- Operator answer: browser saved `specialist_rating=5` successfully.
- After a newer turn, `solved` on the older AI answer returned `outcome_applied=false`; UI said the
  rating was saved without changing current Case, kept the handoff offer, and did not claim closure.

## Security / DevTools evidence

- The production bundle contains only public `/api/v1` session/chat/request/case/handoff/source/
  feedback endpoints. It contains no `/internal/tickets`, operator-key name/value, Ollama, SQLite,
  or external Portal integration.
- Browser access logs contained only public endpoints. Internal reply calls came only from the
  protected local operator procedure, never from frontend transport.
- Production bundle storage strings are only `localStorage` and `tenderhack.current-case-id`; there
  is no `sessionStorage` use or credential key. Cross-tab restore confirmed the pointer restores the
  Case while authentication stays in the HttpOnly cookie and is unavailable to page script.
- Public/browser attempts to add `author_id`, `responder_type`, `answer_origin` were rejected `422`.
  Protected operator route without a key returned `401`; backend authored operator identity fields.
- No direct SQLite, direct Ollama, browser operator key, or fake external Portal integration was
  added. `frontend/scripts/b03_real_api_probe.py` is black-box HTTP-only.

## Acceptance criteria

| AC | Result | Real evidence |
|---|---|---|
| AC03 | PASS | One real clarification (`ROLE_REQUIRED`), then role answer and handoff offer. |
| AC09 | PASS | `ticket=null` before consent; one Ticket after consent; exact repeat reused it. |
| AC10 | PASS | Protected reply in same browser Case; user follow-up returned Ticket to `new` with zero AI work. |
| AC14 | PASS | useful/solved separation, operator-only rating, AI rating `422`, stale feedback did not close Case. |
| AC15 | PASS | Refresh restored ordered history; retry used `retry_of` without duplicate user text. |
| AC19 | PASS | Polling, refresh, dedupe, new-topic guard, late-result rejection and two-tab stale recovery passed. |

## Verification results

| Check | Result |
|---|---|
| `npm run check:generated` | PASS; generated client unchanged |
| `npm run typecheck` | PASS |
| `npm test` | PASS; 4 files passed, 1 opt-in live file skipped; 26 passed, 1 skipped |
| `npm run build` | PASS; Vite 8.3.0, 40 modules, JS 263.43 kB (81.10 kB gzip) |
| `python -m compileall -q frontend/scripts` | PASS |
| `python frontend/scripts/b03_real_api_probe.py` | PASS; idempotency/stale/feedback/forgery/auth/policy assertions |
| real browser + protected operator CLI | PASS; observations and IDs above |
| production bundle/source security scan | PASS |

The test pool is pinned to one fork worker for reproducible execution in the constrained Windows
runner; the exact required `npm test` command passes with that project configuration.

## Blockers and scope

No B03 blocker remains. No CR was required because A04 and current generated contracts expose every
required state. B04 was not started.
