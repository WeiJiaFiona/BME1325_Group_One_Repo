# Week13 ED–ICU Interface Merge Summary

- 本次实现范围是 ED-side interface merge，不是 ICU full runtime merge。
- 新增 `downstream_units` 子系统，用 stub ICU/Ward 床位替代 admission 后随机 boarding duration。
- `Patient.do_disposition()` 现在会在 admission 命中后分流到 `ward` 或 `ICU`，创建 transfer request，并根据 broker 返回 `accepted` 或 `pending`。
- `pending` 患者进入 `ADMITTED_BOARDING`，保留旧兼容字段，并在 `next_check_minute` 自动重试。
- `accepted` 患者保留 transfer turnaround；`boarding_timeout` 只对 `pending` 状态生效。
- `sim_status.json` 新增 downstream capacity / occupancy / transfer counters / boarding patient counters。
- probe 脚本在 `scripts/run_ed_icu_handoff_probe.py`，输出落在 `analysis/ed_icu_handoff_probe_report.*`。
