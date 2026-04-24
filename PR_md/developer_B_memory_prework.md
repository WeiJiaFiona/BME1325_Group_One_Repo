# Week 8 Memory v1 — Developer B Prework (Integration + Evaluation)

Working root:
- `/home/jiawei2022/BME1325/week8/merge`

This doc defines what Developer B will implement **before** Developer A delivers the memory substrate. It also specifies the **exact A-side contracts** required to start deep integration.

## 0) Hard Boundaries
- Do **NOT** implement `app_core/memory` substrate yet.
- Do **NOT** invent a second memory schema or storage backend.
- Do **NOT** change doctor planner ownership.
- Do **NOT** change `next_slot` ownership.
- Do **NOT** change safety floor ownership.
- Do **NOT** change disposition ownership.
- Do **NOT** modify `EDSIM_MODE` mode boundaries.
- Do **NOT** add `tests_week8` into default `pytest.ini` yet.

## 1) A-Side Minimal Delivery (Contract Freeze) Required for Deep Integration

Before Developer B starts real hook integration in production code, Developer A must provide an importable, stable, fail-open skeleton under `app_core/memory/`.

### Required files and symbols

1. `app_core/memory/schema.py`
- `MemoryItem`
- `CurrentEncounterSummary`
- `HandoffMemorySnapshot`
- `MemoryQuery`

2. `app_core/memory/taxonomy.py`
- frozen event taxonomy names (strings / constants)

3. `app_core/memory/service.py`
- `append_event(...)`
- `upsert_current_summary(...)`
- `get_current_summary(...)`
- `write_handoff_snapshot(...)`
- `retrieve(...)`
- `export_replay(...)`
- `append_audit(...)`

4. `app_core/memory/config.py`
- `MEMORY_ENABLED` master switch
- `data/memory` path policy
- mode isolation policy (`run_id + mode + encounter_id + patient_id`)

5. Fail-open backend
- `NullMemoryService` or `InMemoryMemoryService`
- Service must never break auto/user flow on failures (audit/log only)

6. Helpers
- `generate_user_run_id(...)`
- `generate_auto_run_id(...)`
- `next_memory_step(...)`

### Non-negotiable semantics
- `MEMORY_ENABLED=0/1` is the master switch (default ON when unset). Read once per run/encounter start.
- Every record is keyed by at least: `run_id`, `mode`, `encounter_id`, `patient_id`.
- `MemoryItem.step` is a monotonically increasing event sequence within a run.
- auto alignment uses `structured_facts.sim_step` (simulation step); user alignment may use `structured_facts.dialogue_turn` optionally.

## 2) What Developer B Implements Now (Prework)

### 2.1 Hook-point inventory
- Maintain `PR_md/developer_B_hook_inventory.md` as the single source of truth of where hooks will be inserted and what each event must contain.

### 2.2 tests_week8 skeletons
- Create `tests_week8/` with:
  - support fake services
  - contract checks
  - integration tests that auto-skip until `app_core.memory` exists

### 2.3 ON/OFF ablation plan (runtime)
- Use `MEMORY_ENABLED=0/1`.
- Value must be recorded into run metadata/replay export so results are traceable.

## 3) Runbook (Developer B Prework)

### Run Week8 memory tests only (current step)

```bash
cd /home/jiawei2022/BME1325/week8/merge
pytest -q tests_week8
```

### Ablation: OFF vs ON (will become meaningful after A substrate lands)

```bash
cd /home/jiawei2022/BME1325/week8/merge
MEMORY_ENABLED=0 pytest -q tests_week8
MEMORY_ENABLED=1 pytest -q tests_week8
```

Expected behavior in current prework stage:
- Contract/fake-service tests pass.
- Integration tests should skip cleanly with a clear message.

## 4) Merge Safety Notes
- B will not patch user/auto logic to do file IO.
- B will only integrate production hooks after A provides `memory_service.*` (single service boundary).
- All new runtime data must live under `data/memory/` and be gitignored.

