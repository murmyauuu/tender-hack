# A01 — ранний Linux/GPU/model smoke — handoff

- Task ID / status: `A01` / hardware and model smoke completed; Linux admission remains blocked until organizers explicitly accept WSL2.
- Owner / machine: Артём / agent A / profile G.
- Repo path: `C:\Users\Artem\Desktop\Tender_Hack\tender-hack`.
- Worktree path: `C:\Users\Artem\Documents\Codex\2026-09-12\a-tenderhack-a01-linux-gpu-model\work\tender-hack-a01`.
- Branch: `task/a01`.
- Base SHA: `dddb724f454c986a60c6b3243db41f22bfbfabea` (`origin/main` at task start; required integration SHA is its ancestor and, at fetch time, the same commit).
- Result SHA: the commit containing this handoff on `task/a01`; the immutable pushed SHA is reported in the task delivery because a commit cannot contain its own SHA.
- Runtime code SHA used for the smoke: `dddb724f454c986a60c6b3243db41f22bfbfabea`.
- Canonical raw KB input SHA-256: `71bf714a9e205a35f5d8ec0fd2d0f9bbd4ad3a8409968b754eb8de7b349d79ae`; the historical `439e…` value is not an active input.
- GPU slot: exclusive A01 use from `2026-09-12T12:29:28Z` through `2026-09-12T13:35:14Z`; no parallel generator/embedding load was run.

## Result summary

- `Qwen3-8B` Q4_K_M fits on the RTX 3070 Laptop at operational context `8192`; Ollama offloaded `37/37` layers. A 4B fallback was not invoked.
- Linux generation ran for real in Ubuntu 22.04 under WSL2 with CUDA and local Ollama `0.33.1`. Short, 4098-token long-context, warmed-repeat, sequential load, stop/start, and post-restart requests passed with thinking disabled.
- `Qwen3-Embedding-0.6B` ran a real normalized query embedding on the same GPU from the already-local Hugging Face snapshot, with network-disabled library settings. The vector dimension is `1024`.
- The embedding adapter was exercised from the existing Windows CUDA Python environment. Linux has no installed pip/PyTorch/Transformers adapter, so an official all-Linux final runtime is not yet complete. No second model copy or second Python/CUDA stack was installed silently.
- Final Ollama inventory has exactly one model manifest, named `qwen3:8b-q4_K_M`, backed by exactly one GGUF model blob. The former local alias was renamed without copying the blob. Task-created incomplete downloads were removed.

## Hardware and OS — actual

| Item | Actual observation |
|---|---|
| Windows | Microsoft Windows 10 Pro, version `10.0.19045`, DisplayVersion `22H2`, full host build `19045.6466`, x64 |
| Linux | Ubuntu `22.04.5 LTS` (Jammy), kernel `6.18.33.2-microsoft-standard-WSL2`, x86_64 |
| WSL | WSL `2.7.12.0`, WSL kernel package `6.18.33.2-2`, WSLg `1.0.73.2`; Ubuntu-22.04 is WSL version 2 |
| CPU | `12th Gen Intel(R) Core(TM) i7-12650H`; Windows reports 10 physical / 16 logical cores; WSL exposes 16 logical CPUs |
| Physical RAM | `17,179,869,184` bytes (16 GiB); Windows OS-visible about 15.63 GiB. WSL limit: `7,935,644 kB` (7.568 GiB) plus 2 GiB swap |
| GPU | `NVIDIA GeForce RTX 3070 Laptop GPU`, compute capability `8.6` |
| VRAM | `8192 MiB` total; `8020 MiB` free with no model loaded |
| NVIDIA driver | `566.07`; `nvidia-smi` reports CUDA compatibility `12.7` |
| CUDA/runtime | WSL `libcuda.so.1` is present; Ollama selected `CUDA v12`, compute 8.6. CUDA toolkit / `nvcc` is not installed. Embedding environment: PyTorch `2.13.0+cu126`, runtime CUDA `12.6` |
| Free space after preparation | Windows `A:` 241.11 GiB; Windows `C:` fluctuated about 31–34 GiB because the system pagefile grew during the smoke. WSL `/` reported about 947 GiB available inside its dynamic VHD; `/mnt/a` about 242 GiB |

Representative inventory commands and actual output:

```text
Get-CimInstance Win32_OperatingSystem / Win32_Processor / Win32_PhysicalMemory
→ Windows 10 Pro 10.0.19045; i7-12650H; 10 cores / 16 logical; 17179869184 RAM bytes

wsl.exe -d Ubuntu-22.04 -- bash -lc 'source /etc/os-release; uname -r; ...'
→ Ubuntu 22.04.5 LTS; 6.18.33.2-microsoft-standard-WSL2; MemTotal 7935644 kB; SwapTotal 2097152 kB

nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free,driver_version --format=csv,noheader
→ NVIDIA GeForce RTX 3070 Laptop GPU, 8192 MiB, 0 MiB, 8020 MiB, 566.07
```

WSL2 is a measured execution environment only. No organizer confirmation that WSL2 satisfies the official Linux requirement was found in the repository or supplied materials; it must not be treated as accepted for submission.

## Generator identity and inventory

- Final Ollama name: `qwen3:8b-q4_K_M`.
- Ollama manifest digest / model ID: `a0a5ad8024dd21401f07634d0c71393b9c9d37aa57a6b594e02b86ab72c450b4`.
- GGUF blob SHA-256: `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785`.
- GGUF blob size: `5,027,783,488` bytes; Ollama manifest total reports `5,027,783,639` bytes.
- Format / quantization: GGUF V3 / `Q4_K_M` (`Q4_K - Medium`, 4.68 GiB, 4.90 BPW).
- Architecture / parameters: `qwen3`, 8.19B (Ollama display: 8.2B), 36 layers.
- Native model context: `40960`; tested operational context: `8192`; model embedding length reported by GGUF: `4096`.
- GGUF metadata name: `Qwen3 8B Awq Compatible Instruct`; upstream source revision is not encoded in the local GGUF and could not be recovered. The manifest digest and blob SHA above are the reproducible local pins.
- Thinking: every request sent both `think: false` and `/no_think`; returned `thinking` was empty and the response contained no `<think>` tags.
- Ollama runtime: `0.33.1`; Linux archive SHA-256 `88e0d36bd90121595e5516c84f6ab61b546368fbd2d825b4aae70999c949649d`.

Final inventory output:

```text
ollama list
NAME               ID              SIZE      MODIFIED
qwen3:8b-q4_K_M    a0a5ad8024dd    5.0 GB    ...

ollama show qwen3:8b-q4_K_M
architecture qwen3; parameters 8.2B; context length 40960;
embedding length 4096; quantization Q4_K_M
```

The manually downloaded source `A:\AI\manual-qwen\Qwen3-8B-Q4_K_M.gguf` and the Ollama blob are byte-identical (same length and SHA-256). They are a source file plus its imported Ollama storage, not two Ollama models. The task did not delete either valid user asset. It did remove the failed official-model partial download and temporary Linux installer archives: 19 task-created files, `6,995,264,796` bytes, non-recoverably; no valid manifest or model blob was removed.

## Generation — actual WSL2/CUDA run

Command shape:

```text
OLLAMA_MODELS=/mnt/c/Users/Artem/.ollama/models \
OLLAMA_HOST=127.0.0.1:11434 OLLAMA_NO_CLOUD=true \
/home/workd69/.local/ollama-v0.33.1/bin/ollama serve

python3 .../work/a01_linux_generation_smoke.py
```

All requests used `qwen3:8b-q4_K_M`, `think=false`, `/no_think`, `num_ctx=8192`, `temperature=0.1`, seed 42, and a single worker.

| Case | Wall / total / load | Prompt eval | Decode | Result |
|---|---:|---:|---:|---|
| Cold short | 85,202.899 / 85,016.661 / 83,466.825 ms | 42 tok / 917.159 ms / 45.79 tok/s | 9 tok / 535.883 ms / 16.79 tok/s | `Столица России — Москва.`; stop; thinking empty |
| Long context | 3,959.675 / 3,927.568 / 40.067 ms | 4098 tok / 3,299.271 ms / 1,242.09 tok/s | 21 tok / 500.762 ms / 41.94 tok/s | exact requested JSON with count 220; thinking empty |
| Warmed short repeat | 3,875.120 / 3,871.766 / 29.346 ms | 42 tok / 84.382 ms / 497.74 tok/s | 9 tok / 234.863 ms / 38.32 tok/s | same short answer; thinking empty |

The first Linux pass on the former alias, backed by the same digest/blob, measured 53.80 s cold wall, 4.10 s long wall and 7.55 s warmed wall. Repeated cold loads from a GGUF on `/mnt/c` varied from about 46 to 85 seconds. Windows-native Ollama on the same blob was much faster: 9.66 s cold, 3.83 s long, and 0.507 s warmed. This is strong evidence that the WSL-to-NTFS model path, plus prompt-cache persistence, dominates startup/warm wall time.

Ollama/llama-server memory output at `num_ctx=8192`:

```text
offloaded 37/37 layers to GPU
CUDA0 model buffer 4455.34 MiB
CUDA0 KV buffer 1152.00 MiB (K f16 576 + V f16 576)
CUDA0 compute buffer 104.01 MiB
CPU-mapped model buffer 333.84 MiB; host compute 24.01 MiB
projected CUDA use 5711 MiB; 7118 MiB free before load; leaves 1406 MiB
observed nvidia-smi after load: 5878–5884 MiB used, 2137–2143 MiB free
```

Observed non-fatal warning: after one unload, Ollama logged `llama-server GPU discovery watchdog timed out` and reused old free-memory values. Requests did not fail and the GPU returned to 0 MiB used. Track this if frequent load/unload is retained.

## Embedding — actual query

- Exact model: `Qwen/Qwen3-Embedding-0.6B`.
- Exact Hugging Face revision: `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`.
- `model.safetensors` target: `1,191,586,416` bytes; SHA-256 `0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd`.
- Configuration: hidden size / output dimension `1024`, max positions `32768`, last-token pooling, normalized output.
- Query prompt: `Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery:` followed by a real Russian retrieval query.
- Environment: existing Windows CUDA venv, PyTorch `2.13.0+cu126`, CUDA `12.6`; `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `local_files_only=True`.

Actual output:

```text
load_ms=4756.561
first_query_ms=897.526
warm_query_ms=39.336
dimension=1024; finite=true; l2_norm=1.0; repeat_max_abs_diff=0.0
process RSS before/after load=684.730/864.559 MiB
GPU allocated/reserved after load=1136.368/1160.000 MiB
GPU peak first query=1152.000 MiB
system RAM used before/after=13.778/14.260 GiB
```

No substitution model was used. The model is not registered as a second Ollama model; it remains one existing Hugging Face snapshot.

## Sequential load and restart

- Required order was respected: embedding process completed and exited; `nvidia-smi` then reported `0 MiB used, 8020 MiB free`; only then generation began.
- The post-embedding generation ran from `2026-09-12T13:34:11.904316Z` to `2026-09-12T13:35:14.026592Z`, returned `локально`, and again left no established non-local TCP connection in the process check.
- No simultaneous embedding + generator measurement was attempted.
- Restart: WSL Ollama was interrupted at `2026-09-12T13:20:12Z`; port `11434` was confirmed closed (`PORT_OPEN=False`) at `13:20:34Z`; a new Ollama process listened at `13:20:44Z`.
- Post-restart request ran `13:21:33.496670Z`–`13:22:19.460695Z`, returned `локально`, with `load=46,264.247 ms`, `prompt_eval=122.327 ms`, `decode=57.675 ms`, thinking empty. The long load is the NTFS/WSL cold-start issue, not an OOM.

## Online preparation versus offline runtime

Online preparation performed:

- `git fetch --prune origin` for the published base.
- Downloaded the official Ollama Linux `0.33.1` binary archive and verified its SHA-256 before extracting it to `/home/workd69/.local/ollama-v0.33.1`.
- No generator or embedding weight was downloaded: both required assets already existed locally. A partial attempted official generator pull created no manifest and was removed after inventory verification.

Final offline runtime proof:

- Ollama was started with `OLLAMA_NO_CLOUD=true`; llama-server logged its own `--offline` argument and used the local `/mnt/c/Users/Artem/.ollama/models` manifest/blob.
- An earlier restart check additionally routed all outbound HTTP(S) proxies to `127.0.0.1:9`; cloud hydration failed while the local request still succeeded.
- Embedding loaded with both Hugging Face/Transformers offline flags and `local_files_only=True`.
- Socket inspection after the final request showed no established non-local TCP connections. Physical network disconnection was not performed, so this is application-enforced offline evidence rather than an air-gap test.

Assets that must be local before demo:

1. Ollama Linux runtime `0.33.1` and its CUDA v12 libraries.
2. Ollama manifest `qwen3:8b-q4_K_M`, config blob `b2dd1377…`, and GGUF blob `d98cdcbd…`.
3. Full `Qwen/Qwen3-Embedding-0.6B` snapshot at revision `97b0c614…`, including tokenizer/config/SentenceTransformer modules and safetensors blob `0437e45c…`.
4. A pinned embedding runtime. The existing tested one is Windows Python/PyTorch; an all-Linux runtime still needs to be prepared if WSL2/Linux is selected.
5. Repository, canonical KB `71bf714a…`, derived retrieval/index artifacts produced by later tasks, and all application dependencies/caches.

## Blockers and recommended runtime budget

- **Submission blocker:** WSL2 acceptance as Linux is unknown; obtain explicit organizer confirmation or repeat this smoke on accepted native Linux.
- **All-Linux runtime blocker:** no Linux pip/PyTorch/Transformers/SentenceTransformers embedding environment is installed. Do not claim the current embedding adapter is Linux-ready.
- **Reproducibility gap:** upstream generator source revision is absent from the manual GGUF metadata. The local manifest/blob pins are exact, but provenance should be recovered before sealing if the rules require it.
- **Storage/startup risk:** host `C:` had only about 31–34 GiB free after runtime preparation, and GGUF on `/mnt/c` cold-loaded in 46–85 s. Move the already-existing blob to a single Linux-native location only as a coordinated migration, not as an extra copy.
- **Memory risk:** Windows had about 1.6 GiB free during final inventory. Avoid browsers/builds competing with inference at demo time.

Recommended budget for profile G:

- one runtime worker; one GPU-heavy operation at a time;
- embedding first, let its process release approximately 1.15 GiB VRAM, then generation;
- generator context `8192`, expected steady VRAM approximately 5.9 GiB and at least 1.4 GiB measured headroom;
- reserve at least 7 GiB WSL RAM plus 2 GiB swap, and keep at least 20 GiB host free disk;
- allow 90 seconds for WSL cold prewarm, 5 seconds for a 4k-token prompt after load, and roughly 20–25 ms/token decode under the measured warmed regime;
- keep the generator resident for the demo rather than unload/reload; prewarm before network isolation;
- do not add a 4B fallback now: the specified 8B model fit and completed every request.

## Repository verification

Before handoff, run from the A01 worktree:

```text
uv run python -m tools.generate_contracts
uv run python -m tools.validate_fixtures
uv run pytest
git diff --check
Get-FileHash -Algorithm SHA256 TenderHack_KnowledgeBase/knowledge_base_FINAL.jsonl
```

Actual post-edit output:

```text
generate_contracts → exit 0; no generated tracked diff
validate_fixtures → 8/8 valid
pytest → 29 passed in 0.69s
canonical KB SHA-256 → 71BF714A9E205A35F5D8EC0FD2D0F9BBD4AD3A8409968B754EB8DE7B349D79AE
git diff --check → exit 0 (only Git's LF→CRLF checkout warning for gpu_slots.md)
```

A02 was not started.
