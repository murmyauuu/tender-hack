# D05 — Настоящая BPMN-модель реализованного процесса

## Status and pins

- **Status**: done
- **Branch**: `task/d05`
- **BASE_SHA**: `461c114` (fresh `origin/main` after A04 merge)
- **Result SHA**: `dd249655ffd6a23eda8ee2dce20068338e57200b` (task/d05 commit)
- **Owner**: D / Егор

## A04 / B03 states reflected in this BPMN

This BPMN model reflects the actual implemented process from A04 backend/runtime and B03 frontend verification:

| Category | States / API |
|---|---|
| **Policy check** | `policy.check(text)` → `profanity`, `explicit_human_request` |
| **Chat admission** | `accept_chat()` → `chat_mode` (ai/policy/handoff/operator) |
| **Retrieval** | `knowledge.retrieve(QueryContext)` |
| **Evidence gate** | `decide_gate()` → `GateDecision: ANSWER_ALLOWED / CLARIFY / ESCALATE / OUT_OF_SCOPE` |
| **Clarification** | Max 1 clarification (`clarification_count >= 1` → handoff) |
| **Generation** | `generator.generate()` → `GenerationAnswer / GenerationClarify / GenerationEscalate` |
| **Awaiting feedback** | `case_status = AWAITING_FEEDBACK` |
| **Handoff offered** | `case_status = HANDOFF_OFFERED`, `ticket = null` |
| **Explicit handoff confirmation** | `confirm_handoff()` → `ticket` created, `case_status = HANDED_OFF` |
| **Waiting for specialist** | `ticket_status = NEW`, case `HANDED_OFF` |
| **Operator reply** | `reply_as_operator()` → `ticket NEW → WAITING_USER` |
| **User response to specialist** | User reply → `ticket back to NEW`, AI NOT launched |
| **Technical failure / retry** | `invalidate_request()` / `retry_of` |
| **Out of scope** | Notice + case stays `OPEN` |
| **Feedback** | `save_feedback()` → specific to AI/operator answer |
| **Resolved** | `ticket.status = RESOLVED`, `case.status = RESOLVED` |
| **Closed policy** | Profanity → `CLOSED_POLICY` |

## Process Overview

The BPMN 2.0 model at `docs/process/d05.bpmn` describes the real support flow implemented in the TenderHack backend and frontend. The model includes all actual API calls, state transitions, and gate decisions from the codebase.

Key principles reflected in the model:

1. **Real implementation, not architecture** - every gateway, task, and event maps to actual backend logic
2. **No operator cabinet, CRM, or Portal integration** - these are explicitly absent from the product
3. **Single sequential runtime** - one local runtime node, no multiple LLM agents
4. **Exactly one clarification allowed** before handoff offer
5. **Ticket created only after explicit confirmation** or explicit human request
6. **AI does not run after user responds to specialist** - ticket reverts to NEW, next operator reply operates without AI
7. **Multiple valid endings** - CLOSED_POLICY, RESOLVED, OUT_OF_SCOPE (case remains OPEN)

### Participants

- **User** - submits questions, can request handoff, responds to specialist
- **AI support service** - runs policy check, retrieval, generation, answers
- **Human specialist** - receives handoff, provides replies, resolves cases

### Gateways and Transitions

All gateways have correct exits (no impossible transitions). Start and end events are properly defined. Message/user/service tasks correspond to the implementation.

## Outputs

- `.bpmn` file: `docs/process/d05.bpmn` - BPMN 2.0 XML model
- `docs/process/d05.svg` - readable SVG visualization of the process
- Brief process description above for defense

## Known simplifications

1. SVG visualization is hand-crafted and not generated from the .bpmn by automated tool
2. Some intermediate timing/technical details omitted for readability
3. The BPMN model uses scriptTasks with inline script calls to represent the actual Python logic

## Validation status

- BPMN XML validated with Python lxml - structure is well-formed
- Process has 1 start event, 6 end events, 23 tasks, 6 exclusive gateways
- All gateways have defined exits, no impossible transitions
- Start/event tasks map to actual implemented API functions

## Viewer/validator used

Python lxml validation (structure well-formed). No dedicated BPMN viewer available in environment; visual inspection of SVG performed manually.