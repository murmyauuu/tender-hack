# B03 — handoff

- Task ID / status: B03 — Полный пользовательский цикл с человеком / **partial — fixture/UI phase complete, awaiting A04 real verification**
- Owner / tool: Стас / агент B / Codex
- BASE_SHA: `f62ce7784d4e166cab4b6015732fa8e23c1c9254` (fresh `origin/main`; rebased before push after C03 acceptance advanced main)
- Result/content SHA: `9645e20ce0dff5bbe9999e93cab16dd75d92d4cd`
- Branch: `task/b03`
- Dependency state: B02 accepted in `origin/main` via `393e8b0`; A04 handoff/accepted result is absent.
- Contracts: current generated client from `contracts/openapi/openapi.json`, version `2.1.0-a02`; no DTO was added or changed.

## Implemented states and behavior

- Clarification replies, ordinary follow-up messages and replies after an operator answer use the current loaded `case_version`.
- `handoff_offered` has a separate explicit confirmation step. Confirmation calls only the public handoff operation and sends `request_key` plus the current `expected_case_version`.
- Ticket UI distinguishes `new` (waiting for a specialist), `waiting_user`, `resolved` and `closed_policy`. Text refers only to a specialist and the local queue of our service.
- The generated public handoff operation is connected to the real browser transport. The internal operator reply operation and operator key are not connected to browser code.
- Operator and AI answers have different labels and visual classes. Specialist rating is rendered only for a message whose server-authored fields are `responder_type=operator` and `answer_origin=operator`.
- Failed Requests expose explicit retry. Retry uses a new `request_key`, `text=null`, `retry_of=<failed request id>` and the current Case version, so it does not duplicate the original user Message.
- Feedback remains message-specific. `useful` and `solved` are separate writes. A response with `outcome_applied=false` is shown as saved feedback whose Case status did not change, never as a resolved Case.
- Existing B02 recovery remains active: Case restoration from the stored pointer, server-history reread, `message_id` deduplication and late/current-case guards. A new topic invalidates in-flight old Case/Request/source work.
- Policy closure is rendered as closed and disables the composer.
- Test concurrency is capped at one worker so the complete frontend suite is reproducible on this Windows machine without the earlier worker OOM.

## Fixture/UI verification completed

The following are verified with frozen contract fixtures or explicitly controlled browser-transport fixtures, not with A04:

- clarification prompt and reply with version 2;
- `handoff_offered` → explicit confirmation → one Ticket in `new` state;
- repeated fixture handoff returns the same Ticket for the Case;
- Ticket `new` and `waiting_user` presentation;
- operator reply presentation, concrete-message specialist rating, and a user reply that returns Ticket to `new` without presenting an AI result;
- explicit `retry_of` with `text=null`;
- policy closure and disabled composer;
- refresh/history recovery and duplicate operator-message protection;
- stale error presentation and both pre-fetch and in-flight late-result rejection;
- separate useful/solved controls, operator-only rating, and honest `outcome_applied=false` presentation;
- generated public handoff request path and `credentials: include`.

## Actual test results

Run from `frontend/` on local Windows with Node `24.18.0` and npm `11.16.0`:

| Check | Actual result |
|---|---|
| `npm run check:generated` | PASS; `@hey-api/openapi-ts v0.99.0`, 4 generated entry files, no generated diff |
| `npm run typecheck` | PASS; `tsc --noEmit`, exit 0 |
| `npm test` | PASS; 4 files passed + 1 opt-in live file skipped, 25 tests passed + 1 skipped |
| `npm run build` | PASS; Vite 8.3.0, 40 modules; HTML 0.50 kB, CSS 7.40 kB, JS 263.06 kB |
| Security source check excluding generated code | PASS; no operator key, Bearer construction, internal reply call, direct SQLite/Ollama, or fake external Portal integration in authored frontend runtime |
| Real A04 operator/handoff flow | **NOT RUN — A04 is not published/accepted** |

The skipped live test is the existing opt-in B02 HTTP smoke. No fixture result above is claimed as a real operator or handoff PASS.

## What still requires A04

- Real creation/idempotent reuse of the single Ticket for one Case.
- Real protected operator reply, backend-authored operator identity, `waiting_user` and resolved transitions.
- Proof that a user reply after an operator answer saves a Message, moves Ticket to `new`, and does not invoke AI.
- Cross-process refresh/polling while an operator reply arrives.
- Real stale-version conflict/recovery and late-result behavior across handoff/new-topic transitions.
- Real feedback semantics for AI versus operator answers, including server rejection of specialist rating on AI and `outcome_applied=false` on stale feedback.
- AC03/09/10/14/15/19 final evidence. Until these checks run, B03 is not a full real PASS.

## Exact real verification plan after A04

1. Fetch fresh `origin/main`; require the accepted A04 handoff/result SHA to be an ancestor, record the new BASE_SHA, run `npm run check:generated`, typecheck, tests and build before runtime testing.
2. Start the published A04 backend with its documented local configuration and the frontend in `VITE_API_MODE=real` through the same-origin proxy. Keep the operator credential only in the A04 CLI/process environment; inspect the browser network/storage to confirm it is absent.
3. In a new browser session create a Case that asks one clarification. Record Case versions before the clarification reply and after the terminal Request; verify exactly one clarification and no automatic second clarification.
4. Create a no-evidence Case, verify `handoff_offered` with `ticket=null`, open and cancel the confirmation once, then confirm using the currently reread Case version. Repeat the handoff operation per A04's idempotency procedure and verify both responses reference the same Ticket and Case history contains only one Ticket.
5. From the separate protected A04 operator CLI send a `waiting_user` reply. Refresh the browser and verify one visually distinct operator Message, Ticket `waiting_user`, no duplicate after repeated Case reads, and rating controls only on that operator Message.
6. Reply from the browser to that operator Message. Verify the mutation carries the latest Case version, history gains one user Message, Ticket becomes `new`, and no AI generation/answer is created. Send a second protected operator reply with `resolved` and verify Case/Ticket resolution and `resolved_by=operator`.
7. Force one documented retryable Request failure. Use the UI retry button and verify the accepted mutation has `retry_of=<failed request>`, `text=null`, a new request key, the latest Case version, and no duplicate original user Message.
8. Start a delayed Request, choose **Новая тема**, submit a different Case, then allow the old Request/Case/source response to finish. Verify the current Case id, messages, Ticket and source drawer remain those of the new topic. Repeat with an in-flight Request restored after a page refresh.
9. Trigger a documented stale version between read and each mutation (chat, retry and handoff). Verify 409 causes a Case reread, preserves relevant user input, does not retry blindly and requires an explicit new action based on the refreshed version.
10. Save `useful` and `solved` independently on an AI answer; verify no specialist rating control. Save rating on the operator answer. Apply solved feedback to an older answer and verify the API returns `outcome_applied=false` and the UI does not show the Case as closed.
11. Submit the policy-closure input in an eligible open/handed-off Case. Verify current Request invalidation, unfinished Ticket `closed_policy`, closed Case UI and disabled composer.
12. Capture exact commands, HTTP/status evidence without secrets, browser observations and resulting SHAs; only then update B03 acceptance to a real PASS. Do not substitute frozen fixtures or the B02 fake-backed smoke.

## CR / security

No contract gap was found: current generated contracts already contain `HandoffInput`, Ticket states, `retry_of`, operator-authored Message fields and `FeedbackResponse.outcome_applied`. Therefore no CR to A was created. A04 absence is a runtime verification dependency, not a DTO gap.

No operator key, cookie, token, model endpoint, SQLite path, Ollama call or external Portal imitation is present in this change. `frontend/dist` and `frontend/node_modules` remain local ignored artifacts.

B04 was not started.
