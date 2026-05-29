#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/jiawei2022/BME1325/week9"
PORT="${1:-8011}"
ORIGIN="${2:-ed_sim_n5}"
TARGET="${3:-curr_sim}"

cd "$ROOT"
if [[ -f ~/miniconda3/etc/profile.d/conda.sh ]]; then
  source ~/miniconda3/etc/profile.d/conda.sh
elif [[ -f ~/anaconda3/etc/profile.d/conda.sh ]]; then
  source ~/anaconda3/etc/profile.d/conda.sh
else
  source ~/.bashrc >/dev/null 2>&1 || true
fi
conda activate edsim39
echo "[user-all] conda env: ${CONDA_DEFAULT_ENV:-unknown}"

export NO_PROXY="127.0.0.1,localhost,0.0.0.0,::1"
export no_proxy="127.0.0.1,localhost,0.0.0.0,::1"

pkill -f "manage.py runserver" || true
pkill -f "reverie.py --frontend_ui yes" || true
rm -f environment/frontend_server/temp_storage/commands/cmd_*.json || true
rm -f environment/frontend_server/temp_storage/curr_step.json || true

set -a
source "$ROOT/.env"
set +a

mkdir -p "$ROOT/runtime_data/logs"
echo "[user-all] starting django on 127.0.0.1:${PORT} ..."

cd "$ROOT/environment/frontend_server"
nohup env \
  EDSIM_MODE=user \
  ENABLE_LLM_AGENTS=1 \
  ENABLE_DOCTOR_RAG=1 \
  MEMORY_V1_ENABLED=1 \
  MEMORY_ENABLED=1 \
  NO_PROXY="$NO_PROXY" \
  no_proxy="$no_proxy" \
  python manage.py runserver "127.0.0.1:${PORT}" --noreload \
  > "$ROOT/runtime_data/logs/user_frontend_${PORT}.log" 2>&1 &

sleep 2
echo "[user-all] save_simulation_settings ..."

curl --noproxy "127.0.0.1,localhost,0.0.0.0,::1" --max-time 15 -X POST \
  "http://127.0.0.1:${PORT}/save_simulation_settings/" \
  -H "Content-Type: application/json" \
  -d '{"doctor_starting_amount":30,"triage_starting_amount":20,"bedside_starting_amount":1,"preload_waiting_room_patients":30,"fill_injuries":0.3,"add_patient_threshold":0,"seed":20260522}'

echo "[user-all] start_backend ..."
curl --noproxy "127.0.0.1,localhost,0.0.0.0,::1" --max-time 20 -X POST \
  "http://127.0.0.1:${PORT}/start_backend/${ORIGIN}/${TARGET}/?headless=1"

echo "[user-all] send run 1 ..."
curl --noproxy "127.0.0.1,localhost,0.0.0.0,::1" --max-time 15 -X POST \
  "http://127.0.0.1:${PORT}/send_sim_command/" \
  -H "Content-Type: application/json" \
  -d '{"command":"run 1"}'

echo
echo "[user-all] User frontend: http://127.0.0.1:${PORT}/simulator_home?ui_mode=user"
