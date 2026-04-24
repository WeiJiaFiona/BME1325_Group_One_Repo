# Week 8 Merge System (Auto + User) README

本目录为 Week 8 合并后的可运行系统根目录：

- 路径：`/home/jiawei2022/BME1325/week8/merge`
- 支持双模式：`auto` 与 `user`
- `user` 模式支持：LLM 问诊 + doctor-only RAG + Memory v1（可审计/可回放）

## 本周已实现内容 (Week 8)

### 1) 合并后的双 Mode 运行边界

- 运行时 mode 由后端环境变量 `EDSIM_MODE` 决定（权威）。
- 前端 `ui_mode` 仅影响 UI 展示，不允许切换运行时 mode。

### 2) User Mode：LLM + RAG（医生）

- 医生问诊在硬规则边界内接入 LLM：
  - LLM 负责：问句措辞/解释（patient-facing explanation）、部分抽取辅助。
  - 硬规则仍负责：`next_slot`、安全底线（safety floor）、处置（disposition）、doctor planner 决策权归属不变。
- Doctor-only RAG：
  - 只影响“解释/措辞/证据引用”，不改变 `next_slot` 与 disposition。

### 3) Memory v1：事件流 + 摘要 + 快照 + 审计（user hooks）

Memory v1 存储在 `MEMORY_V1_ROOT` 下（默认写到本项目的 `runtime_data/memory`）。

当前写入类型：

- `events.jsonl`：关键流程事件流水（encounter_started / vitals_measured / triage_completed / doctor checkpoints / disposition / handoff 等）。
- `audit.jsonl`：每次 memory 读写操作的审计流水（成功/失败/错误信息）。
- `current/`：每个 run 的 CurrentEncounterSummary（快速读取“当前态摘要”）。
  - 已补充写入：`latest_doctor_findings.chief_complaint` 与 `latest_doctor_findings.latest_note`。
- `snapshots/`：handoff requested/completed 的不可变快照。

Fail-open 机制：

- memory 任意异常不得阻断临床流程（吞异常继续跑）。

### 4) 本周测试覆盖与结果

已在合并系统中通过的测试（以本地执行为准）：

- Memory substrate 单测（schema/storage/service/retrieval）
- `tests_week8`：user hooks 集成测试 + ablation（`MEMORY_V1_ENABLED=0/1`）+ fail-open 测试
- `tests_user`：user mode 现有回归测试

运行方式见下方“测试命令”。

## 如何运行 (Auto / User)

### 0) 环境建议

推荐 conda 环境：`edsim39`

### 1) 运行 User Mode 后端（LLM + RAG + Memory）

在 `edsim39` 中启动 Django：

```bash
cd /home/jiawei2022/BME1325/week8/merge/environment/frontend_server
source ~/.bashrc
conda activate edsim39

export EDSIM_MODE=user
export ENABLE_LLM_AGENTS=1
export MEMORY_V1_ENABLED=1
export MEMORY_V1_ROOT=/home/jiawei2022/BME1325/week8/merge/runtime_data/memory

python manage.py runserver 0.0.0.0:8012
```

前端地址：

- `http://127.0.0.1:8012/simulator_home?ui_mode=user`

注意：若浏览器出现 `502`，通常是本机代理没有 bypass localhost。请将 `127.0.0.1/localhost` 加入 no-proxy。

### 2) 运行 Auto Mode 后端

Auto mode 的拉起方式同上，只需切换：

```bash
export EDSIM_MODE=auto
```

本周重点优先保证 user mode memory hooks，auto mode memory hooks 暂未深度集成（按 Week 8 分工约束）。

## 前端 demo 对话建议（用于验证 LLM/RAG/Memory 写入）

User mode 推荐用以下路径触发“解释 + 继续问诊 + disposition/handoff”：

1. `你好`
2. `我头很疼，9级，刚刚突然开始的，还恶心想吐。`
3. `我这种头痛要做什么影像？CT还是MRI？`
4. 按医生问题回答数轮（例如 `今天上午10点左右`、`加重`、`有晕厥` 等）

完成后检查 memory 是否写入：

- `runtime_data/memory/events.jsonl`
- `runtime_data/memory/current/user/<run_id>/*.json`
- `runtime_data/memory/snapshots/user/<run_id>/**.json`（若触发 handoff）

## 测试命令

从项目根目录运行：

```bash
cd /home/jiawei2022/BME1325/week8/merge

# Week8 集成测试（注意：pytest.ini 未默认收录 tests_week8，需显式跑）
pytest -q tests_week8

# Memory substrate 单测
pytest -q tests/backend/test_memory_schema.py \
         tests/backend/test_memory_storage.py \
         tests/backend/test_memory_service.py \
         tests/backend/test_memory_retrieval.py

# user mode 回归
pytest -q tests_user
```

## 已知问题 / 待升级内容 (Backlog)

- Memory 仍偏“流程/状态”日志：
  - 已补充 `chief_complaint` 与 `latest_note`，但更完整的“医生评估记录（impression/plan）”仍需要进一步结构化与标准化。
- Auto mode memory hooks：
  - 本周按约束未做深度集成，后续可选仅做最小安全 hook（如 `boarding_timeout`），再逐步扩展。
- 端口与代理：
  - `0.0.0.0` 访问在浏览器里可能被代理/策略影响，建议使用 `127.0.0.1` 并设置 no-proxy。

## Week 9 目标（Safety/Ethics + Recovery）

### Target

- 风险控制可测试、可审计（testable + auditable）。

### Implementation Plan

- 高风险建议阻断规则（dangerous advice block rules）。
- PHI 脱敏与审计追踪（PHI redaction + audit trail）。
- LLM/工具超时降级：fallback-to-rule 模式，确保 workflow 不崩溃。

### Test Plan

- 危险用药剂量注入攻击（dangerous dosage suggestion injection）。
- 敏感信息泄漏尝试（sensitive info leakage attempt）。
- encounter 进行中发生超时（timeout during active encounter）。

### Robustness Evidence

- 安全降级但不破坏流程归属边界：不改变 planner ownership / next_slot / safety floor / disposition。

### Milestone

- safety 测试套件 + 审计日志通过 review。

