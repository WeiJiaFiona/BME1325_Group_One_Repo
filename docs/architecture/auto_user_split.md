# Auto Mode / User Mode Split

This note documents the intended merge baseline for `week7_auto`.

## Four-layer split

### 1. Simulation Runtime Layer

- Path: `reverie/backend_server/`
- Main entry: `reverie.py`
- Responsibility:
  - boot from `environment/frontend_server/storage/<sim>/reverie/meta.json`
  - run the auto-mode step loop
  - invoke LLM-backed agent cognition
  - write `movement/`, `environment/`, `sim_status.json`, `curr_step.json`

Week7 resource realism also belongs here:

- arrival profiles via `effective_arrival_rate(...)`
- lab/imaging capacity and turnaround handling
- boarding timeout event recording

### 2. Operational Rule / User Encounter Layer

- Path: `week5_system/app/` and `week5_system/rule_core/`
- Responsibility:
  - user-mode encounter start
  - chat turn handling
  - session status/reset
  - ED handoff request/complete
  - queue snapshot and payload validation

This layer is intentionally rule/service oriented. It is not a step-based simulation runtime.

### 3. Gateway / UI Layer

- Path: `environment/frontend_server/translator/views.py`
- Responsibility:
  - host the shared Django entrypoint
  - bridge frontend commands to the auto-mode backend
  - expose auto-mode dashboard and sim output polling
  - expose user-mode and handoff APIs under the same host

Shared Django URLs are the merge point:

- Auto mode:
  - `/start_simulation/`
  - `/start_backend/<origin>/<target>/`
  - `/send_sim_command/`
  - `/get_sim_output/`
  - `/live_dashboard`
  - `/api/live_dashboard/`
- User mode:
  - `/mode/user/encounter/start`
  - `/mode/user/chat/turn`
  - `/mode/user/session/status`
  - `/mode/user/session/reset`
  - `/ed/handoff/request`
  - `/ed/handoff/complete`
  - `/ed/queue/snapshot`

### 4. Analysis / Evidence Layer

- Path: `analysis/compute_metrics.py`
- Responsibility:
  - compress or load the chosen simulation export
  - compute patient timing metrics
  - compute CTAS aggregates
  - summarize Week7 resource and timeout signals

## Boundary decisions

- Auto mode is the simulation runtime.
- User mode is a rules/API service.
- Django is the shared host and gateway.
- The merge point should stay at the gateway/UI layer instead of forcing user-mode flows into `ReverieServer`.

## Runtime note

- `curr_step.json` is updated after each `run N` command finishes.
- During a long command, the better progress signals are:
  - backend timestamp logs
  - `sim_status.json`
  - `movement/<step>.json`
  - `environment/<step>.json`
