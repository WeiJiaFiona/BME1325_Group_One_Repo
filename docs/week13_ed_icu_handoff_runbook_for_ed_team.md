# Week13 ED–ICU Handoff Runbook for ED Team

## Goal

在不接 ICU service 的情况下，验证 ED disposition → transfer → boarding/exit → metrics 闭环是否成立。

## Commands

```bash
python -m pytest tests/backend/test_downstream_units.py -q
python -m pytest tests/backend/test_transfer_broker.py -q
python -m pytest tests/backend/test_ed_icu_handoff_metrics.py -q
python -m pytest tests/backend/test_failure_metrics.py -q
python -m pytest tests/analysis/test_success_metrics.py -q
python -m pytest tests --collect-only -q
python scripts/run_ed_icu_handoff_probe.py
```

## What To Check

- `analysis/transfer_requests.jsonl` 是否出现 transfer request / response 日志
- `sim_status.json` 是否出现 `downstream` 与 `resources.downstream_*`
- `pending` patient 是否保留在 `ADMITTED_BOARDING`
- `accepted` patient 是否在 transfer turnaround 后离开 ED
- `failure_reason_counts.boarding_timeout` 是否随 `icu_capacity` 降低而上升

## Scope Boundary

- 不接 ICU FastAPI / Postgres / Redis
- 不改 frontend playback / movement schema
- 不模拟 ICU 内部治疗
