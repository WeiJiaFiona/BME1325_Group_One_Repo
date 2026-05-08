# Week 9 ED-HIS v1 — Developer B Codex Plan Spec

## 0. Role Definition

You are **Developer B** for Week 9 ED-HIS v1.

Your main task is **integration and validation**, not raw SQL substrate construction.

Working root:

```text
/home/jiawei2022/BME1325/week8/merge
```

You are responsible for upgrading the already-implemented **Memory v1** and the current **ED workflow** into the new HIS substrate built by Developer A.

---

## 1. What you own

You own:
- Memory v1 → HIS upgrade adapter
- current ED flow ↔ HIS service integration
- user-mode HIS write path
- contract alignment checks
- encounter timeline export
- summary / handoff connectivity validation
- smoke tests and golden-path validation

You do **not** own:
- PostgreSQL schema design as the source of truth
- table naming decisions after A freezes them
- service layer business ownership
- planner ownership / next_slot / safety floor / disposition logic

---

## 2. Must-read references

Read these before coding:

1. `app_core/memory/*`
2. `app_core/app/api_v1.py`
3. Developer A HIS spec
4. teacher contract v1.0
5. `PR_md/week8_proposal.md`
6. `审查报告.html`
7. `scripts/export_memory_replay.py` if present
8. Group4 repo backend docs

Your job is to understand both:
- the old Memory v1 shape
- the new HIS substrate that A exposes

---


## 2.5 Minimal serial dependency on Developer A (must be respected)

This work is **not** fully zero-dependency parallel development.
It follows this rule:

> **Developer B should not start deep HIS integration until Developer A has delivered the minimum HIS substrate and frozen the shared contract.**

### Do not start deep integration until A provides all of the following

1. initial `app_core/his/schemas/*`
   - at least: `patient.py`, `encounter.py`, `triage.py`, `order.py`, `lab.py`, `imaging.py`, `handoff.py`, `audit.py`
2. `app_core/his/storage/base.py`
3. importable service stubs in `app_core/his/services/*`
4. SQL initial migrations:
   - `sql/postgres/001_core_master_tables.sql`
   - `sql/postgres/002_encounter_tables.sql`
   - `sql/postgres/003_order_result_tables.sql`
5. frozen Memory → HIS substrate expectations
6. frozen contract-critical names:
   - `patient_id`
   - `encounter_id`
   - CTAS / zone
   - event envelope
   - transfer / admissions / summary / timeline route names

### What you may do before A finishes the minimum gate

Before A finishes the above minimum gate, you may still work on:
- `tests_his/` scaffolding
- field-mapping documents
- adapter placeholder files
- contract smoke design
- STEMI golden-path script planning
- replay/timeline export design

But you must **not**:
- invent a second schema
- guess SQL table names and hardcode them into integration files
- invent service names that A has not frozen yet
- write direct DB logic in ED workflow files

### What you should do immediately after A finishes the minimum gate

Once A finishes the minimum gate, you should begin in this order:
1. `memory_adapter.py` and `contract_adapter.py`
2. ED workflow → HIS service write path
3. summary / handoff / timeline integration
4. contract smoke tests
5. STEMI golden-path smoke

This sequencing is required to keep final merge smooth.

---

## 3. Primary responsibilities

## 3.1 Build the Memory → HIS upgrade path

Create:

```text
app_core/his/adapters/
  memory_adapter.py
  contract_adapter.py
```

### `memory_adapter.py`
Must map existing Memory v1 artifacts into formal HIS persistence targets.

At minimum, upgrade:
- `MemoryItem` → `memory_events` / `event_registry`
- `CurrentEncounterSummary` → `current_encounter_summaries`
- `HandoffMemorySnapshot` → `handoff_snapshots` / `clinical_documents`
- replay export → `replay_exports` and timeline exporter

### `contract_adapter.py`
Must map current ED internal fields to teacher contract external fields:
- patient_id
- encounter_id
- CTAS / zone
- external state dictionary
- event envelope
- API payload shape

## 3.2 Integrate current ED flow with A’s HIS service layer

Use only A’s HIS service entrypoints.

Do not:
- write SQL directly from `api_v1.py`
- invent another DB model
- bypass service layer

### Required integration targets
At minimum wire these ED checkpoints into HIS:
- patient registration / lookup
- encounter open
- triage persistence
- vital sign persistence
- doctor checkpoint persistence
- handoff requested / completed persistence
- transfer / admission persistence
- encounter close
- summary query
- timeline export

## 3.3 Keep old Memory v1 useful

Do not remove Memory v1.

Instead:
- preserve current memory hooks
- preserve current user continuity behavior
- make HIS persistence a formalized downstream layer

Meaning:
- current Memory v1 stays as the encounter timeline substrate
- HIS becomes the official queryable/persistent layer

## 3.4 Contract smoke and golden-path validation

Build a real validation path for:
- contract alignment
- transfer / admission API shape
- timeline export
- STEMI-like ED path

---

## 4. Exact references and what to borrow

## 4.1 From current repo

### Existing Memory v1
Read:
- `app_core/memory/schema.py`
- `app_core/memory/service.py`
- `app_core/memory/hooks.py`
- `app_core/memory/replay_buffer.py`

Borrow:
- current event model
- current summary model
- handoff snapshot format
- replay structure

### Existing ED flow
Read:
- `app_core/app/api_v1.py`

Borrow:
- where ED checkpoints happen
- where existing memory is already updated
- how current user flow behaves

## 4.2 From Group4 repo

Read:
- `system/backend/api/README.md`
- `system/backend/数据规范/前端输入数据协议.md`
- `system/backend/数据规范/数据库使用规范.md`
- `system/backend/数据规范/数据类型.md`

Borrow:
- API boundary discipline
- DB usage discipline
- data contract writing style

## 4.3 From contract v1.0

Borrow and enforce:
- exact ID format
- exact state/triage rules
- exact event envelope rules
- exact transfer/admission route requirements

---

## 5. What you need from Developer A

Do not start deep integration until A provides:

1. frozen schema modules
2. frozen service method names
3. stable config names
4. table names frozen enough for adapter work
5. a clear way to persist:
   - memory events
   - current summary projection
   - handoff snapshots
   - event registry
   - audit logs

### How A should reduce your merge conflicts

A must avoid renaming files, methods, or config keys after you start.
If A needs a change, prefer:
- alias methods
- backwards-compatible wrappers

instead of hard renames.

---

## 6. What A needs from you

To reduce final merge conflict, you must:

1. keep all ED-flow integration logic under adapters and service calls
2. avoid editing A-owned schema and storage files unless absolutely necessary
3. put all translation logic into:
   - `memory_adapter.py`
   - `contract_adapter.py`
4. keep tests under `tests_his/` and not mixed into A-only substrate tests
5. document every field mapping you introduce

If you need a new field in A’s schema, request it explicitly instead of silently editing A’s files.

---

## 7. Implementation goals

## 7.1 HIS write-path integration for user-mode

At minimum, after A’s service layer exists, wire these into HIS:
- encounter open
- triage create
- vital sign append
- doctor checkpoint summary persistence
- handoff requested / completed persistence
- transfer / admission write
- encounter close

## 7.2 Timeline / replay alignment

Implement a clean timeline export path that combines:
- memory events
- summaries
- handoff snapshots
- key HIS records

for one encounter.

This should be usable for:
- classroom demo
- QA
- future similar-case retrieval

## 7.3 Contract alignment

Build explicit validation that current ED outputs comply with:
- external IDs
- CTAS
- zone derivation
- state dictionary
- event envelope
- `/api/v1/` payloads

## 7.4 Golden path

Use STEMI as the first integrated path.

At minimum, verify:
- patient enters ED
- triage stored
- vitals stored
- doctor assessment stored
- order / result placeholders created or mapped
- transfer / admission route works
- timeline export works

---

## 8. Testing owned by B

Create under:

```text
tests_his/
```

at least:
- `test_memory_upgrade_path.py`
- `test_contract_alignment.py`
- `test_his_user_flow_integration.py`
- `test_handoff_summary_connectivity.py`
- `test_timeline_export.py`
- `test_stemi_golden_path_smoke.py`

### Minimum assertions
- existing Memory v1 artifacts can be persisted into HIS tables
- no second schema is created
- contract IDs are correct
- CTAS / zone output is correct
- handoff data is queryable from HIS layer
- timeline export includes events + summaries + snapshots
- user ED flow still runs without planner ownership changes

If you still keep memory ON/OFF testing, ensure it remains compatible with HIS write path.

---

## 9. Implementation phases

### Phase B1 — adapter scaffolding
Deliver:
- `memory_adapter.py`
- `contract_adapter.py`

### Phase B2 — user ED ↔ HIS integration
Deliver:
- write-path integration to A’s services
- handoff persistence bridge
- summary persistence bridge

### Phase B3 — validation and export
Deliver:
- timeline export
- contract smoke
- STEMI smoke

### Phase B4 — documentation
Deliver:
- field mapping note
- runbook for tests

---

## 10. Done criteria for B

B is done only if:
- Memory v1 is systematically upgraded into HIS persistence
- current ED flow writes to A’s HIS layer through services only
- contract alignment tests pass
- handoff and timeline are queryable from HIS
- STEMI-like flow can be demonstrated on ED side
- B changes can merge into A’s substrate without major file conflicts
