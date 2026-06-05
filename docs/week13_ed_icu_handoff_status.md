# Week13 ED–ICU Handoff Status

## Status

- ED-side interface merge code is implemented.
- Unit tests and metrics regression checks for the ED-side merge pass.
- End-to-end probe validation is not complete.

## Completed

- Added ED-side downstream stub modules under `reverie/backend_server/downstream_units/`.
- Added `TransferBroker` with local `accepted | pending` semantics for bed allocation.
- Added `DispositionTargetResolver` for ED admission target split (`discharge | ward | ICU`).
- Extended patient runtime evidence to persist:
  - decision to admit
  - transfer request id / transfer status
  - boarding start
  - ward transfer time
  - ICU admit time
  - boarding timeout time
- Wired downstream summary fields into `sim_status.json`.
- Added focused tests for downstream units, transfer broker, and ED–ICU handoff metrics.

## Not Completed

- End-to-end `run_ed_icu_handoff_probe.py` is not fully validated across all intended capacity points.
- No validated `icu_capacity=0/1/6` comparison report is ready for submission.
- No real ICU HTTP adapter is implemented.

## Blocker

- The current blocker is a probe/runtime settings override injection bug.
- Observed symptom in generated runtime artifacts:
  - `hospital_profile_name = null`
  - `icu_capacity = 0`
  - `ward_capacity = 0`
  - `downstream_transfer_request_count = 0`
- Because the backend runtime does not receive the intended downstream profile overrides, transfer requests do not trigger in the probe run, so the probe cannot validate the new handoff path.

## What This Means

- ED-side merge implementation is ready for code review and commit.
- ED-side merge is **not yet ready for final operational signoff** based on probe results.
- ICU-side teammates can review the interface contract and boundaries now, but should not assume the end-to-end probe has passed.

## Handoff Boundary

### In Scope for This Handoff

- ED-side downstream contract shape
- ED-side `pending` versus `accepted` semantics
- ED-side runtime evidence fields
- ED-side `sim_status` downstream summary fields
- ED-side local stub behavior for ICU/Ward bed shortage

### Out of Scope for This Handoff

- ICU internal treatment workflow
- ICU internal agent runtime
- ICU FastAPI integration
- ICU database / Redis / frontend integration
- cross-repo production API validation

## Required Next Fix

1. Fix `scripts/run_ed_icu_handoff_probe.py` or the underlying smoke-launch path so settings overrides actually reach backend runtime.
2. Re-run the small probe matrix for `icu_capacity = 0 / 1 / 6`.
3. Verify that:
   - transfer requests are emitted
   - `pending_transfer_count` changes with capacity
   - `boarding_timeout_count` changes with capacity
   - `throughput_success_rate` changes with capacity
4. Only after that, treat the ED-side merge as end-to-end validated.

## Commit Boundary

Only commit ED–ICU interface merge code, tests, and docs:

- `reverie/backend_server/downstream_units/`
- `reverie/backend_server/persona/memory_structures/scratch_types/patient_scratch.py`
- `reverie/backend_server/persona/persona_types/patient.py`
- `reverie/backend_server/reverie.py`
- `scripts/run_ed_icu_handoff_probe.py`
- `tests/backend/test_downstream_units.py`
- `tests/backend/test_transfer_broker.py`
- `tests/backend/test_ed_icu_handoff_metrics.py`
- `docs/week13_ed_icu_handoff_status.md`
- `docs/week13_ed_icu_interface_merge_summary.md`
- `docs/week13_ed_icu_handoff_runbook_for_ed_team.md`

Do not commit:

- `environment/frontend_server/storage/*`
- large `movement/*.json`
- temporary runtime probe directories
- unrelated analysis/runtime artifacts

## Ready For Review

- Yes, for ED-side code review and handoff review.
- No, for final probe-based acceptance.
