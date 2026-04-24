# Developer A Memory Contract-Freeze Delivery Note

This document is a handoff-oriented explanation of the **Developer A** delivery for Week 8 Memory v1.

It does **not** describe new business integration into `api_v1.py`, `reverie.py`, or `patient.py`.
It only describes the already implemented **shared memory substrate** under `app_core/memory/`, so **Developer B** can begin integration without creating a second schema or storage path.

## 1. Delivery Scope

Developer A has implemented a **minimal contract-freeze substrate** under:

```text
week8/app_core/memory/
```

The implementation is designed to satisfy these goals:

1. All core memory dataclasses/interfaces are importable.
2. A single shared storage path and schema are frozen.
3. The service entrypoint is stable and callable.
4. The backend is fail-open when memory is disabled.
5. Helper functions for run IDs and step tracking are available to Developer B.

This delivery is intentionally **parallel** to the old persona memory system:

* it does **not** replace `scratch`
* it does **not** write back to old `associative_memory`
* it does **not** read `spatial_memory`
* it does **not** add embedding retrieval

That means the old auto agent behavior remains intact, while Week 8 Memory v1 becomes a separate ED event substrate.

---

## 2. File Map

Implemented files:

```text
week8/app_core/memory/__init__.py
week8/app_core/memory/config.py
week8/app_core/memory/taxonomy.py
week8/app_core/memory/schema.py
week8/app_core/memory/storage.py
week8/app_core/memory/episode_memory.py
week8/app_core/memory/current_memory.py
week8/app_core/memory/handoff_memory.py
week8/app_core/memory/retrieval.py
week8/app_core/memory/replay_buffer.py
week8/app_core/memory/audit.py
week8/app_core/memory/hooks.py
week8/app_core/memory/service.py
```

Validation tests:

```text
week8/tests/backend/test_memory_schema.py
week8/tests/backend/test_memory_storage.py
week8/tests/backend/test_memory_retrieval.py
week8/tests/backend/test_memory_service.py
```

---

## 3. Detailed Delivery by Requirement

### 3.1 `schema.py`

Path:

```text
week8/app_core/memory/schema.py
```

Developer A implemented the following frozen schema/dataclass layer:

* `MemoryItem`
* `CurrentEncounterSummary`
* `HandoffMemorySnapshot`
* `MemoryQuery`
* `AuditRecord`

### What this file does

`schema.py` is the **single source of truth for the Week 8 Memory v1 data contract**.
It validates:

* required IDs such as `run_id`, `encounter_id`, `patient_id`
* `mode` values (`auto` / `user`)
* allowed `event_type`
* bounded retrieval fields such as `top_k`
* shape of summary/snapshot payload objects

### Why this matters for Developer B

Developer B can now:

* import one canonical schema
* build hook payloads against one stable contract
* avoid inventing a second `MemoryItem` or summary format inside user/auto runtime code

### Important implementation note

The naming freeze is respected as:

* `CurrentEncounterMemory` = runtime module/class behavior
* `CurrentEncounterSummary` = schema/dataclass object

This follows the proposal principle that the summary is a **derived view**, not the raw source of truth.

---

### 3.2 `taxonomy.py`

Path:

```text
week8/app_core/memory/taxonomy.py
```

Developer A froze the minimum event taxonomy and checkpoint names in one place.

### Delivered contents

The file defines:

* `EVENT_TYPES`
* `CHECKPOINTS`
* `MODES`

### Minimum event taxonomy included

* `encounter_started`
* `calling_nurse_called`
* `vitals_measured`
* `triage_started`
* `triage_completed`
* `doctor_assessment_started`
* `doctor_assessment_checkpoint`
* `test_ordered`
* `test_result_ready`
* `handoff_requested`
* `handoff_completed`
* `disposition_decided`
* `boarding_started`
* `boarding_timeout`
* `patient_deterioration`
* `resource_bottleneck`
* `encounter_closed`

### Why this matters for Developer B

Developer B can import the same taxonomy constants when wiring hooks into:

* `api_v1.py`
* `reverie.py`
* `patient.py`

This prevents user mode and auto mode from drifting into different event names.

---

### 3.3 `service.py`

Path:

```text
week8/app_core/memory/service.py
```

Developer A implemented the main stable service entrypoint:

* `MemoryService`
* `create_memory_service(...)`

### Delivered callable methods

Implemented on `MemoryService`:

* `append_event(...)`
* `get_current_summary(...)`
* `write_handoff_snapshot(...)`
* `retrieve(...)`
* `export_replay(...)`
* `append_audit(...)`

Also implemented:

* `update_current_summary(...)`

### Naming note

The original freeze request asked for:

* `upsert_current_summary(...)`

The actual public service method currently exposed is:

* `update_current_summary(...)`

Internally this still performs an **upsert** through storage/current-memory behavior.
So functionally the requirement is met, but the **service-layer method name differs**.

If Developer B wants to call the service today, the correct method is:

```python
memory_service.update_current_summary(...)
```

### Why this matters for Developer B

Developer B should treat `service.py` as the **only allowed entrypoint** into Memory v1, instead of touching JSON files or file paths directly.

---

### 3.4 `config.py`

Path:

```text
week8/app_core/memory/config.py
```

Developer A implemented configuration helpers for:

* memory enable/disable policy
* runtime data root path

### Delivered behavior

Implemented:

* `memory_v1_enabled()`
* `get_runtime_root()`
* `DEFAULT_RUNTIME_ROOT`

Default runtime root:

```text
week8/runtime_data/memory/
```

### Policy behavior

* If `MEMORY_V1_ENABLED` is unset, memory defaults to enabled.
* If `MEMORY_V1_ROOT` is unset, runtime data defaults to `week8/runtime_data/memory/`.
* Mode isolation is enforced at the schema/storage level using:
  * `run_id`
  * `mode`
  * `encounter_id`

### Naming note

The original freeze request asked for:

* `MEMORY_V1_ENABLED` (master switch, default ON)

The current implementation exposes:

* environment variable `MEMORY_V1_ENABLED`
* function `memory_v1_enabled()`

So the requirement is satisfied behaviorally, but implemented as a **function-based config helper**, not as a plain module constant.

---

### 3.5 Fail-open backend

Paths:

```text
week8/app_core/memory/storage.py
week8/app_core/memory/service.py
```

Developer A implemented a fail-open backend through:

* `NullMemoryStorage`

and the service factory:

* `create_memory_service(...)`

### Delivered behavior

When memory is disabled:

* no runtime data directory is created
* `append_event(...)` returns `None`
* `retrieve(...)` returns `[]`
* replay export returns an empty structured payload

### Naming note

The original request allowed:

* `NullMemoryService` or `InMemoryMemoryService`

The current implementation uses:

* `NullMemoryStorage`

paired with:

* `MemoryService(enabled=False)`

This still satisfies the fail-open requirement, but the no-op behavior is implemented at the **storage layer**, not as a separate `NullMemoryService` class.

---

### 3.6 Helper functions

Path:

```text
week8/app_core/memory/hooks.py
```

Developer A implemented the requested helper layer.

### Delivered helper functions

Implemented:

* `generate_user_run_id(...)`
* `generate_auto_run_id(...)`
* `next_memory_step(...)`

Also added:

* `generate_auto_encounter_id(...)`
* `build_memory_event(...)`
* `build_handoff_snapshot_id(...)`
* `build_audit_record(...)`

### Why this matters for Developer B

Developer B can now reuse the shared helper functions for:

* deterministic run ID generation
* auto encounter ID generation
* step sequencing
* event object construction
* audit object construction

without creating mode-specific local helper logic.

---

## 4. Storage Strategy Actually Implemented

Primary storage implementation lives in:

```text
week8/app_core/memory/storage.py
```

Implemented storage backend:

* `JsonFileMemoryStorage`

### Actual runtime file layout

Append-only events:

```text
week8/runtime_data/memory/events.jsonl
```

Audit log:

```text
week8/runtime_data/memory/audit.jsonl
```

Current summary:

```text
week8/runtime_data/memory/current/<mode>/<run_id>/<encounter_id>.json
```

Handoff snapshots:

```text
week8/runtime_data/memory/snapshots/<mode>/<run_id>/<encounter_id>/<snapshot_id>.json
```

### Implemented storage interface

The storage abstraction includes:

* `append_event(...)`
* `upsert_current_summary(...)`
* `get_current_summary(...)`
* `write_snapshot(...)`
* `retrieve(...)`
* `append_audit(...)`

So the **storage contract** requested by the freeze note is already present.

---

## 5. Replay and Audit Delivery

Paths:

```text
week8/app_core/memory/replay_buffer.py
week8/app_core/memory/audit.py
```

### Replay

Developer A implemented:

* `ExperienceReplayBuffer`

with export support for:

* raw events
* summaries
* snapshots
* audits

### Audit

Developer A implemented:

* `AuditTrail`
* `AuditRecord`

This gives Developer B a stable place to append memory write/retrieve audits during integration.

---

## 6. Relationship to the Original Request

The request said Developer A must first provide a minimal contract-freeze implementation under `app_core/memory/`.

That requirement is now met in substance:

1. `schema.py` is implemented.
2. `taxonomy.py` is implemented.
3. `service.py` is implemented and importable.
4. `config.py` is implemented.
5. a fail-open backend is implemented.
6. helper functions are implemented.

### The only important naming differences to note

1. Requested:

   * `upsert_current_summary(...)`
     Actual public service method:
   * `update_current_summary(...)`
2. Requested:

   * `MEMORY_V1_ENABLED`
     Actual config interface:
   * `MEMORY_V1_ENABLED` + `memory_v1_enabled()`
3. Requested:

   * `NullMemoryService` or `InMemoryMemoryService`
     Actual no-op backend:
   * `NullMemoryStorage` + disabled `MemoryService`

These are **interface wording differences**, not missing functionality.

---

## 7. What Developer B Can Safely Do Next

Developer B can now:

1. import schema/dataclasses from:

```text
week8/app_core/memory/schema.py
```

2. import taxonomy names from:

```text
week8/app_core/memory/taxonomy.py
```

3. instantiate the service through:

```python
from app_core.memory.service import create_memory_service
```

4. call helper functions from:

```text
week8/app_core/memory/hooks.py
```

5. begin wiring user-mode and auto-mode hooks without inventing:

* a second schema
* a second storage root
* a second retrieval contract

---

## 8. Validation Evidence

The following tests were added to validate the A-side substrate:

```text
week8/tests/backend/test_memory_schema.py
week8/tests/backend/test_memory_storage.py
week8/tests/backend/test_memory_retrieval.py
week8/tests/backend/test_memory_service.py
```

They verify:

* schema validation
* stable auto/user ID generation
* JSON storage write/read behavior
* bounded retrieval behavior
* fail-open behavior when memory is disabled
* replay export shape

---

## 9. Final Summary

Developer A has already delivered a **minimal, importable, stable, callable memory substrate** under:

```text
week8/app_core/memory/
```

This delivery is sufficient for Developer B to start integration and testing **without creating a second schema or storage path**.

The main thing B must remember is:

* use `service.py` as the entrypoint
* use `schema.py` as the canonical contract
* use `hooks.py` helper functions for IDs and event construction
* note that the current public method name is `update_current_summary(...)`, not `upsert_current_summary(...)`
