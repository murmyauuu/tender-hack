# C03 — independent real GPU runtime acceptance

- **Verification status:** PASS
- **Verifier:** Стас / independent runtime verifier and integration operator / Codex
- **Verification date:** 2026-09-12
- **BASE_SHA:** `b62a35d7675a415e8ac3f9a78c47b7a1b7a4982f`
- **Original C03 result SHA:** `16875ec966b11535191cf900156ff2088286330b`
- **Integrated C03 implementation commits:** `1495dfc877153c349d9569dd2b3987019bcfe8f4`, corrective fix `77e69adbab6ac5b71b39dc984189c77295592173`
- **GPU main SHA during build:** `abea7ae6831a30cfcdc4d662caeefc9ced4b69a2`
- **Logical KB snapshot:** `kb-4918a97f0874d1e8`
- **Contracts version:** `2.0.0-c0`
- **Runtime/data mode:** real CUDA, real C02 KB, real D01 DEV20, no mock dense path

The historical `docs/coordination/eduard/C03-handoff.md` remains unchanged and correctly
describes the earlier pre-GPU state as partial. This document is the subsequent acceptance
evidence for the completed real GPU run.

## 1. Scope and evidence basis

This acceptance maps the real machine-G report to the C03 criteria in
`TenderHack_UNIFIED_SPEC_v2.1_prefilled.md` and checks the identity rules in the accepted
implementation. No C03 implementation, `knowledge/**`, `config/knowledge/**`, or historical
C03 handoff was changed.

The persistent `A:` artifact volume was not mounted in the verifier session. Artifact hashes
below are therefore preserved from the machine-G completion report; that report also records
successful `validate_index_artifact` and an independent NumPy/SQLite check. Repository code,
provenance rules, accepted Git history, and regression tests were independently checked in the
verification worktree.

The C03 implementation tree in current `main` is identical to original result
`16875ec966b11535191cf900156ff2088286330b` for `knowledge/**` and
`config/knowledge/**`. The original commits were integrated as the two commits listed above.

## 2. Logical snapshot provenance and cross-platform SQLite verdict

`knowledge/kb/ingest.py::build_manifest` computes `snapshot_id` from exactly:

1. ordered canonical `input_files` names and SHA-256 values;
2. `NORMALIZER_VERSION`;
3. `SCHEMA_VERSION`.

The SHA-256 of the generated SQLite container is calculated only after the logical manifest and
database have been built and is stored as a file-integrity hash. It is not an input to
`snapshot_id`. The v2.1 specification requires a manifest, reproducible provenance, stable IDs,
counts/hashes, and saved index/mapping/results; it does not require byte-identical SQLite files
across SQLite builds or operating systems.

Verified logical provenance:

- `snapshot_id`: `kb-4918a97f0874d1e8` on C02 macOS and G Windows.
- `normalizer_version`: `c02-normalizer-1.0.0`.
- `schema_version`: `c02-schema-1.0.0`.
- All 8 canonical input hashes on G matched C02:
  - `TenderHack_KnowledgeBase/knowledge_base_FINAL.jsonl`: `71bf714a9e205a35f5d8ec0fd2d0f9bbd4ad3a8409968b754eb8de7b349d79ae`
  - `Регламент_информационного_взаимодействия-4.pdf`: `ef09670556196f6acf00d78e4e3aefe688665cecbf1fd8622afaa5fb488b707b`
  - `НН 2026/Инструкция по работе с Порталом для заказчика.pdf`: `7355b2c39b4aa4fbac758f64aeab0bdfd4a8219cc483dd5ca52e28eacb59fcde`
  - `НН 2026/Инструкция по электронному актированию.pdf`: `d14f883b14f8f117842541900300901404b37d43cdddf13c3e3266cfbd9155b3`
  - `НН 2026/Инструкция по работе с машиночитаемыми доверенностями.pdf`: `755870a7454fd166146bfd64a7c50009fc834340798d28ff9cee3132265272b9`
  - `НН 2026/Инструкция по созданию оферты и СТЕ.pdf`: `ce50227cb1bb29b9145dd0fb52181c353c03bb11e00a0ab467cf544914b20159`
  - `НН 2026/Инструкция по работе с Порталом для поставщика.pdf`: `3c52c3633b6bc84e99ca1a23336536e9408ba83b28f160ee5c02738a2f754c6b`
  - `НН 2026/Инструкция по формированию YML.pdf`: `753fc58d5c7ae3b15932ef658d88f4eb2886273af2e3067389c5aa0934bd9a9c`
- Counts matched: `chunks=1528`, `vectors=1528`, `parents=636`.
- ID mapping contained 1528 unique IDs and matched `ORDER BY ord, source_id`.

SQLite container hashes, both retained without concealment:

- C02 macOS `knowledge.sqlite`: `6d1555777d9bbf9ae7f2df93a69cf61f53dd04263877a8ebaf7fc35e16a4bdf8`.
- G Windows reconstruction `knowledge.sqlite`: `11e1f4b04b0e3c484c1fce1213f9f4ded4add513983600b4f5262c67d21753a6`.

**Verdict:** the differing SQLite SHA values are a **platform-specific SQLite container
serialization difference**, not a different logical KB snapshot. The initial strict provenance
FAIL based only on byte inequality is rejected by the actual identity implementation and v2.1
criteria. A repeat embedding build solely to obtain a byte-identical SQLite container is not
required.

## 3. Embedding and index evidence

| Item | Actual value |
|---|---|
| Model | `Qwen/Qwen3-Embedding-0.6B` |
| Revision | `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3` |
| `model.safetensors` SHA-256 | `0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd` |
| Adapter | `c03-qwen3-embedding-last-token-l2-1.0.0` |
| Pooling / normalization | last token / L2 |
| Index type | `numpy_exact_cosine` |
| Shape | `1528 x 1024` |
| dtype | `float32` |
| Finite | `true` |
| L2 norm min / mean / max | `0.997459 / 1.000103 / 1.002627` |

The main command was `python -m knowledge.kb.gpu.embed_and_smoke` with real CUDA and
`batch-size=16`. `--skip-safetensors-check` was used only because the Hugging Face cache used a
non-standard layout; `model.safetensors` was manually hashed before the run and matched the
pinned SHA above. Weight verification was therefore performed, not omitted.

`validate_index_artifact`: OK. The independent NumPy/SQLite verification: OK.

## 4. Persistent artifacts on G

Directory:
`A:\AI\retrieval-results\c03-kb-4918a97f0874d1e8-gpu-abea7ae-20260912T1619Z`

| Artifact | SHA-256 |
|---|---|
| `index.npy` | `396e8ee4e5ce4c457292eea2b107058b7941ea0c498434a70f8da6abc9b8de87` |
| `index_ids.json` | `b328deae1ba6868da115d66e81e19b60b92f6601cf20717cfb7070b14bca110d` |
| `manifest.json` | `589600e50e02239806d98a43f41ee88e42d20bef5f3aabbb7ece4e844aae9f77` |
| `retrieval_log_dev20.json` | `47718bb1f2bf72451bcb8abd5ef2d9ba1ae2710119b154cb524732498ddd0cf0` |

DEV20 input SHA-256:
`7dff9fc14660e1f938208987400dd65ec70bde164f1c91168b1e91350084cda2`.

Heavy runtime artifacts were not added to Git. The machine report records C-owned tracked diff
as 0; the verification worktree was also clean before this evidence document was created.

## 5. Actual dense DEV20 results

- `gold_in_candidates = 20/20`.
- `gold_in_selected = 18/20`.
- Candidate failures: none.
- Selected misses: `DEV-007`, `DEV-015`.
- Gate decisions: `ANSWER_ALLOWED = 20/20`.
- Gate reason codes: none.
- Retrieval time: approximately `255 ms/case`.
- Parameters and thresholds were not changed after reviewing DEV results.

The 20 cases have known roles and are answerable by design, so `ANSWER_ALLOWED=20/20` is the
correct gate result. `DEV-007` and `DEV-015` are retained as known retrieval limitations. C03
does not require `gold_in_selected=20/20`; its criterion is that real applicable sources are
found on dev, unsafe pointer/role/unknown-ID cases do not get unjustified `ANSWER_ALLOWED`, and
actual results are saved. No tuning or implementation change is warranted in this acceptance.

## 6. Performance and resource evidence

| Measurement | Actual value |
|---|---|
| Model load | `12.559 s` |
| Document encoding | `113.563 s` |
| Encoding throughput | approximately `74.32 ms/chunk` |
| DEV retrieval | approximately `255 ms/case` |
| Full runner | `133.501 s` |
| Peak VRAM | `4662 MiB` |
| Peak process working set | `1.51 GiB` |
| Peak process private memory | `7.52 GiB` |
| System RAM used | `12.18–15.20 GiB` |
| GPU after run | `0 MiB` |

## 7. Acceptance mapping

| C03 criterion | Evidence | Verdict |
|---|---|---|
| Real applicable sources found on dev | Real dense DEV20 has gold in candidates `20/20` | PASS |
| Safe minimal evidence gate | Answerable known-role DEV20 gives `ANSWER_ALLOWED=20/20`; existing gate tests cover pointer, role mismatch, and unknown ID | PASS |
| Similarity is not confidence | Accepted C03 code retains score as an internal retrieval score; no probability claim | PASS |
| Real index saved | `1528 x 1024`, float32, finite, valid L2 norms, persistent hashed artifact | PASS |
| ID mapping saved | 1528 unique IDs in canonical order; hashed artifact | PASS |
| Manifest and hashes saved | Stamped manifest and all artifact hashes recorded | PASS |
| Actual retrieval results saved | Hashed `retrieval_log_dev20.json` with actual dense metrics and known misses | PASS |
| No new unlisted requirement | No byte-identical cross-platform SQLite or selected `20/20` requirement exists in v2.1/C02/C03 | PASS |

## 8. Regression evidence

- Machine-G completion report: full suite `359 passed` after the GPU completion.
- Independent verifier on current BASE_SHA:
  - C03-focused suite: `59 passed in 22.55s`.
  - Full current suite: `432 passed in 157.04s`.
  - `git diff --check`: clean.
  - `git diff 16875ec... HEAD -- knowledge config/knowledge`: no implementation-tree difference.
- No implementation defect or blocking mismatch was found.

## 9. PASS criterion and downstream readiness

PASS requires all actual C03 obligations to be evidenced: the logical C02 snapshot is identified
by canonical inputs and versions; the pinned real embedding model produces a validated persistent
index and canonical ID mapping; artifact hashes and actual DEV20 retrieval results are retained;
the evidence gate behaves correctly for the applicable dev set and remains covered for unsafe
cases; no C03 implementation defect or regression is present. Byte-identical SQLite serialization
across platforms and `gold_in_selected=20/20` are not C03 acceptance requirements.

All of these requirements are met. Open limitations are `DEV-007` and `DEV-015` not reaching the
final selected set; neither is a C03 blocker. No other blockers remain.

`C03_REAL_DENSE_READY=yes`

`A03_RUNTIME_DEPENDENCY_READY=yes`
