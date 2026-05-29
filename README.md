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
