# EDMAS 接入 FullView 统一前端与院内转诊调联系统集成方案

## 0. 集成目标

本阶段目标是将 `/home/jiawei2022/BME1325/week9` 下的 EDMAS 急诊系统接入 `/home/jiawei2022/BME1325/BME_1325_Full_Vis` 下的 FullView 全医院统一前端与调度架构。

核心目标不是重写 EDMAS 或 FullView，而是在保持双方已有规则和映射尽量不变的前提下，实现：

1. EDMAS 内部继续负责急诊分诊、问诊、医生/护士 agent、检查、出院/住院/ICU 判断。
2. FullView 继续负责全医院地图展示、跨科室房间/床位状态、移动事件审核、event-log 和动画播放。
3. EDMAS 在产生“检查、转 ICU、转住院、出院、返回急诊”等 disposition decision 后，通过标准 request 调用 FullView。
4. FullView 接收 request 后，根据已有 event-rules、room-state、bed availability 和 transfer rules 判断是否允许移动。
5. FullView accepted 后写入 event-log，前端地图自动播放跨科室移动。
6. FullView rejected 后 EDMAS 保持原状态，并记录阻塞原因，例如 ICU 无床、住院无床、转运资源不足。

本集成应尽量采用 adapter 层方式，不直接破坏 EDMAS 当前 auto/user 逻辑，也不直接修改 FullView 前端渲染逻辑。

---

## 1. 不应修改的内容

本次集成应遵守以下约束：

1. 不修改或清理集群已有 VPN/proxy 环境变量。
2. 不让 EDMAS 直接写 FullView 的 `patients.json`、`room-state.json`、`event-log.json`。
3. 不让 EDMAS 直接控制 FullView canvas 上的人物坐标。
4. 不重写 FullView 已有 `event-rules` 语义。
5. 不改变 FullView 已有 `room_id`、`event_id` 命名，除非发现规则文件缺失。
6. 不强行把 EDMAS auto mode 和 user mode 的内部状态统一成一套；只在 adapter 层做最小映射。
7. 不把临床指南做成真实诊疗系统；只用于仿真中的转诊/转运触发规则和安全展示逻辑。

---

## 2. 需要优先确认的一致性问题

### 2.1 EDMAS 侧已知事实

根据 `system_interpretation.md`，EDMAS 当前至少存在两条主线：

* Auto mode / 仿真主线：

  * 由 Django 前端向 backend 发送命令；
  * `reverie/backend_server/reverie.py` 读取 `temp_storage/commands/cmd_*.json`；
  * 推进 step；
  * 输出 `storage/<sim_code>/movement/*.json`、`environment/*.json` 和 `sim_status.json`；
  * 具有真实地图 movement、床位、分诊、检查、出院、住院 boarding 逻辑；
  * 但 ICU/ward 的真实空间与跨科移动尚未在 EDMAS 地图内实现。

* User mode / 规则对话主线：

  * 经 Django `/mode/user/*` 暴露接口；
  * 核心逻辑在 `app_core/app/api_v1.py`、`app_core/app/mode_user.py` 和 `app_core/rule_core/*`；
  * 已有 calling_nurse、doctor、bedside_nurse 文本流程；
  * 已有 handoff ticket 和 HIS event；
  * 但它更接近“流程编排与对话状态机”，不是地图驱动仿真。

这意味着接入 FullView 时，不应该让 FullView 依赖 EDMAS 内部 movement 文件，而应让 EDMAS 在关键节点主动向 FullView 发送结构化 request。

### 2.2 FullView 侧需要确认的文件

请 Codex 在 `/home/jiawei2022/BME1325/BME_1325_Full_Vis` 中逐一确认以下文件，不要凭记忆修改：

| 文件                                       | 需要确认的问题                                                                                      |
| ---------------------------------------- | -------------------------------------------------------------------------------------------- |
| `README.md`                              | FullView 启动方式、统一前端定位                                                                         |
| `docs/fullview-integration-manual.md`    | department 接入原则、ID 标准、adapter 约定                                                             |
| `full_view/API.md`                       | `/api/hospital/snapshot`、`/api/hospital/events/move`、`/api/hospital/patients/admit` 的请求/响应格式 |
| `full_view/HOSPITAL_CORE_STANDARD.md`    | patient、staff、room、bed、event 的标准字段                                                           |
| `full_view/DATA_ALIGNMENT_STANDARD.md`   | 外部系统字段如何对齐 FullView                                                                          |
| `full_view/map-config.json`              | 急诊、ICU、住院、检查、电梯、交接区房间 ID                                                                     |
| `full_view/backend-data/patients.json`   | 当前 patient 数据结构                                                                              |
| `full_view/backend-data/staff.json`      | 当前 staff 数据结构                                                                                |
| `full_view/backend-data/room-state.json` | 床位、队列、房间资源、转运资源状态                                                                            |
| `full_view/backend-data/event-log.json`  | accepted/rejected event 结构                                                                   |
| `full_view/dev-server.py`                | 后端 API 实现、move request 校验、event-log 写入                                                       |
| `full_view/hospital-api.js`              | 前端如何请求 snapshot/events/move                                                                  |
| `full_view/main.js`                      | 前端如何轮询 event-log 并播放 animationPlan                                                           |
| `full_view/console.js`                   | 控制台如何人工发送 admit/move request                                                                 |
| `full_view/event-rules/transfer.json`    | ED→ICU、ED→Ward、Ward→ICU、ICU→Ward 等跨科规则                                                       |
| `full_view/event-rules/emergency.json`   | 急诊内部移动规则                                                                                     |
| `full_view/event-rules/icu.json`         | ICU 接收入科、转出、检查规则                                                                             |
| `full_view/event-rules/ward.json`        | 住院接收、转 ICU、出院规则                                                                              |
| `rules/transfer-rules.md`                | 跨科规则的文字说明                                                                                    |
| `rules/emergency-rules.md`               | 急诊内部流程规则                                                                                     |
| `rules/icu-rules.md`                     | ICU 内部规则                                                                                     |
| `rules/ward-rules.md`                    | 住院部内部规则                                                                                      |
| `rules/resource-and-blocking-rules.md`   | 床位/资源不足时的阻塞规则                                                                                |

---

## 3. 集成总体架构

推荐架构如下：

```text
EDMAS internal state
    |
    | 1. triage / doctor / disposition agent 判断下一步
    v
EDMAS disposition decision
    |
    | 2. EDMAS -> FullView adapter 转换 ID / room / event / context
    v
POST FullView /api/hospital/events/move
    |
    | 3. FullView 后端检查 event rule + room + bed + transfer resource
    v
accepted / rejected
    |
    | 4a. accepted: 写 event-log，前端播放 animation
    | 4b. rejected: 返回 reasonCode，EDMAS 维持原状态
    v
EDMAS 更新内部记录 / user chat 提示 / auto status
```

推荐新增模块：

```text
/home/jiawei2022/BME1325/week9/app_core/integration/fullview_client.py
/home/jiawei2022/BME1325/week9/app_core/integration/fullview_mapping.py
/home/jiawei2022/BME1325/week9/app_core/integration/disposition_rules.py
/home/jiawei2022/BME1325/week9/app_core/integration/fullview_config.py
```

如果 EDMAS 代码风格不适合新建 `app_core/integration/`，也可以放在：

```text
/home/jiawei2022/BME1325/week9/app_core/app/fullview_client.py
```

但建议单独建 integration 目录，避免污染已有 user mode 和 auto mode 逻辑。

---

## 4. ID 映射策略

### 4.1 原则

EDMAS 当前存在 ID 分裂：

| 来源                     | 示例                             | 问题                               |
| ---------------------- | ------------------------------ | -------------------------------- |
| auto persona name      | `Patient 1`                    | 只是显示名，可能重置                       |
| auto memory patient_id | `Patient_1`                    | 与前端显示名不完全一致                      |
| user mode patient_id   | `patient-ab12cd` 或 `Patient 1` | 来源不稳定                            |
| HIS patient_id         | `P-xxxxxxxx`                   | 更适合作为 FullView patient_id        |
| user/HIS encounter_id  | `enc-...` 或 `E-...`            | 更适合作为 FullView case/encounter id |

### 4.2 推荐方案

不改 EDMAS 内部 patient name。只在 adapter 层生成 FullView ID。

```text
FullView patient_id = EDMAS HIS patient_id，优先使用 P-xxxxxxxx
FullView context.edmas_case_id = EDMAS encounter_id，优先使用 E-... 或 enc-...
FullView patient.name = EDMAS display_name，例如 Patient 1
```

如果当前 auto mode 没有 HIS patient_id，则新增一个轻量映射文件：

```text
/home/jiawei2022/BME1325/week9/runtime_data/fullview/patient_id_map.json
```

示例：

```json
{
  "Patient 1": {
    "fullview_patient_id": "P-ER-001",
    "edmas_display_name": "Patient 1",
    "edmas_auto_id": "Patient_1",
    "edmas_encounter_id": "auto_auto_curr_sim_20260521_062827_Patient_1"
  }
}
```

Codex 需要确认是否已有类似 mapping 文件。如果没有，新增该文件和读写工具。

---

## 5. Room 映射策略

### 5.1 不重命名 EDMAS 房间

EDMAS 内部仍使用：

| EDMAS room/location      | 语义                  |
| ------------------------ | ------------------- |
| `waiting room`           | 候诊                  |
| `triage room`            | 分诊                  |
| `major injuries zone`    | 中重症区                |
| `minor injuries zone`    | 轻中症区                |
| `trauma room`            | 抢救/危重               |
| `diagnostic room`        | 检查                  |
| `exit`                   | 离院                  |
| `doctor_assessment_zone` | user mode 虚拟医生接诊区   |
| `vitals_station`         | user mode 虚拟生命体征测量区 |
| `triage_waiting_area`    | user mode 虚拟候诊区     |

### 5.2 Adapter 层映射到 FullView

Codex 需要根据 FullView 的 `map-config.json` 和 `event-rules/*.json` 最终确认 room_id。初步建议如下：

| EDMAS location        | FullView room_id 候选                           | 备注                                            |
| --------------------- | --------------------------------------------- | --------------------------------------------- |
| `waiting room`        | `ed_waiting`                                  | 如果 FullView 使用 `ED_WAITING`，以实际 map-config 为准 |
| `triage room`         | `ed_triage`                                   | 分诊区                                           |
| `major injuries zone` | `ed_observation` 或 `ed_major`                 | 以 FullView emergency rules 为准                 |
| `minor injuries zone` | `ed_minor` 或 `ed_waiting`                     | 轻症区                                           |
| `trauma room`         | `ed_red_resus`                                | 抢救区，ED→ICU 推荐 from_room                       |
| `diagnostic room`     | `diagnostic_center` 或 `ed_diagnostic`         | 以 FullView 规则为准                               |
| `exit`                | `hospital_exit` 或 `ed_exit`                   | 出院                                            |
| ICU 接收                | `icu_admission`                               | FullView 跨科规则中应已存在                            |
| ICU 床位                | `icu_beds_a` / `icu_beds_b` / `icu_isolation` | FullView 分配                                   |
| 住院接收                  | `ward_admission`                              | FullView 跨科规则中应已存在                            |
| 住院病房                  | `resp_ward` / `card_ward` / `neuro_ward` 等    | 根据 context.specialty 选择                       |

注意：如果 FullView 规则已经规定 `TRANSFER_ED_TO_ICU` 的 `fromRoomId` 应为 `ed_red_resus` 或 `ed_observation`，EDMAS adapter 必须转换到这些 room_id，而不是要求 FullView 接受 EDMAS 的原始 location 名称。

---

## 6. Event 映射策略

EDMAS 内部不一定有明确 event_id，因此 adapter 需要根据状态变化选择 FullView event_id。

| EDMAS 事件/状态变化 | FullView event_id                                     | 是否优先使用                 |
| ------------- | ----------------------------------------------------- | ---------------------- |
| 新患者进入急诊       | `/api/hospital/patients/admit` 或 `ED_PATIENT_ARRIVAL` | 优先 admit/upsert        |
| 等待到分诊         | `ED_REGISTRATION_TO_TRIAGE_OR_WAITING`                | 如 FullView 已自动处理，可不重复发 |
| 分诊到医生         | `ED_WAITING_TO_CONSULT_ROOM`                          | 可选，若只做跨科展示可先不接         |
| 医生开检查         | `ED_TO_DIAGNOSTIC_MOVE`                               | 推荐接                    |
| 检查返回          | `ED_DIAGNOSTIC_RETURN`                                | 推荐接                    |
| 急诊转 ICU       | `TRANSFER_ED_TO_ICU`                                  | 必须接                    |
| 急诊转住院         | `TRANSFER_ED_TO_WARD`                                 | 必须接                    |
| 急诊出院          | `ED_PATIENT_EXIT_HOSPITAL`                            | 推荐接                    |
| ICU 转住院       | `TRANSFER_ICU_TO_WARD`                                | 后续跨科联调                 |
| 住院转 ICU       | `TRANSFER_WARD_TO_ICU`                                | 后续跨科联调                 |
| MDT 会诊        | `TRANSFER_CASE_TO_MDT`                                | 可选                     |

Codex 必须检查 FullView 里真实存在的 event_id。如果 `ED_TO_ICU_MOVE` 和 `TRANSFER_ED_TO_ICU` 同时存在，应优先使用跨部门标准事件 `TRANSFER_ED_TO_ICU`，避免重复语义。

---

## 7. 临床转诊/转运规则设计

### 7.1 规则来源

规则来源分三层：

1. EDMAS 已有 CTAS / A-D / 症状关键词 / vitals 规则。
2. 国家或行业急诊流程/转诊规范中的高层原则。
3. FullView 现有 `event-rules` 和资源阻塞规则。

不要在本阶段实现复杂真实诊断。只实现“仿真可解释”的 disposition gate。

### 7.2 严重程度分层字段

在 EDMAS adapter context 中增加：

```json
{
  "clinical_risk": {
    "ctas": 2,
    "acuity_ad": "B",
    "mews": 6,
    "severity_layer": "high_risk",
    "transfer_need_level": 2,
    "red_flags": ["possible_acs"],
    "requires_life_support_during_transfer": false,
    "transport_level": "level_2",
    "escort_required": true,
    "equipment": ["portable_monitor", "oxygen"]
  }
}
```

### 7.3 ED -> ICU 触发规则

建议最小规则：

满足任一条件，可触发 `TRANSFER_ED_TO_ICU`：

1. CTAS 1 或 A 级。
2. CTAS 2 或 B 级，并且存在持续监护/抢救需求。
3. MEWS >= 9。
4. 生命体征极高危，例如明显低血压伴灌注不足、严重呼吸异常、严重意识障碍、恶性心律失常等。
5. 疑似急性冠脉综合征、肺栓塞、主动脉夹层、颅高压/脑出血等不能排除，且需要 ICU 监护。
6. 医生/规则明确给出 `needs_icu_monitoring = true`。
7. FullView ICU 有床且 ICU 接收确认。

若 ICU 无床或 ICU 拒收：

```text
FullView rejected -> EDMAS 保持患者在 ED 原位置 -> 记录 ICU_BLOCKED -> 可进入 ED boarding / observation
```

### 7.4 ED -> Ward 触发规则

建议最小规则：

满足以下条件，可触发 `TRANSFER_ED_TO_WARD`：

1. 病情稳定，不需要 ICU 级监护。
2. 医生认为需要住院治疗或继续观察。
3. CTAS C/3 或部分 B/2 经过急诊处理后稳定。
4. 需要普通病房专科接收，例如呼吸、心内、神内、普外等。
5. FullView 住院部有匹配床位，且 ward 接收确认。

若住院无床：

```text
FullView rejected -> EDMAS 保持患者在 ED observation / boarding -> 记录 WARD_BLOCKED
```

### 7.5 ED -> Diagnostic 触发规则

满足以下条件，可触发 `ED_TO_DIAGNOSTIC_MOVE`：

1. 医生已开立检查。
2. 患者可安全转运。
3. 检查房可用或允许排队。
4. 若患者不稳定，应先留在 ED red/resus 或 observation，不进行普通检查转运。

建议 `context` 中包含：

```json
{
  "diagnostic_type": "ct",
  "reason": "rule-out intracranial bleeding",
  "return_expected": true
}
```

检查后触发：

```text
ED_DIAGNOSTIC_RETURN
```

### 7.6 ED -> Discharge 触发规则

满足以下条件，可触发 `ED_PATIENT_EXIT_HOSPITAL`：

1. 症状缓解或医生判断无需继续急诊处理。
2. 生命体征稳定。
3. 未触发 ICU/住院/进一步检查。
4. 已给出离院建议或复诊提示。

### 7.7 转运分级与装备

在 FullView request context 中加入转运准备字段：

| 风险等级    | 适用场景            | transport              | escortRoles                        | equipment                                         |
| ------- | --------------- | ---------------------- | ---------------------------------- | ------------------------------------------------- |
| level_1 | 极高危、需生命支持、抢救中转运 | stretcher              | `["ed_nurse", "doctor", "porter"]` | `["portable_monitor", "oxygen", "transport_bag"]` |
| level_2 | 高危但短时可转运        | stretcher 或 wheelchair | `["ed_nurse", "porter"]`           | `["portable_monitor"]`                            |
| level_3 | 稳定住院/检查         | wheelchair 或 walking   | `["porter"]`                       | `[]`                                              |
| level_4 | 平诊离院或门诊转诊       | walking                | `[]`                               | `[]`                                              |

注意：FullView 实际动画使用的 transport/equipment 应以 `event-rules/*.json` 为准。EDMAS 只在 `context` 中提供建议，不直接覆盖 FullView 规则。

---

## 8. EDMAS 需要新增的 adapter

### 8.1 fullview_config.py

新增配置：

```python
FULLVIEW_BASE_URL = os.getenv("FULLVIEW_BASE_URL", "http://127.0.0.1:8000")
FULLVIEW_TIMEOUT = float(os.getenv("FULLVIEW_TIMEOUT", "5"))
FULLVIEW_ENABLED = os.getenv("FULLVIEW_ENABLED", "0") == "1"
```

注意不要改 VPN/proxy。请求 localhost 时在 requests 中设置不走代理：

```python
proxies = {"http": None, "https": None}
```

或在启动脚本中设置：

```bash
export NO_PROXY=127.0.0.1,localhost,0.0.0.0,::1
export no_proxy=127.0.0.1,localhost,0.0.0.0,::1
```

### 8.2 fullview_mapping.py

实现：

```python
def get_fullview_patient_id(edmas_patient) -> str:
    ...

def map_edmas_location_to_fullview_room(location: str, context: dict) -> str:
    ...

def map_disposition_to_fullview_event(decision: dict) -> str:
    ...

def build_fullview_context(edmas_state: dict, decision: dict) -> dict:
    ...
```

### 8.3 fullview_client.py

实现：

```python
class FullViewClient:
    def __init__(self, base_url: str):
        ...

    def snapshot(self) -> dict:
        ...

    def admit_patient(self, payload: dict) -> dict:
        ...

    def move_patient(self, payload: dict) -> dict:
        ...

    def ensure_patient_synced(self, edmas_patient: dict) -> dict:
        ...
```

核心调用：

```python
POST /api/hospital/events/move
```

payload 示例：

```json
{
  "requestId": "edmas-E-20260612-0001-transfer-icu",
  "source": "edmas",
  "operatorId": "edmas.disposition_agent",
  "eventId": "TRANSFER_ED_TO_ICU",
  "patientId": "P-ER-001",
  "fromRoomId": "ed_red_resus",
  "toRoomId": "icu_admission",
  "context": {
    "edmas_case_id": "E-20260612-0001",
    "chief_complaint": "sudden severe headache with vomiting",
    "ctas": 2,
    "acuity_ad": "B",
    "mews": 6,
    "reason": "possible intracranial emergency; needs monitored transfer",
    "transport_level": "level_2",
    "requires_escort": true,
    "suggested_equipment": ["portable_monitor", "oxygen"]
  }
}
```

### 8.4 disposition_rules.py

实现最小规则函数：

```python
def determine_transfer_decision(encounter: dict, patient_state: dict) -> dict:
    """
    Return one of:
    - {"target": "ICU", "event_id": "TRANSFER_ED_TO_ICU", ...}
    - {"target": "WARD", "event_id": "TRANSFER_ED_TO_WARD", ...}
    - {"target": "DIAGNOSTIC", "event_id": "ED_TO_DIAGNOSTIC_MOVE", ...}
    - {"target": "DISCHARGE", "event_id": "ED_PATIENT_EXIT_HOSPITAL", ...}
    - {"target": "NONE"}
    """
```

要求：

1. 优先使用 EDMAS 已有 triage 结果。
2. 如果已有 `handoff ticket`，不要重复造一个新的临床判断。
3. 如果 user mode 已经决定 A/B -> ICU，C -> WARD，可先复用该逻辑，但补充 vitals/red flags/transport context。
4. auto mode 如已有 `ADMITTED_BOARDING`，可映射为 `TRANSFER_ED_TO_WARD` 或 `WARD_BLOCKED`，由 FullView 资源判断是否成功。
5. 如果没有足够信息，不触发跨科转运，只记录 `target = NONE`。

---

## 9. FullView 需要检查或最小补充的接口

### 9.1 已有接口优先

优先使用 FullView 已有：

```http
GET /api/hospital/snapshot
GET /api/hospital/events?after=...
POST /api/hospital/patients/admit
POST /api/hospital/events/move
```

### 9.2 是否需要 patient upsert

如果 EDMAS 已经有患者，并且不希望通过 FullView `/patients/admit` 创建新患者，则需要 Codex 检查 FullView 是否已有 upsert 接口。

如果没有，建议最小新增：

```http
POST /api/hospital/patients/upsert
```

用途：

1. 将 EDMAS 已存在患者同步到 FullView。
2. 不触发 FullView 默认 registration -> triage 路径。
3. 保留 EDMAS 当前所在房间映射。

payload 示例：

```json
{
  "requestId": "edmas-sync-P-ER-001",
  "source": "edmas",
  "patient": {
    "patientId": "P-ER-001",
    "name": "Patient 1",
    "departmentId": "emergency",
    "status": "IN_CONSULTATION",
    "roomId": "ed_observation",
    "clinical": {
      "edmas_case_id": "E-20260612-0001",
      "chief_complaint": "acute headache",
      "ctas": 3
    }
  }
}
```

如果 FullView 现有 API 已能通过 `/patients/admit` 满足测试，则先不要新增 upsert。

### 9.3 是否需要 CORS

如果 EDMAS 后端 Python 调用 FullView，不需要 CORS。

如果 EDMAS 浏览器前端直接请求 FullView，需要在 FullView `dev-server.py` 中补充 CORS：

```http
Access-Control-Allow-Origin: *
Access-Control-Allow-Headers: Content-Type
Access-Control-Allow-Methods: GET, POST, OPTIONS
```

本阶段推荐后端 server-to-server 调用，避免前端跨域复杂化。

---

## 10. FullView 转诊规则检查与最小修改

### 10.1 优先检查现有规则

Codex 先检查：

```text
/home/jiawei2022/BME1325/BME_1325_Full_Vis/full_view/event-rules/transfer.json
/home/jiawei2022/BME1325/BME_1325_Full_Vis/rules/event-rules/transfer.json
/home/jiawei2022/BME1325/BME_1325_Full_Vis/rules/transfer-rules.md
```

必须确认以下 event 是否存在：

```text
TRANSFER_ED_TO_ICU
TRANSFER_ED_TO_WARD
TRANSFER_ICU_TO_WARD
TRANSFER_WARD_TO_ICU
ED_TO_DIAGNOSTIC_MOVE
ED_DIAGNOSTIC_RETURN
ED_PATIENT_EXIT_HOSPITAL
```

若存在，不要重命名。

若不存在，按现有 JSON schema 增补，不要改变其他规则。

### 10.2 ED -> ICU 规则需要确认

`TRANSFER_ED_TO_ICU` 至少应包含：

```json
{
  "eventId": "TRANSFER_ED_TO_ICU",
  "movement": {
    "from": "ed_red_resus or ed_observation or current_ed_room",
    "to": "icu_admission",
    "via": ["ed_handoff", "elevator_1", "elevator_3"],
    "transport": "stretcher",
    "escortRequired": true,
    "escortRoles": ["ed_nurse", "porter"],
    "equipment": ["portable_monitor", "oxygen", "transport_bag"],
    "resourcePolicy": {
      "targetBedRequired": true,
      "releaseSourceBed": true
    },
    "failurePolicy": {
      "keepPatientInSourceRoom": true
    }
  }
}
```

### 10.3 ED -> Ward 规则需要确认

`TRANSFER_ED_TO_WARD` 至少应包含：

```json
{
  "eventId": "TRANSFER_ED_TO_WARD",
  "movement": {
    "from": "ed_observation or current_ed_room",
    "to": "ward_admission",
    "via": ["ed_handoff", "elevator_1", "elevator_5"],
    "transport": "wheelchair or stretcher",
    "resourcePolicy": {
      "targetBedRequired": true,
      "releaseSourceBed": true
    },
    "failurePolicy": {
      "keepPatientInSourceRoom": true
    }
  }
}
```

### 10.4 Diagnostic 规则需要确认

`ED_TO_DIAGNOSTIC_MOVE` 与 `ED_DIAGNOSTIC_RETURN` 应支持：

1. 患者从 ED major/minor/observation 去检查；
2. 检查期间是否保留原 ED bed；
3. 检查结束返回原 ED bed 或医生诊区；
4. 检查资源忙时 rejected 或 queued。

如果 FullView 当前规则未保留 source bed，应按 FullView 的 bed-retain 标准补充 `retainSourceBed: true`。

---

## 11. EDMAS 触发 request 的位置

Codex 需要在 EDMAS 中检查并选择最小插入点。

### 11.1 User mode 插入点

优先检查：

```text
/home/jiawei2022/BME1325/week9/app_core/app/api_v1.py
```

重点函数：

```text
start_encounter
user_mode_chat_turn
request_handoff
complete_handoff
user_mode_session_status
```

建议插入：

1. 当 user mode 产生 `handoff target = ICU` 时，调用 FullView `TRANSFER_ED_TO_ICU`。
2. 当 user mode 产生 `handoff target = WARD` 时，调用 FullView `TRANSFER_ED_TO_WARD`。
3. 当 user mode `DONE` 且建议离院时，调用 FullView `ED_PATIENT_EXIT_HOSPITAL`。
4. 如果只是医生建议检查，但还未进入真实检查流程，暂不触发 FullView；等 EDMAS 产生明确 diagnostic decision 后再发。

### 11.2 Auto mode 插入点

优先检查：

```text
/home/jiawei2022/BME1325/week9/reverie/backend_server/persona/persona_types/patient.py
/home/jiawei2022/BME1325/week9/reverie/backend_server/persona/persona_types/doctor.py
/home/jiawei2022/BME1325/week9/reverie/backend_server/persona/persona_types/bedside_nurse.py
/home/jiawei2022/BME1325/week9/reverie/backend_server/reverie.py
```

建议插入：

1. `Patient.do_disposition` 后，如果状态变为检查，触发 `ED_TO_DIAGNOSTIC_MOVE`。
2. 检查返回后，触发 `ED_DIAGNOSTIC_RETURN`。
3. 状态变为 `ADMITTED_BOARDING` 时，触发 `TRANSFER_ED_TO_WARD`。
4. 状态变为出院/离开时，触发 `ED_PATIENT_EXIT_HOSPITAL`。
5. ICU 目前 EDMAS auto 没有真实空间，只有当 doctor/disposition 明确给出 ICU target 时才触发 `TRANSFER_ED_TO_ICU`。

为避免每个 step 重复发送 request，必须记录已发送事件：

```text
runtime_data/fullview/sent_events.jsonl
```

或在 patient scratch 中记录：

```json
{
  "fullview_sent_events": [
    "TRANSFER_ED_TO_WARD:E-xxx"
  ]
}
```

---

## 12. 请求幂等与失败处理

### 12.1 requestId 规则

所有 request 必须有唯一且可重复推导的 `requestId`。

格式：

```text
edmas-{encounter_id}-{event_id}-{step}
```

示例：

```text
edmas-E-20260612-abcd-TRANSFER_ED_TO_ICU-114
```

若同一个 request 重试，requestId 不变。FullView 如果支持幂等，应返回同一结果；如果不支持，EDMAS 自己需要避免重复发送。

### 12.2 accepted 处理

FullView accepted 时，EDMAS 记录：

```json
{
  "fullview_status": "accepted",
  "eventSeq": 124,
  "eventId": "TRANSFER_ED_TO_ICU",
  "target": "ICU"
}
```

同时在 user mode 中可以提示：

```text
已向全院调度系统发送 ICU 转运请求，已获得接收，患者将由急诊转运至 ICU。
```

### 12.3 rejected 处理

FullView rejected 时，EDMAS 不应强行修改患者位置。

记录：

```json
{
  "fullview_status": "rejected",
  "reasonCode": "NO_BED_AVAILABLE",
  "message": "ICU no bed available"
}
```

user mode 回复可用：

```text
目前已发起 ICU 转运申请，但 ICU 暂无可用床位。患者会继续留在急诊监护/观察区域，等待 ICU 接收或进一步处理。
```

auto mode 则保持 `ADMITTED_BOARDING` 或 ED observation 状态。

---

## 13. 集成测试计划

### T0：FullView 启动与健康检查

```bash
cd /home/jiawei2022/BME1325/BME_1325_Full_Vis/full_view
python dev-server.py 8000
```

测试：

```bash
curl -i 'http://127.0.0.1:8000/api/hospital/snapshot'
```

目标：

```text
HTTP 200
返回 floors / rooms / patients / staff / eventSeq
```

### T1：FullView console 手动验证现有规则

打开：

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/console.html
```

用 console 手动发送：

```text
TRANSFER_ED_TO_ICU
TRANSFER_ED_TO_WARD
ED_TO_DIAGNOSTIC_MOVE
ED_DIAGNOSTIC_RETURN
```

目标：

1. accepted 时地图有动画；
2. rejected 时返回明确 reasonCode；
3. snapshot 中 patient room/status 与地图一致。

### T2：EDMAS 启动

启动 EDMAS：

```bash
cd /home/jiawei2022/BME1325/week9
bash start_user_frontend_8011.sh
bash start_user_backend_edsim39.sh
```

或使用当前已经验证可用的启动脚本。

确认：

```bash
curl --noproxy '127.0.0.1,localhost,0.0.0.0,::1' \
  'http://127.0.0.1:8011/mode/user/session/status'
```

目标：

```text
ok=true
```

### T3：EDMAS -> FullView admit/upsert

如果使用 FullView admit：

```bash
curl -X POST 'http://127.0.0.1:8000/api/hospital/patients/admit' \
  -H 'Content-Type: application/json' \
  -d '{
    "requestId": "edmas-admit-test-001",
    "source": "edmas",
    "operatorId": "edmas.integration_test",
    "department": "emergency",
    "context": {
      "edmas_case_id": "E-test-001",
      "reason": "test patient from EDMAS"
    }
  }'
```

如果新增 upsert，则测试：

```bash
curl -X POST 'http://127.0.0.1:8000/api/hospital/patients/upsert' \
  -H 'Content-Type: application/json' \
  -d '{
    "requestId": "edmas-upsert-test-001",
    "source": "edmas",
    "patient": {
      "patientId": "P-ER-TEST-001",
      "name": "Patient 1",
      "departmentId": "emergency",
      "status": "IN_CONSULTATION",
      "roomId": "ed_observation",
      "clinical": {
        "edmas_case_id": "E-test-001",
        "chief_complaint": "acute headache",
        "ctas": 3
      }
    }
  }'
```

目标：

```text
FullView snapshot 中能看到该患者。
```

### T4：EDMAS 发送 ED -> Diagnostic

```bash
curl -X POST 'http://127.0.0.1:8000/api/hospital/events/move' \
  -H 'Content-Type: application/json' \
  -d '{
    "requestId": "edmas-E-test-001-ED_TO_DIAGNOSTIC_MOVE-001",
    "source": "edmas",
    "operatorId": "edmas.doctor_agent",
    "eventId": "ED_TO_DIAGNOSTIC_MOVE",
    "patientId": "P-ER-TEST-001",
    "fromRoomId": "ed_observation",
    "toRoomId": "diagnostic_center",
    "context": {
      "edmas_case_id": "E-test-001",
      "diagnostic_type": "ct",
      "reason": "rule out dangerous cause"
    }
  }'
```

目标：

1. accepted=true；
2. eventSeq 增加；
3. 地图播放去检查动画；
4. snapshot 中患者在检查区域或处于检查中。

### T5：EDMAS 发送 ED -> ICU

```bash
curl -X POST 'http://127.0.0.1:8000/api/hospital/events/move' \
  -H 'Content-Type: application/json' \
  -d '{
    "requestId": "edmas-E-test-002-TRANSFER_ED_TO_ICU-001",
    "source": "edmas",
    "operatorId": "edmas.disposition_agent",
    "eventId": "TRANSFER_ED_TO_ICU",
    "patientId": "P-ER-TEST-001",
    "fromRoomId": "ed_red_resus",
    "toRoomId": "icu_admission",
    "context": {
      "edmas_case_id": "E-test-002",
      "ctas": 1,
      "acuity_ad": "A",
      "reason": "needs ICU monitoring",
      "transport_level": "level_1",
      "requires_escort": true,
      "suggested_equipment": ["portable_monitor", "oxygen", "transport_bag"]
    }
  }'
```

目标：

1. accepted=true；
2. statusUpdates 中有 targetReserved 或 bedRoomId；
3. 地图显示从 ED 到 ICU；
4. ICU 床位占用增加；
5. ED 原床释放。

### T6：EDMAS 发送 ED -> Ward

```bash
curl -X POST 'http://127.0.0.1:8000/api/hospital/events/move' \
  -H 'Content-Type: application/json' \
  -d '{
    "requestId": "edmas-E-test-003-TRANSFER_ED_TO_WARD-001",
    "source": "edmas",
    "operatorId": "edmas.disposition_agent",
    "eventId": "TRANSFER_ED_TO_WARD",
    "patientId": "P-ER-TEST-002",
    "fromRoomId": "ed_observation",
    "toRoomId": "ward_admission",
    "context": {
      "edmas_case_id": "E-test-003",
      "ctas": 3,
      "acuity_ad": "C",
      "reason": "stable but requires inpatient treatment",
      "target_specialty": "respiratory"
    }
  }'
```

目标：

1. accepted=true；
2. 住院床位占用增加；
3. ED observation 床位释放；
4. 患者 status 变为 ADMITTED 或 FullView 当前标准中对应状态。

### T7：资源阻塞测试

人为填满 ICU 或 ward 床位后再次发送 ED -> ICU 或 ED -> Ward。

目标：

1. accepted=false；
2. reasonCode 明确；
3. patient 留在原房间；
4. 原床不释放；
5. EDMAS 记录 blocked 状态。

### T8：EDMAS 自动触发测试

用 EDMAS user mode 输入高危 case，例如：

```text
我突然胸痛，出冷汗，喘不上气
```

期望：

1. EDMAS 规则分诊产生高 acuity；
2. doctor 或 disposition agent 产生 ICU/monitoring decision；
3. EDMAS adapter 自动发送 FullView request；
4. FullView accepted 后地图移动；
5. user mode chat 提示已发起/已完成转运。

### T9：event-log 与 snapshot 一致性

测试：

```bash
curl 'http://127.0.0.1:8000/api/hospital/events?after=0'
curl 'http://127.0.0.1:8000/api/hospital/snapshot'
```

目标：

1. event-log 中有 EDMAS source；
2. eventSeq 单调递增；
3. snapshot 中患者最终 room/status 与最后 accepted event 一致。

---

## 14. Codex 执行步骤

### Phase 1：只读核查

不要改代码。输出核查结果：

1. FullView 当前有哪些 event_id。
2. FullView 当前有哪些 room_id。
3. `TRANSFER_ED_TO_ICU`、`TRANSFER_ED_TO_WARD`、`ED_TO_DIAGNOSTIC_MOVE` 是否可直接使用。
4. FullView 是否已有 patient upsert。
5. EDMAS 是否已有可复用 HIS patient_id。
6. EDMAS user/auto 各自何处产生 ICU/WARD/DISCHARGE/DIGNOSTIC decision。

输出文件：

```text
/home/jiawei2022/BME1325/week9/fullview_integration_audit.md
```

### Phase 2：新增 EDMAS adapter

新增：

```text
app_core/integration/fullview_config.py
app_core/integration/fullview_mapping.py
app_core/integration/fullview_client.py
app_core/integration/disposition_rules.py
```

要求：

1. 默认 `FULLVIEW_ENABLED=0`，避免影响现有系统。
2. 只有设置 `FULLVIEW_ENABLED=1` 后才发送真实 request。
3. request 失败不能中断 EDMAS 原流程。
4. 所有 accepted/rejected 记录到日志。

### Phase 3：接入 user mode

在 `api_v1.py` 的 handoff / disposition 处调用 adapter。

要求：

1. ICU handoff -> `TRANSFER_ED_TO_ICU`。
2. Ward handoff -> `TRANSFER_ED_TO_WARD`。
3. DONE/discharge -> `ED_PATIENT_EXIT_HOSPITAL`。
4. 不重复发送同一个 event。

### Phase 4：接入 auto mode

在 auto patient disposition 处调用 adapter。

要求：

1. 检查 -> `ED_TO_DIAGNOSTIC_MOVE`。
2. 检查返回 -> `ED_DIAGNOSTIC_RETURN`。
3. `ADMITTED_BOARDING` -> `TRANSFER_ED_TO_WARD`。
4. 出院 -> `ED_PATIENT_EXIT_HOSPITAL`。
5. ICU 仅在明确规则给出时触发。

### Phase 5：FullView 最小补充

只有在确认缺失时才补：

1. 缺 patient upsert 时新增 `/api/hospital/patients/upsert`。
2. 缺 transfer event 时补 `event-rules/transfer.json`。
3. 缺 room_id 时先确认是否应使用现有等价房间；不要随意新增地图房间。
4. 如要新增房间，必须同步 `map-config.json`、`room-state.json`、`event-rules`。

### Phase 6：联调测试

按 T0–T9 执行，记录每个 curl 返回和地图表现。

输出：

```text
/home/jiawei2022/BME1325/week9/fullview_integration_test_report.md
```

---

## 15. 最终验收标准

集成完成需要满足：

1. EDMAS 不依赖直接改 FullView JSON 文件。
2. EDMAS 可以通过 adapter 向 FullView 发送 move request。
3. FullView 可以根据 event-rules accepted/rejected。
4. accepted 后地图动画播放。
5. rejected 后患者不移动，EDMAS 能收到 reasonCode。
6. ED -> Diagnostic、Diagnostic -> ED、ED -> ICU、ED -> Ward、ED -> Discharge 至少各有一个可测试闭环。
7. ICU/ward 无床时能阻塞。
8. event-log 与 snapshot 一致。
9. user mode 和 auto mode 原本功能不被破坏。
10. VPN/proxy 设置未被修改。

---

## 16. 最小可交付文件清单

Codex 最终应交付：

```text
/home/jiawei2022/BME1325/week9/fullview_integration_audit.md
/home/jiawei2022/BME1325/week9/app_core/integration/fullview_config.py
/home/jiawei2022/BME1325/week9/app_core/integration/fullview_mapping.py
/home/jiawei2022/BME1325/week9/app_core/integration/fullview_client.py
/home/jiawei2022/BME1325/week9/app_core/integration/disposition_rules.py
/home/jiawei2022/BME1325/week9/fullview_integration_test_report.md
```

如果修改 FullView，则额外记录：

```text
/home/jiawei2022/BME1325/BME_1325_Full_Vis/full_view/dev-server.py
/home/jiawei2022/BME1325/BME_1325_Full_Vis/full_view/event-rules/*.json
/home/jiawei2022/BME1325/BME_1325_Full_Vis/full_view/map-config.json
/home/jiawei2022/BME1325/BME_1325_Full_Vis/full_view/backend-data/*.json
```

但 FullView 修改应尽量少，优先通过 EDMAS adapter 与现有 FullView API 完成集成。

---

## 17. 给 Codex 的最终任务摘要

请在不破坏现有 EDMAS 和 FullView 映射规则的前提下，实现 EDMAS -> FullView 的标准 request adapter。先只读核查 FullView 现有 API、event-rules、room_id、patient/status schema，再新增 EDMAS adapter，将 EDMAS 的 disposition decision 转换为 FullView 的 `/api/hospital/events/move` 请求。临床转诊判断只做高层仿真规则：ED->ICU、ED->Ward、ED->Diagnostic、ED->Discharge。转运规则参考 CTAS/MEWS/生命体征危险分层和院内分级转运流程，但不要做真实诊疗系统。最后用 curl 和地图前端验证 accepted/rejected、event-log、snapshot、床位占用和动画播放。
