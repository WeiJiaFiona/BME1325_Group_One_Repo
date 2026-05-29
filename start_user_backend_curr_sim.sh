#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-8011}"
ORIGIN="${2:-ed_sim_n5}"
TARGET="${3:-curr_sim}"

export NO_PROXY="127.0.0.1,localhost,0.0.0.0,::1"
export no_proxy="127.0.0.1,localhost,0.0.0.0,::1"

curl --noproxy "127.0.0.1,localhost,0.0.0.0,::1" -X POST \
  "http://127.0.0.1:${PORT}/save_simulation_settings/" \
  -H "Content-Type: application/json" \
  -d '{"doctor_starting_amount":30,"triage_starting_amount":20,"bedside_starting_amount":1,"preload_waiting_room_patients":30,"fill_injuries":0.3,"add_patient_threshold":0,"seed":20260522}'

curl --noproxy "127.0.0.1,localhost,0.0.0.0,::1" -X POST \
  "http://127.0.0.1:${PORT}/start_backend/${ORIGIN}/${TARGET}/?headless=1"

curl --noproxy "127.0.0.1,localhost,0.0.0.0,::1" -X POST \
  "http://127.0.0.1:${PORT}/send_sim_command/" \
  -H "Content-Type: application/json" \
  -d '{"command":"run 1"}'

