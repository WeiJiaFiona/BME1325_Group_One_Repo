#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/home/jiawei2022/BME1325/week9"
FRONTEND_DIR="$ROOT_DIR/environment/frontend_server"
ENV_FILE="$ROOT_DIR/.env"
PORT="${1:-8010}"
ORIGIN="${2:-ed_sim_n5}"
TARGET="${3:-curr_sim}"

echo "[auto-backend] root=$ROOT_DIR"
echo "[auto-backend] frontend_dir=$FRONTEND_DIR"
echo "[auto-backend] conda_env=edsim39"
echo "[auto-backend] target_port=$PORT"
echo "[auto-backend] sim_origin=$ORIGIN sim_target=$TARGET"

if [[ -f ~/miniconda3/etc/profile.d/conda.sh ]]; then
  source ~/miniconda3/etc/profile.d/conda.sh
elif [[ -f ~/anaconda3/etc/profile.d/conda.sh ]]; then
  source ~/anaconda3/etc/profile.d/conda.sh
else
  source ~/.bashrc >/dev/null 2>&1
fi
conda activate edsim39

cd "$ROOT_DIR"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  source "$ENV_FILE"
  set +a
  echo "[check] loaded_env=.env"
else
  echo "[check] loaded_env=missing (.env not found)"
fi

export EDSIM_MODE=auto
export LLM_MODE="${LLM_MODE:-local_only}"
export EMBEDDING_MODE="${EMBEDDING_MODE:-local_only}"
export ENABLE_LLM_AGENTS="${ENABLE_LLM_AGENTS:-0}"
export ENABLE_DOCTOR_RAG="${ENABLE_DOCTOR_RAG:-0}"
export MEMORY_V1_ENABLED="${MEMORY_V1_ENABLED:-1}"
export MEMORY_ENABLED="${MEMORY_ENABLED:-1}"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-frontend_server.settings}"

echo "[check] EDSIM_MODE=$EDSIM_MODE"
echo "[check] LLM_MODE=$LLM_MODE"
echo "[check] EMBEDDING_MODE=$EMBEDDING_MODE"
echo "[check] ENABLE_LLM_AGENTS=$ENABLE_LLM_AGENTS"
echo "[check] ENABLE_DOCTOR_RAG=$ENABLE_DOCTOR_RAG"
echo "[check] MEMORY_V1_ENABLED=$MEMORY_V1_ENABLED"

cd "$FRONTEND_DIR"
echo "[auto-backend] starting django on 0.0.0.0:$PORT ..."
echo "[auto-backend] auto frontend url: http://127.0.0.1:$PORT/simulator_home?ui_mode=auto"
echo "[auto-backend] start backend after django is up:"
echo "curl -X POST \"http://127.0.0.1:$PORT/start_backend/$ORIGIN/$TARGET/?headless=1\""
echo "[auto-backend] run steps command example:"
echo "curl -X POST \"http://127.0.0.1:$PORT/send_sim_command/\" -H 'Content-Type: application/json' -d '{\"command\":\"run 100\"}'"
exec python manage.py runserver "0.0.0.0:$PORT" --noreload

