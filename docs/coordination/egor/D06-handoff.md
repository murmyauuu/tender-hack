# D06 — handoff

- Status: done
- Owner: Егор / opencode
- Base SHA: 461c114 (fresh origin/main after A04 merge)
- Result SHA: pending (commit after this handoff)
- Contracts version: 2.0.0-c0
- Machine profile: local, Python 3.14.5, pandas 3.0.3, openpyxl 3.1.5, PowerShell 5.1
- Runtime SHA / KB snapshot: kb-4918a97f0874d1e8 (C02 snapshot, 1528 included, 0 cards_reviewed)
- Changed files:
  - content/cards/egor/card-egor-001.json
  - content/cards/egor/card-egor-002.json
  - docs/coordination/egor/D06-handoff.md

## Implemented behavior

Created exactly 2 draft ScenarioCard entries in content/cards/egor/:

1. **CARD-EGOR-001** — attach_electronic_signature_to_profile
   - intent: attach electronic signature to supplier profile
   - role: supplier
   - source: portal_api:226860:1 (инструкция по прикреплению ЭП)
   - conditions: supplier role, ES attach action
   - steps: profile → attach ES → select ES → enter password → confirm
   - status: draft, not reviewed, not approved
   - reviewer_id: null
   - Not imported into runtime

2. **CARD-EGOR-002** — fulfill_contract_execution
   - intent: fulfill contract execution as customer
   - role: customer
   - source: portal_api:242148:1 (инструкция по исполнению контракта)
   - conditions: contract status "Заключен", customer role
   - steps: open contract → click "Исполнен" → confirm → status changes to "Исполнен"
   - status: draft, not reviewed, not approved
   - reviewer_id: null
   - Not imported into runtime

## Acceptance: passed

- Both cards validate against ScenarioCard schema (model_validate_json round-trip ✓)
- Source IDs verified in frozen KB snapshot (portal_api:226860:1, portal_api:242148:1 exist in knowledge_base_FINAL.jsonl ✓)
- Conditions/evidence based on real KB sources, not invented ✓
- Frozen snapshot compatibility: snapshot_id kb-4918a97f0874d1e8 used, final jsonl untouched ✓
- No duplication of A08/C05 scenarios ✓
- Cards are draft, not reviewed, not approved, reviewer_id=null ✓
- Not imported into runtime (store.get_card() returns None for content/cards/) ✓

## Intentions

- CARD-EGOR-001: Supplier needs to attach/replace ES on portal profile
- CARD-EGOR-002: Customer needs to fulfill/execute contract after signing

## Sources

- portal_api:226860:1 — "Как прикрепить электронную подпись?" (supplier ES attachment)
- portal_api:242148:1 — "Исполнение контракта" (customer contract execution)

## Conditions

- CARD-EGOR-001: supplier role + ES attach action
- CARD-EGOR-002: customer role + contract "Заключен" status

## Human-check status

Егор-человек должен фактически посмотреть обе карточки и источники (portal_api:226860:1, portal_api:242148:1) перед сдачей.
Агент не подписывает human validation от имени Егора.

## What Стас should check in C06

- Validate that both cards conform to ScenarioCard schema
- Verify source IDs exist in the frozen KB snapshot (C07 state)
- Check that conditions/evidence are based on real KB sources, not invented
- Confirm handoff_required=false and routing is appropriately set (or absent) for draft cards
- Ensure reviewer_id=null, status=draft, not approved, not imported into runtime
- Verify no hidden final modifications

## Blockers

- None