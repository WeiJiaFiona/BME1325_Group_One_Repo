# Week 9: ED Simulation (Auto + User + HIS)

This directory contains a runnable ED simulation system with:
- **Auto mode**: multi-patient simulation driven by `reverie/backend_server/`.
- **User mode**: interactive "one patient under user control" flow driven by `app_core/app/`.
- **HIS (SQLite dev backend)**: both modes persist structured encounter records.
- **Django + Phaser UI**: the primary UI entrypoint under `environment/frontend_server/`.

## What Was Improved This Week

### Frontend / UI Runtime Sync
- Stabilized **UI runtime sync** so the Phaser map playback does not stall when pointer/status frames drift.
- Added **backend health checks** and **stale runtime self-heal** logic during `/start_backend/...` startup and polling.
- Improved robustness around temp-storage command consumption and runtime pointers (`curr_step.json`, `sim_status.json`, movement/environment frames).

### Backend: Auto/User Fusion + Deterministic Control
- Enabled **auto runtime hosting user interaction**:
  - Start backend with `EDSIM_MODE=auto` and still open the UI with `?ui_mode=user`.
  - A user-controlled patient can be injected into the auto world via the existing command bridge.
- Preserved ownership boundaries:
  - Auto state machine remains rule-driven.
  - User mode enables **doctor LLM + doctor-only RAG** only for the user patient during the doctor encounter.

### HIS: "Write Everything" Baseline
- Both auto-mode and user-mode flows write to HIS via `sqlite_dev` storage.
- HIS internal IDs are contract-aligned:
  - `patient_id`: `P-xxxxxxxx` (lowercase hex)
  - `encounter_id`: `E-YYYYMMDDHHmmss-xxxx`
- Public-facing legacy IDs (e.g. `enc-...`, `Patient 1`) are retained in `encounters.metadata.public_encounter_id` (mapping only).

### Security / Secrets Hygiene
- Secrets are no longer stored in repo JSON configs.
- API keys are expected to be provided via environment variables loaded from `.env`.

## Removed / Pruned (Not Required for Running)

To reduce size and noise, the following non-runtime directories were removed:
- `environment/react_frontend/` (React + R3F viewer; not used by the main UI)
- `app_core/RAG/refs/` (reference repos snapshot; not needed at runtime)
- `tests/`, `tests_his/`, `tests_user/`
- `docs/`, `analysis/`, `examples/sample_statistics/`
- runtime artifacts and caches (e.g. `__pycache__/`, exported data bundles)

## How To Run

### 1) Install Python Dependencies

From the repo root (`week9/`):
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r environment/frontend_server/requirements.txt
```

### 2) Configure Secrets (.env)

Create `.env` in the repo root (already supported by the team workflow) and load it before starting:
```bash
set -a
source .env
set +a
```

Minimum required variables (example names; any one of the key variants is acceptable):
- Model key: `OPENAI_KEY` or `OPENAI_API_KEY` or `EDSIM_MODEL_KEY`
- Model endpoint: `OPENAI_ENDPOINT` or `EDSIM_MODEL_ENDPOINT`
- Model name: `OPENAI_MODEL` or `EDSIM_MODEL`
- (Optional) Embeddings: `EMBEDDINGS_KEY`, `EMBEDDINGS_ENDPOINT`, `EMBEDDINGS_MODEL`

### 3) Start Django UI Server

```bash
export EDSIM_MODE=auto
export HIS_DB_BACKEND=sqlite_dev
export ENABLE_LLM_AGENTS=1
cd environment/frontend_server
python manage.py runserver 127.0.0.1:8010
```

Open UI:
- Auto UI: `http://127.0.0.1:8010/simulator_home?ui_mode=auto`
- User UI (hosted on auto runtime): `http://127.0.0.1:8010/simulator_home?ui_mode=user`

### 4) Start Auto Simulation Backend (reverie)

From the UI, use the "start simulation" flow, or directly call:
```bash
curl -X POST "http://127.0.0.1:8010/start_backend/ed_sim_n5/curr_sim/?headless=1"
```

Notes:
- `headless=1` is recommended for reliable step progression (movement frame generation).
- The UI writes commands to `environment/frontend_server/temp_storage/commands/`.

### 5) Running Steps

In the UI command box, use:
- `run 10`
- `run 100`

If the UI does not move while the backend claims it ran steps:
- Check `environment/frontend_server/storage/curr_sim/movement/` is producing new `<step>.json` frames.
- Check `environment/frontend_server/storage/curr_sim/sim_status.json` is updating.

## HIS Output Location

Default SQLite dev DB:
- `data/his_dev.sqlite3`

Quick inspection:
```bash
sqlite3 data/his_dev.sqlite3 ".tables"
sqlite3 data/his_dev.sqlite3 "SELECT encounter_id, payload FROM encounters ORDER BY rowid DESC LIMIT 5;"
sqlite3 data/his_dev.sqlite3 "SELECT payload FROM event_registry ORDER BY rowid DESC LIMIT 10;"
```

## Repo Layout (Runtime-Relevant)

- `environment/frontend_server/`: Django + Phaser UI and runtime bridge (start backend, send commands, runtime pointers).
- `reverie/backend_server/`: Auto-mode simulation runtime (`reverie.py`, persona system, queues, movement output).
- `app_core/app/`: User-mode interactive API and doctor LLM/RAG integration.
- `app_core/his/`: HIS schemas/services/storage (SQLite dev backend by default).
- `RAG/doctor_kb/`: doctor-only local KB content used by user-mode doctor RAG.
