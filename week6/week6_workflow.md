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

## 合并工作（与队友 week6 对齐）
状态：已完成

A. week6/tests/ 对比
仅你这边有（队友没有）
test_handoff_integration.py
test_malformed_payloads.py
test_mode_user_contracts.py
test_queue_snapshot.py
仅队友有（你这边没有）
test_week5_multi_agent_surge.py
test_week6_l1_api.py
test_week6_user_mode_chat.py
两边都有但内容不同
test_week5_scope.py
差异点：
队友版本期望 acuity_ad = B，你这边期望 A
队友版本增加字段断言：green_channel、level_1_4
队友版本新增测试：test_yellow_zone_wait_cap_hook（包含 max_wait_minutes 和 wait_cap_30m）

B. week6/week5_system/ 对比
仅你这边有（队友没有）
app/handoff.py
app/mock_server.py
app/schema.py
queue_state_primitives/snapshot.py
仅队友有（你这边没有）
agents/agents.md
app/api_v1.py
app/surge_sim.py
两边都有但内容不同
rule_core/triage_policy.py
rule_core/state_machine.py
rule_core/encounter.py
app/mode_user.py

### 已合入的队友文件（按你的“方案 B”）
- `week5_system/app/api_v1.py`
- `week5_system/app/surge_sim.py`
- `week5_system/agents/agents.md`
- `tests/test_week6_l1_api.py`
- `tests/test_week6_user_mode_chat.py`
- `tests/test_week5_multi_agent_surge.py`
- `tests/test_week5_scope.py`（已用队友版本覆盖）

### 两边都有但内容不同的文件对比（关键差异表）
| 文件 | 我方版本（合并前） | 队友版本 | 当前处理 |
|---|---|---|---|
| `tests/test_week5_scope.py` | 胸痛+出汗期望 `acuity_ad=A` / `ctas_compat=1`；FAST 期望 A；无 wait_cap 测试 | 胸痛/FAST 期望 `acuity_ad=B`；增加 `green_channel`、`level_1_4` 断言；新增 `yellow_zone_wait_cap_hook` | **已覆盖为队友版本**，后续需确认与 Week6 L1 Freeze 是否一致 |
| `week5_system/rule_core/triage_policy.py` | 仅 CN_AD/CTAS 及 `zone`，hooks 只有 `green_channel`、`abnormal_vitals` | 增加 `level_1_4`、`green_channel` 布尔、`required_resources_count`、`max_wait_minutes`、`wait_cap_30m`；zone 按 level 映射 | **暂保留我方版本**，待决定是否合并队友扩展字段 |
| `week5_system/rule_core/encounter.py` | triage 输出仅含 `acuity_ad/ctas_compat/zone/hooks` | triage 输出增加 `level_1_4/green_channel/required_resources_count/max_wait_minutes` | **暂保留我方版本**，需与 triage_policy 对齐后统一 |
| `week5_system/app/mode_user.py` | 有 schema 校验 + 错误码 + `event_trace` | 直接透传（无校验、无 event_trace） | **保留我方版本**（符合 Week6 Freeze） |
| `week5_system/rule_core/state_machine.py` | 逻辑一致（差异主要在格式） | 逻辑一致 | **无需处理** |

> 注：差异表记录“我方版本”为合并前的逻辑状态，已可在 Git 历史中追溯。

### 合并建议（推荐策略）
**总体建议**
- `app/mode_user.py`、`app/schema.py`、`app/handoff.py`、`queue_state_primitives/snapshot.py` 以 **Zry 版本为主**（符合 Week6 L1 Freeze 与错误码规范）。
- `app/api_v1.py`、`app/surge_sim.py`、`agents/agents.md` 以 **Jw 版本为主**（前端/接口交接与扩展内容）。
- `rule_core/triage_policy.py` 与 `rule_core/encounter.py` 采用 **合并（Combine）**：保留 Zry 的确定性流程与 hooks，同时合入 Jw 的 level_1_4/资源数/等待上限字段，以满足队友测试与接口输出。
- `tests/test_week5_scope.py` 以 **Jw 版本为准**，因为与扩展字段（`level_1_4`、`max_wait_minutes`、`wait_cap_30m`）联动，避免接口层缺字段。

### 逐文件推荐（含是否 Combine）
| 文件 | 推荐方式 | 推荐理由 | 下一步动作 |
|---|---|---|---|
| `tests/test_week5_scope.py` | 采用 Jw | 与扩展 triage 字段联动，覆盖 yellow wait cap | 若 triage_policy 合并扩展字段，则保留该测试 | 
| `rule_core/triage_policy.py` | Combine | Zry 保证基础 triage；Jw 增强 level/资源/等待上限 | 合并数据结构与 hooks，输出 superset triage 字段 |
| `rule_core/encounter.py` | Combine | 输出 triage 字段需对齐 triage_policy | 扩展 triage 输出字段为 superset |
| `app/mode_user.py` | 保留 Zry | 含 schema 校验 + error_code + event_trace | 保留 Zry 逻辑，不移除校验 |
| `rule_core/state_machine.py` | 保留任一 | 逻辑一致，差异仅格式 | 无需处理 |

---

### 面向 Codex 的合并说明（逐文件最终功能 + Zry/Jw 贡献）
**1) `week5_system/rule_core/triage_policy.py`**
- 最终功能为：
  - 同时输出 `acuity_ad/ctas_compat/zone/hooks` 与 `level_1_4/required_resources_count/max_wait_minutes/green_channel`，并在 yellow zone 触发 `wait_cap_30m`。
- Zry（我）实现了：
  - 最小 CN_AD + CTAS_COMPAT 分诊逻辑，`abnormal_vitals`/`green_channel` hooks。
- Jw（队友）实现了：
  - `level_1_4`、`required_resources_count`、`max_wait_minutes`、`wait_cap_30m`，以及 zone 按 level 映射。
- 合并动作：
  - 以 Jw 的数据结构为主，保留 Zry 的 `abnormal_vitals` 与基础 hooks；输出字段为 **superset**。

**2) `week5_system/rule_core/encounter.py`**
- 最终功能为：
  - 统一构造 triage 输出字典，包含所有扩展字段；状态机逻辑保持确定性。
- Zry（我）实现了：
  - 标准转移流程与最小 triage 输出。
- Jw（队友）实现了：
  - triage 输出扩展字段映射。
- 合并动作：
  - 输出 triage 字段 **扩展为 superset**，与 triage_policy 保持一致。

**3) `week5_system/app/mode_user.py`**
- 最终功能为：
  - 入口 payload 校验 + 错误码返回 + event_trace 输出；可容纳扩展 triage 字段。
- Zry（我）实现了：
  - schema 校验、标准错误响应、event_trace 生成。
- Jw（队友）实现了：
  - 基础透传版本（无校验/无 event_trace）。
- 合并动作：
  - **保留 Zry 版本**；确保 triage 字段不被过滤（直接透传 superset）。

**4) `tests/test_week5_scope.py`**
- 最终功能为：
  - 验证扩展 triage 字段（`level_1_4/green_channel/max_wait_minutes/wait_cap_30m`）与既有 hooks。
- Zry（我）实现了：
  - 早期 A 级期望与最小字段断言。
- Jw（队友）实现了：
  - B 级期望 + wait cap 测试与扩展字段断言。
- 合并动作：
  - **采用 Jw 版本**，并确保 triage_policy/encounter 输出支持这些断言。

**5) `week5_system/rule_core/state_machine.py`**
- 最终功能为：
  - 维持统一 encounter 状态机（合法转移 + escalation hooks）。
- Zry/Jw 均实现：
  - 逻辑一致，仅格式差异。
- 合并动作：
  - 无需处理。

### 合并状态（已完成）
- `rule_core/triage_policy.py`：已合并为 superset 输出（level_1_4 / max_wait_minutes / wait_cap_30m 等）。
- `rule_core/encounter.py`：已对齐 triage 输出字段并完成合并。
- `tests/test_week5_scope.py`：已采用队友版本并通过测试。
- `app/mode_user.py`：保留 Zry 版本（含校验与 event_trace）。
