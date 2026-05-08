# Week 9 ED-HIS v1 — A/B Merge Protocol and Conflict-Reduction Rules

## 0. Purpose

This document defines how Developer A and Developer B should work in parallel and later merge their work with minimal conflict.

Working root:

```text
/home/jiawei2022/BME1325/week8/merge
```

---


## 0.5 Minimal-serial then parallel rule

This project should **not** be described as fully zero-dependency parallel development.
The correct execution model is:

> **A first provides the minimum HIS substrate and freezes the contract; B then begins deep integration; after that, both sides proceed in parallel.**

### Minimum gate that A must deliver before B deep integration

A must first provide:
1. initial `app_core/his/schemas/*`
2. `app_core/his/storage/base.py`
3. importable service stubs under `app_core/his/services/*`
4. `sql/postgres/001_core_master_tables.sql`
5. `sql/postgres/002_encounter_tables.sql`
6. `sql/postgres/003_order_result_tables.sql`
7. frozen Memory → HIS mapping expectations
8. frozen contract-critical route and ID naming

### What B may do before this gate is ready

Before the above gate is ready, B may only do:
- adapter placeholders
- tests scaffolding
- contract mapping docs
- smoke-test planning

B must not perform deep workflow integration against guessed schema/service names.

---

## 1. Shared principle

There must be **one ED-HIS schema**, **one service layer**, and **one contract interpretation**.

A and B may work on different parts of the system, but must not create:
- two schema trees
- two SQL table naming systems
- two competing service entrypoint sets
- two incompatible event / contract adapters

---

## 2. Ownership split

## 2.1 Developer A owns

- `app_core/his/schemas/*`
- `app_core/his/storage/*`
- `app_core/his/services/*`
- `app_core/his/auth/*`
- `app_core/his/exchange/outbox.py`
- `app_core/his/config.py`
- `sql/postgres/*`
- substrate-side tests

## 2.2 Developer B owns

- `app_core/his/adapters/*`
- ED-flow integration that calls A’s services
- timeline export helpers
- contract alignment tests
- memory-upgrade tests
- golden-path smoke tests

## 2.3 Shared but edit-with-care

- `app_core/app/api_v1.py`
- `scripts/*`
- `tests_his/*`

If both must edit the same shared file, prefer:
- A adds extension points
- B consumes extension points

instead of both editing the same internal block.

---

## 3. Contracts that must be frozen before deep merge

The following items must be frozen before both sides go deep into implementation:

1. patient schema fields
2. encounter schema fields
3. triage schema fields
4. handoff snapshot fields
5. current summary fields
6. service method names
7. SQL table names
8. contract mapping for:
   - patient_id
   - encounter_id
   - CTAS
   - zone
   - external states
9. event envelope shape

If any of these change later, the owner must provide a compatibility layer.

---

## 4. Naming and compatibility rules

## 4.1 No breaking renames after freeze

After freeze:
- do not rename files
- do not rename public methods
- do not rename SQL tables
- do not rename config variables

If change is unavoidable:
- add alias / wrapper
- deprecate gradually
- update both docs and tests

## 4.2 IDs are single source of truth

Both A and B must use the same formats:
- `patient_id = P-{8 hex}`
- `encounter_id = E-{14 timestamp}-{4 hex}`

No local alternative format is allowed.

## 4.3 External triage is CTAS only

Internal representations may exist, but all external / cross-group / HIS-facing representations must normalize to:
- CTAS L1–L5
- derived `zone`

---

## 5. Branching and file-discipline rules

Recommended branches:
- A: `week9-his-substrate`
- B: `week9-his-integration`

Before merging to shared branch:
1. sync with latest `week8/merge`
2. re-run all owned tests
3. re-run shared smoke tests
4. do not merge broken migration scripts

Do not copy code from reference repos into production directories.
Reference repos must remain under:

```text
/home/jiawei2022/BME1325/week8/reference/
```

---

## 6. Merge checkpoints

## Checkpoint 1 — Contract Freeze
Must exist before B starts deep integration and before A/B begin parallel deep work:
- schema stubs
- service stubs
- table names
- contract mapping doc
- SQL initial migrations (001~003)
- Memory → HIS mapping expectations

## Checkpoint 2 — Substrate Ready
A provides:
- SQL init
- storage backends
- service layer
- auth/audit scaffold

B verifies:
- adapters can compile against A’s services

## Checkpoint 3 — Integration Ready
B provides:
- memory adapter
- contract adapter
- ED write-path integration
- timeline export

A verifies:
- no schema bypass
- no direct DB writes from ED business code

## Checkpoint 4 — Final Merge
Both sides run:
- substrate tests
- integration tests
- contract smoke
- STEMI smoke

Only then merge.

---

## 7. Shared test matrix before final merge

Both A and B must agree to run all of the following before final merge:

### A-side required
- storage boot tests
- patient/encounter service tests
- handoff persistence tests
- audit tests

### B-side required
- memory upgrade path tests
- contract alignment tests
- user ED ↔ HIS integration tests
- handoff connectivity tests
- timeline export tests
- STEMI golden-path smoke test

### Shared required
- one PostgreSQL boot + migration smoke
- one SQLite dev smoke
- one transfer/admission API smoke

---

## 8. Conflict-reduction rules for code editing

### Rule 1
A should expose extension points instead of editing B-owned integration logic.

### Rule 2
B should implement translation/adaptation in adapter files instead of editing A-owned schema/storage internals.

### Rule 3
If both need the same new field, the field must first be added to A-owned schema/service, then consumed by B.

### Rule 4
No silent schema drift.
Any new field added by either side must be documented in:
- schema doc
- migration
- test

### Rule 5
No direct SQL in business-flow files unless explicitly agreed.
Service layer remains the official boundary.

---

## 9. Minimal final deliverable definition

The final merged ED-HIS v1 is accepted only if:

1. PostgreSQL-backed HIS substrate exists
2. Memory v1 is upgraded into formal HIS persistence
3. teacher contract v1.0 is respected
4. transfer/admission/timeline/summary routes exist
5. handoff snapshot is persisted and queryable
6. timeline export is demo-ready
7. A/B code merges without duplicate schema or service systems

---

## 10. Final merge command discipline

Before merging branches, both developers should:

```bash
git fetch origin
git rebase origin/<shared-base-branch>
pytest -q tests_his
```

Then one final integration branch should run:

```bash
pytest -q tests_his
pytest -q tests/backend
pytest -q tests_week8
```

Only after all required tests pass should the work merge into the shared branch.
