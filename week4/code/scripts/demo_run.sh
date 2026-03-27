#!/usr/bin/env bash
set -euo pipefail
PYTHONPATH=backend uvicorn app.main:app --host 0.0.0.0 --port 18180
