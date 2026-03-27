# 急诊科室多智能体系统（MAS）Methodology 规划文档

> 用途：本文件面向 Codex 的 planning / brainstorm 阶段，作为“模拟医院急诊科室 MAS 系统”的统一设计上下文。
>
> 文档目标不是直接给出可部署临床系统，而是把**急诊规范文件中的场景约束**与**EDSim / Generative Agents 的 MAS 实现思想**整合成一份可执行的软件设计蓝图。
>
> 建议 Codex 使用方式：先据此生成 `domain_model / agent_specs / event_bus / state_machine / tool_interfaces / metrics_schema / simulation_config` 等模块，再逐步实现最小可运行版本（MVP）。

---

# 1. 设计目标与边界

## 1.1 目标

构建一个**急诊科室多智能体仿真系统**，用于：

1. 模拟患者从到达急诊到离院/住院/转诊的全过程；
2. 模拟分诊、抢救、诊疗、检查、会诊、留观、住院衔接等关键流程；
3. 在不直接把 LLM 用作最终临床诊断器的前提下，用 MAS 表达：
   - 角色协作；
   - 动态队列与资源竞争；
   - 空间布局对流程的影响；
   - 绿色通道与危急重症中断机制；
   - 不同 staffing / bed / diagnostic capacity 配置下的系统表现；
4. 为后续 what-if 分析提供仿真沙箱，例如：
   - 增减床位；
   - 调整护士/医生数量；
   - 调整影像与检验响应时间；
   - 增加急诊快诊区；
   - 调整住院床位周转与 boarding 时间。

## 1.2 边界

- **本系统优先是运营与流程仿真系统**，不是独立执业医疗系统。
- **LLM 不应直接承担最终医学分诊分级、最终诊断或最终用药决策**；这些环节在 MVP 中应由规则、模板、预设 clinical profile 或人工定义状态驱动。
- 可以让 LLM 负责：
  - 自然语言交互；
  - 上下文推理；
  - 计划拆解；
  - 任务排序建议；
  - 交接班摘要；
  - 病程与流程解释；
  - 仿真角色行为生成。

---

# 2. 急诊科室的职责、适用场景与整体定位

## 2.1 急诊科的功能定位

急诊科是医院中独立设置的临床二级学科，是急诊医疗服务体系的重要组成部分，也是突发公共事件医疗救援的核心节点。它负责急危重症、创伤、慢性病急性发作、公共卫生事件中的紧急医疗救护，并在部分医院承担院前急救衔接功能。

## 2.2 什么情况下应进入急诊

下列情形应视为急诊核心服务对象：

- 心脏骤停、呼吸骤停；
- 急性冠脉综合征、严重心律失常、高血压急症、高血压危象、急性心衰；
- 脑卒中、癫痫持续状态；
- 急性呼吸衰竭、重症哮喘、大咯血；
- 休克、重症感染、急性中毒；
- 上消化道出血、急腹症、电解质酸碱平衡紊乱；
- 严重创伤及其致命并发症（气道梗阻、血气胸、失血性休克等）；
- 电击伤、溺水、中暑、蛇犬咬伤；
- 慢性病急性发作需要急诊处理者。

## 2.3 绿色通道触发情形

应进入急诊绿色通道的典型情形包括：

- 可能在短时间内危及生命的创伤；
- 急性心梗、急性心衰、急性脑卒中、急性呼吸衰竭等重点病种；
- 气道异物/梗阻、急性中毒、电击伤、溺水；
- 休克、急性肺栓塞、严重哮喘持续状态、消化道大出血、昏迷等；
- 宫外孕大出血、产科大出血；
- 消化性溃疡穿孔、急性肠梗阻等急腹症；
- “三无人员”（无姓名、无家属、无治疗经费）也应纳入绿色通道管理。

## 2.4 急诊工作的基本原则

- 24 小时开放；
- 首诊负责制；
- 对危重急诊患者先及时救治、后补手续/费用；
- 绿色通道原则：**先抢救生命，后办理相关手续；全程陪护，优先畅通**；
- 抢救、检查、治疗、转运应在医师监护下进行；
- 急诊患者留观/抢救原则上不超过 72 小时，之后应入 EICU、急诊综合病房或专科病房，或离院/转院。

---

# 3. 急诊科室的空间布局、功能区与资源对象

## 3.1 总体布局原则

急诊科应位于一楼，拥有独立功能区、清晰标识、无障碍通道，并尽量让患者在同一区域内完成急诊就诊需求，减少跨楼栋、跨露天区域移动。急诊入口宜宽敞通畅，条件允许时可区分普通急诊患者通道、危重患者通道和救护车通道。

## 3.2 支持区（Support Areas）

支持区通常包括：

- 挂号 / 登记；
- 候诊区；
- 收费；
- 急诊检验；
- 影像检查；
- 急诊药房；
- 公共卫生间；
- 其他后勤支持窗口。

这些窗口应具备**抢救患者优先**的机制。

## 3.3 医疗区（Clinical Areas）

医疗区通常包括：

- 急诊分诊区 / 分诊台；
- 急诊诊治区；
- 急诊抢救室；
- 急诊创伤处置室；
- 急诊留观室；
- 急诊综合病房；
- 急诊重症监护病房（EICU）；
- 有条件时：急诊手术室、急诊外科病房、急诊内镜、MRI、杂交手术室等；
- 承担院前急救任务的医院还应设院前急救室/科。

## 3.4 分区诊疗（红黄绿）

急诊规范文件明确建议按严重程度进行颜色分区：

- **红区**：1 级、2 级患者；
  - 1 级：濒危，需立即复苏/抢救；
  - 2 级：危重，需快速急诊处理。
- **黄区**：3 级患者；
  - 有急性症状或急诊问题，但当前未明确危及生命，需在一定时间内处理。
- **绿区**：4 级患者；
  - 非急症或低资源需求患者，可采用快诊/快速处置逻辑。

## 3.5 关键设备与资源对象

### 3.5.1 抢救室 / 红区关键设备

- 多功能抢救床；
- 监护仪；
- 输液泵 / 注射泵；
- 简易呼吸器；
- 气管插管装置 / 可视喉镜；
- 有创 / 无创呼吸机、转运呼吸机；
- 心电图机；
- 床旁超声；
- 除颤仪、临时起搏器、心肺复苏机；
- 血气生化分析仪、POCT 设备；
- 洗胃机、负压吸引、供氧装置；
- 抢救车；
- 成人/儿童气道与急救耗材。

### 3.5.2 EICU 关键设备

- 每床监护仪；
- 每 1–2 床 1 台呼吸机；
- 无创呼吸机、便携呼吸器；
- 除颤仪、临时起搏器、心肺复苏机；
- 心电图机；
- 降温仪、肠内营养泵、动态血糖监测；
- 血气分析设备；
- 气管插管箱；
- 纤支镜；
- 血液净化仪；
- 有条件时 IABP、ECMO。

### 3.5.3 影像/检验/药学/手术相关资源

- 急诊超声；
- 急诊 X 线；
- 急诊 CT；
- 有条件时 MRI、急诊内镜、介入导管室；
- 检验标本通道/物流系统；
- 药房优先配药通道；
- 手术室 10 分钟准备机制；
- 创伤复苏单元、创伤抢救床、保温快速输液设施。

## 3.6 与医院其他科室的关系

急诊不是封闭系统，而是医院急救大平台的前门。它与以下系统形成强耦合：

- 心血管内科 / 胸痛中心；
- 神经内科 / 神经外科 / 卒中中心；
- 普外 / 骨科 / 胸外 / 创伤中心；
- 妇产科（产科大出血、宫外孕等）；
- ICU / EICU / 手术室；
- 影像科、检验科、药学部；
- 住院病房与床位管理；
- 院前 120 / 救护车系统；
- 医务部、护理部、后勤、信息、保卫；
- 远程会诊与区域转诊网络。

因此，MAS 设计不能只模拟急诊内部 4 个角色，还应考虑**院内协同代理与资源代理**。

---

# 4. 急诊 MAS 系统的总体 Methodology

## 4.1 总体设计思想

建议采用：

**“规则约束 + 状态机 + 多智能体 + LLM 行为层 + 工具调用 + 事件驱动 + 可编辑空间地图”** 的混合架构。

这样做的原因：

1. 急诊流程高度结构化，必须有确定性规则与状态机；
2. 急诊中的沟通、任务选择、交接与局部排序又具有高度情境性，适合由 LLM 负责生成；
3. 急诊系统存在明显的空间、队列和资源约束，必须显式建模；
4. 危重患者路径不应完全依赖语言模型自由生成，而应由硬约束主导；
5. 多角色协作是系统核心，不应简化为单一 chatbot。

## 4.2 建议的系统分层

### Layer A. Domain Rule Layer（医疗规范层）

负责保存和执行：

- 分诊规则；
- 红/黄/绿区路由规则；
- 绿色通道规则；
- 复苏/抢救/留观/入院/转院硬性条件；
- 影像/检验/会诊时限；
- 72 小时留观边界；
- 首诊负责制与危重优先原则。

### Layer B. World State Layer（环境状态层）

统一维护全局状态：

- 当前时间；
- 地图与房间状态；
- 床位占用；
- 抢救床 / 创伤床 / EICU 床状态；
- 分诊队列 / 医生队列 / 检查队列 / 住院等待队列；
- 患者状态机；
- 医护班次与可用性；
- 检查结果返回状态；
- 会诊请求与应答状态；
- boarding / linger / LWBS 状态。

### Layer C. Agent Layer（多智能体层）

每个 agent 在共享环境中循环执行：

**Observe -> Retrieve -> Plan -> Act -> Update Memory -> Emit Events**

其中：

- Observe：读取与自己角色相关的局部状态；
- Retrieve：从本角色 memory 中检索相关片段；
- Plan：生成下一步动作计划；
- Act：通过 tools/state transition 执行动作；
- Update Memory：记录关键事件；
- Emit Events：通知其他 agent 或全局事件总线。

### Layer D. Tool Layer（工具层）

提供结构化能力，而不是让 agent 直接“想象”世界：

- 查询床位；
- 创建会诊；
- 下达检查；
- 更新生命体征；
- 转运患者；
- 写病历；
- 请求入院床位；
- 触发绿色通道 / Code Blue / 创伤团队；
- 记录时间戳与指标。

### Layer E. UI & Analytics Layer（前端与分析层）

提供：

- 地图视图；
- 队列视图；
- 实时 occupancy / utilization；
- patient timeline；
- stage-level metrics；
- scenario configuration 页面。

---

# 5. Agent 设计：建议的角色体系

下述角色分为两层：

- **MVP 核心 agents**：第一版必须实现；
- **扩展 agents**：第二版及以后逐步纳入。

## 5.1 MVP 核心 agents

1. Patient Agent
2. Triage Nurse Agent
3. ED Physician Agent
4. Bedside Nurse Agent
5. Specialist Consultant Agent
6. ED Flow Coordinator / Charge Nurse Agent

## 5.2 扩展 agents

7. Registration / Clerk Agent
8. Imaging Agent
9. Lab Agent
10. Pharmacy Agent
11. OR / Procedure Room Agent
12. Bed Manager / Admission Agent
13. EMS / Ambulance Agent
14. Security / Incident Agent
15. Family / Caregiver Agent（若要模拟告知、等待与冲突）

---

# 6. 每个 Agent 的 Role / Initialization / Planning / Memory / Tools / Workflow

## 6.1 Patient Agent

### Role

- 急诊服务需求发起者；
- 报告主诉、等待分诊、接受转运、接受检查、接受治疗、接受离院/住院安排；
- 低急迫度患者在长时间等待后可触发 LWBS（Left Without Being Seen）逻辑。

### Initialization

建议初始化字段：

- `patient_id`
- `arrival_mode`：walk-in / ambulance / transfer
- `chief_complaint`
- `clinical_profile`
- `severity_raw`（症状严重度）
- `triage_level`（由规则系统写入，而不是让患者自定）
- `green_channel_flag`
- `patience_limit`
- `mobility`
- `infection_flag`
- `has_family`
- `financial_status`（可模拟“三无人员”）
- `destination_preference`（出院/住院并非主动决定，但可影响行为）

### Planning

Patient 不需要复杂全局规划，主要是局部行为规划：

- 是否主动报告症状；
- 是否配合检查和转运；
- 是否在等待过久后尝试离开；
- 是否重复发起询问 / 焦虑表达；
- 是否在危重状态下进入被动流程。

### Memory

- 到达时间；
- 主诉与对话摘要；
- 已完成阶段；
- 当前等待位置；
- 已见过哪些医护；
- 被告知的下一步事项；
- 已完成检查、待返回结果；
- 是否已签署告知同意。

### Tools

- `report_symptoms()`
- `confirm_consent()`
- `follow_staff()`
- `wait()`
- `decide_walkout()`

### Workflow

Arrival -> Waiting -> Triage -> Route to Red/Yellow/Green -> Bed/Chair Assignment -> Physician Assessment -> Test/Procedure -> Reassessment -> Disposition -> Discharge / Observation / Admission / Transfer / Walkout

---

## 6.2 Triage Nurse Agent

### Role

- 急诊入口守门人；
- 负责预检分诊、生命体征采集、区分病情严重程度、红黄绿分流；
- 对濒危/危重患者触发抢救路径或绿色通道。

### Initialization

- `nurse_id`
- `triage_station_id`
- `shift_schedule`
- `experience_years`
- `zone_scope`
- `priority_policy`
- `can_trigger_green_channel`
- `can_trigger_code_blue`

### Planning

- 决定下一位叫号对象；
- 判断是否中断常规分诊去处理危重患者；
- 决定患者进入红区/黄区/绿区；
- 对特殊人群进行优先分诊；
- 在流量高峰时维持候诊秩序与优先级。

### Memory

- arrival queue 快照；
- 近期分诊病例；
- 当前抢救中断事件；
- 某患者是否已初筛；
- 特殊人群优先记录；
- 高危关键词触发记录。

### Tools

- `collect_vitals()`
- `apply_triage_rules()`
- `assign_zone()`
- `trigger_green_channel()`
- `send_to_resuscitation_room()`
- `create_triage_record()`
- `notify_physician()`

### Workflow

Monitor arrival queue -> Call patient -> Collect complaint/vitals -> Run deterministic triage rule -> Assign acuity/zone -> Trigger red-zone bypass if necessary -> Create triage record -> Hand over to bedside nurse / physician queue

### 设计备注

- MVP 中不要让 LLM 直接输出最终分诊级别；
- 分诊级别应由规则引擎或预设临床 profile 生成；
- LLM 可用于问诊对话与异常解释，不用于最终 CTAS/ESI/分级裁决。

---

## 6.3 ED Physician Agent

### Role

- 急诊临床决策者；
- 负责首诊评估、医嘱、检查、会诊、复评、处置、病历与 disposition；
- 危重事件中承担首诊负责与抢救指挥之一。

### Initialization

- `physician_id`
- `zone_assignment`
- `specialty_bias`（内科/外科/创伤/胸痛等）
- `shift_schedule`
- `max_caseload`
- `efficiency_profile`
- `interrupt_priority_policy`
- `consult_authority`
- `admission_authority`

### Planning

- 从待诊列表中决定先看谁；
- 判断是首诊、复评、看结果、会诊后处理，还是出院；
- 决定是否检查、是否会诊、是否抢救、是否住院；
- 高峰时动态重排任务；
- 接到红区中断时立即抢占当前计划。

### Memory

- 自己当前在管患者列表；
- 每位患者的时间线摘要；
- 已下医嘱与结果返回情况；
- 会诊请求状态；
- 已完成 documentation 状态；
- 关键异常事件（病情恶化、危急值、等待超时）。

### Tools

- `review_tracking_board()`
- `assess_patient()`
- `place_orders()`
- `request_consult()`
- `review_results()`
- `update_disposition()`
- `write_note()`
- `request_admission()`
- `request_transfer()`
- `trigger_resuscitation_protocol()`

### Workflow

Start shift -> Scan tracking board -> Select next patient -> Assess -> Order diagnostics / treatment / consult -> Wait for results / events -> Reassess -> Decide disposition -> Document -> Handover / discharge / admission / transfer

### 设计备注

- 对于急诊仿真，医生 agent 的重点是**任务选择与流程推进**，而不是“自主发明诊断”；
- 建议把诊疗逻辑拆成：
  - `rule-based patient state transition`
  - `LLM-generated explanation/dialogue`
  - `structured order set`

---

## 6.4 Bedside Nurse Agent

### Role

- 负责分区内患者物流与执行护理；
- 连接“患者 - 床位 - 检查室 - 医生队列”；
- 负责转运、监测、基础护理、执行部分医嘱、等待中的状态维护。

### Initialization

- `nurse_id`
- `zone_assignment`
- `shift_schedule`
- `task_queue`
- `transport_authority`
- `monitoring_scope`
- `pager_subscription`（接收 CTAS1 / red zone pager）

### Planning

- 决定先转运哪位患者；
- 决定先执行哪项护理任务；
- 处理“待上床 / 待检查 / 待回床 / 待医生再评估”的局部队列；
- 危重患者出现时中断低优先任务。

### Memory

- 所在分区当前床位状态；
- 患者待办列表；
- 转运完成记录；
- 最近生命体征与病情变化；
- 哪位患者正在等待影像 / 回床 / 医生复评。

### Tools

- `assign_bed()`
- `escort_patient()`
- `collect_repeat_vitals()`
- `monitor_patient()`
- `administer_task()`
- `send_to_diagnostic_room()`
- `return_to_zone()`
- `update_nurse_log()`

### Workflow

Scan zone queue -> Pick next task by acuity + wait time + urgency -> Move patient to bed / test room -> Monitor -> Update queue -> Notify doctor when patient or results are ready -> Continue loop

---

## 6.5 Specialist Consultant Agent

### Role

- 代表神内、神外、骨科、妇产、胸外、ICU 等专科会诊力量；
- 对不属于急诊科单独闭环处理的患者提供专科处理意见；
- 决定接收入院、手术室、ICU 或专科病区。

### Initialization

- `consultant_id`
- `department`
- `on_call_schedule`
- `response_time_profile`
- `admission_authority`
- `procedure_authority`

### Planning

- 按会诊优先级响应请求；
- 判断是否立即到场；
- 决定专科下一步：收住院 / 进手术室 / ICU / 返回急诊继续观察；
- 群体伤/多发伤时参与 MDT。

### Memory

- 待处理会诊请求；
- 已响应患者清单；
- 专科建议与执行状态；
- 与急诊首诊医师的交接记录。

### Tools

- `accept_consult()`
- `examine_patient()`
- `provide_consult_opinion()`
- `accept_inpatient_transfer()`
- `book_or_request_or()`
- `handover_from_ed()`

### Workflow

Receive consult request -> Travel / virtual respond -> Evaluate patient -> Return consult note -> Accept/reject admission destination -> Coordinate transfer

---

## 6.6 ED Flow Coordinator / Charge Nurse Agent

### Role

- 急诊运行协调者；
- 不是临床主诊人，而是全局队列、床位、转运、会诊、异常事件的调度器；
- 类似“全局运营大脑”。

### Initialization

- `coordinator_id`
- `shift_schedule`
- `authority_scope`
- `global_dashboard_access`
- `surge_policy`

### Planning

- 根据队列与 occupancy 重分配床位与人员；
- 决定何时启用快诊区、加开 triage station、调用支援；
- 监控 LWBS 风险、boarding 风险、红区超载；
- 推动会诊超时与报告超时处理；
- 维持绿色通道畅通。

### Memory

- 全局实时指标；
- 各队列长度；
- 报告返回时限；
- 床位与分区占用；
- 当前 surge 状态；
- 事件日志与瓶颈摘要。

### Tools

- `view_global_dashboard()`
- `reallocate_beds()`
- `request_staff_support()`
- `escalate_delay()`
- `enable_fast_track()`
- `broadcast_status_update()`

### Workflow

Monitor system metrics -> Detect bottleneck -> Issue operational actions -> Update staffing/resource state -> Notify relevant agents -> Re-monitor

---

## 6.7 Registration / Clerk Agent（扩展）

### Role

- 负责挂号、登记、收费/补手续；
- 在绿色通道中让位于抢救，后补手续。

### Initialization

- `desk_id`
- `counter_type`
- `schedule`

### Planning / Memory / Tools / Workflow

以事务处理为主，不必使用复杂 LLM。可设计成弱智能或纯规则代理。

---

## 6.8 Imaging Agent（扩展）

### Role

- 管理急诊影像资源（X 线 / CT / 超声 / MRI）；
- 响应急诊优先；
- 维护报告返回时限。

### Initialization

- `modality_type`
- `capacity`
- `turnaround_time`
- `priority_policy`

### Tools

- `enqueue_exam()`
- `start_exam()`
- `complete_exam()`
- `return_report()`

---

## 6.9 Lab Agent（扩展）

### Role

- 维护检验队列、标本状态、危急值通知；
- 满足常规检查、生化、凝血、配血等时限要求。

---

## 6.10 Pharmacy Agent（扩展）

### Role

- 绿色通道下优先配药发药；
- 记录取药完成状态。

---

## 6.11 OR / Procedure Room Agent（扩展）

### Role

- 接收急症手术申请；
- 维护 10 分钟准备机制；
- 协调麻醉与手术相关人员。

---

## 6.12 Bed Manager / Admission Agent（扩展）

### Role

- 负责急诊患者优先住院机制；
- 管理 boarding 时长；
- 协调专科病房和 ICU 接收。

---

## 6.13 EMS / Ambulance Agent（扩展）

### Role

- 模拟院前 120 / 救护车入院；
- 提前上传现场信息；
- 对接创伤中心/胸痛/卒中预警。

---

# 7. Planning、Memory、Tool Use 的统一设计建议

## 7.1 Planning

建议每个 agent 使用**双层 planning**：

### 全局计划（coarse plan）

示例：

- Triage nurse：持续处理 arrival queue；
- Physician：优先处理红区、危重、结果已回的患者；
- Bedside nurse：先上床、再检查转运、再回床、再日常监测；
- Coordinator：优先解决 bottleneck 与资源冲突。

### 局部计划（next action plan）

每一步只决定一到三个最可能动作：

- `call_next_patient`
- `send_to_red_zone`
- `review_CT_result`
- `escort_to_CT`
- `request_consult`
- `discharge_patient`

这种分层规划方式可以减少 LLM 漫游，保持流程可控。

## 7.2 Memory

建议不要把 memory 设计成单一对话历史，而要拆分为 4 类：

### (1) Episodic Memory

记录 agent 个人最近经历：

- 看过谁；
- 做了什么；
- 上一步动作；
- 当前阻塞原因。

### (2) Clinical / Patient Memory

以患者为中心的结构化病程：

- chief complaint
- triage level
- vitals
- tests ordered
- results returned
- consult opinions
- disposition

### (3) Operational Memory

系统级运行信息：

- 队列长度；
- 抢救床是否已满；
- CT 是否拥堵；
- 哪个专科响应慢；
- 哪个病区无床。

### (4) Reflective Memory（建议用于班次级而非秒级决策）

借鉴 Generative Agents，可设计“反思”模块，但不建议用于抢救即时闭环；更适合：

- 班次总结；
- 运行瓶颈归纳；
- 某类患者为何容易堵在 disposition 后；
- 哪类资源最紧张；
- 次日 scenario 初始化建议。

## 7.3 Tool Use

所有高风险动作都应通过工具层执行，而不是通过自然语言“想象执行”。

### 建议最小工具集合

- `get_local_state(agent_id)`
- `get_patient_record(patient_id)`
- `update_patient_state(patient_id, new_state)`
- `assign_triage(patient_id, level, zone)`
- `allocate_bed(patient_id, zone)`
- `place_order(patient_id, order_type)`
- `request_consult(patient_id, department)`
- `post_result(patient_id, result_type)`
- `request_admission(patient_id, dept)`
- `discharge_patient(patient_id)`
- `transfer_patient(patient_id, destination)`
- `trigger_green_channel(patient_id)`
- `trigger_code_blue(location)`
- `log_event(event)`
- `query_metrics()`

---

# 8. 急诊诊断与处置 workflow（建议的运行逻辑）

## 8.1 患者主路径

1. Arrival
2. Pre-triage waiting
3. Triage assessment
4. Zone assignment（Red / Yellow / Green）
5. Bed/seat assignment
6. Initial physician assessment
7. Orders / diagnostics / procedures / consults
8. Reassessment
9. Disposition
   - discharge
   - observation
   - admission to ED ward / specialty ward / ICU
   - OR
   - transfer
   - death / resuscitation failure（如需模拟）
10. Departure / boarding completion

## 8.2 危重患者中断路径

当出现以下事件时立即中断常规队列：

- 1 级濒危患者到达；
- 红区患者生命体征恶化；
- 心跳呼吸骤停；
- 大出血 / 严重创伤 / 昏迷 / 气道梗阻等高危关键词命中；
- 危急值返回。

中断后触发：

- `Code Blue / Red Zone Interrupt`
- 抢救床占用
- 首诊医师与床旁护士抢占任务
- 必要时触发多学科会诊 / OR / ICU

## 8.3 低急迫度患者路径

4 级非急症患者可走：

- 绿区 / 快诊区
- 简化评估
- 较少资源消耗
- 若等待过长可模拟 LWBS

## 8.4 留观与 boarding 路径

- 暂不能明确诊断；
- 等待检查结果；
- 病情有潜在进展风险；
- 明确需住院但暂时无床。

这一路径是急诊拥堵的重要来源，必须单独建模。

---

# 9. Multi-Agent Interaction 机制

## 9.1 交互类型

### 顺序交互

- Patient -> Triage Nurse
- Triage Nurse -> Bedside Nurse
- Bedside Nurse -> Physician
- Physician -> Consultant
- Physician -> Bed Manager

### 并发交互

- 多名 patient 同时排队；
- 多名 nurse 同时处理不同 zone；
- 结果返回触发医生复评；
- 住院申请与会诊申请并发；
- coordinator 同时观察全局。

### 中断交互

- 红区 pager；
- 检查危急值；
- trauma arrival；
- surge overload。

## 9.2 推荐通信模式

### 结构化消息

```json
{
  "event_type": "consult_requested",
  "patient_id": "P1024",
  "from_agent": "ED_Physician_03",
  "to_agent": "Ortho_Consult_01",
  "priority": "high",
  "timestamp": "2026-03-27T14:33:00"
}
```

### 非结构化自然语言

只用于：

- 患者诉说主诉；
- 医护沟通摘要；
- 告知与交代；
- 会诊意见解释；
- 前端展示。

关键业务状态一定要回写成结构化字段。

---

# 10. 从 EDSim 与 Generative Agents 借鉴什么

## 10.1 直接借鉴 EDSim 的部分

1. **混合架构**：LLM 行为层 + 硬约束 clinical protocol + state machine；
2. **四类基础角色**：Patient / Triage Nurse / Bedside Nurse / Physician；
3. **空间显式建模**：地图、床位、房间、碰撞层、可编辑 floor plan；
4. **perceive-plan-act 循环**；
5. **历史聚合数据参数化**：到达率、病种分布、急迫度分布、服务时间、转运延迟；
6. **实时监控 dashboard**；
7. **资源与 agent 可动态增删**；
8. **what-if scenario 配置机制**。

## 10.2 借鉴 Generative Agents 的部分

1. **Memory stream**：将角色经历持续写入可检索 memory；
2. **Retrieval = relevance + recency + importance** 的思想；
3. **Planning**：先高层计划，再细化到下一步动作；
4. **Reflection**：不用于高风险即时诊疗，而用于班次总结、流程优化、瓶颈归因；
5. **长时程行为一致性**：同一班次中角色行为应连贯，不应每轮像全新 agent。

## 10.3 不建议直接照搬的部分

1. 不要把医疗系统做成完全自由的 open-world social sim；
2. 不要让 agent 纯靠 LLM 自由决定病情分级；
3. 不要让自然语言对话直接等价于“临床动作已执行”；
4. 不要把反思模块用于秒级抢救闭环；
5. 不要忽略结构化日志、时限规则和审计机制。

---

# 11. Codex 实现时的模块拆分建议

## 11.1 最小代码目录建议

```text
ed_mas/
  config/
    scenario.yaml
    staffing.yaml
    rules.yaml
    floorplan.json
  core/
    engine.py
    event_bus.py
    scheduler.py
    world_state.py
    metrics.py
  agents/
    base_agent.py
    patient_agent.py
    triage_nurse_agent.py
    bedside_nurse_agent.py
    physician_agent.py
    consultant_agent.py
    coordinator_agent.py
  memory/
    episodic_memory.py
    patient_memory.py
    retrieval.py
    reflection.py
  tools/
    triage_tools.py
    bed_tools.py
    order_tools.py
    consult_tools.py
    transfer_tools.py
    documentation_tools.py
  rules/
    triage_rules.py
    green_channel_rules.py
    zone_routing.py
    disposition_rules.py
  ui/
    dashboard.py
    map_renderer.py
  data/
    patient_profiles.json
    arrival_curves.json
    service_time.json
```

## 11.2 第一阶段（MVP）建议

先实现：

- Patient / Triage Nurse / Bedside Nurse / Physician 四类 agent；
- 红黄绿三区；
- 到达 -> 分诊 -> 床位 -> 首诊 -> 检查 -> 复评 -> 离院；
- CT / Lab 两类检查资源；
- 一个 specialist consult 占位代理；
- boarding duration 占位逻辑；
- 基础 dashboard。

## 11.3 第二阶段建议

- 加入绿色通道细化；
- 加入 EICU / OR / admission；
- 加入创伤 / 胸痛 / 卒中路径；
- 加入 family / security / EMS；
- 加入 reflection 与 shift report；
- 加入 scenario replay。

---

# 12. 指标体系（供仿真评估用）

## 12.1 患者级指标

- Arrival-to-Triage
- Triage-to-Bed
- Arrival-to-PIA（初次医师评估）
- PIA-to-Disposition
- Disposition-to-Leave
- Total Length of Stay
- LWBS rate
- 住院等待时长

## 12.2 资源级指标

- 红区/黄区/绿区 occupancy
- 抢救床 / EICU 床占用率
- CT / US / Lab 队列长度
- 手术室准备延迟
- 各类报告 TAT

## 12.3 人员级指标

- physician active caseload
- nurse utilization
- consult response time
- interruption frequency
- documentation lag

## 12.4 系统级指标

- surge 下性能退化曲线
- bottleneck 定位
- 高危患者及时处置率
- 会诊 10 分钟到场达标率（若模拟）
- 绿色通道完成率
- 72 小时内 disposition 完成率

---

# 13. 建议给 Codex 的一句话任务定义

> 请基于本文件实现一个可扩展的急诊科室多智能体仿真系统：使用状态机与规则引擎表达分诊、红黄绿分流、绿色通道、检查、会诊、留观、住院与转运的硬约束；使用 LLM 负责角色对话、局部计划、交接摘要与情境化行为；使用共享 world state、事件总线、结构化工具调用和可编辑地图来驱动 Patient、Triage Nurse、Bedside Nurse、ED Physician、Consultant 与 Coordinator 等 agents 的协作，并输出实时 dashboard 与 patient-level timeline 指标。

---

# 14. 最后建议：Codex brainstorming 时先回答的关键问题

1. 第一版是否只做 4–6 个核心 agent？
2. 分诊级别是否完全由规则生成，而不是 LLM 决策？
3. 红黄绿三区如何映射到地图与床位对象？
4. 是不是需要单独建模 boarding 和住院床位阻塞？
5. specialist consult 是即时代理，还是外部延迟资源？
6. 哪些动作必须工具化，不能由自然语言直接执行？
7. reflection 是做班次级摘要，还是做在线学习？
8. scenario config 文件如何设计，才能方便测试 staffing / capacity / surge？
9. 前端是否先做 2D 网格地图，后做高保真平面图？
10. 最小成功标准是什么：可运行流程，还是可复现实测指标分布？

---

# 15. 参考资料（供人类阅读，不要求 Codex 解析）

- 《中国县级医院急诊科建设规范专家共识》
- 《医院急诊科规范化流程（WS/T 390-2012）》
- 《市中区人民医院门诊、急诊就诊流程、注意事项、相关制度》
- EDSim: An Agentic Simulator for Emergency Department Operations
- Generative Agents: Interactive Simulacra of Human Behavior

