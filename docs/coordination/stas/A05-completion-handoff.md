# A05 completion — ownership-transfer handoff

## Status and pins

- Task: A05 — устойчивость, очередь и offline runtime.
- Ownership transfer: project lead temporarily transferred ownership of A05 from Артём to
  Стас only for completion; B06 is not in scope and was not started.
- Original branch: `origin/task/a05`.
- Original A05 tip/result: `00cea997bf395e1b35d8c288a693f1cbcfef8e6f` (implementation
  `11307671aac2c888704c7b244806a8c600a9b139`).
- Original A05 BASE: `461c1145983490f6440b47b4b3bb936db39b0b4a`.
- Continuation branch: `fix/a05-completion-stas`, created directly from `00cea997...`.
- Continuation BASE: `00cea997bf395e1b35d8c288a693f1cbcfef8e6f`.
- Final SHA: pending real-G evidence.
- Current verdict: mandatory real-G acceptance is pending.

## Existing-result audit

The original handoff was retained unchanged. Its controlled/M-machine evidence remains valid for
the mechanics it actually exercised, but is not promoted to real-G evidence.

| Requirement | Existing evidence | Audit | Repeat? |
|---|---|---|---|
| Queue/concurrency | 5 real HTTP clients through real backend/SQLite, but controlled retrieval/generation | PARTIAL | Yes, once on real semantic+Ollama pipeline |
| Overflow | capacity 4, one of five received honest `429 QUEUE_FULL` | PASS for admission mechanics | Observe in the same real-G queue run; no separate CPU rerun |
| Retry | restart/DB recovery retry used a new Request and reused original user Message | PASS for durable retry semantics | Only model-outage-specific recovery is missing |
| SQLite/storage outage | real exclusive lock; defect fixed from bare 500 to `503 STORAGE_UNAVAILABLE`; regression present | PASS | No acceptance rerun |
| Model outage | real absent Ollama produced retryable `MODEL_UNAVAILABLE`, no fake answer | PARTIAL | Yes: stop and restore real pinned Ollama, then real retry |
| Retrieval outage | missing lexical snapshot at startup degraded honestly and recovered after restore/restart | PARTIAL | Yes with strict semantic index and preserved source artifacts |
| Restart | real hard process kill mid-generation, persisted `RESTART_INTERRUPTED`, clean retry/no duplicates | PASS | No rerun |
| Handoff during generation | late answer suppression and post-compute slot release proven with controlled generator | PARTIAL | Yes during observed real Ollama generation |
| Offline | localhost/network-surface audit only; no physical disconnect | MISSING | Yes, participant manually disconnects internet on G |
| Real semantic runtime | prior A03/C03 proves accepted runtime/index, not an A05 run | PARTIAL | Yes: `health.mode=semantic` plus local hashes/digest |
| RAM/VRAM | C03 encoder build/smoke numbers and 16.5 MiB no-model A05 server figure | MISSING for combined runtime/load | Yes during real queue/handoff run |

## Work already completed by Артём

- Implemented the A05 harness and real HTTP experiment drivers.
- Proved queue admission/overflow, light-path responsiveness, restart recovery, durable retry,
  SQLite lock handling, lexical retrieval outage behavior, absent-Ollama behavior, and stale result
  suppression using explicitly labelled evidence classes.
- Found and fixed a real SQLite error-envelope defect in
  `backend/tenderhack_backend/app.py`; added its regression test.
- Ran the then-current full suite (`492 passed`) and documented all limitations without calling
  controlled/M-machine results real-G acceptance.

## Completion changes by Стас

Static audit showed that the existing drivers could not perform the requested G acceptance as-is:

- `tools/run_a05_queue_experiment.py` imported Unix-only `resource`, which fails at import on
  Windows G. It also reported child RSS from the client process even though the backend is a
  separate process.
- Its workload could take a non-generation gate branch, so it did not guarantee a genuine combined
  embedding -> dense retrieval -> generation queue measurement.
- The handoff driver slept for 0.4 seconds; real query embedding previously took about 10.8 seconds,
  so that action would happen during retrieval, not generation.
- The harness exposed no strict real-semantic mode.
- There was no reproducible two-phase real model outage/recovery driver or combined RAM/VRAM monitor.
- On Python 3.12, FastAPI derived a different 422 reason phrase than the frozen OpenAPI. The existing
  generated-contract regression reproduced this as a failure.

Minimal fixes/additions:

- Added `real_semantic` harness mode using the production `LazyRealQwen3Encoder`,
  `SemanticOnlyKnowledge`, accepted dense store, and real Ollama adapter.
- Made the queue driver Windows-compatible, used a known A03 answerable question, and extended its
  real-pipeline poll timeout. Removed the misleading client-child RSS value.
- Made handoff wait for observed `processing/generating` before acting and refuse to claim evidence
  otherwise; extended the real slot-release window.
- Added local-only semantic identity/hash preflight, two-phase model recovery evidence, and Windows
  backend/system-RAM/GPU-memory sampling tools.
- Explicitly pinned the accepted 422 description in `_error_responses`, avoiding Python-version
  drift without changing the contract or response body/status.

Before/after for the two reproduced defects:

| Defect | Before | After |
|---|---|---|
| Windows queue driver | import fails: `ModuleNotFoundError: resource` | driver imports/CLI parses on Windows; server RAM/VRAM sampled separately |
| Generated OpenAPI on Python 3.12 | existing `test_generated_openapi_matches_runtime` failed only at 422 reason text | explicit accepted description; full suite passes |

## Machine-G acceptance runbook

This section is intentionally executable by a team participant on G; it does not require Артём's
agent or tokens. Use PowerShell from the clean continuation checkout. Replace only `$A05_HF` with
the existing local Hugging Face cache root containing the accepted Qwen embedding weights.

```powershell
git fetch --prune origin
git switch fix/a05-completion-stas
git pull --ff-only origin fix/a05-completion-stas
git status --short

$A05_KB = 'A:\AI\retrieval-results\c03-kb-4918a97f0874d1e8-gpu-abea7ae-20260912T1619Z'
$A05_HF = '<LOCAL_HF_CACHE_ROOT_ON_G>'
$A05_OUT = 'var\a05-g'
New-Item -ItemType Directory -Force -Path $A05_OUT | Out-Null

uv sync --frozen
uv run python -m tools.run_a05_semantic_preflight `
  --knowledge-dir $A05_KB --hf-home $A05_HF `
  --output "$A05_OUT\semantic-preflight.json"
```

The preflight must show `knowledge_health.mode="semantic"`, the pinned embedding hash, the dense
artifact hashes, and exact Ollama name/digest. Do not continue on mismatch.

Start one heavy worker (queue capacity 4) and retain its PID/logs:

```powershell
$serverArgs = @(
  '-m', 'tools.a05_harness', '--db', "$A05_OUT\queue.sqlite",
  '--knowledge', 'real_semantic', '--generator', 'real_ollama',
  '--knowledge-dir', $A05_KB, '--hf-home', $A05_HF,
  '--embedding-device', 'cuda', '--queue-capacity', '4', '--port', '8010'
)
$server = Start-Process -FilePath '.\.venv\Scripts\python.exe' -ArgumentList $serverArgs `
  -PassThru -WindowStyle Hidden -RedirectStandardOutput "$A05_OUT\queue-server.stdout.log" `
  -RedirectStandardError "$A05_OUT\queue-server.stderr.log"
Start-Sleep -Seconds 3

$monitor = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
  '-NoProfile', '-File', 'tools\monitor_a05_resources.ps1',
  '-ServerProcessId', $server.Id, '-Output', "$A05_OUT\queue-resources.json",
  '-DurationSeconds', '600', '-StopFile', "$A05_OUT\queue-monitor.stop"
) -PassThru -WindowStyle Hidden

uv run python -m tools.run_a05_queue_experiment `
  --base-url http://127.0.0.1:8010 --clients 5 `
  --output "$A05_OUT\queue.json" --poll-timeout-seconds 600
New-Item -ItemType File -Force "$A05_OUT\queue-monitor.stop" | Out-Null
Wait-Process -Id $monitor.Id
Stop-Process -Id $server.Id -Force
```

Use a fresh DB/server for handoff. The driver itself refuses a run unless generation was observed:

```powershell
$serverArgs[3] = "$A05_OUT\handoff.sqlite"
$server = Start-Process -FilePath '.\.venv\Scripts\python.exe' -ArgumentList $serverArgs `
  -PassThru -WindowStyle Hidden -RedirectStandardOutput "$A05_OUT\handoff-server.stdout.log" `
  -RedirectStandardError "$A05_OUT\handoff-server.stderr.log"
Start-Sleep -Seconds 3
uv run python -m tools.run_a05_handoff_during_generation `
  --base-url http://127.0.0.1:8010 --output "$A05_OUT\handoff.json" `
  --generation-wait-seconds 180 --slot-release-wait-seconds 180
Stop-Process -Id $server.Id -Force
```

For model outage, start a fresh semantic server as above with `model.sqlite`. Then the participant
manually stops the Ollama server (not merely `ollama stop`, which allows an automatic reload),
confirms `http://127.0.0.1:11434/api/tags` is unreachable, and runs:

```powershell
uv run python -m tools.run_a05_model_recovery outage `
  --base-url http://127.0.0.1:8010 --state "$A05_OUT\model-recovery.json"
```

The participant starts Ollama again, confirms the exact pinned model in `/api/tags`, and runs:

```powershell
uv run python -m tools.run_a05_model_recovery recovery `
  --base-url http://127.0.0.1:8010 --state "$A05_OUT\model-recovery.json"
```

For semantic retrieval outage, never modify the accepted G directory. Stop the backend, create a
staging copy, omit `index.npy` only in staging, and point a fresh server to staging:

```powershell
$A05_KB_OUTAGE = "$A05_OUT\kb-outage-staging"
New-Item -ItemType Directory -Force -Path $A05_KB_OUTAGE | Out-Null
Copy-Item -LiteralPath "$A05_KB\knowledge.sqlite" -Destination $A05_KB_OUTAGE
Copy-Item -LiteralPath "$A05_KB\index_ids.json" -Destination $A05_KB_OUTAGE
Copy-Item -LiteralPath "$A05_KB\manifest.json" -Destination $A05_KB_OUTAGE
# Start the same harness with --knowledge-dir $A05_KB_OUTAGE and a fresh outage.sqlite.
curl.exe -sS http://127.0.0.1:8010/api/v1/health
uv run python -m tools.run_a05_queue_experiment --clients 1 `
  --base-url http://127.0.0.1:8010 --output "$A05_OUT\retrieval-outage.json"
# Stop backend, copy index.npy into staging, restart with the same staging path.
Copy-Item -LiteralPath "$A05_KB\index.npy" -Destination $A05_KB_OUTAGE
curl.exe -sS http://127.0.0.1:8010/api/v1/health
uv run python -m tools.run_a05_queue_experiment --clients 1 `
  --base-url http://127.0.0.1:8010 --output "$A05_OUT\retrieval-recovery.json"
```

For offline, all Git/dependency/model/index assets must already be present. The participant manually
disconnects external internet on G; no script changes firewall or adapter state. While physically
offline, run semantic preflight and one real request against the local server:

```powershell
uv run python -m tools.run_a05_semantic_preflight `
  --knowledge-dir $A05_KB --hf-home $A05_HF `
  --output "$A05_OUT\offline-semantic-preflight.json"
uv run python -m tools.run_a05_queue_experiment --clients 1 `
  --base-url http://127.0.0.1:8010 --output "$A05_OUT\offline-e2e.json"
```

The participant records that external internet was manually unavailable, no download was attempted,
and returns the JSON/log files. Reconnect the adapter manually afterward.

Final verification on this branch:

```powershell
uv run pytest -q --basetemp var\pytest-a05-final
uv run python -m compileall -q backend contracts/python tools knowledge
git diff --check
git status --short
```

## Real-G evidence

Pending return of actual G stdout/JSON. No CPU/control-delay result will be inserted here.

## Verification so far

- Full Python suite on Стас's Windows CPU machine after the minimal patches: PASS (all collected
  tests; workspace `--basetemp` used because the desktop runtime cannot access its encoded system
  temp directory).
- `python -m compileall -q backend contracts/python tools knowledge`: PASS.
- PowerShell parser check for `tools/monitor_a05_resources.ps1`: PASS.
- Tool CLI/import checks for all new/changed A05 drivers: PASS.
- `git diff --check`: PASS (line-ending notices only).

## Changed A-owned files in the continuation

- `backend/tenderhack_backend/app.py` — stable accepted 422 OpenAPI description across Python.
- `tools/a05_harness.py` — strict real-semantic G mode.
- `tools/run_a05_queue_experiment.py` — Windows support and guaranteed answerable real workload.
- `tools/run_a05_handoff_during_generation.py` — wait for actual generation.
- `tools/run_a05_semantic_preflight.py` — semantic/artifact/model identity evidence.
- `tools/run_a05_model_recovery.py` — real outage/recovery retry evidence.
- `tools/monitor_a05_resources.ps1` — combined runtime RAM/VRAM sampler.
- `docs/coordination/stas/A05-completion-handoff.md` — this ownership-transfer handoff.

No frontend, `knowledge/**`, `config/knowledge/**`, contracts, or unrelated backend files were
changed. Артём's historical handoff was not rewritten.

## AC11–AC17 / AC22 verdict

| AC | Current verdict |
|---|---|
| AC11 | PASS from accepted A04/B03 regression evidence; unaffected |
| AC12 | PASS from A04 and original A05 durable retry evidence |
| AC13 | PARTIAL pending real-generation G run |
| AC14 | PASS from accepted A04/B03 regression evidence; unaffected |
| AC15 | PASS from original A05 hard-restart/retry evidence |
| AC16 | PARTIAL pending real semantic+Ollama concurrency/RAM/VRAM run |
| AC17 | PARTIAL pending real model and semantic-index recovery runs |
| AC22 | PARTIAL pending physical-offline real-G run; restart already PASS |

## Blocker

Mandatory real-G output has not yet been returned to this continuation session. Until it is,
completion cannot be claimed.

`A05_ACCEPTED=no`

`BLOCKER=real G acceptance unavailable`
