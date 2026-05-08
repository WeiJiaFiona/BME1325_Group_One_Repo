# Week 9 HIS Substrate Runbook for Developer B

## Working root

All Week 9 implementation must use:

`/home/jiawei2022/BME1325/week9/week9_v1`

## What Developer A has already frozen

- Contract freeze document:
  - `docs/architecture/week9_his_contract_freeze_v1.md`
- Stable ID rules:
  - `patient_id = P-{8 hex}`
  - `encounter_id = E-{14 timestamp}-{4 hex}`
- External triage normalization:
  - `ctas_level = L1-L5`
  - `zone = red/orange/yellow/green/blue`
- Frozen route names:
  - `transfer`
  - `admissions`
  - `summary`
  - `timeline`

## HIS package entrypoints

- Schemas:
  - `app_core/his/schemas/`
- Storage boundary:
  - `app_core/his/storage/base.py`
- Storage factory:
  - `app_core/his/storage/__init__.py`
- Services:
  - `app_core/his/services/`
- Memory adapter expectation:
  - `app_core/his/adapters/memory_adapter.py`

## Current backend status

- `sqlite_dev` is a real local persistence backend for substrate tests and local integration smoke.
- `postgres` currently supports:
  - migration discovery
  - migration SQL loading
  - optional migration application when a driver is installed
  - shared `HisStorage` interface access through a compatibility delegate

## What Developer B should call

Use A-owned service entrypoints only. Do not write SQL directly from ED workflow code.

Main service modules:

- `patient_registry_service.py`
- `provider_registry_service.py`
- `department_registry_service.py`
- `encounter_service.py`
- `triage_service.py`
- `order_service.py`
- `lab_service.py`
- `imaging_service.py`
- `handoff_service.py`
- `document_registry_service.py`
- `event_registry_service.py`
- `audit_service.py`
- `outbox_service.py`

## Current migration set

Under `sql/postgres/`:

- `001_core_master_tables.sql`
- `002_encounter_tables.sql`
- `003_order_result_tables.sql`
- `004_document_event_tables.sql`
- `005_runtime_audit_tables.sql`
- `006_seed_dev_reference.sql`

## Local substrate tests

Run from `week9_v1`:

```bash
pytest -q tests_his
```

## Integration rules for B

- Do not invent a second schema tree.
- Do not bypass `app_core/his/services/*`.
- Do not guess new table names.
- If a needed field is missing, add it through A-owned schema/service first, then consume it from B-owned adapters/integration.
