# Week6 Workflow

## 一、任务拆解（逐步执行）
1. 明确冻结范围：4 个 L1 接口、统一错误响应、事件追踪策略、handoff 状态机与 mock server 边界。
2. 固定统一错误响应结构与 `error_code` 枚举（全接口一致）。
3. 冻结 `/mode/user/encounter/start`：最小字段集 + 全量 `event_trace`。
4. 冻结 `/ed/handoff/request`：请求字段固定 + `handoff_requested` 事件。
5. 冻结 `/ed/handoff/complete`：完成字段固定 + 超时规则 + `handoff_completed` 事件。
6. 冻结 `/ed/queue/snapshot`：固定统计结构 + `trace_id`（不强制 `event_trace`）。
7. 明确 handoff 状态机合法转移与非法转移错误码。
8. ICU/Ward mock server 采用本地 HTTP，端点与契约对齐。
9. 建立测试矩阵：contract / malformed / state / integration / scenario。
10. 运行测试并修复（以冻结契约为准）。

---

## 二、接口冻结规格（Schema）

### 统一错误响应
- 结构：`{ error_code: str, message: str, field_errors: List[{field: str, error_code: str, message: str}] }`
- error_code 枚举：`INVALID_SCHEMA`, `MISSING_FIELD`, `INVALID_TYPE`, `NOT_FOUND`, `INVALID_STATE`

---

### POST `/mode/user/encounter/start`
**Request**
| field | required | type | notes |
|---|---|---|---|
| chief_complaint | yes | string | 不可为空 |
| vitals | yes | object | 必含 spo2, sbp；其余可选 |
| vitals.spo2 | yes | number | 0–100 |
| vitals.sbp | yes | number | mmHg |
| vitals.hr | no | number | bpm |
| vitals.rr | no | number | /min |
| vitals.temp | no | number | ℃ |
| vitals.dbp | no | number | mmHg |
| symptoms | no | array[string] | 默认 [] |
| patient_id | no | string | 默认 `patient-unknown` |
| arrival_mode | no | string | 枚举：`walk-in`, `ambulance` |

**Response**
| field | type | notes |
|---|---|---|
| patient_id | string | 回传或默认 |
| triage | object | `{acuity_ad, ctas_compat, zone, hooks}` |
| final_state | string | 终态 |
| state_trace | array[string] | 状态序列 |
| event_trace | array[event] | 全量 trace（见下） |

---

### POST `/ed/handoff/request`
**Request**
| field | required | type | notes |
|---|---|---|---|
| patient_id | yes | string | |
| acuity_ad | yes | string | 枚举：`A/B/C/D` |
| zone | yes | string | 枚举：`red/yellow/green` |
| stability | yes | string | 枚举：`stable/unstable/critical` |
| required_unit | yes | string | 枚举：`ICU/WARD` |
| clinical_summary | yes | string | |
| pending_tasks | yes | array[string] | 允许空数组 |

**Response**
| field | type | notes |
|---|---|---|
| handoff_ticket_id | string | 生成 |
| status | string | `REQUESTED` 或 `REJECTED` |
| reason | string | 空字符串或拒绝原因 |
| event_trace | array[event] | 只含 `handoff_requested` |

---

### POST `/ed/handoff/complete`
**Request**
| field | required | type | notes |
|---|---|---|---|
| handoff_ticket_id | yes | string | 必须存在 |
| receiver_system | yes | string | ICU / Ward |
| accepted_at | yes | string | ISO-8601 |
| receiver_bed | yes | string | 成功时必填，失败为空 |

**Response**
| field | type | notes |
|---|---|---|
| final_disposition_state | string | `COMPLETED`/`REJECTED`/`TIMEOUT` |
| transfer_latency_seconds | number | requested_at -> accepted_at |
| event_trace | array[event] | 只含 `handoff_completed` |

**receiver_bed 语义**
- 有值 ⇒ `COMPLETED`
- 空值 ⇒ `REJECTED`
- 超过超时阈值 ⇒ `TIMEOUT`

---

### GET `/ed/queue/snapshot`
**Response**
| field | type | notes |
|---|---|---|
| queues | object | triage/doctor/test/boarding |
| queues.triage | object | `{size:int, avg_wait_seconds:number}` |
| queues.doctor | object | 同上 |
| queues.test | object | 同上 |
| queues.boarding | object | 同上 |
| occupancy | object | 床位统计 |
| occupancy.beds_total | int | |
| occupancy.beds_occupied | int | |
| occupancy.beds_available | int | |
| occupancy.by_zone | object | `{zone: {occupied:int, available:int}}` |
| snapshot_time | string | ISO-8601 |
| trace_id | string | 仅引用（不返回 event_trace） |

> 说明：所有时间单位统一为 **seconds**；无法计算等待时间时返回 `0`。

---

## 三、event_trace 结构与写入策略
**event_trace 元素结构**
| field | type | notes |
|---|---|---|
| ts | string | ISO-8601 |
| event | string | 事件名 |
| state | string | 可选 |
| details | object | 可选 |

**写入策略**
- `/mode/user/encounter/start`：全量 trace（`triage_completed`, `hook_applied`, `state_transition`, `encounter_completed`）
- `/ed/handoff/request`：仅 `handoff_requested`
- `/ed/handoff/complete`：仅 `handoff_completed`
- `/ed/queue/snapshot`：不返回 event_trace，仅 `trace_id`

---

## 四、Handoff 状态机（Freeze）
**状态**
- INIT → REQUESTED → COMPLETED / REJECTED / TIMEOUT

**合法转移**
- INIT -> REQUESTED
- REQUESTED -> COMPLETED
- REQUESTED -> REJECTED
- REQUESTED -> TIMEOUT

**非法转移**
- 任意状态直接进入 COMPLETED/REJECTED/TIMEOUT 需返回 `INVALID_STATE`

**TIMEOUT 规则**
- `accepted_at - requested_at > timeout_seconds` 触发 TIMEOUT
- `timeout_seconds = 1800`

---

## 五、ICU/Ward Mock Server（契约对齐）
**Mock 边界**
- 本地 HTTP mock server（用于契约测试）

**Mock 端点**
- `POST /handoff/request`：输入同 `/ed/handoff/request`，输出 `{accepted, receiver_system, accepted_at, receiver_bed}`
- `POST /handoff/complete`：用于模拟完成确认（测试专用）

---

## 六、测试计划（Freeze 标准）
**Contract Tests**
- 四个接口输入最小字段集均能通过
- 响应字段必须包含冻结字段，不得缺失

**Malformed Payload Tests**
- 缺字段 -> `MISSING_FIELD`
- 类型错误 -> `INVALID_TYPE`
- payload 非对象 -> `INVALID_SCHEMA`

**State Tests**
- handoff_ticket_id 不存在 -> `NOT_FOUND`
- 非法状态转移 -> `INVALID_STATE`

**Integration Tests**
- mock server request → complete 全链路
- timeout 案例：accepted_at 超阈值 -> `TIMEOUT`
- queue snapshot 返回结构与 `trace_id`

**Scenario Tests**
- walk-in chest pain
- ambulance trauma
- dyspnea/fever

---

## 七、Assumptions (Explicit)
- vitals 必含 `spo2` 与 `sbp`
- timeout_seconds = 1800
- 所有时间单位 = seconds
- snapshot 不返回 event_trace，仅 `trace_id`
