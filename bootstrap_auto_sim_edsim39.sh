#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/home/jiawei2022/BME1325/week9"
PORT="${1:-8010}"
ORIGIN="${2:-ed_sim_n5}"
TARGET="${3:-curr_sim}"
RUN_STEPS="${4:-20}"
LOCAL_NO_PROXY="127.0.0.1,localhost,0.0.0.0,::1"

echo "[auto-bootstrap] root=$ROOT_DIR port=$PORT origin=$ORIGIN target=$TARGET run_steps=$RUN_STEPS"

if [[ -f ~/miniconda3/etc/profile.d/conda.sh ]]; then
  source ~/miniconda3/etc/profile.d/conda.sh
elif [[ -f ~/anaconda3/etc/profile.d/conda.sh ]]; then
  source ~/anaconda3/etc/profile.d/conda.sh
else
  source ~/.bashrc >/dev/null 2>&1
fi
conda activate edsim39
export NO_PROXY="${NO_PROXY:-$LOCAL_NO_PROXY}"
export no_proxy="${no_proxy:-$LOCAL_NO_PROXY}"

check_http_200() {
  local url="$1"
  local code
  code="$(curl --noproxy "$LOCAL_NO_PROXY" -s -o /dev/null -w "%{http_code}" "$url" || true)"
  if [[ "$code" != "200" ]]; then
    echo "[fatal] endpoint not ready: $url (http=$code)"
    exit 1
  fi
}

check_http_200_or_404() {
  local url="$1"
  local code
  code="$(curl --noproxy "$LOCAL_NO_PROXY" -s -o /dev/null -w "%{http_code}" "$url" || true)"
  if [[ "$code" != "200" && "$code" != "404" ]]; then
    echo "[fatal] endpoint unhealthy: $url (http=$code)"
    exit 1
  fi
}

post_json() {
  local url="$1"
  local body="$2"
  local resp
  resp="$(curl --noproxy "$LOCAL_NO_PROXY" -sS -X POST "$url" -H "Content-Type: application/json" -d "$body")"
  echo "$resp"
  if ! grep -q '"ok"' <<<"$resp"; then
    echo "[fatal] response missing \"ok\": $url"
    exit 1
  fi
}

echo "[auto-bootstrap] check django gateway ..."
check_http_200 "http://127.0.0.1:${PORT}/simulator_home?ui_mode=auto"

SETTINGS_JSON='{
  "doctor_starting_amount": 30,
  "triage_starting_amount": 20,
  "bedside_starting_amount": 1,
  "preload_waiting_room_patients": 30,
  "fill_injuries": 0.3,
  "add_patient_threshold": 0,
  "seed": 20260522
}'

echo "[auto-bootstrap] save_simulation_settings ..."
post_json "http://127.0.0.1:${PORT}/save_simulation_settings/" "${SETTINGS_JSON}"

echo "[auto-bootstrap] start_backend ..."
post_json "http://127.0.0.1:${PORT}/start_backend/${ORIGIN}/${TARGET}/?headless=1" "{}"

echo "[auto-bootstrap] check live dashboard endpoint ..."
check_http_200_or_404 "http://127.0.0.1:${PORT}/api/live_dashboard/"

echo "[auto-bootstrap] run ${RUN_STEPS} ..."
post_json "http://127.0.0.1:${PORT}/send_sim_command/" "{\"command\":\"run ${RUN_STEPS}\"}"

echo "[auto-bootstrap] wait for movement files ..."
MOVEMENT_DIR="${ROOT_DIR}/environment/frontend_server/storage/${TARGET}/movement"
for i in $(seq 1 30); do
  if [[ -d "$MOVEMENT_DIR" ]] && ls "$MOVEMENT_DIR"/*.json >/dev/null 2>&1; then
    echo "[auto-bootstrap] movement detected."
    break
  fi
  sleep 1
done

echo "[auto-bootstrap] verify step contract ..."
cd "$ROOT_DIR"
python scripts/verify_step_contract.py --sim-code "${TARGET}"

echo "[auto-bootstrap] frontend: http://127.0.0.1:${PORT}/simulator_home?ui_mode=auto"
