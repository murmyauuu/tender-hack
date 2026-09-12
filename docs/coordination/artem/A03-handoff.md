# A03 — first real dense RAG E2E handoff

## Status and immutable pins

- Status: **PASS**. A03 is complete; A04 was not started.
- Branch: `task/a03`
- BASE_SHA / accepted `origin/main`: `f62ce7784d4e166cab4b6015732fa8e23c1c9254`
- Result SHA / runtime SHA: `d899a5165d608b072690ec494e661687e2f8916c`
- Logical KB snapshot: `kb-4918a97f0874d1e8`
- Persistent runtime directory on G: `A:\AI\retrieval-results\c03-kb-4918a97f0874d1e8-gpu-abea7ae-20260912T1619Z`
- `knowledge.sqlite`: `11e1f4b04b0e3c484c1fce1213f9f4ded4add513983600b4f5262c67d21753a6`
- `index.npy`: `396e8ee4e5ce4c457292eea2b107058b7941ea0c498434a70f8da6abc9b8de87`
- `index_ids.json`: `b328deae1ba6868da115d66e81e19b60b92f6601cf20717cfb7070b14bca110d`
- `manifest.json`: `589600e50e02239806d98a43f41ee88e42d20bef5f3aabbb7ece4e844aae9f77`
- `retrieval_log_dev20.json`: `47718bb1f2bf72451bcb8abd5ef2d9ba1ae2710119b154cb524732498ddd0cf0`
- Embedding model: `Qwen/Qwen3-Embedding-0.6B`
- Embedding revision: `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`
- Embedding safetensors SHA-256: `0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd`
- Generator: `qwen3:8b-q4_K_M`, thinking off, no automatic generation retries
- Ollama model digest: `a0a5ad8024dd21401f07634d0c71393b9c9d37aa57a6b594e02b86ab72c450b4`
- GGUF SHA-256: `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785`

All five runtime artifact hashes above were independently recomputed immediately before the accepted run. The platform-specific SQLite serialization difference from the macOS C02 artifact is covered by the formal C03 runtime acceptance. No embeddings were rebuilt in A03.

## Dependency preflight

Fresh `origin/main` was fetched and fast-forwarded to the stated BASE_SHA. A01 PASS, A02, B01, B02, C01, C03 implementation, and `docs/coordination/stas/C03-runtime-acceptance.md` were present. The canonical acceptance contains both `C03_REAL_DENSE_READY=yes` and `A03_RUNTIME_DEPENDENCY_READY=yes`. The historical pre-completion C03 handoff remains `partial` and was not treated as the current verdict.

Before the run, the only GPU consumer was the intended Ollama server. The exact pinned model was available from `/api/tags`. C03 artifacts were opened in place and were not rebuilt or copied.

## Runtime wiring

Production/default `runtime_mode=real` now wires the accepted C01 policy, the accepted C03 `KnowledgePort`, its real dense index, the CUDA Qwen3 query encoder, and the accepted A02 Ollama backend. It fails closed unless knowledge health is semantic and the exact A01 model name/digest is available. There is no lexical or fake fallback in real mode. Fakes remain available only through explicit `runtime_mode=test` and tests.

Observed real health:

```text
status=ready
knowledge=ready
generator=ready
KnowledgePort.health.available=true
KnowledgePort.health.mode=semantic
KnowledgePort.health.snapshot_id=kb-4918a97f0874d1e8
reason=C03: корпус dense векторов реальный (1528 строк), query encoder реальный
```

The real retrieval smoke covered D01 cases DEV-010, DEV-012, and DEV-019. Each returned `ANSWER_ALLOWED` using dense candidates. The accepted full HTTP E2E below uses DEV-019.

## Accepted real E2E

- Classification: **real**, not mock or mixed.
- Question: `Как изменить банковские реквизиты организации на Портале поставщиков?`
- Session ID: `12506c41-7818-49a8-a016-ae4b4a125b86`
- Case ID: `12d8773c-6340-4b01-8b18-3dba0b044fb5`
- Request ID: `4829958c-2a43-4d71-8efe-f8daed9721cf`
- User message ID: `8232b9f9-96e7-4ed9-9046-66831bef239b`
- Answer message ID: `490abee6-908d-4c61-9bac-8e8f7347b655`
- HTTP: session `201`, chat `202`, source `200`, feedback `201`
- Observed lifecycle: `queued -> processing/generating -> final`
- Query embedding calls: `1`
- Retrieval calls: `1`
- Generation calls: `1`
- Final case after feedback: `resolved`

Actual answer:

> Для изменения банковских реквизитов организации на Портале поставщиков необходимо добавить банковский счет через раздел Заявка на изменение данных в Профиле компании.
>
> 1. Перейдите в Профиль компании;
> 2. Нажмите на вкладку Заявка на изменение данных;
> 3. В разделе Банковские реквизиты нажмите на кнопку Добавить и заполните необходимые поля;
> 4. После внесения изменений нажмите Отправить заявку и дождитесь её утверждения.

Actual answer source IDs: `portal:292330:1` only. It is a member of the eligible IDs passed to generation; no other source ID was emitted.

Actual `GET /api/v1/sources/portal:292330:1` record:

- Title: `Как добавить банковский счет в банковских реквизитах организации на Портале поставщиков?`
- Source type: `portal_kb`
- Version: `null`
- Page: `null`
- URL / file URL / source date: `null` (the answer did not invent any of them)
- Content status: `complete`
- Conditions: `[]`; therefore no mandatory condition was dropped
- Excerpt begins: `Как добавить банковский счет в банковские реквизиты организации на Портале поставщиков? Для добавления банковского счета ... Перейдите в Профиль компании; Нажмите на вкладку Заявка на изменение данных...`

Timings from the persisted request, milliseconds:

| Measurement | ms |
|---|---:|
| query embedding | 10844.698 |
| retrieval | 10985.834 |
| time to first source | 10998.456 |
| Ollama prompt eval | 27.646 |
| Ollama decode | 3944.626 |
| Ollama total | 4100.373 |
| generation total | 4111.275 |
| end-to-end total | 15134.514 |

Retained local evidence (gitignored runtime output):

- `var/a03/real-d899a51.sqlite`
- `var/a03/real-e2e-d899a51.json`
- `var/a03/real-export-d899a51.json`

## Feedback and export

- Feedback ID: `aa304b35-956a-403b-8e49-8477809df5ae`
- Payload/result: `useful=true`, `solved=true`, `outcome_applied=true`, `case_status=resolved`, `case_version=3`
- Export: succeeded and contained exactly one corresponding `EvaluationRow`
- Export row: same Case ID, `cohort=live`, `case_status=resolved`, `policy_closed=false`, answer origin `rag`
- Exported feedback contains the same answer message with `useful=true` and `solved=true`
- `current_resolution.confirmed_by=user` and `current_resolution.answer_origin=rag`
- Export pins `app_commit=d899a5165d608b072690ec494e661687e2f8916c` and `kb_snapshot_id=kb-4918a97f0874d1e8`

## Policy and invalid-generation checks

### Profanity — real runtime

An HTTP request containing `блять` was sent through the same real runtime composition (real C01 policy, strict semantic C03 port, real encoder object, real Ollama adapter). It closed synchronously with `closed_policy` and `POLICY_LANGUAGE`:

```text
query_embedding_calls=0
retrieval_calls=0
generation_calls=0
```

This is a real runtime policy check; neither the encoder nor Ollama was invoked.

### Invalid generation — real and controlled

A real pre-acceptance run at runtime SHA `4838e3c5153445c5e3389f2a53f9f2172c8963d8` deliberately exercised the invalid proposal path:

- Request ID: `17533d37-73e1-4516-aa31-19fe12ff311e`
- Case ID: `b3bc91a0-a864-4381-83ef-30cfbdfbf4b7`
- One real query embedding, one real dense retrieval, one real Qwen3-8B generation
- Verifier result: rejected proposal
- Final state: `handoff_offered`
- Reason: `INVALID_GENERATION`
- Automatic second generation: absent

The deterministic controlled tests additionally assert `generation_calls=1`, `handoff_offered/INVALID_GENERATION`, and no retry for invalid JSON, invalid proposal shape, and an ungrounded proposal. They use fake dependencies intentionally and are classified **mixed/controlled**, not evidence for AC01.

## Acceptance verdict

| Criterion | Actual status | Evidence class |
|---|---|---|
| AC01 | **PASS** — real HTTP RAG reached dense retrieval, one generation, verified Message, real source lookup, saved feedback, and matching export row | real |
| AC05 basic | **PASS** — verifier/invalid proposal caused one generation only and `handoff_offered/INVALID_GENERATION`; no automatic retry | real plus mixed/controlled regression tests |
| AC08 | **PASS** — benign case is the accepted real E2E; real-runtime profanity short-circuited with 0 embedding, 0 retrieval, 0 generation | real |

## Real / mock / mixed separation

- **Real:** accepted AC01 E2E, dense smoke, exact-model health, source lookup, feedback/export, profanity short-circuit, and the recorded pre-acceptance invalid-generation run.
- **Mock:** unit tests for individual ports and verifier behavior only.
- **Mixed/controlled:** deterministic HTTP runner and invalid-proposal regression tests with injected fake dependencies. These were not used to mark AC01 PASS.

## Blockers

None. Two A-owned integration defects discovered during pre-acceptance runs were fixed before the accepted run: Ollama grammar limits in the generated schema, and optional discriminator handling for the answer-only transport schema. No C-owned implementation was changed and no FIX/CR is required.
