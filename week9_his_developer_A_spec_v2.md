# Week 9 ED-HIS v1 — Developer A Codex Plan Spec

## 0. Role Definition

You are **Developer A** for Week 9 ED-HIS v1.

Your job is **not** to rewrite ED business flow, and **not** to own user-mode agent interaction logic.
Your job is to build the **shared HIS substrate** that both the current ED workflow and Developer B’s integration layer can rely on.

Working root:

```text
/home/jiawei2022/BME1325/week8/merge
```

---

## 1. What you are building

You are building the **formal HIS infrastructure layer** that upgrades the existing Memory v1 into a SQL-backed ED-HIS.

You own:
- HIS schema
- SQL migrations
- storage backend
- service layer
- registries
- audit
- authorization scaffolding
- event outbox / publisher scaffolding

You do **not** own:
- user-mode conversation logic
- current doctor planner behavior
- current rule ownership
- front-end interaction flow
- Memory v1 hook placement in ED flow

Those belong to Developer B or to the existing system.

---

## 2. Must-read references

Read these before coding:

### Internal / uploaded materials
1. teacher contract v1.0
2. 卫建委 PDF
3. 医院信息化 PPT
4. `PR_md/week8_proposal.md`
5. `app_core/memory/*`

### Local reference repos
6. `/home/jiawei2022/BME1325/week8/reference/BME_1325_Group4_repo/system/backend/api/`
7. `/home/jiawei2022/BME1325/week8/reference/BME_1325_Group4_repo/system/backend/数据规范/`
8. `/home/jiawei2022/BME1325/week8/reference/openemr/API_README.md`
9. `/home/jiawei2022/BME1325/week8/reference/openhospital`

---


## 2.5 Minimal serial handoff to Developer B (must happen before B deep integration)

This Week 9 work is **not** fully zero-dependency parallel development.
It follows this rule:

> **Developer A first delivers the minimum HIS substrate and freezes the shared contract; only then should Developer B start deep integration.**

Before Developer B begins deep workflow integration, you must provide and freeze the following minimum set:

### A-minimum substrate gate

1. `app_core/his/schemas/*` initial versions
   - at least: `patient.py`, `encounter.py`, `triage.py`, `order.py`, `lab.py`, `imaging.py`, `handoff.py`, `audit.py`
2. `app_core/his/storage/base.py`
   - with stable storage/service interface expectations
3. importable service stubs under `app_core/his/services/*`
   - files must exist
   - public class/function names must exist
   - B must be able to import them safely
4. SQL initial migrations:
   - `sql/postgres/001_core_master_tables.sql`
   - `sql/postgres/002_encounter_tables.sql`
   - `sql/postgres/003_order_result_tables.sql`
5. Memory → HIS adapter input contract
   - even if B implements the adapter body later, you must freeze what the substrate expects for:
     - `MemoryItem`
     - `CurrentEncounterSummary`
     - `HandoffMemorySnapshot`
6. contract-critical field freeze
   - `patient_id`
   - `encounter_id`
   - CTAS / zone
   - external state mapping
   - transfer / admissions / summary / timeline route names
   - event envelope shape

### Additional requirement to reduce merge conflicts

Once B starts integration, do **not** casually rename:
- schema file names
- service file names
- public service methods
- SQL table names
- config variable names

If a change is unavoidable, add compatibility wrappers or aliases instead of hard renames.

### What B is allowed to do before your minimum gate is ready

Before you deliver the minimum gate, B should only do:
- test scaffolding
- mapping docs
- adapter placeholders
- smoke-test planning

B should **not** guess your schema or directly invent parallel services.

---

## 3. Primary responsibilities

## 3.1 Freeze and expose one shared HIS contract

Before deep implementation, you must freeze:
- patient / provider / department / encounter / triage / order / lab / imaging / handoff / document / audit schemas
- service method names
- SQL table names
- Memory → HIS adapter input expectations
- event outbox schema

Developer B will depend on these names. Do not change them casually after B starts integration.

## 3.2 Build HIS file structure

Create under:

```text
app_core/his/
```

with at least:

```text
app_core/his/
  __init__.py
  config.py
  schemas/
    patient.py
    provider.py
    department.py
    encounter.py
    triage.py
    order.py
    lab.py
    imaging.py
    handoff.py
    document.py
    audit.py
  services/
    patient_registry_service.py
    provider_registry_service.py
    department_registry_service.py
    encounter_service.py
    triage_service.py
    order_service.py
    lab_service.py
    imaging_service.py
    handoff_service.py
    document_registry_service.py
    event_registry_service.py
    audit_service.py
  storage/
    base.py
    postgres.py
    sqlite_dev.py
  exchange/
    outbox.py
    event_publisher.py
  auth/
    roles.py
    permissions.py
    access_control.py
    phi_redaction.py
  projections/
    encounter_state_projection.py
```

Also create:

```text
sql/postgres/
```

for migrations and seed scripts.

---

## 4. Implementation goals

## 4.1 PostgreSQL-first core

Main backend must be PostgreSQL-first.

Implement at least these table groups:

### Master registries
- `patients`
- `providers`
- `departments`
- `rooms`
- `beds`
- `terminology_dictionary`

### Encounter core
- `encounters`
- `triage_records`
- `vital_signs`
- `clinical_assessments`
- `diagnosis_records`
- `care_transitions`
- `admissions`
- `discharges`

### Orders and results
- `orders`
- `order_executions`
- `lab_requests`
- `lab_results`
- `imaging_requests`
- `imaging_results`

### Document / event registry
- `clinical_documents`
- `document_registry`
- `event_registry`
- `handoff_snapshots`

### Runtime / audit
- `memory_events`
- `current_encounter_summaries`
- `audit_logs`
- `outbox_events`
- `idempotency_keys`
- `replay_exports`

## 4.2 Service layer

All DB access must be mediated through service layer methods.

Provide stable service entrypoints for:
- patient registry
- encounter open/read/update
- triage create/read
- order create/read
- lab request/result create/read
- imaging request/result create/read
- handoff snapshot write/read
- current summary read
- event registry write/query
- audit append/query

Developer B must not bypass this layer.

## 4.3 Outbox + event publishing scaffold

Implement a simple transactional outbox pattern:
- write business change
- write `outbox_events`
- later publish to Redis / contract envelope

Do not fully solve hospital-wide bus in this phase, but do provide the schema and publishing scaffold.

## 4.4 Auth / audit scaffold

Implement minimum RBAC and audit structure:
- roles
- permissions
- access control helper
- audit record schema and append path
- PHI redaction helper scaffold

This can be minimal, but the structure must exist.

---

## 5. Exact references and what to borrow

## 5.1 Group4 repo

Read:
- `system/backend/api/README.md`
- `system/backend/api/app/`
- `system/backend/数据规范/数据类型.md`
- `system/backend/数据规范/数据库使用规范.md`
- `system/backend/测试数据库/`

Borrow:
- PostgreSQL-first storage discipline
- API/service boundary
- DB init and seed style
- schema documentation style
- admission/event oriented backend organization

Do not copy:
- ICU-specific APACHE semantics
- their exact business meaning

## 5.2 OpenEMR

Read:
- `API_README.md`
- `Documentation/api/`

Borrow:
- API professionalism
- docs-first service exposure
- environment-driven configuration

## 5.3 Hospital informatization PPT + standards PDF

Borrow:
- EMR-centered unified data center logic
- document registry / event registry / index / audit logic
- why registries are mandatory

These references justify your module decomposition.

---

## 6. What you must provide to Developer B

Developer B will integrate Memory v1 and the existing ED flow into your HIS substrate.

So before B starts deep wiring, you must provide:

1. stable schema modules
2. stable service method names
3. SQL table names frozen enough for adapter work
4. a clear way to write:
   - encounter timeline events
   - current summary projection
   - handoff snapshots
5. one config strategy for DB selection
6. one contract for `patient_id` / `encounter_id` / CTAS / zone / event envelope

### Specific requirement to reduce merge conflicts

Do **not** rename:
- schema file names
- service file names
- table names
- config variable names

once B begins integration.

If you need compatibility, add alias layers instead of renaming.

---

## 7. Testing owned by A

You must provide substrate-side tests at least under:

```text
tests_his/
```

with these files:
- `test_patient_registry.py`
- `test_encounter_service.py`
- `test_document_registry.py`
- `test_event_registry.py`
- `test_handoff_persistence.py`
- `test_storage_postgres.py`
- `test_storage_sqlite_dev.py`

### Minimum assertions
- schema objects validate
- PostgreSQL tables initialize
- SQLite dev backend can boot for local smoke
- patient / encounter create and read work
- handoff snapshot persists and reads back
- event registry accepts normalized events
- audit logs append correctly

---

## 8. Implementation phases

### Phase A1 — schema and config freeze
Deliver:
- `schemas/*`
- `config.py`
- `storage/base.py`

### Phase A2 — SQL tables and storage backends
Deliver:
- `sql/postgres/001_*.sql` to `006_*.sql`
- `storage/postgres.py`
- `storage/sqlite_dev.py`

### Phase A3 — service layer
Deliver:
- registry / encounter / triage / order / result / handoff / audit services

### Phase A4 — outbox and auth scaffolding
Deliver:
- `exchange/outbox.py`
- `exchange/event_publisher.py`
- `auth/*`

### Phase A5 — tests and docs
Deliver:
- `tests_his/*`
- short runbook for B

---

## 9. Done criteria for A

A is done only if:
- one shared HIS schema exists
- PostgreSQL-first substrate boots
- SQLite dev backend exists for local smoke
- service layer is stable enough for B adapters
- handoff / summary / event registry persistence exists
- substrate tests pass
- B can integrate without inventing a second schema or storage path
