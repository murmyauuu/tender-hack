# FIX-D06-01 — handoff

- Status: done
- Owner: Егор / opencode
- Base SHA: 0faf332b4b0f48fefa2e14e31257ba2a85c0ad37 (origin/main)
- Original D06 SHA: e9ed335a6b65eafb4c77460f9bbc2ce34eb5d2e4
- FIX SHA: 2c65d6549b598a03d672cf73721b26ea13845bae
- Contracts version: 2.0.0-c0
- Machine profile: local, Python 3.14.5, pandas 3.0.3, openpyxl 3.1.5, PowerShell 5.1
- Runtime SHA / KB snapshot: kb-4918a97f0874d1e8 (C02 snapshot, 1528 included, 0 cards_reviewed)
- Changed files:
  - content/cards/egor/card-egor-001.json
  - content/cards/egor/card-egor-002.json
  - docs/coordination/egor/FIX-D06-01-handoff.md

## Findings C06 (from Стас review packet)

### Finding 1: Неверные runtime source IDs
**Описание:** Обе D06 карточки используют `portal_api:` source IDs, которых нет в C07 frozen KB snapshot (chunks_fts).

**Подтвердилось:** ДА
- `portal_api:226860:1` → 0 occurrences в chunks_fts
- `portal_api:242148:1` → 0 occurrences в chunks_fts
- Правильные `portal:` ID с теми же номерами существуют в chunks_fts:
  - `portal:226860:1` — 1 occurrence
  - `portal:242148:1` — 1 occurrence

### Finding 2: CARD-EGOR-001 — неподтверждённая кнопка «Подписать»
**Описание:** В step 5 указано «Подтвердить действие кнопкой «Подписать»», но evidence в источнике указывает на «Сохранить».

**Подтвердилось:** ДА
- Источник `portal:226860:1` («как прикреп электрон подп»): «нажа кнопк сохран»
- В исходной карточке: «Подтвердить действие кнопкой «Подписать»»
- Исправлено на: «Подтвердить действие кнопкой «Сохранить»»

## Before / After

### CARD-EGOR-001 (attach_electronic_signature_to_profile)

| Поле | Before | After |
|------|--------|-------|
| source_ids | `["portal_api:226860:1"]` | `["portal:226860:1"]` |
| route.basis_source_ids | `["portal_api:226860:1"]` | `["portal:226860:1"]` |
| step 5 | `Подтвердить действие кнопкой «Подписать»` | `Подтвердить действие кнопкой «Сохранить»` |

### CARD-EGOR-002 (fulfill_contract_execution)

| Поле | Before | After |
|------|--------|-------|
| source_ids | `["portal_api:242148:1"]` | `["portal:242148:1"]` |
| route.basis_source_ids | `["portal_api:242148:1"]` | `["portal:242148:1"]` |

## Исправленные source IDs

- CARD-EGOR-001: `portal:226860:1` (существует в C07 snapshot chunks_fts)
- CARD-EGOR-002: `portal:242148:1` (существует в C07 snapshot chunks_fts)

## Исправленный step CARD-EGOR-001

- **Before:** `Подтвердить действие кнопкой «Подписать»`
- **After:** `Подтвердить действие кнопкой «Сохранить»`
- **Evidence:** Источник `portal:226860:1` содержит «нажа кнопк сохран»

## Validation Results

- ✅ Обе карточки проходят ScenarioCard schema (model_validate_json round-trip)
- ✅ Source IDs существуют в C07 snapshot (chunks_fts): `portal:226860:1` (1 occ), `portal:242148:1` (1 occ)
- ✅ Every required fact/condition имеет evidence в соответствующем источнике
- ✅ Никаких invented UI actions (кнопка «Подписать» заменена на «Сохранить» по evidence)
- ✅ Sealed final untouched (KB hash match: 71bf714a9e205a35f5d8ec0fd2d0f9bbd4ad3a8409968b754eb8de7b349d79ae)
- ✅ Cards remain draft, reviewer_id=null, not imported into runtime

## Tests

1. Schema validation: `ScenarioCard.model_validate_json()` — PASS (both cards)
2. Source ID existence in C07 snapshot: `chunks_fts` lookup — PASS (both sources)
3. Evidence verification: Steps match source text — PASS
4. KB hash integrity: SHA-256 match — PASS

## Blockers

- None