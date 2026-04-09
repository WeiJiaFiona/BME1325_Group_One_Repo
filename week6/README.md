# Week6 README

本文件用于周内交接与协作，概述 Week6 已完成的工作、接口冻结范围、测试重点，以及常用 PowerShell 指令。

---

## 1. 本周目标（Week6 User Mode + L1 API Freeze）
- 冻结 4 个 L1 接口的输入/输出契约（schema）、错误码与事件追踪结构。
- 完成 handoff 状态机与本地 mock server 以支持契约验证。
- 建立 contract / malformed / state / integration / scenario 测试闭环。

---

## 2. 已完成内容（可对外同步）

### 2.1 L1 接口冻结
- `/mode/user/encounter/start`
  - 最小字段集，必填 `chief_complaint` + `vitals.spo2` + `vitals.sbp`。
  - 响应包含 `patient_id / triage / final_state / state_trace / event_trace`。
  - event_trace 为全量轨迹。

- `/ed/handoff/request`
  - 固定字段：`patient_id, acuity_ad, zone, stability, required_unit, clinical_summary, pending_tasks`。
  - 响应：`handoff_ticket_id, status, reason, event_trace`。
  - event_trace 仅 `handoff_requested`。

- `/ed/handoff/complete`
  - 固定字段：`handoff_ticket_id, receiver_system, accepted_at, receiver_bed`。
  - 响应：`final_disposition_state, transfer_latency_seconds, event_trace`。
  - event_trace 仅 `handoff_completed`。

- `/ed/queue/snapshot`
  - 固定统计结构：`queues + occupancy + snapshot_time + trace_id`。
  - 不强制返回 event_trace，避免过度工程化。

### 2.2 统一错误响应
- 结构：`{error_code, message, field_errors}`。
- 固定 error_code：
  - `INVALID_SCHEMA`
  - `MISSING_FIELD`
  - `INVALID_TYPE`
  - `NOT_FOUND`
  - `INVALID_STATE`

### 2.3 Handoff 状态机
- 状态：`INIT -> REQUESTED -> COMPLETED / REJECTED / TIMEOUT`
- 超时规则：`accepted_at - requested_at > 1800s`。
- 非法转移返回 `INVALID_STATE`。

### 2.4 ICU/Ward Mock Server（HTTP）
- 本地 mock server，端点：
  - `POST /handoff/request`
  - `POST /handoff/complete`
- 供测试使用，确保与 “mock server” 描述一致。

---

## 3. 目录结构（本周相关）
```
week6/
  week5_system/
    app/                 # L1 接口逻辑层与 schema
    queue_state_primitives/  # queue snapshot
    rule_core/           # Week5 规则核心复用
  tests/                 # Week6 新增测试
  week6_workflow.md      # 冻结版方案文档
```

---

## 4. 常用 PowerShell 指令

### 进入 Week6 并运行测试
```powershell
cd D:\projects\BME1325Spring2026\BME1325_Group_One_Repo\week6
python -m pytest -q
```

### 指定 mock server（环境变量）
```powershell
$env:HANDOFF_MOCK_URL = "http://127.0.0.1:8001/handoff/request"
```

---

## 5. 测试重点（What we validate）

### Contract Tests
- 4 个接口输入最小字段集能通过
- 响应字段完整且稳定

### Malformed Payload Tests
- 缺字段 -> `MISSING_FIELD`
- 类型错误 -> `INVALID_TYPE`
- payload 非对象 -> `INVALID_SCHEMA`

### State Tests
- handoff_ticket_id 不存在 -> `NOT_FOUND`
- 非法状态转移 -> `INVALID_STATE`

### Integration Tests
- mock server request -> complete 全链路
- timeout case（accepted_at 超阈值）
- queue snapshot 返回结构 + trace_id

### Scenario Tests
- walk-in chest pain
- ambulance trauma
- dyspnea / fever

---

## 6. 说明与注意事项
- 本周接口冻结为“函数级入口”，未绑定真实 HTTP 路由。
- 如果需要前端/外部直接访问，需要在上层 FastAPI 中增加路由绑定。
- 所有时间单位统一为 seconds。
- `receiver_bed` 为空代表拒绝，非空代表成功。

---

## 7. 参考文档
- `week6/week6_workflow.md`
- `week5/edmas/EDMAS_week5_12_workflow.md`
