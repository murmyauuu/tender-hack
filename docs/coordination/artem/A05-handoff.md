# A05 — Устойчивость, очередь и offline runbook

## Status and pins

- Status: **partial** (core resilience mechanics verified real and PASS; real-GPU/real-Ollama
  end-to-end evidence could not be produced on the actual machine this session ran on — see
  §0 hardware caveat below, and §"Known limitations / blockers").
- Branch: `task/a05`.
- BASE_SHA: `461c1145983490f6440b47b4b3bb936db39b0b4a` (`origin/main`, confirmed via
  `git fetch --prune origin && git switch main && git pull --ff-only origin main &&
  git status --short` — HEAD matched exactly, working tree clean except the pre-existing,
  unrelated untracked `data/processed/`).
- Result SHA: `1130767` (`task/a05`, implementation commit); this docs-only follow-up commit
  records that SHA here, same pattern C07 used.
- Contracts: `2.1.0-a02`, **unchanged**. The one behavioral fix in this task (see §"Backend
  defect fixed") reuses the existing `ErrorEnvelope`/`DomainError` shape and an HTTP status
  (`503`) already documented for `/api/v1/chat` in the accepted OpenAPI; no CR was needed.

## 0. Hardware caveat — read this before the numbers below

The task prompt pins **machine G** (`i7-12650H`, RTX 3070 Laptop 8GB) and forbids loading
models on a weak machine ("не загружай модели на слабой машине" — this exact sentence is in
`TenderHack_UNIFIED_SPEC_v2.1_prefilled.md`'s own A05 card). This session actually executed on
**machine M** (a MacBook Air M2, 8GB unified RAM, no CUDA, no discrete GPU, no Ollama installed
at session start) that C03/C04/C07 already documented as the honest fallback machine class.
Verified directly this session:

```text
uname -a            -> Darwin ... arm64 (Apple M2)
python3 -c "import torch"  -> ModuleNotFoundError
sysctl hw.memsize    -> 8 GB
which ollama         -> not found (before this session installed the *binary only*)
```

Consequences, decided deliberately and documented honestly rather than faked:

- I did **not** download or run the real Qwen3-Embedding-0.6B GPU encoder, and did **not** pull
  or run the pinned `qwen3:8b-q4_K_M` Ollama model. Both are explicitly out of reach on this
  hardware, and the spec text itself says not to force it. `backend/tenderhack_backend/runtime.py`'s
  `LazyRealQwen3Encoder.probe()` also hard-requires `torch.cuda.is_available()` when
  `embedding_device` starts with `"cuda"` — the accepted "real" runtime path is architecturally
  CUDA-only, so `health.mode=semantic` is not reachable on this machine regardless of effort.
- I installed the `ollama` *binary* via Homebrew (harmless, no model loaded) so a real,
  un-mocked "Ollama absent" condition could be exercised for the model-outage test — see §6.
- All queue/concurrency/restart/retry timing experiments use a small, explicitly-labeled
  **controlled-delay substitute** for the embedding+retrieval and generation steps
  (`tools/a05_harness.py`, `DelayedControlledKnowledge` / `DelayedControlledGenerator`), wired
  into the real, unmodified `BackendService`/`Database`/FastAPI app — exactly the same
  "real runtime, controlled heavy dependency" pattern A04's handoff used ("controlled no-model
  knowledge dependencies because the handoff path must perform no generation"). The queue,
  admission, SQLite persistence, HTTP layer, and C01 policy adapter in every experiment below
  are the real, unmodified project code — only the embedding/dense-retrieval/8B-decode latency
  is substituted with a configurable `asyncio.sleep`.
- Where the real code path *could* be exercised without GPU/Ollama, I used it: real
  `knowledge.policy.build_policy()` (real C01 policy engine, real trigger phrases verified
  against it) in every experiment, and the real, C07-frozen `var/knowledge/knowledge.sqlite`
  lexical store (`knowledge.kb.store.open_store(..., encoder=None)`, `health.mode=lexical_only`
  — the same honest degraded mode C03/C04/C07 already recorded on this machine class) for the
  retrieval-outage experiment and one offline-mode smoke.
- GPU-slot ledger: this session did **not** occupy the machine-G GPU slot in
  `docs/integration/gpu_slots.md` (no GPU was used); I added an honest own-row for this session
  instead of touching the stale `planned` rows other tasks own — see §"docs/integration update".

Everything below states plainly, per measurement, whether it is "real" (real code, real
process, real HTTP, controlled-delay stand-in for GPU/model latency) or blocked by hardware.
Nothing is invented.

## 1. Dependencies verified in `main`

- A04 PASS: `docs/coordination/artem/A04-handoff.md` (`Status: PASS`, result SHA
  `7ef5f1a0d3284c59eca5325c9d632995013482bc`) — present in `main` at BASE_SHA.
- B03 done: `docs/coordination/stas/B03-handoff.md` (`Status: done`, real-verification content
  SHA `c69a13ebdb1909bb7d1ef9f0f674c42695797191`) — present in `main`.
- C03 real-dense acceptance: `docs/coordination/stas/C03-runtime-acceptance.md`
  (`snapshot_id=kb-4918a97f0874d1e8`, `index_type=numpy_exact_cosine`, PASS) — present in `main`.
- C07 freeze: **confirmed NOT merged into `main`** at BASE_SHA — exists only as
  `origin/task/c07` (`config/knowledge/kb_freeze.json`,
  `docs/coordination/eduard/C07-handoff.md`), no open PR. Per the task instructions this is not
  a blocker; I read both files directly off the branch
  (`git show origin/task/c07:config/knowledge/kb_freeze.json` and
  `git show origin/task/c07:docs/coordination/eduard/C07-handoff.md`, the same pattern C04/C05
  used for C03) purely as a hash/limitations reference for this handoff. I did not merge,
  rebase onto, or edit anything under `knowledge/**` / `config/knowledge/**` — A05 does not
  touch that zone. **This is a fact about integration state, not an A05 blocker.**
- C06: not required per task instructions ("используется по готовности, не проверяй и не жди
  её"); not checked.

## 2. Runtime / model / index hashes

Not rebuilt this session — reused verbatim from C07's branch manifest and C03's accepted
acceptance doc, both explicitly attributed here (no new snapshot was fabricated):

| Artifact | SHA-256 | Source |
|---|---|---|
| `knowledge.sqlite` (local reproduction, verified this session: `shasum -a 256 var/knowledge/knowledge.sqlite`) | `6d1555777d9bbf9ae7f2df93a69cf61f53dd04263877a8ebaf7fc35e16a4bdf8` | matches C02/C03/C07 macOS build exactly |
| `var/knowledge/manifest.json` (verified this session) | `e0d01a74dcfe43f8a562a10837793fa04a052e775e60877115dce7785f24d061` | matches C07 |
| Embedding model `Qwen/Qwen3-Embedding-0.6B` rev `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`, `model.safetensors` | `0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd` | C03 acceptance / C07 freeze; not re-verified here (no GPU) |
| `index.npy` (dense, machine G only) | `396e8ee4e5ce4c457292eea2b107058b7941ea0c498434a70f8da6abc9b8de87` | C03 acceptance / C07 freeze |
| `index_ids.json` | `b328deae1ba6868da115d66e81e19b60b92f6601cf20717cfb7070b14bca110d` | C03 acceptance / C07 freeze |
| `manifest.json` (G-stamped, dense) | `589600e50e02239806d98a43f41ee88e42d20bef5f3aabbb7ece4e844aae9f77` | C03 acceptance / C07 freeze |
| Ollama `qwen3:8b-q4_K_M` digest | `a0a5ad8024dd21401f07634d0c71393b9c9d37aa57a6b594e02b86ab72c450b4` | `config/runtime/a02.json` / `generator.py` pin; not pulled/run this session |
| Ollama GGUF SHA-256 | `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785` | `config/runtime/a02.json` pin |

The dense index/id-mapping/G-stamped manifest and the real Ollama model physically exist only
on machine G and were not reproduced here — consistent with C07's own finding on this same
machine class.

## 3. Backend defect found and fixed (A-owned, `backend/tenderhack_backend/app.py`)

While running the real DB-outage/lock experiment (§6.3) I found that a genuine SQLite lock
contention on `var/app.sqlite` was **not** translated into the project's `ErrorEnvelope`
contract shape: it surfaced as FastAPI's bare `Internal Server Error` / HTTP `500`, with no
`error.code`, no `retryable` flag — a "generic 500 without a reason", exactly what AC17
prohibits. Root cause: `Database.transaction()` lets `sqlite3.OperationalError` ("database is
locked", after the existing `PRAGMA busy_timeout=10000`) propagate unhandled past
`BackendService`/FastAPI's own domain-error handling.

Fix (squarely in A-owned `backend/**`, no contract change — `503` was already documented for
`/api/v1/chat` in the accepted OpenAPI, and `ErrorEnvelope`'s `error.code` is a free string, not
an enum): added an `@application.exception_handler(sqlite3.Error)` in
`backend/tenderhack_backend/app.py` that returns the existing `ErrorEnvelope` shape with
`code="STORAGE_UNAVAILABLE"`, `status_code=503`, `retryable=True`. Verified:

- Real repro before the fix: a separate real `sqlite3` connection held `BEGIN EXCLUSIVE` on
  `var/app.sqlite`; a real `POST /api/v1/chat` against the running server returned
  `HTTP 500 "Internal Server Error"` after ~10.7s (the existing busy-timeout).
- Same repro after the fix: `HTTP 503`,
  `{"error":{"code":"STORAGE_UNAVAILABLE","message":"Хранилище временно недоступно","retryable":true,...}}`.
- Added a permanent regression test:
  `tests/test_app.py::test_locked_storage_returns_honest_error_not_generic_500` (real
  `sqlite3.connect(...).execute("BEGIN EXCLUSIVE")` against a real `Database`/`BackendService`/
  `TestClient`, no mocking of the lock itself).
- Full suite after the fix: `uv run pytest` → `492 passed in 28.31s` (491 pre-existing + 1 new).
- `uv run python -m compileall -q backend contracts/python tools knowledge` → exit `0`.
- `git diff --check` → clean.
- Admission-counter sanity after a failed (locked-DB) admission: re-ran the 5-client
  concurrency probe (§4) immediately afterward — still exactly one `429` among 5, confirming
  the failed admission did not leak a reserved queue slot (the existing
  `except BaseException: reserved -= 1; raise` in `service.accept_chat` already handled this
  correctly; only the HTTP-layer error shape was the defect).

## 4. Queue / concurrency / overflow (real HTTP, real backend, controlled heavy-step delay)

Code inspected and confirmed by live experiment, not assumed: `queue_capacity: int = 4` (single
constructor default, `backend/tenderhack_backend/service.py:39`), admission check
`self._reserved >= self.queue_capacity` → `DomainError("QUEUE_FULL", status_code=429,
retryable=True)` (same file, `:87-93`), FIFO `deque`, single `worker_loop` consuming one
request at a time under `self._processing_lock`. `_reserved` is only decremented in
`process_next`'s `finally`, i.e. **after** `_process()` — retrieval **and** generation —
actually returns, confirming the heavy slot really is one indivisible
embedding→retrieval→generation occupancy, not released early.

Harness: `tools/a05_harness.py --knowledge controlled --generator controlled
--retrieval-delay 0.3 --generation-delay 3.0 --queue-capacity 4`. Driver:
`tools/run_a05_queue_experiment.py` (real `httpx` clients, independent session cookies per
client, real concurrent `ThreadPoolExecutor` submission — not mocked HTTP).

Command actually run:

```bash
.venv/bin/python3 -m tools.a05_harness --db var/a05/queue_exp.sqlite \
  --knowledge controlled --generator controlled \
  --retrieval-delay 0.3 --generation-delay 3.0 --queue-capacity 4 --port 8012 &
uv run python3 -m tools.run_a05_queue_experiment --base-url http://127.0.0.1:8012 \
  --clients 5 --output var/a05/queue_experiment.json
```

5 real concurrent clients fired at once against `queue_capacity=4`:

| client | submit HTTP | outcome | queue wait (ms) | retrieval (ms) | generation (ms) | total processing (ms) |
|---|---|---|---|---|---|---|
| 0 | 202 | `answer` (rag) | 304.9 | 300.0 | 3001.5 | 3305.9 |
| 1 | 202 | `answer` (rag) | 3611.8 | 300.0 | 3001.4 | 3308.0 |
| 2 | 202 | `answer` (rag) | 6929.2 | 300.0 | 3000.8 | 3319.1 |
| 3 | **429** | **`QUEUE_FULL`** | n/a | n/a | n/a | n/a |
| 4 | 202 | `answer` (rag) | 10237.7 | 300.0 | 3000.5 | 3310.6 |

Exactly 1 of 5 real concurrent clients was rejected with `429`/`QUEUE_FULL`
(`{"error":{"code":"QUEUE_FULL","message":"Очередь обработки заполнена","retryable":true,...}}`),
the other 4 were admitted and processed strictly sequentially (queue wait grows by ~3.3s per
admitted client ahead of it — one worker, capacity 4). This is a live measurement, not a
restatement of the config default.

Lightweight paths fired **while the heavy queue was completely full** (same run):

| path | real trigger | HTTP | elapsed |
|---|---|---|---|
| profanity/policy short-circuit (C01, real policy engine, phrase `нах*й иди` → real `matched_rule_ids=['POL.PROF.HUY']`) | `POST /api/v1/chat` | 202 (accepted as its own fast, non-AI `chat_mode="policy"` turn) | 5.3ms |
| health/read | `GET /api/v1/health` | 200 | 4.3ms |
| health/read (baseline, before load) | `GET /api/v1/health` | 200 | 0.7ms |

Both lightweight calls returned in single-digit milliseconds while 4 heavy requests were
occupying the entire queue — confirmed not queued behind GPU/generation work, matching
`service.py`'s `fast = chat_mode != "ai"` bypass of the admission lock entirely.

Server process RSS during this run (`ps -o rss`): **16.5 MiB** — expected for a Python/FastAPI
process with no ML model resident; not comparable to a real embedding+8B-model RSS/VRAM figure
on machine G (see §0).

## 5. Handoff during generation (real HTTP)

Driver: `tools/run_a05_handoff_during_generation.py`. Harness:
`--knowledge controlled --generator controlled --retrieval-delay 0.2 --generation-delay 4.0
--queue-capacity 4`.

Sequence (all real HTTP calls against a real running server):

1. Client submits a real AI chat request (`generation-delay=4.0s`).
2. 0.4s later, same case: a second real chat message with text `Соедините меня с оператором`
   — verified against the real `knowledge.policy.build_policy()` engine first
   (`explicit_human_request=True`, `matched_rule_ids=['POL.HUMAN.TRANSFER_REQUEST']`). This
   supersedes the in-flight request (`chat_mode="handoff"`, fast path) and creates a real
   Ticket/handoff.
3. Immediately after, 4 more real AI requests are fired to probe admission capacity, then a
   background watcher probes admission every ~150ms until it succeeds again.

Measured, real results (background status-watcher thread polling
`GET /api/v1/requests/{id}` every 20ms from submission):

- API-visible status transition: `processing/retrieving` at `t=0.009s` →
  `cancelled` / `error.code=SUPERSEDED_BY_POLICY` at **`t=0.438s`** (i.e. the client sees the
  original request as cancelled almost immediately after handoff — good UX, matches
  `storage.publish_message`'s active-request/version guard).
- **Heavy admission slot released only at `t=4.300s`–`4.365s`** (two independent repeated runs),
  i.e. essentially exactly the full `generation-delay=4.0s` later, **not** at the `t=0.44s`
  handoff moment. Measured by repeatedly re-probing admission (fresh sessions, real `POST
  /api/v1/chat`) every ~150–180ms after the queue was saturated (original in-flight + 3 probe
  requests = capacity 4); every probe returned `429` until `t≈4.3s`, then succeeded. This is
  the concrete, measured answer to "does the slot free before or after the computation actually
  stops": **after** — the still-running `generator.generate()` coroutine (asyncio sleep
  standing in for real decode time) is not cancelled, it runs to completion in the background,
  and only then does `process_next`'s `finally` decrement `_reserved`.
- `stale_ai_message_present`: **False** — no AI answer message was added to the case after
  handoff (`storage.publish_message`'s version/active-request/status guard rejected the late
  publish and marked the original request `cancelled`, exactly as A04's handoff already
  documented for this code path).
- Final case status: `handed_off`, with one real Ticket created
  (`reason_codes=["EXPLICIT_HUMAN_REQUEST"]`), 3 messages total (original question, handoff
  phrase, one system "Обращение передано специалисту по вашему запросу." notice) — no
  duplicate/orphaned messages.

## 6. Restart, outages, retry (all real: real `kill -9`, real process restart, real sqlite lock, real absent Ollama)

### 6.1 Backend/worker restart mid-generation

Harness: `.venv/bin/python3 -m tools.a05_harness --generation-delay 6.0 ...` (direct venv
Python invocation, **not** `uv run`, so the captured PID is the actual server process — an
earlier attempt via `uv run ... &; kill -9 $!` only killed `uv`'s wrapper and left an orphaned
server child alive holding the port; this was caught by `lsof -nP -iTCP:8014 -sTCP:LISTEN`
after the "kill" still showing a live listener, and corrected before drawing any conclusion).

1. Submitted a real AI chat request; confirmed via `GET /api/v1/requests/{id}` at `t=1.5s`:
   `status=processing, progress=generating` (mid-way through the 6s generation).
2. `kill -9 <confirmed real server PID>` — confirmed dead (`ps -p <pid>` → no such process,
   `lsof -nP -iTCP:8014 -sTCP:LISTEN` → empty) before proceeding.
3. Direct sqlite inspection of the surviving DB file immediately after the crash:
   `request.status='processing', progress='generating'` (genuinely stuck, as expected from a
   hard kill), `messages` count `1`, `tickets` count `0`.
4. Restarted the exact same command against the same `--db` file. `recover_interrupted_requests()`
   ran automatically in the FastAPI `lifespan` (no manual intervention beyond the restart
   itself).
5. Post-restart, real client with the original session cookie: `GET /api/v1/requests/{id}` →
   `status=error, error.code=RESTART_INTERRUPTED, retryable=true` (not stuck at "processing"
   forever, not a silent fake success). `GET /api/v1/cases/{id}`: `active_request_id=null`,
   `case_version` incremented, `status=open`.
6. Sqlite counts after restart: `messages=1` (unchanged — no duplicate), `tickets=0` (unchanged
   — no duplicate).

### 6.2 Retry after restart-interrupted failure

Real `POST /api/v1/chat` with `retry_of=<original failed request_id>`,
`expected_case_version=2`:

- New `request_id` returned (`b8404480-...` vs original `a700f9e0-...`) — a new accepted
  Request, not a mutation of the old one.
- `user_message_id` in the response is the **same** id as the original user message
  (`a5e03d47-...`) — confirmed by direct sqlite count: `messages` table still has exactly 2
  rows after the retry completes (1 user question + 1 AI answer) — the original user Message
  was **not** duplicated.
- Retry ran to a real `final` answer (`generation_total=6001.3ms`, matching the configured
  6.0s delay) with no automatic internal retry: `service._process()` calls
  `self.generator.generate(...)` exactly once per `_process()` invocation (static code fact,
  `backend/tenderhack_backend/service.py:243`, no retry loop around it) — the dynamic
  single-answer-per-request result above is consistent with that.

### 6.3 DB outage / lock — see §3 for the defect found and fixed. Post-fix real behavior:

- Request submitted while a real second `sqlite3` connection holds `BEGIN EXCLUSIVE` on
  `var/app.sqlite` → `HTTP 503`, `error.code=STORAGE_UNAVAILABLE`, `retryable=true`, after
  ~10.75s (the existing `PRAGMA busy_timeout=10000`).
- Lock released (the locking process killed) → **the very next request succeeds immediately**
  (`202`, `~4ms`) with **no restart needed** — recovers on its own once the underlying
  contention clears.
- No fake/partial answer was persisted for the failed request (verified via sqlite: only the
  user's own question message exists for that case).

### 6.4 Retrieval / KB-index outage (real KB file, real `open_store`, no mocking)

Harness: `--knowledge real_lexical --knowledge-dir var/knowledge` (the real, C07-frozen,
hash-verified `knowledge.sqlite`, `encoder=None` → real `health.mode=lexical_only`).

- **Baseline (KB present):** a real question ("Как подписать акт сверки?") produced real
  candidate sources from the real KB (`portal:593140:1 "Как подписать контракт?"`, etc.) and a
  real gate decision (`CLARIFY`, asking role first) — genuine `knowledge/kb/retrieval.py`
  pipeline behavior, not fabricated.
- **Attempted outage via rename-while-running:** renaming `knowledge.sqlite` away while the
  server was already running did **not** cause a failure — a real, important, honestly-reported
  finding: `knowledge/kb/store.py`'s `SqliteKnowledgeStore` opens **one** `sqlite3` connection
  at construction time and keeps using it; on POSIX, an open file descriptor survives its path
  being renamed/unlinked, so a live process keeps working against the vanished path. This is
  not a bug I introduced or found reason to "fix" — it is accurate, expected sqlite/POSIX
  behavior, and it means: **this specific outage only manifests if the KB file is missing at
  process *startup*, not if it disappears mid-life.** I report this instead of silently
  re-running until I got the result I expected.
- **Genuine outage (file absent at startup):** killed the server, confirmed the file was still
  absent, restarted → `GET /api/v1/health` → `"knowledge":"unavailable"` (honest). A real chat
  request then produced, **without any exception/generic 500**: a graceful `ESCALATE` decision
  with `reason_codes=["SEARCH_UNAVAILABLE"]`, surfaced to the user as a handoff-offer notice
  ("Недостаточно проверенных материалов (SEARCH_UNAVAILABLE). Передать специалисту?"),
  `case.status="handoff_offered"`. No fake answer, no fake sources, a specific reason code —
  this is the real `knowledge/kb/store.py` behavior for a missing snapshot, not an exception
  path through `service.py`'s `except Exception: fail_request(..., "SEARCH_UNAVAILABLE", ...)`
  (that branch exists for a different failure mode, e.g. a corrupt file that raises inside
  `retrieve()`; I observed the actual, real behavior rather than assuming which branch fires).
- **Recovery:** restored the real KB file, restarted the process (recovery **required** a
  restart here, because of the single-persistent-connection design noted above — reported
  honestly, not glossed over) → `GET /api/v1/health` → `"knowledge":"lexical_only"` again, real
  retrieval resumed.

### 6.5 Model / generator outage (real absent Ollama — not simulated)

Homebrew-installed the `ollama` **binary only** (no model pulled, no `ollama serve` started —
per §0, no model was loaded on this machine). Harness: `--generator real_ollama` (the real,
unmodified `OllamaGenerator` pointed at the real default `http://127.0.0.1:11434`, which
genuinely has nothing listening — confirmed via `curl -m 2 http://127.0.0.1:11434/api/tags` →
connection refused).

- `GET /api/v1/health` → `"generator":"unavailable"` (real `OllamaGenerator.health()` performing
  a real, failing HTTP call and catching the exception) — honest before any request is even
  sent.
- Real chat request (real controlled-KB retrieval → real attempted Ollama call) →
  `GET /api/v1/requests/{id}` → `status=error, error.code=MODEL_UNAVAILABLE, retryable=true`.
  No fake answer was persisted (sqlite: only the user's own question exists for that case).
- Recovery-after-fix for this specific outage was **not** exercised end-to-end (would require
  actually pulling/running the pinned 8B model, which §0 explains was deliberately not done on
  this hardware). The retryable contract and the structural single-call-per-request guarantee
  are otherwise demonstrated in §6.2/§6.3.

## 7. Offline run

Prepared-before-disconnect: backend code (local checkout), real KB snapshot
(`var/knowledge/knowledge.sqlite`, hash-verified §2), SQLite app DB (created on first request,
purely local file), Python deps (`uv sync`, already resolved/cached locally, no new downloads
needed for anything exercised in this session). Frontend `npm install`/`dist` build was **not**
produced in this session — out of A-owned scope (`frontend/**`) and already validated
separately by B03 (`npm run build` → PASS in `docs/coordination/stas/B03-handoff.md`); not
re-verified here.

**What I did not do, and why:** the task asks to physically cut network access (firewall rule
or disabling the network adapter). Doing that myself is exactly the kind of "modify
system/security settings" action I must refuse regardless of task instructions, and — more
concretely — this machine's own network is also this interactive session's control channel;
disabling it risked cutting off the session itself with no safe way to recover. I did not do
this, and I'm stating that plainly rather than silently skipping it or pretending I did.

**What I verified instead, as an honest, safe substitute:** ran a full real request cycle
(`POST /api/v1/sessions` → `POST /api/v1/chat` → poll `GET /api/v1/requests/{id}` → real
`SqliteKnowledgeStore` lexical retrieval against the real local KB → controlled local
generator) and inspected the live backend process's actual open network sockets:

```bash
lsof -i -P -n -p <backend_pid>
# -> exactly one entry: TCP 127.0.0.1:8019 (LISTEN)
```

No established outbound connection, no DNS, nothing non-localhost. Corroborated by a static
audit: the only outbound HTTP call anywhere in `backend/tenderhack_backend/` is
`generator.py`'s `urlopen`, targeting `settings.ollama_url`
(default `http://127.0.0.1:11434` — localhost-only, configurable but never pointed anywhere
external in any config in this repo). `LazyRealQwen3Encoder` (the only code path that could ever
reach Hugging Face Hub) sets `HF_HUB_OFFLINE=1`/`TRANSFORMERS_OFFLINE=1` unconditionally and is
never constructed by the "test"/controlled/real_lexical paths exercised in this session.

**Conclusion:** the backend, in the configuration this session could actually run, makes zero
external network calls while serving real requests. A literal adapter/firewall-level test was
not performed, for the safety reason stated above — flagged here as an explicit limitation, not
silently dropped. If a stricter physical test is wanted, the next agent/human running on
machine G (or anyone comfortable disabling their own network adapter) can repeat exactly the
same request cycle with the network physically off; nothing in the exercised code paths is
expected to behave differently.

## 8. `docs/integration/gpu_slots.md` update

The existing rows for C03/A03/C07 say `planned`, but their own handoffs say `completed` — per
the task instructions I did not touch those (no independent confirmation of their actual
run details, and they are not mine to certify). I added one new row, for this session's own
A05 slot, stating plainly that **no GPU was used** (see §0):

```text
| 2026-09-12 22:17–22:32 UTC | A05 | A | (this branch's result SHA) |
Concurrency/restart/outage/retry/offline resilience harness, NO GPU (machine M, not G — see
A05-handoff §0) | completed, no GPU slot occupied |
docs/coordination/artem/A05-handoff.md |
```

## 9. AC11–AC17 / AC22 — actual results

| AC | Text | Result | Evidence |
|---|---|---|---|
| AC11 | Чужой Case/поддельный author/секреты защищены | **PASS (regression, not re-verified with new scenarios this session)** | Established by A04/B03 (`docs/coordination/artem/A04-handoff.md` §Security evidence, `docs/coordination/stas/B03-handoff.md` §Security/DevTools evidence); unaffected by this session's changes; full suite incl. those security tests: `492 passed`. |
| AC12 | Повторы chat/handoff/reply без дублей | **PASS** | §6.2 real retry: new `request_id`, reused `user_message_id`, sqlite `messages` count unchanged (2, not 3). |
| AC13 | Handoff во время generation исключает поздний AI-ответ | **PASS** | §5: `stale_ai_message_present=False`; slot released only at real generation completion (`t≈4.3s`), not at the `t≈0.44s` handoff moment. |
| AC14 | Полезность отдельно от solved; старый answer не закрывает новый вопрос | **PASS (regression, not re-verified this session)** | Established by A04/B03; unaffected by this session's changes; covered by full suite. |
| AC15 | Restart, история цела, retry без дубля | **PASS** | §6.1: real `kill -9` on a confirmed real server PID, real restart, `RESTART_INTERRUPTED` (not stuck "processing"), no duplicate messages/tickets (sqlite counts unchanged); §6.2 retry succeeded cleanly afterward. |
| AC16 | 3 клиента и overflow, API отзывчив, GPU последовательный | **PASS (queue/HTTP mechanics; "GPU" substituted per §0)** | §4: 5 real concurrent clients, exactly 1×`429`/`QUEUE_FULL`, sequential single-worker processing (queue wait grows ~3.3s per position), lightweight paths respond in single-digit ms while the heavy queue is full. |
| AC17 | Честная деградация model/search/DB, без скрытых mocks | **PASS, and one real defect found+fixed** | §6.3 DB lock → was a raw HTTP 500 (found), now honest `503 STORAGE_UNAVAILABLE` (fixed, regression-tested); §6.4 real KB-file-absent → honest `SEARCH_UNAVAILABLE` escalation, no fake answer; §6.5 real absent-Ollama → honest `MODEL_UNAVAILABLE`, no fake answer. No knowledge/generator adapter was mocked to *hide* a failure — every degraded path shown here is either the real code's own real behavior, or an openly-labeled controlled-delay stand-in for GPU/model latency (§0), never a stand-in for correctness/error-handling logic. |
| AC22 | Linux/offline/restart целевого релиза | **PARTIAL** | Restart: PASS (§6.1, real). Offline: real backend makes zero external network calls in every exercised path (§7), but a literal adapter/firewall network cutoff was not performed (safety refusal, §7) and this session did not run on Linux (machine M is macOS, not machine G/Linux) — both stated as explicit limitations, not silently skipped. |

No OOM was observed (server process peak RSS ≈16.5 MiB across every experiment — no ML model
resident on this machine, §0). No hidden mocks in the proven-real paths described above (every
substitution is named and reasoned in §0/§4-§7). No fake persistence anywhere: every degraded
path was checked directly against sqlite row counts, never against logs alone.

## 10. Verification

- `uv run pytest` → `492 passed in 28.31s` (491 pre-existing + 1 new regression test for the
  DB-lock fix).
- `uv run python -m compileall -q backend contracts/python tools knowledge` → exit `0`.
- `git diff --check` → clean.
- `test_generated_openapi_matches_runtime` (existing test, still passing) confirms the
  `sqlite3.Error` handler introduced no contract drift — `contracts/openapi/openapi.json` is
  unchanged, `503` was already documented for `/api/v1/chat`.
- Real experiments: §4 (queue/concurrency/overflow), §5 (handoff-during-generation), §6.1–6.5
  (restart, retry, DB/retrieval/model outages), §7 (offline network audit) — raw JSON outputs
  saved under `var/a05/*.json` (gitignored, reproducible via the exact commands quoted in each
  section and in §11).

## 11. Runbook (every command below was actually executed this session)

Preflight:

```bash
git fetch --prune origin
git switch main
git pull --ff-only origin main
git status --short
uv sync
```

Start (real backend, controlled heavy-step substitute — see §0 for why):

```bash
TENDERHACK_OPERATOR_REPLY_KEY=<key> .venv/bin/python3 -m tools.a05_harness \
  --db var/a05/run.sqlite --knowledge controlled --generator controlled \
  --retrieval-delay 0.3 --generation-delay 3.0 --queue-capacity 4 --port 8012
```

Start (real local KB, no GPU — `health.mode=lexical_only`):

```bash
.venv/bin/python3 -m tools.a05_harness \
  --db var/a05/run.sqlite --knowledge real_lexical --generator controlled \
  --generation-delay 0.2 --queue-capacity 4 --knowledge-dir var/knowledge --port 8016
```

Health:

```bash
curl -sS http://127.0.0.1:8012/api/v1/health
```

Smoke (one real full cycle):

```bash
COOKIES=var/a05/cookies.txt
curl -sS -c $COOKIES -b $COOKIES -X POST http://127.0.0.1:8012/api/v1/sessions
curl -sS -c $COOKIES -b $COOKIES -H "Content-Type: application/json" \
  -d '{"request_key":"<uuid>","text":"Как подписать контракт?"}' \
  http://127.0.0.1:8012/api/v1/chat
curl -sS -b $COOKIES http://127.0.0.1:8012/api/v1/requests/<request_id>
```

Concurrency/overflow experiment:

```bash
uv run python3 -m tools.run_a05_queue_experiment --base-url http://127.0.0.1:8012 \
  --clients 5 --output var/a05/queue_experiment.json
```

Handoff-during-generation experiment:

```bash
uv run python3 -m tools.run_a05_handoff_during_generation \
  --base-url http://127.0.0.1:8013 --output var/a05/handoff_experiment.json
```

Stop:

```bash
kill -9 <confirmed real server PID from `ps`/`lsof -iTCP:<port>`>
```

(Never `kill $!` after `uv run ... &` — `uv` forks a wrapper; confirm the real PID first, see
§6.1.)

Restart (against the same DB, recovers automatically):

```bash
.venv/bin/python3 -m tools.a05_harness --db var/a05/run.sqlite \
  --knowledge controlled --generator controlled \
  --retrieval-delay 0.3 --generation-delay 6.0 --queue-capacity 4 --port 8014
```

Export: A05 did not change `export.py`; no new export command was needed for this task's scope.

Offline start (network audit, not a physical cutoff — see §7):

```bash
.venv/bin/python3 -m tools.a05_harness --db var/a05/offline.sqlite \
  --knowledge real_lexical --generator controlled --generation-delay 0.2 \
  --queue-capacity 4 --knowledge-dir var/knowledge --port 8019
# in another shell, during a real request cycle:
lsof -i -P -n -p <pid>
```

Recovery after outage (DB lock example — release the lock, no restart needed):

```bash
kill -9 <pid holding BEGIN EXCLUSIVE>
curl -sS -b $COOKIES -H "Content-Type: application/json" \
  -d '{"request_key":"<new-uuid>","text":"..."}' http://127.0.0.1:8018/api/v1/chat
# -> 202 within milliseconds, no restart required
```

Recovery after outage (KB-file-absent example — requires restart, see §6.4):

```bash
mv var/knowledge/knowledge.sqlite.disabled var/knowledge/knowledge.sqlite
# then restart the process (single persistent connection, see §6.4)
```

## 12. Known limitations

- No real GPU/CUDA/Ollama evidence was produced (§0) — this is a hardware fact about the
  machine this session ran on, not a shortcut taken carelessly. Every number in §4–§7 is either
  a real measurement against real code, or an explicitly labeled controlled-delay substitute.
- `knowledge/kb/store.py`'s single persistent sqlite connection means a KB-file outage that
  starts *while the process is already running* is invisible to that process until restart
  (§6.4) — this is existing, real, unowned-by-A05 `knowledge/**` behavior, observed and
  reported, not modified (out of A-owned scope).
- Model-outage recovery-after-fix (pulling/running the real pinned Ollama model) was not
  exercised end-to-end, for the reason in §0/§6.5.
- Literal Linux and literal network-adapter-off testing were not performed (§7); the backend's
  own real network-call surface was audited instead and found to be localhost-only.
- Frontend offline-asset readiness (`npm install`/`npm run build` reproducibility) was not
  re-verified in this session — out of A-owned scope, already covered by B03.

## 13. Blockers / CR

None requiring another owner's zone. The one defect found (§3, honest-error-shape for a locked
SQLite DB) was inside A-owned `backend/tenderhack_backend/app.py` and was fixed directly, with a
regression test, per the task's own instruction to fix backend defects in A's own paths rather
than filing a CR for them.

## 14. Changed files

- `backend/tenderhack_backend/app.py` — added `sqlite3.Error` → `STORAGE_UNAVAILABLE` (503,
  retryable) exception handler (see §3).
- `tests/test_app.py` — added
  `test_locked_storage_returns_honest_error_not_generic_500` regression test.
- `tools/a05_harness.py` — new: real FastAPI/uvicorn harness with controlled-delay
  knowledge/generator substitutes and a `real_lexical` mode against the real C07-frozen KB.
- `tools/run_a05_queue_experiment.py` — new: real concurrent-HTTP-client queue/overflow/
  lightweight-bypass experiment driver.
- `tools/run_a05_handoff_during_generation.py` — new: real handoff-during-generation experiment
  driver with a background status-transition watcher and slot-release probe.
- `docs/integration/gpu_slots.md` — added this session's own A05 row (§8); no other row
  touched.
- `docs/coordination/artem/A05-handoff.md` — this file.

## 15. Data mode summary (mock / real / mixed — where exactly)

- Real, unmodified: `BackendService`, `Database`/SQLite persistence, FastAPI HTTP layer,
  `knowledge.policy` C01 adapter, `knowledge.kb.store.SqliteKnowledgeStore` (in `real_lexical`
  mode), `OllamaGenerator` (in `real_ollama` mode, against a genuinely absent Ollama).
- Controlled/labeled substitute (never hidden): `DelayedControlledKnowledge` /
  `DelayedControlledGenerator` in `tools/a05_harness.py` — configurable `asyncio.sleep` standing
  in for GPU embedding+retrieval and 8B-model decode latency, returning a fixed,
  verifier-valid answer. Used only for the timing-sensitive queue/concurrency/restart/retry
  experiments in §4–§6.1–6.3, where real GPU latency would make timing non-deterministic and
  where downloading/running an 8B model on 8GB RAM is exactly what the task's own spec text
  says not to do (§0).
