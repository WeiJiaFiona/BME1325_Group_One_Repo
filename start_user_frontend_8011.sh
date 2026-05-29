#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/jiawei2022/BME1325/week9"
PORT="${1:-8011}"

cd "$ROOT"
source ~/.bashrc >/dev/null 2>&1 || true
conda activate edsim39

export NO_PROXY="127.0.0.1,localhost,0.0.0.0,::1"
export no_proxy="127.0.0.1,localhost,0.0.0.0,::1"

pkill -f "manage.py runserver" || true
pkill -f "reverie.py --frontend_ui yes" || true

rm -f environment/frontend_server/temp_storage/commands/cmd_*.json || true
rm -f environment/frontend_server/temp_storage/curr_step.json || true

set -a
source "$ROOT/.env"
set +a

export EDSIM_MODE=user
export ENABLE_LLM_AGENTS=1
export ENABLE_DOCTOR_RAG=1
export MEMORY_V1_ENABLED=1
export MEMORY_ENABLED=1

cd "$ROOT/environment/frontend_server"
python manage.py runserver "127.0.0.1:${PORT}" --noreload

