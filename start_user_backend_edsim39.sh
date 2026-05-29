#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/home/jiawei2022/BME1325/week9"
FRONTEND_DIR="$ROOT_DIR/environment/frontend_server"
ENV_FILE="$ROOT_DIR/.env"
PORT="${1:-8002}"

echo "[user-backend] root=$ROOT_DIR"
echo "[user-backend] frontend_dir=$FRONTEND_DIR"
echo "[user-backend] conda_env=edsim39"
echo "[user-backend] target_port=$PORT"

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

export EDSIM_MODE=user
export ENABLE_LLM_AGENTS="${ENABLE_LLM_AGENTS:-1}"
export ENABLE_DOCTOR_RAG="${ENABLE_DOCTOR_RAG:-1}"
export MEMORY_V1_ENABLED="${MEMORY_V1_ENABLED:-1}"
export MEMORY_ENABLED="${MEMORY_ENABLED:-1}"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-frontend_server.settings}"
echo "[check] EDSIM_MODE=$EDSIM_MODE"
echo "[check] ENABLE_LLM_AGENTS=$ENABLE_LLM_AGENTS"
echo "[check] ENABLE_DOCTOR_RAG=$ENABLE_DOCTOR_RAG"
echo "[check] MEMORY_V1_ENABLED=$MEMORY_V1_ENABLED"

python - <<'PY'
from app_core.app.llm_adapter import llm_enabled
from app_core.clinical_kb.registry import registry_map
import os

enabled = bool(llm_enabled())
kb = registry_map()
keys = sorted(list(kb.keys()))
print(f"[check] llm_enabled={enabled}")
print(f"[check] rag_registry_count={len(keys)}")
print(f"[check] rag_registry_keys={keys}")
print(f"[check] EDSIM_MODE={os.getenv('EDSIM_MODE','')}")
print(f"[check] model_endpoint={os.getenv('EDSIM_MODEL_ENDPOINT','')}")
print(f"[check] model_name={os.getenv('EDSIM_MODEL','')}")

if not enabled:
    raise SystemExit("[fatal] LLM is not enabled. Please set EDSIM_MODEL_KEY / endpoint / model.")
if len(keys) == 0:
    raise SystemExit("[fatal] RAG registry is empty.")
PY

cd "$FRONTEND_DIR"
echo "[user-backend] starting django on 0.0.0.0:$PORT ..."
echo "[user-backend] user frontend url: http://127.0.0.1:$PORT/simulator_home?ui_mode=user"
exec python manage.py runserver "0.0.0.0:$PORT" --noreload
