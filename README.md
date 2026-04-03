# EDMAS Week 5 Implementation Summary

![Pipeline](figs/pipeline.png)

## Week 5 Goal
Build a deterministic ED core that can run user encounter flow end-to-end with explicit triage rules, explicit patient state transitions, and stress-testable multi-agent queue dynamics.

## Folder-by-Folder Implementation

### `week5_system/rule_core`
- `triage_policy.py`
  - Implements Chinese-style triage outputs: `acuity_ad (A/B/C/D)`, `level_1_4`, `ctas_compat`, `zone`, `green_channel`, `required_resources_count`, `max_wait_minutes`, `hooks`.
  - Core functions: `_contains_any`, `_estimate_required_resources_count`, `triage_cn_ad`.
  - Rules include: symptom triggers (chest pain/sweat, FAST stroke, severe dyspnea, trauma), vitals override (`SpO2<90` or `SBP<90`), level-zone mapping, yellow-zone wait cap hook (`wait_cap_30m`).
- `state_machine.py`
  - Defines `ALLOWED_TRANSITIONS` and `HOOK_ESCALATIONS`.
  - `EncounterStateMachine.transition()` blocks illegal transitions.
  - `EncounterStateMachine.apply_hook()` handles escalation hooks (`green_channel`, `abnormal_vitals`, etc.) deterministically.
- `encounter.py`
  - `start_user_encounter()` orchestrates triage + state machine flow and returns structured encounter result.

### `week5_system/app`
- `mode_user.py`
  - Entry for user-mode execution.
  - Builds `TriageInput` from payload and returns `triage/final_state/state_trace`.
- `surge_sim.py`
  - Multi-patient surge simulator for queue/worker stress testing.
  - Simulates `ARRIVAL -> TRIAGE_QUEUE -> NURSE_QUEUE(optional) -> DOCTOR_QUEUE -> COMPLETE`.
  - Uses staffing config (`doctors`, `triage_nurses`, `bedside_nurses`) and returns completion/timeout/queue-peak metrics.

### `week5_system/agents`
- `patient.py`, `triage_nurse.py`, `bedside_nurse.py`, `doctor.py` define role behaviors.
- Mechanism highlights (planning/memory/tools):
  - Planning: role-specific `move()` logic with deterministic queue/timer decisions.
  - Memory: role `scratch` state (e.g., `state`, `assigned_doctor`, `time_to_next`, `chatting_with`, wait-stage timestamps).
  - Tools: queue operations (`triage_queue`, `patients_waiting_for_doctor`, `pager`, `bedside_nurse_waiting`), bed assignment/release, task dispatch.

![MAS loop](figs/MAS_loop.png)


### `week5_system/simulation_loop`
- `reverie.py`, `run_simulation.py` provide the simulation runtime loop and batch runner entry.
- Purpose: global time-step orchestration and runtime control.

### `week5_system/queue_state_primitives`
- `maze.py`
  - ED space, zone occupancy, and queue containers (`triage_queue`, doctor queue, zone patient lists).
- `wait_time_utils.py`
  - CTAS-based staged waiting targets (`stage1/2/3`) and sampling helpers.

![State machine](figs/state_machine.png)


## How Components Interact
1. `mode_user.start(payload)` creates `TriageInput`.
2. `triage_cn_ad()` computes triage output + hooks.
3. `EncounterStateMachine` advances patient state with legal-transition enforcement.
4. Escalation hooks trigger deterministic state upgrades.
5. Queue/state primitives hold waiting structures and resource pressure.
6. Agent `move()` logic consumes and updates queues/resources over time.
7. `surge_sim` validates system behavior under concurrent arrivals and staffing constraints.

## Week 5 Rules Used by the System
- Severity mapping: A/B/C/D -> level 1/2/3/4 -> red/red/yellow/green.
- Vitals override: abnormal vitals force escalation.
- Green-channel trigger: high-risk presentations receive expedited path.
- Transition safety: illegal state jumps are rejected.

## Testing Completed (All Passed)
Test command:
```bash
cd /home/jiawei2022/BME1325/week5_progress/EDMAS/edmas/week5_edmas
python -m pytest -q
```

Passed suites:
- Triage + state-machine scenario tests (`tests/test_week5_scope.py`):
  - chest pain + diaphoresis
  - FAST-positive stroke
  - mild sprain low-acuity path
  - low-SpO2 override
  - illegal transition rejection
  - deterministic replay
  - yellow-zone wait-cap hook
- Multi-agent surge tests (`tests/test_week5_multi_agent_surge.py`):
  - 20 patients surge with `3 doctors + 2 triage nurses + 2 bedside nurses`
  - full encounter completion and no timeout
  - deterministic under same staffing configuration

Current result: `10 passed`.

## Week 6 Planned Work
- Implement and freeze L1 APIs:
  - `POST /mode/user/encounter/start`
  - `POST /ed/handoff/request`
  - `POST /ed/handoff/complete`
  - `GET /ed/queue/snapshot`
- Add payload schema validation and malformed-input robustness tests.
- Add ICU/Ward mock integration tests for handoff contract verification.




