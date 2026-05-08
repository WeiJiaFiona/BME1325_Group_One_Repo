# Week8 Merge Handoff (Auto + User)

Location of merged system:
- `/home/jiawei2022/BME1325/week8/merge`

This document is written for a new developer (or Codex agent) to validate that:
- collaborator's **auto mode upgrades** are preserved,
- Jiawei's **user mode upgrades** (LLM brain + doctor-only local KB/RAG + calling nurse + UX fixes) are preserved,
- the merge respects the rule: **backend startup `EDSIM_MODE` is the single source of truth** (frontend must not switch runtime mode).

## 1. What The Collaborator Upgraded (Auto Mode / week7)

Source baseline used for merge:
- GitHub branch: `week7`
- directory: `week7/auto/`
- fetched into: `/home/jiawei2022/BME1325/week8/auto`

Key auto upgrades (per `week7_progress_summary.md` and code layout):
- Arrival profiles:
  - new config `arrival_profile_mode` with at least `normal / surge / burst`.
- Resource realism:
  - `lab_capacity`, `lab_turnaround_minutes`
  - `imaging_capacity`, `imaging_turnaround_minutes`
- Boarding timeout event:
  - `boarding_timeout_minutes` records timeout events without removing patients.
- Frontend settings integration:
  - `start_simulation` / `save_simulation_settings` UI writes these fields into `meta.json`.
- Observability + analysis:
  - `analysis/compute_metrics.py` reads new fields/events and outputs:
    - `patient_time_metrics.csv`
    - `ctas_daily_metrics.csv`
    - `resource_event_metrics.json`
  - regression artifacts were produced under `analysis/scenario_regressions/*`.
- Runtime robustness improvements in Django `translator/views.py`:
  - storage/temp path resolution uses env-var + pointer + runtime sync helpers.
  - guards against stale `curr_step` pointer; syncs from movement/environment frames and `sim_status.json`.

Auto mode is still an EDSim-style multi-agent simulation under:
- `reverie/backend_server/*`

## 2. What Jiawei Upgraded (User Mode / week8)

Source of user mode:
- `/home/jiawei2022/BME1325/week8/user_mode`

Key user upgrades preserved in merge:
- User-mode session state machine with immediate agent handoffs (no extra “hello” required):
  - Intake -> Calling nurse vitals -> Triage -> Queue/wait -> Doctor -> Bedside nurse -> Done.
- **Calling nurse** introduced:
  - calls number, measures vitals, triggers next stage (prevents “must self-report SpO2/SBP” deadlocks).
- Shared memory across roles:
  - chief complaint, vitals, triage result, doctor findings, handoff/bed result.
- `pending_messages` queue + phase auto-progression:
  - state transitions can push messages without requiring the user to type again.
- Doctor improvements:
  - “one question per turn” guard + anti-repeat mechanisms.
  - slot extraction fixes (duration like “早上/上午…”, and yes/no answers count as informative when answering active slot).
  - triage pain-score upgrade: severe pain (>=8/10) no longer always defaults to CTAS 3.
- Doctor-only local KB + selective RAG integration:
  - local KB artifacts under `RAG/doctor_kb/**`
  - KB validators, compiler, lexical indices, retrieval eval set
  - selective doctor bridge that **must not** output disposition or modify `next_slot`.
- LLM adapter:
  - supports OpenAI-compatible endpoint; tolerant config parsing (first JSON object even with trailing notes).

User mode runtime logic lives under:
- `app_core/` (in merge root)

## 3. What Was Merged, And Whether Upgrades Were Kept

Merged system root:
- `/home/jiawei2022/BME1325/week8/merge`

How merge was done:
1. Seeded merge from collaborator auto tree (full copy).
2. Grafted Jiawei user features:
   - `app_core/` overwritten from `/home/jiawei2022/BME1325/week8/user_mode/app_core`
   - `RAG/doctor_kb/` copied from `/home/jiawei2022/BME1325/week8/user_mode/RAG/doctor_kb`
   - user tests copied to `tests_user/` (kept separate from auto tests).

Preservation status:
- Auto upgrades: preserved because merge started from collaborator’s auto tree and we did NOT rewrite its `reverie/`, `analysis/`, `environment/` (except the template/script splitting and translator import binding described below).
- User upgrades: preserved because `app_core/` and `RAG/doctor_kb/` are taken from Jiawei’s week8/user_mode as the source of truth.

## 4. Conflicts Found During Merge And How They Were Resolved

### 4.1 Conflict: `translator/views.py` user-mode API binding
Problem:
- Auto tree’s Django frontend originally imported user-mode APIs from `week5_system.app.api_v1`.
Requirement:
- User mode in week8 is implemented in `app_core.app.api_v1` (calling nurse, shared memory, RAG, etc.).
Resolution:
- In merge: `environment/frontend_server/translator/views.py` imports:
  - `from app_core.app.api_v1 import ...`
  - while keeping collaborator’s path resolution + runtime sync logic intact.

### 4.2 Conflict: Frontend must not switch backend runtime mode
Problem:
- `ui_mode=auto|user` exists as a query param, but must not reconfigure runtime behavior.
Resolution (implemented):
- `translator/views.py` defines:
  - `backend_mode = os.environ.get("EDSIM_MODE", "auto")`
  - `effective_ui_mode = backend_mode`
  - if user requests mismatched `ui_mode`, the page shows a clear warning.
- All `/mode/user/*` endpoints return `409 MODE_MISMATCH` unless `EDSIM_MODE=user`.

### 4.3 Conflict: Auto vs User map scripts (main_script.html)
Problem:
- Auto and user modified `templates/home/main_script.html` differently (map playback/sync vs role visualization/calling nurse).
Decision from Jiawei:
- Split panel + script by mode; no single-file override and no forced full union.
Resolution (implemented):
- `templates/home/scripts/auto_main_script.html` = collaborator map script
- `templates/home/scripts/user_main_script.html` = Jiawei map script
- `templates/home/main_script.html` is now a wrapper:
  - includes one or the other based on `effective_ui_mode`.

### 4.4 Conflict: User chat panel duplication risk
Fix applied:
- We introduced `templates/home/panels/user_panel.html` and `home.html` includes it.
Note:
- The main `home.html` content is still largely the collaborator version; user panel is included once at the right column.

## 5. How To Run And Test (Merged System)

### 5.1 Python env / dependencies
The merged repo includes both:
- auto stack dependencies (needs `django`, `openai`, `pandas`, etc.)
- user-mode unit tests (pure python, no django required for tests_user)

If you run `pytest -q tests` in a bare environment you may see missing deps errors (e.g., `pandas`, `openai`, `django`).
This is environment-related, not necessarily a merge bug.

### 5.2 Run Auto Mode (EDSIM_MODE=auto)
Terminal A (frontend):
```bash
cd /home/jiawei2022/BME1325/week8/merge/environment/frontend_server
EDSIM_MODE=auto python manage.py runserver 0.0.0.0:8010
```

Terminal B (backend):
```bash
cd /home/jiawei2022/BME1325/week8/merge/reverie/backend_server
# follow collaborator README/scripts; typical:
python reverie.py
```

Notes for auto-mode tester:
- Use the start_simulation page to set `arrival_profile_mode`, capacities, TAT, boarding timeout.
- Validate the outputs exist under `environment/frontend_server/storage/<sim_code>/...`.
- Run analysis:
```bash
cd /home/jiawei2022/BME1325/week8/merge/analysis
python compute_metrics.py --sim <sim_code>
```
- Verify `resource_event_metrics.json` includes week7 resource/timeout events.

### 5.3 Run User Mode (EDSIM_MODE=user)
Terminal A (frontend):
```bash
cd /home/jiawei2022/BME1325/week8/merge/environment/frontend_server
EDSIM_MODE=user python manage.py runserver 0.0.0.0:8010
```

Open:
- `http://127.0.0.1:8010/simulator_home?ui_mode=user`

Notes for user-mode tester:
- If backend is started with `EDSIM_MODE=auto`, user endpoints will return `409 MODE_MISMATCH` by design.
- User mode uses `app_core` and does not require running the auto simulation loop.

LLM/RAG:
- RAG (local) should work offline (uses `RAG/doctor_kb` local artifacts).
- LLM requires credentials:
  - set `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL`, or provide `openai_config.json` (gitignored).
  - If no key, system should degrade gracefully (LLM disabled).

### 5.4 Tests
User-mode tests (fast, recommended baseline):
```bash
cd /home/jiawei2022/BME1325/week8/merge
pytest -q tests_user
```
Expected: `60 passed`.

Auto-mode tests:
- `pytest -q tests` requires that your environment has `django`, `openai`, `pandas`, etc. installed.

## 6. Checklist For The Auto-Mode Developer (What To Verify)

1. Settings wiring:
- confirm `save_simulation_settings` writes new week7 fields into `meta.json` (arrival profile + capacities + TAT + boarding timeout).

2. Arrival profile:
- run `normal` vs `surge` vs `burst` and confirm patient arrivals differ in logs/metrics.

3. Resource realism:
- reduce `imaging_capacity` or increase `imaging_turnaround_minutes` and confirm bottleneck manifests:
  - longer waits,
  - resource event metrics show increased queueing / utilization.

4. Boarding timeout:
- set low `boarding_timeout_minutes` and run enough steps; verify timeout event is recorded but sim continues.

5. Analysis:
- `analysis/compute_metrics.py` runs and outputs metrics including `resource_event_metrics.json`.

6. Mode invariants:
- with `EDSIM_MODE=auto`, opening `?ui_mode=user` must show a warning and user endpoints must be blocked (409).

## 7. Known Limitations / Areas To Watch

- Auto tests failing due to missing Python deps is expected unless you install requirements in the chosen environment.
- The merge introduces mode wrapper logic; if you see map playback issues, isolate whether it happens in:
  - `auto_main_script.html` path, or
  - `user_main_script.html` path.
- If you need auto-panel extraction into `panels/auto_panel.html` for cleaner separation, do it carefully:
  - do NOT change backend mode enforcement (EDSIM_MODE remains authoritative).

