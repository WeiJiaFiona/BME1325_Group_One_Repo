# Auto Mode Memory Hooks Design

## Summary

This document defines a system-level design for extending Week 8 Memory v1 into Auto Mode without changing the existing User Mode Memory behavior. The implementation target is a fail-open, auditable, incrementally extensible hook layer that records a minimum safe set of Auto Mode events into Memory v1.

The initial priority is to support `boarding_timeout` as the first production hook. After that, the same mechanism should expand to `encounter_spawned`, `resource_bottleneck`, and `encounter_closed`, then later to `disposition_decided`, `handoff_requested`, and `handoff_completed`.

## Current State

- Memory v1 infrastructure already exists under [app_core/memory](./app_core/memory).
- The supported entrypoint is [service.py](./app_core/memory/service.py), which exposes:
  - `append_event(...)`
  - `update_current_summary(...)`
  - `get_current_summary(...)`
  - `write_handoff_snapshot(...)`
  - `retrieve(...)`
  - `export_replay(...)`
  - `append_audit(...)`
- Auto Mode runtime currently lives in:
  - [reverie/backend_server/reverie.py](./reverie/backend_server/reverie.py)
  - [reverie/backend_server/persona/persona_types/patient.py](./reverie/backend_server/persona/persona_types/patient.py)
- User Mode already has structured memory continuity logic in:
  - [app_core/app/api_v1.py](./app_core/app/api_v1.py)
- Auto Mode does not yet write Memory v1 events, summaries, or audit records.

## Design Goals

1. Add Memory v1 support to Auto Mode using only the shared `app_core/memory` substrate.
2. Keep the first implementation small and safe.
3. Guarantee fail-open behavior so simulation progress never depends on memory writes.
4. Produce auditable event records with run/encounter/patient/step/sim-time identity.
5. Avoid coupling Auto Mode hooks to User Mode session or `shared_memory`.

## Hook Priority

### P0: Minimum Safe Hook

- `boarding_timeout`

### P1: Core Flow Hooks

- `encounter_spawned`
- `resource_bottleneck`
- `encounter_closed`

### P2: Expansion Hooks

- `disposition_decided`
- `handoff_requested`
- `handoff_completed`

Future cross-mode alignment may also add a semantic bridge for `next_slot`, but that should remain out of the minimum Auto Mode rollout.

## Runtime Integration Model

### Integration Style

Use explicit helper calls plus a lightweight Auto Hook Manager inside Auto Mode. Do not introduce a general event bus or observer framework.

### Proposed Auto Hook Manager Responsibilities

The manager should be created during Auto Mode backend startup and own:

- one `MemoryService` instance
- one Auto Mode `run_id`
- a safe write wrapper
- helper methods for event recording, summary update, and audit

Suggested placement:

- initialize in [reverie/backend_server/reverie.py](./reverie/backend_server/reverie.py)
- rely on helper builders from [app_core/memory/hooks.py](./app_core/memory/hooks.py)

### Required Identity Rules

Use the existing frozen conventions:

- `run_id = auto_<sim_code>_<timestamp>`
- `patient_id = safe_patient_name`
- `encounter_id = auto_<run_id>_<safe_patient_name>`
- `mode = "auto"`

The following existing helpers should be reused rather than redefined:

- `generate_auto_run_id(...)`
- `build_memory_event(...)`
- `next_memory_step(...)`

## Trigger Points

### 1. `encounter_spawned`

Suggested write point:

- after a new patient is fully created and inserted into triage or waiting flow

Likely code path:

- [reverie/backend_server/reverie.py](./reverie/backend_server/reverie.py)
  - new patient generation in the runtime loop
  - startup preloading helpers

Payload should include:

- patient identity
- CTAS
- initial zone
- source (`startup_fill`, `preload_waiting_room`, or `runtime_arrival`)

### 2. `resource_bottleneck`

Suggested write point:

- when queue pressure or occupancy exceeds a configured threshold

Likely sources:

- doctor global queue
- bedside nurse waiting queue
- full diagnostic/imaging/lab capacity
- zero available doctors for new assignment

Likely code path:

- [reverie/backend_server/reverie.py](./reverie/backend_server/reverie.py)
  - queue aggregation and status snapshot code

Payload should include:

- resource type
- queue length
- capacity
- blocking context

### 3. `boarding_timeout`

Suggested write point:

- the first moment the timeout condition becomes true

Likely code path:

- [reverie/backend_server/persona/persona_types/patient.py](./reverie/backend_server/persona/persona_types/patient.py)
  - existing `boarding_timeout_recorded` and `boarding_timeout_at` logic

Payload should include:

- timeout timestamp
- threshold minutes
- patient state
- disposition/boarding context if available

### 4. `encounter_closed`

Suggested write point:

- when the patient is discharged, leaves ED, or otherwise exits the simulated encounter

Likely code path:

- [reverie/backend_server/reverie.py](./reverie/backend_server/reverie.py)
  - leaving patients cleanup / export logic

Payload should include:

- final state
- close reason
- zone at closure
- elapsed step count if available

## Memory Write Contract

All Auto Mode writes must go through [app_core/memory/service.py](./app_core/memory/service.py).

### Required Calls

- `append_event(...)`
- `update_current_summary(...)`
- `append_audit(...)`

### Optional Calls

- `write_handoff_snapshot(...)` only when Auto Mode later gains explicit handoff event support
- `export_replay(...)` for future replay CLI and analysis workflows

### Required Event Fields

Every Auto Mode memory event should include:

- `run_id`
- `mode`
- `encounter_id`
- `patient_id`
- `step`
- `sim_time`
- `event_type`
- `payload`

### Current Summary Shape

Auto summaries should at minimum maintain:

- current patient state
- current zone or area
- queue context
- latest bottleneck note
- latest timeout note
- closure/disposition status

The summary remains a derived view and must not become the source of truth.

## Fail-open and Error Handling

Auto Memory Hooks must never block simulation.

### Required Behavior

- any memory exception is caught locally
- simulation step continues
- runtime log records the failure
- audit attempts to record `failed` or `skipped`

### Suggested Wrapper

Use a single `safe_memory_write(...)` layer inside the Auto Hook Manager that:

- executes the memory service call
- catches all exceptions
- returns a structured internal result such as:
  - `{"ok": True}`
  - `{"ok": False, "reason": "..."}`

### Disabled Mode

When `MEMORY_V1_ENABLED=0`:

- manager becomes no-op
- no hook should alter simulation flow
- replay/export remains empty or skipped

## Audit and Logging

Audit records should capture:

- write attempt timestamp
- event type
- run/encounter/patient identifiers
- simulation step
- success / failed / skipped
- short error message when present

In addition to audit, runtime logging in Auto Mode should include:

- hook trigger name
- patient name
- step
- sim time
- whether memory write succeeded

This provides both durable audit output and human-readable runtime traceability.

## Extensibility Strategy

The Auto Hook Manager should not encode event-specific storage rules directly in multiple places. Instead:

- build payloads per event
- convert them to Memory v1 records through shared helper functions
- keep all service calls centralized

This allows later addition of:

- `disposition_decided`
- `handoff_requested`
- `handoff_completed`
- replay export CLI
- richer queue/resource events

without changing the substrate interface.

## Testing Strategy

### Unit Tests

- `build_memory_event(...)` generates valid `MemoryItem` for Auto payloads
- Auto `run_id` and `encounter_id` generation is stable
- `append_event(...)`, `retrieve(...)`, `update_current_summary(...)` behave correctly for Auto records

### Integration Tests

- short Auto sim run that triggers `boarding_timeout`
- verify:
  - `events.jsonl` contains the event
  - `audit.jsonl` records the write
  - `current/auto/<run_id>/...` updates correctly

### Stress / Fail-open Tests

- trigger multiple hook writes in quick succession
- inject `MemoryService` failure or storage exception
- verify simulation continues and audit/runtime logs mark failure

### Regression Tests

- existing User Mode Memory tests still pass
- `MEMORY_V1_ENABLED=0` keeps both User Mode and Auto Mode behavior stable
- Auto `run 20` still succeeds after hook integration

## Recommended Rollout Order

1. Wire `run_id` creation and Auto Hook Manager initialization.
2. Implement `boarding_timeout` hook only.
3. Add audit and current summary updates for timeout.
4. Add `encounter_spawned`.
5. Add `resource_bottleneck`.
6. Add `encounter_closed`.
7. Add tests and replay/export follow-up support.

## Expected Outcome

After the minimum rollout:

- Auto Mode will write at least one high-value safety-relevant event (`boarding_timeout`) into Memory v1.
- The system will remain fail-open.
- Audit visibility will exist for Auto writes.
- The architecture will be ready for later disposition, handoff, and replay expansion without requiring a new storage path or a second schema.
