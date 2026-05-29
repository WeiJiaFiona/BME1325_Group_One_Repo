#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/home/jiawei2022/BME1325/week9"
PORT="${1:-8010}"
ORIGIN="${2:-ed_sim_n5}"
TARGET="${3:-curr_sim}"
RUN_STEPS="${4:-20}"
LOCAL_NO_PROXY="127.0.0.1,localhost,0.0.0.0,::1"
LOG_DIR="$ROOT_DIR/runtime_data/logs"
DJANGO_LOG="$LOG_DIR/auto_django_${PORT}.log"

mkdir -p "$LOG_DIR"

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

echo "[all-in-one] stop old processes on port ${PORT} ..."
pkill -f "manage.py runserver 0.0.0.0:${PORT}" || true
pkill -f "manage.py runserver 127.0.0.1:${PORT}" || true
pkill -f "reverie.py --frontend_ui yes --origin ${ORIGIN} --target ${TARGET}" || true

echo "[all-in-one] start django in background ..."
cd "$ROOT_DIR/environment/frontend_server"
nohup bash -lc "
  source ~/.bashrc >/dev/null 2>&1 || true
  conda activate edsim39
  cd '$ROOT_DIR'
  source '$ROOT_DIR/.env' 2>/dev/null || true
  export EDSIM_MODE=auto
  export LLM_MODE=\${LLM_MODE:-local_only}
  export EMBEDDING_MODE=\${EMBEDDING_MODE:-local_only}
  export ENABLE_LLM_AGENTS=\${ENABLE_LLM_AGENTS:-0}
  export ENABLE_DOCTOR_RAG=\${ENABLE_DOCTOR_RAG:-0}
  export MEMORY_V1_ENABLED=\${MEMORY_V1_ENABLED:-1}
  export MEMORY_ENABLED=\${MEMORY_ENABLED:-1}
  cd '$ROOT_DIR/environment/frontend_server'
  python manage.py runserver 0.0.0.0:${PORT} --noreload
" >"$DJANGO_LOG" 2>&1 &

echo "[all-in-one] wait django ready ..."
for i in $(seq 1 40); do
  code="$(curl --noproxy "$LOCAL_NO_PROXY" -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${PORT}/simulator_home?ui_mode=auto" || true)"
  if [[ "$code" == "200" ]]; then
    echo "[all-in-one] django ready (http=200)"
    break
  fi
  sleep 1
  if [[ "$i" -eq 40 ]]; then
    echo "[fatal] django not ready on port ${PORT}, last_http=${code}"
    echo "[hint] check log: $DJANGO_LOG"
    exit 1
  fi
done

echo "[all-in-one] run bootstrap pipeline ..."
cd "$ROOT_DIR"
bash "$ROOT_DIR/bootstrap_auto_sim_edsim39.sh" "$PORT" "$ORIGIN" "$TARGET" "$RUN_STEPS"

echo "[all-in-one] done."
echo "[all-in-one] frontend: http://127.0.0.1:${PORT}/simulator_home?ui_mode=auto"
echo "[all-in-one] django log: $DJANGO_LOG"

