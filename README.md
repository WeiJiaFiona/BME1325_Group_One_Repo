# Week9 Run Guide (Frontend + Backend)

This guide is the single source of truth for starting the full system.
It covers both `user` mode and `auto` mode, including which bash scripts to run and the frontend URLs.

## 1) Prerequisites

- Repo root: `/home/jiawei2022/BME1325/week9`
- Conda env: `edsim39`
- Secrets/config: `.env` exists at repo root
- Do **not** change cluster VPN proxy settings.
- For localhost requests, scripts already use `NO_PROXY/no_proxy` or `curl --noproxy`.

---

## 2) User Mode (Recommended for QA + Doctor LLM/RAG)

### Option A: Split startup (best for debugging)

Terminal A (frontend gateway):

```bash
bash /home/jiawei2022/BME1325/week9/start_user_frontend_8011.sh
```

Terminal B (backend simulation):

```bash
bash /home/jiawei2022/BME1325/week9/start_user_backend_curr_sim.sh
```

Frontend URL:

```txt
http://127.0.0.1:8011/simulator_home?ui_mode=user
```

### Option B: One-command startup

```bash
bash /home/jiawei2022/BME1325/week9/start_user_all_in_one.sh
```

Frontend URL:

```txt
http://127.0.0.1:8011/simulator_home?ui_mode=user
```

---

## 3) Auto Mode

Terminal A (frontend gateway):

```bash
bash /home/jiawei2022/BME1325/week9/start_auto_backend_edsim39.sh 8010
```

Terminal B (settings + backend + run + verify):

```bash
bash /home/jiawei2022/BME1325/week9/bootstrap_auto_sim_edsim39.sh 8010 ed_sim_n5 curr_sim 20
```

Frontend URL:

```txt
http://127.0.0.1:8010/simulator_home?ui_mode=auto
```

---

## 4) Manual Health Checks

Check frontend gateway:

```bash
curl --noproxy "127.0.0.1,localhost,0.0.0.0,::1" \
  -s -o /dev/null -w "%{http_code}\n" \
  "http://127.0.0.1:8011/simulator_home?ui_mode=user"
```

Start backend manually:

```bash
curl --noproxy "127.0.0.1,localhost,0.0.0.0,::1" -X POST \
  "http://127.0.0.1:8011/start_backend/ed_sim_n5/curr_sim/?headless=1"
```

Run steps:

```bash
curl --noproxy "127.0.0.1,localhost,0.0.0.0,::1" -X POST \
  "http://127.0.0.1:8011/send_sim_command/" \
  -H "Content-Type: application/json" \
  -d '{"command":"run 1"}'
```

---

## 5) Common Problems

1. `Backend is started with EDSIM_MODE=auto...`
- Cause: old Django process is still running in `auto` mode.
- Fix: stop all `manage.py runserver` processes, then restart with the user script.

2. `Please start the backend first...`
- Cause: frontend is up, but backend simulation not started (or stale runtime state).
- Fix: run the backend script (`start_user_backend_curr_sim.sh`) or call `/start_backend/...` + `/send_sim_command`.

3. Port in use
- Stop stale process:

```bash
pkill -f "manage.py runserver" || true
pkill -f "reverie.py --frontend_ui yes" || true
```

---

## 6) Script List Summary

- User frontend only:  
  `/home/jiawei2022/BME1325/week9/start_user_frontend_8011.sh`
- User backend only:  
  `/home/jiawei2022/BME1325/week9/start_user_backend_curr_sim.sh`
- User all-in-one:  
  `/home/jiawei2022/BME1325/week9/start_user_all_in_one.sh`
- Auto frontend gateway:  
  `/home/jiawei2022/BME1325/week9/start_auto_backend_edsim39.sh`
- Auto bootstrap pipeline:  
  `/home/jiawei2022/BME1325/week9/bootstrap_auto_sim_edsim39.sh`

---

## 7) Which Frontend Is Actually Running

Definite frontend root used by `manage.py runserver`:

```txt
/home/jiawei2022/BME1325/week9/environment/frontend_server
```

Definite page template rendered for simulator UI:

```txt
/home/jiawei2022/BME1325/week9/environment/frontend_server/templates/home/home.html
```

Definite script entry included by that page:

```txt
/home/jiawei2022/BME1325/week9/environment/frontend_server/templates/home/main_script.html
```

Current map playback logic used by both modes is loaded from:

```txt
/home/jiawei2022/BME1325/week9/environment/frontend_server/templates/home/scripts/auto_main_script.html
```

---

## 8) Do User/Auto Share the Same Frontend?

Yes. They share the same Django frontend app and the same simulator page template:

- shared route: `/simulator_home`
- shared template: `templates/home/home.html`
- shared backend bridge endpoints: `/send_sim_command`, `/update_environment`, `/process_environment`

They differ by `ui_mode` and backend `EDSIM_MODE`:

- Auto URL: `/simulator_home?ui_mode=auto`
- User URL: `/simulator_home?ui_mode=user`

---

## 9) Specific Differences Between Auto and User Mode

1. Interaction model
- `auto`: no conversational panel; user drives simulation via commands (`run N`, `fin`, etc.).
- `user`: includes patient chat panel calling `/mode/user/*` APIs for triage/doctor dialogue.

2. Clinical dialogue pipeline
- `auto`: crowd/system simulation focus; no user patient chat workflow.
- `user`: one controlled patient encounter workflow with doctor QA, LLM, and doctor RAG enabled.

3. Mode guardrails
- If page query `ui_mode` mismatches backend `EDSIM_MODE`, UI shows a mode mismatch warning.
- Practical rule: start backend in `EDSIM_MODE=user` for user chat; start in `EDSIM_MODE=auto` for auto simulation.

4. Shared simulation data path
- Both modes read/write the same simulation storage tree under:
  `/home/jiawei2022/BME1325/week9/environment/frontend_server/storage/curr_sim/`

---

## 10) FullView Integration Status

`week9` is now partially integrated with the unified FullView frontend in:

```txt
/home/jiawei2022/BME1325/BME_1325_Full_Vis/full_view
```

Current integration goal is:

- keep EDMAS clinical/user-mode and auto-mode logic unchanged as much as possible;
- translate EDMAS disposition or transfer decisions into standard FullView hospital movement requests;
- let FullView remain the execution side for cross-room / cross-department move validation, event-log, snapshot update, bed occupancy, and animation playback.

The current adapter path is:

```txt
EDMAS decision
  -> app_core/integration/fullview_adapter.py
  -> FullView POST /api/hospital/patients/ensure
  -> FullView POST /api/hospital/events/move
  -> FullView event-log / snapshot / animationPlan
```

Related EDMAS files:

- `app_core/integration/fullview_adapter.py`
- `app_core/integration/fullview_client.py`
- `app_core/integration/fullview_mapping.py`
- `app_core/integration/disposition_rules.py`
- `app_core/app/api_v1.py`
- `reverie/backend_server/auto_memory_hooks.py`
- `reverie/backend_server/persona/persona_types/patient.py`

Related FullView file:

- `/home/jiawei2022/BME1325/BME_1325_Full_Vis/full_view/dev-server.py`

---

## 11) Current Inter-Room / Inter-Department Transfer Rules

At the current stage, the integration only covers high-level simulated transfer rules.
This is not a real clinical transfer engine.

Supported outward movement types:

1. `ED -> ICU`
- FullView event: `TRANSFER_ED_TO_ICU`
- Triggered when EDMAS user-mode doctor disposition or auto-mode admit rule determines ICU-level destination.

2. `ED -> Ward`
- FullView event: `TRANSFER_ED_TO_WARD`
- Triggered when EDMAS disposition result is stable for admission but does not require ICU.

3. `ED -> Diagnostic`
- FullView event: `ED_TO_DIAGNOSTIC_MOVE`
- Triggered by doctor ordered test / auto-mode testing transition.

4. `ED -> Discharge`
- FullView event: `ED_PATIENT_EXIT_HOSPITAL`
- Triggered when EDMAS concludes low-risk discharge.

High-level routing logic currently uses:

- EDMAS triage acuity (`A/B/C/D`)
- CTAS-compatible level
- simplified MEWS-like risk scoring
- simplified danger stratification from vitals such as `SpO2`, `SBP`, `resp_rate`, `heart_rate`

Current default routing summary:

- `acuity A/B`, CTAS 1, or severe danger-tier -> ICU
- `acuity C`, CTAS 2/3, or moderate danger-tier -> Ward
- explicit test / exam need -> Diagnostic
- lower-risk completion -> Discharge

Important limitation:

- EDMAS internal movement and FullView movement are not yet a single source of truth.
- FullView move success does not yet fully back-propagate to all EDMAS internal states.
- Auto mode still does not simulate a true internal ICU/Ward floor transition inside EDMAS itself.

---

## 12) Current Test Results

### Automated checks completed

Static compile check passed for:

- `BME_1325_Full_Vis/full_view/dev-server.py`
- `week9/app_core/integration/*.py`
- `week9/app_core/app/api_v1.py`
- `week9/reverie/backend_server/auto_memory_hooks.py`
- `week9/reverie/backend_server/persona/persona_types/patient.py`

Focused backend tests passed:

```bash
cd /home/jiawei2022/BME1325/week9
pytest -q --noconftest \
  tests/backend/test_fullview_adapter.py \
  tests/backend/test_fullview_ensure_api.py
```

Result:

```txt
6 passed
```

### End-to-end integration checks completed

The following FullView-side movement chains were successfully verified:

1. `ED -> ICU`
- event accepted: `TRANSFER_ED_TO_ICU`
- verified patient moved into ICU bed room

2. `ED -> Ward`
- event accepted: `TRANSFER_ED_TO_WARD`
- verified patient moved into ward bed room

3. `ED -> Diagnostic`
- event accepted: `ED_TO_DIAGNOSTIC_MOVE`
- verified patient moved into diagnostic room

4. `ED -> Discharge`
- event accepted: `ED_PATIENT_EXIT_HOSPITAL`
- verified patient moved to `exit` pseudo-target and marked discharged

### Concrete verified examples

Example ICU case from EDMAS user mode:

- HIS patient id: `P-5d9fc8fc`
- FullView event: `TRANSFER_ED_TO_ICU`
- FullView eventSeq: `95`
- Final FullView location: `icu_beds_a`
- Final FullView status: `ADMITTED`

Example Ward case:

- FullView eventSeq: `100`
- Event: `TRANSFER_ED_TO_WARD`

Example Diagnostic case:

- FullView eventSeq: `101`
- Event: `ED_TO_DIAGNOSTIC_MOVE`

Example Discharge case:

- FullView eventSeq: `102`
- Event: `ED_PATIENT_EXIT_HOSPITAL`

Example rejected case:

- FullView eventSeq: `103`
- Event: `TRANSFER_ED_TO_WARD`
- Rejection reason: `PATIENT_ROOM_MISMATCH`

This rejection check is important because it confirms FullView is still enforcing movement legality and not blindly accepting adapter requests.

---

## 13) Next Optimization Targets

The current adapter proves the request chain is working, but it is still a v1 integration layer.
Next-stage priorities are:

1. Unify state truth
- reduce divergence between EDMAS internal workflow phase and FullView room/state snapshot;
- define which side is canonical for patient location, transfer status, and disposition state.

2. Expand event coverage
- support more detailed ED internal room transitions;
- support diagnostic return, observation, boarding, and richer consult-room states.

3. Improve stable identity mapping
- ensure one stable patient id and one stable encounter id are used consistently across:
  - EDMAS user mode
  - EDMAS auto mode
  - HIS storage
  - FullView

4. Improve reverse synchronization
- after FullView accepts or rejects a move, expose a clearer callback/result path into EDMAS UI and runtime state.

5. Strengthen test coverage
- add regression tests for:
  - ICU full / ward full
  - diagnostic blocked
  - repeated ensure/upsert requests
  - repeated move requests
  - user-mode and auto-mode consistency

6. Clarify clinical simulation policy
- keep the system at high-level simulation fidelity;
- avoid drifting into real-world diagnostic/clinical decision claims;
- document simplified CTAS/MEWS/disposition assumptions explicitly.
