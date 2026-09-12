# A08 — two draft ScenarioCard handoff

## Status and immutable pins

- Task ID / status: **A08 / done**.
- Owner / tool: Артём / agent A / Codex.
- Branch: `task/a08`.
- BASE_SHA / current accepted `origin/main` at task start:
  `476643812fac0ba62b545659abb4e4ffe888c186`.
- Result SHA for the two card files:
  `6030216bcaebb38c3fd64334e3e88f6eed329969`.
- Contracts version: `2.1.0-a02`; the contract was not changed.
- KB snapshot: `kb-4918a97f0874d1e8`.
- Machine / mode: Windows, CPU-only; real local KB snapshot with lexical FTS retrieval.
  No GPU, generation, or runtime import was needed.

A03 was accepted before this task: `f92d87dbc77a4af1ca94660de7ddd0f9084946a9`
is an ancestor of the BASE_SHA, and `docs/coordination/artem/A03-handoff.md` records PASS.
The later independent C03 acceptance contains both `C03_REAL_DENSE_READY=yes` and
`A03_RUNTIME_DEPENDENCY_READY=yes`.

## Changed files

- `content/cards/artem/card-artem-001.json`
- `content/cards/artem/card-artem-002.json`
- `docs/coordination/artem/A08-handoff.md`

No runtime, retrieval, backend, contract, evaluation, C05, or sealed-final file was changed.
The cards were not imported into the KB/runtime.

## Card 1 — CARD-ARTEM-001

- Intent: `replace_or_add_organization_bank_details`.
- Title: «Изменение или добавление банковских реквизитов организации».
- Role/audience: `supplier`; the source has `audience_raw="supplier"`,
  `applicable_roles=["supplier"]`, and `role_verified=true`.
- Source: `portal:559886:1`, «Как изменить банковские реквизиты организации или
  добавить новые на Портале поставщиков?».
- Source status: `complete`.
- Page / section / public article URL / source date: unavailable in the accepted snapshot;
  kept unknown rather than inferred. The collection API endpoint is not an article URL.
- Required facts:
  - `role=supplier`;
  - `bank_details_action=replace_or_add`.
- Required conditions:
  - the user works on the Portal as a supplier;
  - the request is to change the organization's bank details or add new ones.
- Deterministic outcome: existing bank details are not edited; add new details through
  «Управление профилем» → «Профиль компании» → «Заявка на изменение данных», archive
  the old details, submit the application, and wait for its review.
- `handoff_required=false`.
- Routing: deliberately neutral (`topic_id`, `subtopic_id`, `support_line`, recipient,
  and `rule_id` are null). The accepted taxonomy produced no supported match, so no route
  was invented.
- Fallback: `ScenarioCard` has no dedicated fallback field. Per v2.1, if the required facts
  or exact intent do not match, this draft must not fire and ordinary RAG is used. The source
  gives no separate escalation recipient for a failed bank-details application, so none was
  invented in the card.

## Card 2 — CARD-ARTEM-002

- Intent: `bind_unregistered_certificate_to_supplier_profile`.
- Title: «Ошибка “Сертификат не зарегистрирован” при входе по ЭП».
- Role/audience: `supplier`; the source has `audience_raw="supplier"`,
  `applicable_roles=["supplier"]`, and `role_verified=true`.
- Source: `portal:559723:1`, «При авторизации по электронной подписи появляется ошибка:
  “Сертификат не зарегистрирован”».
- Source status: `complete`.
- Page / section / public article URL / source date: unavailable in the accepted snapshot;
  kept unknown rather than inferred. The collection API endpoint is not an article URL.
- Required facts:
  - `role=supplier`;
  - `authentication_method=electronic_signature`;
  - `error_message=Сертификат не зарегистрирован`.
- Required conditions:
  - the user works on the Portal as a supplier;
  - the error occurs during electronic-signature authentication;
  - the exact error text is «Сертификат не зарегистрирован».
- Deterministic outcome: log in with login/password, open «Управление пользователем» →
  «Профиль пользователя» → «Операции с ЭП», authenticate again, select the signature,
  and confirm it.
- `handoff_required=false`.
- Evidence-backed fallback: if difficulties occur, contact the Portal supplier technical
  support service through the feedback form. This wording is present in the source.
- Routing, recomputed using only this source as evidence:
  - topic `TH1`, subtopic `ST03`, line `L2`;
  - recommended recipient: `службу технической поддержки Портал поставщиков по форме
    обратной связи`;
  - basis source: `portal:559723:1`;
  - rule: `ROUTE.LINE.L1_L2_UNCERTAIN_TRIAGE`;
  - `is_probable_defect=false`, `is_ambiguous=false`.

## Evidence and validation

The local C02 snapshot was rebuilt from the tracked raw KB and documents:

```text
uv run python -m knowledge.kb.ingest --out var/knowledge
snapshot_id kb-4918a97f0874d1e8
raw 1468, included 1528, excluded 44, articles 480
knowledge.sqlite SHA-256 11e1f4b04b0e3c484c1fce1213f9f4ded4add513983600b4f5262c67d21753a6
```

The Windows SQLite container hash matches the already accepted C03 Windows build. The logical
snapshot identity is the same cross-platform snapshot described by C03 acceptance.

A fresh validation script loaded exactly the two JSON files through
`ScenarioCard.model_validate_json()`, checked draft/reviewer/snapshot fields, verified each
`source_id` in SQLite, required `content_status=complete` and `role_verified=1`, checked the
card roles against source roles, opened both records through `store.get_source()`, and
recomputed each route from only its own source evidence.

```text
validated: 2/2 ScenarioCard drafts
sources: portal:559886:1, portal:559723:1 (complete, role_verified supplier)
routing: CARD-ARTEM-001 neutral; CARD-ARTEM-002 TH1/ST03/L2 with evidence-based recipient
```

Full regression suite after creating the cards:

```text
uv run pytest
491 passed in 43.85s
```

`git diff --check` passed. D01 DEV was not needed for candidate selection or card content;
the cards were derived from and checked against the real current KB. No sealed final data was
opened or used.

## Blockers and limitations

- Blockers: none for A08.
- The current `ScenarioCard` schema has no dedicated fallback/page/section fields. The contract
  was not expanded. Evidence fallback and unavailable page/section metadata are recorded here;
  the only source-backed fallback is also retained as the last step of CARD-ARTEM-002.
- Local retrieval health was `lexical_only` because machine-G index artifacts are not present
  in this worktree. This does not weaken source verification: both exact source records were
  opened directly, and real dense C03 is independently accepted upstream.

## What Eduard must check in C06

1. Independently reread `portal:559886:1` and `portal:559723:1` from the accepted snapshot.
2. Confirm that each summary, condition, and step is entailed by its source and that no missing
   screenshot/attachment is required.
3. Confirm that `supplier` is the appropriate verified role and that all required facts are
   sufficient to prevent near-intent collisions (especially other electronic-signature errors).
4. Recompute routing independently. In particular, preserve the neutral route for card 1 unless
   a real taxonomy/routing basis exists, and verify the exact-source basis for card 2's recipient.
5. Check fallback behavior: card 1 must fall back to ordinary RAG when not exactly applicable;
   card 2 may state only the support referral present in its source.
6. Verify snapshot identity, keep both cards draft until the independent review is complete,
   and only then decide whether to import them. Do not treat this A08 handoff as review approval.

## CR and next-task boundary

- CR: none.
- A05 was not started. A08 stops after commit and push of `task/a08`.
