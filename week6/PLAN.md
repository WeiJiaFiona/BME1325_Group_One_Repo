# Week6 L1 API Freeze 决策完备规划

## Summary
- 冻结 4 个 L1 接口的输入/输出契约、错误码、事件追踪结构与 handoff 状态机，并补齐完整测试标准。
- /mode/user 使用最小字段集，event_trace 全接口返回，ICU/Ward 使用本地 HTTP mock server 验证契约。

## Public API Schemas (Freeze)

**统一错误响应**
- 结构：`{ error_code: str, message: str, field_errors: List[{field: str, error_code: str, message: str}] }`
- error_code 枚举：`INVALID_SCHEMA`, `MISSING_FIELD`, `INVALID_TYPE`, `NOT_FOUND`, `INVALID_STATE`

---

**POST /mode/user/encounter/start**

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
| event_trace | array[event] | 见 event_trace 结构 |

---

**POST /ed/handoff/request**

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
| event_trace | array[event] | 只含 handoff_requested |

---

**POST /ed/handoff/complete**

**Request**
| field | required | type | notes |
|---|---|---|---|
| handoff_ticket_id | yes | string | 必须存在 |
| receiver_system | yes | string | 如 ICU / Ward |
| accepted_at | yes | string | ISO-8601 |
| receiver_bed | yes | string | 允许空表示拒绝 |

**Response**
| field | type | notes |
|---|---|---|
| final_disposition_state | string | `COMPLETED`/`REJECTED`/`TIMEOUT` |
| transfer_latency_seconds | number | requested_at -> accepted_at |
| event_trace | array[event] | 只含 handoff_completed |

---

**GET /ed/queue/snapshot**

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
| event_trace | array[event] | 只含 queue_snapshot_generated |

> 说明：`avg_wait_seconds` 无法计算时返回 `0`，不返回 null，避免 schema 漂移。

---

## Event Trace 结构与写入策略

**event_trace 元素结构**
| field | type | notes |
|---|---|---|
| ts | string | ISO-8601 |
| event | string | 事件名 |
| state | string | 可选，状态机相关事件时填 |
| details | object | 可选键值 |

**写入策略**
- `/mode/user/encounter/start`：全量 trace  
  事件序列包括 `triage_completed`、`hook_applied`(0..n)、`state_transition`(n)、`encounter_completed`
- `/ed/handoff/request`：仅 `handoff_requested`
- `/ed/handoff/complete`：仅 `handoff_completed`
- `/ed/queue/snapshot`：仅 `queue_snapshot_generated`（summary）

---

## Handoff 状态机（Freeze）

**状态**
- INIT → REQUESTED → COMPLETED / REJECTED / TIMEOUT

**合法转移**
- INIT -> REQUESTED
- REQUESTED -> COMPLETED
- REQUESTED -> REJECTED
- REQUESTED -> TIMEOUT

**非法转移**
- 任何状态直接跳到 COMPLETED/REJECTED/TIMEOUT 必须抛 `INVALID_STATE`

**TIMEOUT 规则**
- `accepted_at - requested_at > timeout_seconds` 触发 TIMEOUT  
- timeout_seconds 采用默认 `1800` 秒（30 min）

---

## ICU/Ward Mock Server（契约对齐）

**Mock 边界**
- 本地 HTTP mock server  
- 由 handoff 请求触发（或在测试中显式调用）  

**Mock 接口（测试专用）**
- `POST /mock/handoff/receive`  
  输入同 `/ed/handoff/request`  
  输出 `{accepted: bool, receiver_system: str, accepted_at: ISO, receiver_bed: str}`

---

## Test Plan（Freeze 标准）

**Contract Tests**
- 四个接口输入最小字段集均能通过  
- 响应字段必须包含冻结字段，不得缺失

**Malformed Payload Tests**
- 缺字段 -> `MISSING_FIELD`
- 字段类型错误 -> `INVALID_TYPE`
- payload 非对象 -> `INVALID_SCHEMA`

**State Tests**
- handoff_ticket_id 不存在 -> `NOT_FOUND`
- 非法状态转移 -> `INVALID_STATE`

**Integration Tests**
- mock server 接收 request → complete 走通  
- timeout 案例：人为设置 accepted_at 超阈值 → TIMEOUT  
- queue snapshot 返回结构与 event_trace summary

**Scenario Tests**
- walk-in chest pain  
- ambulance trauma  
- dyspnea/fever  
均验证 triage、state_trace、event_trace 完整性

---

## Assumptions (Explicit)
- vitals 必含 `spo2` 与 `sbp`  
- timeout_seconds = 1800  
- queue wait time 缺失时用 0  
