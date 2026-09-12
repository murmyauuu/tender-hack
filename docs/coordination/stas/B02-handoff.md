# B02 — handoff

- Task ID / status: B02 — Подключение первого реального API / **done**
- Owner / tool: Стас / агент B / Codex
- Base SHA: `abea7ae6831a30cfcdc4d662caeefc9ced4b69a2` (`origin/main` после preflight)
- Result/content SHA: `4302e03277891538979c48524025bbbb11e6b261`
- Branch: `task/b02`
- Contracts version: `2.1.0-a02`; TypeScript client regenerated from current `contracts/openapi/openapi.json`
- Machine: local Windows; Node `24.18.0`, npm `11.16.0`
- Runtime / KB: A02 real HTTP contract; controlled-dependency smoke uses explicit fakes. A03 runtime and real C03 dense index are not published inputs for this task.

## Changed files

- `frontend/src/apiTransport.ts` — typed A02 transport over the generated SDK.
- `frontend/src/realChat.ts`, `frontend/src/useRealChat.ts` — polling and real chat state/history orchestration.
- `frontend/src/App.tsx`, `frontend/src/styles.css` — explicit real UI mode alongside the retained mock UI.
- `frontend/src/apiTransport.test.ts`, `frontend/src/realChat.test.ts`, `frontend/src/App.test.tsx` — transport/state/UI regression.
- `frontend/src/apiTransport.live.test.ts`, `frontend/scripts/a02_smoke_server.py` — opt-in real HTTP smoke with explicitly controlled backend dependencies.
- `frontend/vite.config.ts`, `frontend/.env.example`, `frontend/package.json`, `frontend/README.md` — same-origin dev proxy, mode configuration, commands and runbook.
- `frontend/src/generated/**` was regenerated and verified against A02 OpenAPI; generation produced no content diff from accepted main.

## Implemented behavior

- Real mode connects the six B02 operations: session, chat, Request polling, Case/history read, source read and feedback write. All calls use the generated A02 SDK and `credentials: include`; the browser never reads the HttpOnly cookie.
- Mock is still a separate mode. `VITE_API_MODE=real` is required to enter real mode; missing/other values select the frozen fixture mode. The header always states which mode is active.
- Vite proxies `/api` to `VITE_API_PROXY_TARGET` for a same-origin local browser flow. Production can use a same-origin reverse proxy or an explicit allowed `VITE_API_BASE_URL`.
- After accepted chat the UI follows Request every 800 ms in a foreground tab and every 3 seconds in a hidden tab. After final/error/cancelled it rereads Case.
- Current `case_id` is restored from localStorage after session creation; localStorage is only a pointer and confers no authorization. Case ownership remains server/cookie enforced.
- Messages are deduplicated by `message_id` and ordered by `seq` after every Case read.
- A generation/current-case token prevents an in-flight old Request, Case or source result from mutating a newly selected topic. Polling stops before the next request once the case is no longer current.
- Input is not cleared after 409, 429, 503 or network rejection. There is no blind mutation retry. An explicit retry of the same body reuses its idempotency `request_key`; editing the text or changing Case/version gets a new key.
- On 409 the current Case is reread before the user chooses whether to submit again.
- A02 `structured_content` renders summary, conditions and steps; the flat `content` remains the fallback. Source candidate stays visibly marked as not yet an answer.
- Feedback remains attached to a specific message; useful, solved and specialist rating keep their separate contract fields.
- No direct Ollama, SQLite, model, secret or operator-key access was added to the browser.

## Acceptance and actual results

| Check | Actual result |
|---|---|
| `npm ci` | success; 149 packages installed from lockfile |
| `npm run generate:api` | success; `@hey-api/openapi-ts v0.99.0`, 4 generated entry files |
| `npm run check:generated` | success; generated SDK/types have no diff from A02 OpenAPI |
| `npm run typecheck` | success; `tsc --noEmit`, exit 0 |
| `npm test` | success; 4 files passed + 1 opt-in live file skipped, 18 tests passed + 1 skipped |
| `npm run build` | success; Vite 8.3.0, 40 modules; HTML 0.50 kB, CSS 7.07 kB, JS 257.97 kB |
| `B02_LIVE_API_URL=http://127.0.0.1:8766 npm run smoke:api` | success; 1/1 live HTTP test passed |
| Real HTTP path | session 201 → chat 202 → Request polling final → Case/history 200 → source 200 → feedback 201 |
| Full browser RAG E2E | **not run — awaiting real C03/A03 runtime** |

The live smoke used a real loopback HTTP socket, FastAPI/A02 endpoints, generated TypeScript transport,
Origin validation and cookie persistence. Policy, Knowledge and Generator behind that HTTP server were
explicit A02 fakes so the smoke proves transport/API compatibility only. It is not a dense, lexical or
real-generation RAG claim.

## Data mode

- Frozen scenario UI: mock, unchanged and explicitly labelled.
- Production transport implementation: real HTTP.
- Live transport smoke: real HTTP plus controlled fake backend dependencies.
- Final browser RAG E2E: not run; no mock or lexical-only result is presented as that acceptance.

## Artifacts

- Source and tests are tracked under `frontend/**`.
- `frontend/dist`, `frontend/node_modules`, `var/b02-smoke` and smoke SQLite/logs are local ignored artifacts and are not committed.
- No weights, dense index, cookies, tokens or secrets are included.

## Blockers and reproducible defects

No blocker for B02 transport completion. Full browser RAG E2E remains intentionally pending until a real
A03 runtime with the real C03 dense index is published. Re-run the real-mode browser flow against that
runtime; do not substitute `frontend/scripts/a02_smoke_server.py`, because it is intentionally fake-backed.

## CR

None. DTOs and public endpoints were not changed.

## Inputs needed by next task

- A03 can use `task/b02` real mode with `VITE_API_MODE=real` and the same-origin proxy/reverse proxy.
- A03 acceptance must supply the real runtime URL and dense C03 artifacts, then execute the browser RAG flow with actual source and feedback.
- B03 is not started here. It still requires the accepted B02 result and A04 for real human handoff/reply verification.
