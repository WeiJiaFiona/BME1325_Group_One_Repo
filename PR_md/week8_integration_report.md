# Week 8 Memory v1 — A/B Integration & Validation Report

Repo root:
- `/home/jiawei2022/BME1325/week8/merge`

Date:
- 2026-04-24

## 1) What Was Validated

### A-side substrate validation
Verified `app_core/memory/*` core components are present and functional:
- schema/taxonomy validation
- JSONL/JSON storage write/read
- bounded retrieval
- replay export (events + summaries + snapshots + audits)

### B-side user integration validation
Verified user-mode emits memory events via A-side `MemoryService` using:
- lazy getter (env-driven, test-monkeypatchable)
- stable `memory_encounter_id` for the entire user run
- summary updates at checkpoints
- handoff snapshot writes at requested/completed
- fail-open behavior (memory failures do not crash clinical flow)

### Ablation validation
Verified both runs execute:
- `MEMORY_V1_ENABLED=0` (memory disabled)
- `MEMORY_V1_ENABLED=1` (memory enabled)

## 2) Test Commands Used + Results

### Substrate tests
```bash
cd /home/jiawei2022/BME1325/week8/merge
pytest -q tests/backend/test_memory_schema.py \
         tests/backend/test_memory_storage.py \
         tests/backend/test_memory_service.py \
         tests/backend/test_memory_retrieval.py
```
Result: **12 passed**

### Week8 integration tests
```bash
cd /home/jiawei2022/BME1325/week8/merge
pytest -q tests_week8
```
Result: **9 passed, 1 skipped**
- skipped: auto-mode integration skeleton (intentionally deferred)

### User regression tests
```bash
cd /home/jiawei2022/BME1325/week8/merge
pytest -q tests_user
```
Result: **62 passed** (with warnings)

## 3) What Failed Initially And How It Was Fixed

1. Documentation/env mismatch
- Old docs referenced `MEMORY_ENABLED`.
- Unified to `MEMORY_V1_ENABLED` / `MEMORY_V1_ROOT`.

2. Service compatibility
- Added low-risk alias:
  - `MemoryService.upsert_current_summary = update_current_summary`

## 4) Artifacts Manually Inspected (Expected Paths)

With `MEMORY_V1_ENABLED=1` and a configured `MEMORY_V1_ROOT`, expected runtime artifacts:
- `events.jsonl`
- `audit.jsonl`
- `current/<mode>/<run_id>/<encounter_id>.json`
- `snapshots/<mode>/<run_id>/<encounter_id>/<snapshot_id>.json`

## 5) What Remains Deferred

- Auto-mode memory hooks beyond user-mode scope.
- Auto-mode import-path shim (only needed if we hook reverie backend to app_core.memory at runtime).
- Broad resource-bottleneck event bridging from reverie runtime logs.

## 6) Demo/Export Helper

A small helper script was added:
```bash
MEMORY_V1_ROOT=runtime_data/memory python scripts/export_memory_replay.py \
  --run_id <run_id> --mode user --encounter_id <memory_encounter_id> --out analysis/replay.json
```

## 7) Completion Status

For Week 8 Memory v1 (A+B combined):
- User-mode memory integration + validation: **complete**
- Auto-mode memory integration: **deferred by design**
