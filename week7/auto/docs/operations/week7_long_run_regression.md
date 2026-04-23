# Week7 Long-run Regression Notes

This note explains how the Week7 runtime works and how to observe slow real runs tonight.

## Runtime chain

1. `meta.json` is loaded from `environment/frontend_server/storage/<sim>/reverie/meta.json`.
2. `ReverieServer` initialises staff, patients, maze resources, and Week7 resource knobs.
3. The frontend or orchestration script sends `run N` / `fin` through `temp_storage/commands`.
4. `reverie.py` executes chunked steps and writes:
   - `movement/<step>.json`
   - `environment/<step>.json`
   - `sim_status.txt`
   - `sim_status.json`
   - `temp_storage/curr_step.json`
5. `live_dashboard` consumes `sim_status.json`.
6. `compute_metrics.py` generates analysis evidence after the run.

## Week7 resource rules

### Arrival pressure

- Config:
  - `patient_rate_modifier`
  - `arrival_profile_mode`
- Logic:
  - `effective_arrival_rate(patient_rate_modifier, arrival_profile_mode, hour)`
- Meaning:
  - `normal`: baseline multiplier
  - `surge`: elevated multiplier all day
  - `burst`: hour-sensitive peaks, especially morning and late afternoon

### Lab / Imaging scheduling

- Config:
  - `lab_capacity`
  - `lab_turnaround_minutes`
  - `imaging_capacity`
  - `imaging_turnaround_minutes`
- Logic:
  - CTAS high acuity prefers imaging
  - lower acuity prefers lab
  - a patient starts testing only when the corresponding slot is available
  - otherwise the patient remains in `WAITING_FOR_TEST`

### Boarding timeout

- Config:
  - `simulate_hospital_admission`
  - `admission_probability_by_ctas`
  - `boarding_timeout_minutes`
- Logic:
  - disposition can move a patient into `ADMITTED_BOARDING`
  - timeout is recorded by `boarding_timeout_reached(...)`
  - the event is stored in `data_collection.json` and surfaced in `sim_status.json`

## Tonight's logging contract

Permanent lightweight runtime logs now cover:

- backend boot and meta load
- command receipt and command duration
- per-step start/end with wall-clock elapsed time
- status snapshot writes
- arrival profile application
- patient arrivals
- lab/imaging slot occupation
- boarding timeout events
- LLM request begin/done/retry/fail timings

## Observation checklist

For a slow real command, inspect in this order:

1. backend timestamp logs
2. `sim_status.json`
3. `movement/<step>.json`
4. `environment/<step>.json`
5. `reverie/data_collection.json`
6. `analysis/resource_event_metrics.json`

## Scenario runner

Use `scripts/run_week7_long_regression.py` for tonight's real regression.

It is designed to:

- prepare scenario-specific seed folders
- drive the backend with chunked `run` commands
- sample `sim_status.json` after each chunk
- store JSON and Markdown evidence under `analysis/scenario_regressions/`
