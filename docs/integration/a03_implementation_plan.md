# A03 Real RAG E2E Implementation Plan

> **For agentic workers:** execute this plan inline with test-first changes; the GPU run is serial and must not be delegated.

**Goal:** Wire the accepted A01/A02/C01/C03 components into the first fail-closed real dense RAG path and retain reproducible HTTP, feedback, and export evidence.

**Architecture:** Add an A-owned runtime composition layer. Real mode injects the C03 store with a lazy real Qwen3 query encoder and refuses retrieval unless health is `semantic`; explicit test mode retains the existing mock encoder. A standalone A03 runner drives the FastAPI routes through an HTTP client while retaining counters, timings, sources, feedback, and the matching export row.

**Tech Stack:** Python 3.12/3.13, FastAPI, HTTPX/TestClient, SQLite, PyTorch/Transformers CUDA, Ollama, pytest.

---

### Task 1: Fail-closed real runtime composition

**Files:**
- Create: `backend/tenderhack_backend/runtime.py`
- Modify: `backend/tenderhack_backend/config.py`
- Modify: `backend/tenderhack_backend/app.py`
- Modify: `.env.example`
- Create: `tests/test_runtime.py`

- [ ] Write tests proving real mode passes the configured C03 directory to `open_store`, injects a non-mock encoder, rejects non-semantic retrieval, and test mode is explicit.
- [ ] Run `uv run pytest tests/test_runtime.py -q` and verify the new tests fail because the runtime module/settings do not exist.
- [ ] Implement the minimal runtime builder, lazy real encoder, and strict semantic KnowledgePort wrapper.
- [ ] Re-run the focused tests and verify they pass.

### Task 2: Generator identity, health, calls, and timings

**Files:**
- Modify: `backend/tenderhack_backend/generator.py`
- Modify: `backend/tenderhack_backend/service.py`
- Modify: `backend/tenderhack_backend/app.py`
- Modify: `tests/test_generator.py`
- Modify: `tests/test_service.py`

- [ ] Write failing tests for one-call telemetry, Ollama model readiness, structured JSON-schema output, and persisted prompt/decode timings.
- [ ] Run the focused tests and verify the expected failures.
- [ ] Implement the smallest changes without adding retries or fallback models.
- [ ] Re-run the focused tests and verify they pass.

### Task 3: Reproducible A03 HTTP-client runner

**Files:**
- Create: `tools/run_a03_e2e.py`
- Create: `tests/test_a03_runner.py`
- Modify: `README.md`

- [ ] Write a failing test that drives the runner with controlled ports and verifies session/chat/poll/case/source/feedback/export capture.
- [ ] Run the focused test and verify it fails because the runner does not exist.
- [ ] Implement the runner so real mode builds the production service, requires semantic health, uses `is_demo=false`, and writes a JSON evidence bundle plus EvaluationExport.
- [ ] Re-run the focused test and verify it passes.

### Task 4: Real GPU execution and controlled safety checks

**Files:**
- Runtime artifacts only under `var/a03/` (Git-ignored)

- [ ] Confirm the C03 artifact hashes, idle GPU, local embedding weights, and restored Ollama model digest.
- [ ] Run 2–3 D01 retrieval smokes with the real encoder/index; require `health.mode=semantic`.
- [ ] Run one normal answerable HTTP E2E and capture exact IDs, answer, sources, timings, generation count, feedback, and export row.
- [ ] Run the real-policy profanity test and controlled invalid-generation test; require 0/0/0 and one generation with no retry respectively.

### Task 5: Verification and handoff

**Files:**
- Create: `docs/coordination/artem/A03-handoff.md`

- [ ] Run contract generation/fixture validation, all Python tests, frontend tests/build/typecheck, lint/compile checks, and `git diff --check`.
- [ ] Write the handoff with exact BASE/result/runtime identities and an explicit real/mock/mixed boundary.
- [ ] Verify the handoff against the retained evidence bundle.
- [ ] Commit on `task/a03`, push `origin task/a03`, record the immutable result SHA, and stop without starting A04.
