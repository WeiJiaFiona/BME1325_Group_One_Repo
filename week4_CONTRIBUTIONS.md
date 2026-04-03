# Week 4 小组贡献总结与分析

> 本文档对 Week 4 onsite 阶段四个小组的工作进行汇总与评述，覆盖场景定位、技术架构、已完成内容、当前局限及后续规划。

---

## 一、总览

| 小组 | GitHub ID | 主攻场景 | 核心技术路线 | 主要交付物 |
|------|-----------|----------|-------------|-----------|
| A | Jangbo7 | 门诊（Outpatient，兼作医院统一视觉环境） | HTML5 Canvas + Python 后端 REST API | 伪 3D 全院沙盒原型 + 护士分诊 Agent 后端 |
| B | WeiJiaFiona | 急诊科（Emergency Department，ED-MAS） | FastAPI + React/TypeScript + TDD | 可运行可测试的 ED 多智能体骨架 |
| C | XanderZhou2022 | 重症监护室（ICU） | PostgreSQL 数据层 + 多 Agent 分层架构设计 | ICU 系统任务书 + Agent 设计方案 + 测试数据库 |
| D | littlegrass-bme | 骨科门诊 + 住院部 | Pygame + LangChain LLM + FastAPI | 骨科就诊可交互原型（w4-1）+ 住院部后端骨架可运行版本（w4-2） |

---

## 二、各小组贡献详述

### 2.1 Jangbo7 — 门诊伪 3D 全院视觉环境 + 护士分诊 Agent

#### 场景定位

最终目标是**门诊（Outpatient）流程仿真**，同时承担整个 SIM Hospital 的**统一视觉前端**角色。玩家以患者身份进入医院大厅，在护士台完成初步分诊后，根据病情被导流至门诊诊室、急诊区、骨科/住院部或 ICU 等不同区域。

值得注意的是，当前 `gameObjects.js` 中定义的医院地图已包含**全院所有功能区域**：

| 房间标识 | 中文名称 | 对应组 / 功能 |
|----------|----------|--------------|
| `病房` | 普通病房 | littlegrass-bme 住院部 |
| `药房` | 药房 | littlegrass-bme 骨科门诊取药 |
| `办公室` | 医护办公室 | 共用行政功能 |
| `急诊室` | 急诊室 | WeiJiaFiona ED-MAS |
| `大厅` | 医院大厅 | 患者到达入口（所有组共用） |
| `休息室` | 等候/休息室 | 等待队列可视化 |
| `实验室` | 检验科 | XanderZhou2022 ICU 化验 |
| `重症室` | ICU/重症室 | XanderZhou2022 ICU |

这意味着 Jangbo7 的 Canvas 是天然的**统一视觉承载层**，四个小组的场景可各自对应画布内的不同房间，无需重建地图。

#### 技术架构

- **前端**（`scene/`）：原生 HTML5 + Canvas，实现第三人称伪 3D 等轴渲染，已完成多房间布局、自动玻璃门、碰撞检测、小地图。
- **后端**（`backend/`）：Python 轻量 HTTP 服务（`server.py`），提供三个接口：`GET /health`、`GET /api/statuses`、`POST /api/triage/request`。
- **核心 Agent 逻辑**：
  - `backend/services/triage_service.py`：分诊服务，支持 LLM 模型分诊与规则回退。
  - `backend/rag/`：基于规则 JSON（`rule_store.json`）的 RAG 检索器。
  - `backend/memory/`：患者记忆与会话存储（`patient_memory.py`、`session_store.py`）。
  - `backend/services/validator.py`：输入验证。
- **安全策略**：API Key 从 `.env` 读取，前端私有配置文件不入库（`.gitignore`）。

#### 主要成果

1. 完整的伪 3D 医院箱庭原型可在浏览器直接运行。
2. 护士分诊 Agent 异步执行分诊，前端通过轮询实时显示病人状态。
3. 状态流转：`待分诊 → 正在分诊 → 等待问诊`，逻辑清晰。
4. 前后端已联调，玩家按 E 键触发分诊请求，任务栏实时更新。
5. Mock 模式和真实 LLM 模式均已考虑，具备回退能力。

#### 局限与待改进

- 当前已实现护士分诊入口，NPC 行为、寻路与日程系统尚未加入。
- 医院场景数据仍硬编码，缺乏配置化；房间数量/布局需扩展以完整覆盖门诊诊室。
- 暂不支持多患者并发分诊，后端会话隔离尚未实现。
- 后续计划：完善门诊诊室可交互点、NPC 自主寻路、房间配置化，并对接其他三组的后端 API，使各科室房间成为可切入的子场景。

---

### 2.2 WeiJiaFiona — ED-MAS 急诊多智能体可运行骨架

#### 场景定位

以急诊科（Emergency Department）为核心，目标是构建一个**完整可运行、可测试的 ED 多智能体仿真框架**，为 Week 5–12 的扩展打基础。

#### 技术架构

- **后端**：FastAPI（Python），提供 `/health` 与 `/mode/user/encounter/start` 接口。
- **核心模块**：
  - `domain/triage_rules.py`：分诊等级 + 红/黄/绿分区路由规则。
  - `domain/state_machine.py`：就诊流程状态机（`Arrival → Triage → Routed → Evaluation → Treatment → Disposition`）。
  - `world/event_bus.py`：统一事件总线。
  - `modes/user_mode.py` & `auto_mode.py`：Mode-U（用户参与）与 Mode-A（自动仿真）双模式。
  - `safety/guardrails.py`：高风险医疗建议拦截。
  - `metrics/`：KPI 快照采集与聚合统计。
- **前端**（React/TypeScript）：Mode-U / Mode-A 切换占位，Dashboard、MapView、QueuePanel、UserPatientChat 四个组件骨架。
- **测试体系**：单元测试 5 套（bootstrap / triage / state machine / tools / metrics）+ 集成测试 3 套（user mode / auto mode / safety）+ E2E 占位测试（Playwright）。
- **文档**：周推进 DoD 矩阵（Week 4–12）+ 最终报告骨架 + 详细 proposal（含急诊流程、Stanford Town 映射、六层系统架构、状态机、Memory 设计等）。

#### 主要成果

1. 最完整的**系统设计文档**，proposal 覆盖完整急诊工作流、Agent 职责表、患者状态机（含 Escalation Hooks）、Memory/Scratch/Event Log 分层设计、空间与资源建模。
2. 后端原型代码"能跑 + 可测"，测试体系完整，符合 TDD 风格。
3. 明确定义了 Week 4–12 的 DoD 矩阵，路线清晰。
4. 双模式设计（Mode-U / Mode-A）为后续用户参与和自动仿真实验提供扩展点。
5. 安全护栏与 KPI 采集已作为基础设施纳入，具备面向最终答辩的可演示性。

#### 局限与待改进

- 本周重点是"骨架"，真实 Phaser 地图渲染与可视化联动尚未完成。
- Agent 策略循环（医生/护士/协调员）尚未实现，当前只有状态机和规则层。
- 长时稳定性实验与大规模 KPI 面板留待后续迭代。

---

### 2.3 XanderZhou2022 — ICU 多智能体系统设计 + 数据层搭建

#### 场景定位

聚焦**重症监护室（ICU）**，针对高频时序数据驱动、弱语言交互、强风险约束的 ICU 特殊环境，设计了一套完整的多智能体系统方案。

#### 技术架构与设计成果

**系统设计层（任务书）**：

- **三层架构**：患者状态层（Patient Digital Twin，20 床位）→ 多智能体协作层 → 人类在环层。
- **8 类 Agent，84 个实例**（按 20 床计算）：
  - 中央协调层：ICU Orchestrator Agent（1）
  - 床位级感知层：Bedside Monitor / Intervention Tracker / Risk Sentinel / Patient Memory（各 20）
  - 共享专家层：Clinical Summary Agent / Ward Coordinator Agent（各 1）
  - 人文沟通层：Compassion & Family Communication Agent（1–2）
- **4 条核心交互流程**：生命体征异常触发链、治疗干预闭环链、查房摘要生成链、家属沟通链。
- **共享状态板设计**（Shared Patient State Board）：所有 Agent 读写同一状态板，而非两两直接通讯，对应 environment-driven coordination 模式。
- **告警管理**：告警聚合、去重、优先级排序、跨床位调度，解决 ICU "告警风暴"问题。
- **可解释性要求**：每个 Agent 输出必须包含数据依据、时间窗口和判断逻辑。
- **参考资料**：包含 APACHE II 评分系统说明与 JSON 实现文件，ICU 提示词设计，Agent 总体分层文档，以及 ICU 主治医师手册与 ICU 手册 PDF 作为医学背景参考。

**数据层（测试数据库）**：

- 本地搭建 PostgreSQL 16 数据库（`icu_agent`）。
- 12 张核心表已创建：`patients`、`beds`、`admissions`、`events`、`vital_sign_events`（遵循 ICU/APACHE 规范字段）、`lab_events`、`intervention_events`、`patient_state_current`、`patient_state_snapshots`、`risk_assessments`、`alerts`、`audit_logs`。
- 已插入场景化测试数据（感染性休克、呼吸恶化、补液反应不佳三类场景）。
- 提供 `init_core_tables.py`、`seed_test_data.py`、`verify_db.py` 三个脚本及 `view_all_tables.py` 查看工具。
- 数据库已实际运行，可通过 Python psycopg 直接读取，为后续 Agent 开发提供数据基础。

#### 主要成果

1. 最系统化的**ICU 场景 Agent 架构设计**，涵盖 agent 分层、信息流、交互流程与实现建议。
2. APACHE II 评分 JSON 文件为风险 Agent 提供了可直接调用的评分规范。
3. **数据层已落地**：本地 PostgreSQL + 测试数据已可用，是四组中唯一完成数据库搭建的小组。
4. 强调 Human-in-the-loop 与可解释性，设计上具有较高安全意识。

#### 局限与待改进

- 当前以**设计与规划**为主，Agent 代码实现尚未开始。
- 数据库仅在本地，尚未与任何 Agent 或后端服务联通。
- Multi-Agent drawio 架构图已创建但 Agent 间的通信代码还未实现。
- 建议下一步先实现 Bedside Monitor Agent 与 Risk Sentinel Agent 的最小原型，接入已有数据层。

---

### 2.4 littlegrass-bme — 骨科门诊可交互原型 + 住院部后端框架落地

#### 场景定位

以**骨科就诊流程**为核心，实现一个玩家可操控的医院模拟游戏；Week 4 同时聚焦**住院部管理**场景，先后完成住院部重构计划（`w4-1`）和住院部后端骨架的实际落地（`w4-2`）。

#### 技术架构

**沿用 Week 3 基础（`hospital_w3/`）**：

- Pygame 2D 斜 45° 像素风引擎，支持护士、医生、技师、手术医生、药剂师五类 NPC。
- 已实现分诊流程、医生问诊（SimpleAgent）、技师拍片、手术室流程、药房取药。
- NavigationSystem 区域划分与碰撞检测，基于射线法。

**Week 4 第一阶段（`w4-1/`）**：

- **后端 AI 层重构**（`backend_ai/`）：
  - `agent_base.py`：抽象基类 `AbstractAgent`。
  - `doctor_agent.py`：医生 Agent，集成 LangChain + OpenAI 兼容接口。
  - `triage_agent.py`：分诊 Agent。
  - `service.py`：`MedicalAgentService` 统一入口，支持 LLM 调用与 fallback。
  - `model_config.yml` + `prompt_config.yml`：模型与提示模板配置化。
- **终端模式**（`main.py`）：新增命令行交互，支持 `/register`、`/status`、`/imaging`、`/surgery`、`/pharmacy` 等命令，及直接文本与医生 Agent 对话。
- **统一业务层**：`HospitalEngine` 类统一管理患者会话、任务状态、NPC 交互，终端与 Pygame 共享同一套业务逻辑。
- **住院部扩展**（`inpatient/patient_manager.py`）：PatientManager 作为住院患者状态唯一数据源，支持入院→分床→医嘱→查房→出院全流程。
- 中文输入已完善（`w4-1` 相较 `hospital_w3` 新增）。

**Week 4 第二阶段（`w4-2/`）**：

住院部后端骨架从计划阶段推进到实际可运行状态，文档也从旧版 `docs/plan.md` 更新为三份更精准的说明文档（`docs/使用说明.md`、`docs/当前完成与下一步.md`、`docs/项目详细规划.md`）。

- **中央调度器**（`central_dispatcher.py`）：统一入口，接收命令、识别命令并转发至对应服务，内置消息分发、优先级队列与中断控制，同时兼容原有轻量消息路由结构。
- **领域层**（`backend/domain/`）：
  - `models.py`：患者、医嘱、体征等核心业务数据模型。
  - `state_store.py`：系统唯一状态存储，作为所有 Agent 的读写真相源。
  - `rules.py`：状态迁移规则、前置检查与异常判定逻辑。
- **服务层**（`backend/services/`）：8 类住院流程服务独立封装：
  - `admission_service.py`：入院登记。
  - `ward_service.py`：病区与床位分配。
  - `round_service.py`：查房服务。
  - `order_service.py`：医嘱下达。
  - `execute_service.py`：医嘱执行。
  - `monitor_service.py`：生理监测与异常触发。
  - `interrupt_service.py`：紧急中断与恢复。
  - `discharge_service.py`：出院评估与办理。
  - `workflow_service.py`：住院主工作流，驱动上述服务按 cycle 顺序运行（查房 → 医嘱 → 执行 → 监测 → 中断 → 出院）。
- **接口协议层**（`backend/schemas/protocol.py`）：统一请求 / 响应 / 事件结构（`ProtocolRequest` / `ProtocolResponse` / `ProtocolEvent`），前端、调试脚本与 Agent 均围绕同一套协议工作。
- **适配层**（`backend/adapters/legacy_engine_adapter.py`）：将 `w4-1` 旧业务逻辑（`outpatient_engine` 等）包装为统一接口接入新框架，避免重写已有逻辑。
- **API 骨架**（`backend/api/server.py`）：FastAPI HTTP 服务，提供 `/dispatch` 统一调度接口，为后续网页前端接入预留接口。
- **可运行 Demo**（`backend/api/run_demo_flow.py`）：本地验证脚本，自动执行入院 → 分床 → 住院工作流三步，输出结构化 JSON 响应，验证主链路贯通。

#### 主要成果

1. **最完整的可运行游戏原型**：骨科就诊全流程（注册→问诊→拍片→手术/取药）均可在 Pygame 中实际体验。
2. 双交互模式（Pygame GUI + 终端 CLI）共用同一业务层，架构清晰。
3. LangChain + 模型配置化的 Agent 服务，支持不同 LLM 后端，具备 fallback 容错。
4. **住院部后端骨架从设计阶段切实落地**（`w4-2`）：中央调度器 + 分层后端已可运行，入院→分床→住院工作流 demo 可实际执行。
5. 分层结构清晰（`domain` / `services` / `schemas` / `adapters` / `api`），旧业务逻辑通过 adapter 平滑接入，无需全部重写。
6. 像素画风美术资源完整（医生/护士/患者/技师/手术医生/药剂师动画帧全部自制）。

#### 局限与待改进

- 住院工作流 demo 当前以顺序方式执行 `clinical_branch` 与 `monitor_branch`，尚非真正并行双支路推进。
- Demo 输出以大段 JSON 为主，可观察性较弱，尚不适合作为最终演示界面。
- 工作流循环容易被过早出院打断，`查房→监测` 多轮循环的演示效果需进一步改善。
- 暂未接入 RAG 或更复杂的临床知识库，医学知识仍依赖 prompt。

---

## 三、横向比较与整体分析

### 3.1 场景覆盖

四组合力覆盖了 SIM Hospital 的四个关键场景：门诊入口与通用视觉环境（Jangbo7）、急诊科完整流程（WeiJiaFiona）、ICU 重症监护（XanderZhou2022）、骨科门诊与住院部（littlegrass-bme）。场景互补，且 Jangbo7 的画布已包含所有科室房间，为最终统一演示提供了天然载体。

### 3.2 技术路线多样性

| 维度 | Jangbo7 | WeiJiaFiona | XanderZhou2022 | littlegrass-bme |
|------|---------|-------------|----------------|-----------------|
| 前端技术 | HTML5 Canvas | React/TypeScript | 暂无前端实现 | Pygame |
| 后端框架 | 轻量 Python HTTP | FastAPI | PostgreSQL | FastAPI（w4-2）|
| Agent 框架 | 自研 | 自研 | 设计阶段 | LangChain |
| 测试覆盖 | 无（接口联调） | TDD，完整测试 | 脚本验收 | fallback 测试 |
| 文档完整性 | 中 | 高 | 高 | 高 |
| 代码可运行性 | 高 | 高 | 数据库可运行 | 高 |

### 3.3 各组优势

- **Jangbo7**：视觉原型最直观，前后端已联调，适合作为最终演示的入口场景。
- **WeiJiaFiona**：系统设计最完整，测试体系最规范，可作为整体框架的参考蓝本，DoD 矩阵为后续迭代提供清晰节奏。
- **XanderZhou2022**：ICU 场景设计最深入，数据层已落地，Compassion Agent 是四组中最具创新性的设计点，APACHE II 评分 JSON 可直接复用。
- **littlegrass-bme**：可玩性最强，美术资源最完整，LangChain Agent 架构实践最成熟；`w4-2` 已将住院部后端从设计切实落地，`central_dispatcher` + 分层后端（domain / services / schemas / adapters）可运行，是四组中住院流程实现最完整的小组。

### 3.4 共同挑战

1. **Agent 策略循环尚未完整实现**：四组均处于"规则 + 骨架"阶段，LLM 驱动的 Agent 决策闭环（Perceive → Plan → Act）在所有组中均未完整落地。
2. **跨组接口未对齐**：各组技术栈差异较大，当前缺乏统一的 Agent 通信协议和患者数据格式。
3. **可视化与后端分离**：Jangbo7 和 littlegrass-bme 有前端但 Agent 逻辑弱；WeiJiaFiona 和 XanderZhou2022 后端/设计强但前端薄。
4. **医学知识深度**：除 XanderZhou2022 引入 APACHE II 评分外，其余小组的医学规则仍较为简化。

### 3.5 后续建议

1. **数据格式对齐**：各组统一患者数据结构（patient_id、vitals、triage_level、department 等），便于未来跨模块集成。
2. **Agent 接口标准化**：参考 littlegrass-bme 的 `BaseHospitalAgent` 规范（`observe` + `act`），推广到所有小组。
3. **分阶段集成**：以 Jangbo7 前端画布为统一视觉层；WeiJiaFiona FastAPI + event bus 为后端主干；各组业务逻辑通过 REST 接口注入；XanderZhou2022 的 PostgreSQL 扩展为全院统一数据存储。
4. **可演示性优先**：建议所有组在 Week 5 前各完成至少一个"端到端 demo"，即从患者到达到一次流程闭环可完整运行。

---

## 四、共同基础与统一医院集成方案

四组的最终目标是让各自的科室模块能够**运行在同一个医院环境中，并作为整体演示**。本节分析各组现有资产在统一系统中的角色，并提出一个可行的集成架构。

### 4.1 各组资产在统一系统中的角色

| 资产 | 来源组 | 在统一系统中的定位 |
|------|--------|--------------------|
| HTML5 Canvas 全院地图（病房/药房/急诊室/重症室/大厅等） | Jangbo7 | **统一前端视觉层**，所有科室共享同一画布 |
| FastAPI 后端 + EventBus + 状态机 | WeiJiaFiona | **统一后端 API 主干**，各科室注册为独立模块 |
| PostgreSQL 12 张核心表 + 场景化数据 | XanderZhou2022 | **统一数据存储层**，扩展 schema 以覆盖全院 |
| `BaseHospitalAgent` 接口（`observe` + `act`） | littlegrass-bme | **统一 Agent 接口规范**，各组 Agent 按此标准实现 |
| LangChain Agent 服务 + 配置化 prompt | littlegrass-bme | **LLM 接入参考实现**，其他组可复用或适配 |
| APACHE II 评分 JSON + ICU 提示词 | XanderZhou2022 | **医学规则库**，可被 WeiJiaFiona 急诊 + 其他组 Agent 引用 |

### 4.2 统一架构图

```
┌────────────────────────────────────────────────────────────────────┐
│              Jangbo7: HTML5 Canvas  (统一前端视觉层)                 │
│  [ 大厅 ] ──→ [ 护士分诊 ] ──→ [ 急诊室 ] / [ 病房/药房 ] / [ 重症室 ] │
└──────────────────────────┬─────────────────────────────────────────┘
                           │  HTTP Polling / WebSocket
┌──────────────────────────▼─────────────────────────────────────────┐
│          WeiJiaFiona: FastAPI + EventBus  (统一后端 API 主干)         │
│  /outpatient  |  /emergency  |  /inpatient  |  /icu                 │
│  TriageRouter → 按 triage_level 将患者分派到对应科室模块              │
└───────┬──────────────────┬──────────────────┬───────────────────────┘
        │                  │                  │
┌───────▼──────┐  ┌────────▼────────┐  ┌─────▼────────────────────┐
│ littlegrass  │  │  WeiJiaFiona    │  │  XanderZhou2022          │
│ 门诊/住院模块 │  │  ED 急诊模块     │  │  ICU 多智能体模块          │
│ HospitalEng  │  │  StateMachine   │  │  Shared State Board       │
│ +PatientMgr  │  │  +GuardRails    │  │  +RiskSentinel+Monitor   │
└───────┬──────┘  └────────┬────────┘  └─────┬────────────────────┘
        │                  │                  │
        └──────────────────▼──────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────────────┐
│         XanderZhou2022: PostgreSQL  (统一数据存储层)                  │
│  patients | admissions | vital_sign_events | risk_assessments | ...  │
└────────────────────────────────────────────────────────────────────┘
```

### 4.3 患者跨科室流转协议

统一演示的核心是**患者可以从一个科室流转到另一个科室**，这要求各组共同遵守一份最小患者数据格式：

```json
{
  "patient_id": "P-20260328-001",
  "name": "张三",
  "triage_level": 2,
  "department": "emergency",
  "state": "under_evaluation",
  "vitals": {
    "heart_rate": 112,
    "systolic_bp": 88,
    "spo2": 94,
    "temp_c": 38.7
  },
  "encounter_history": [
    { "dept": "outpatient", "event": "triage_complete", "ts": "..." },
    { "dept": "emergency",  "event": "routed_to_red_zone", "ts": "..." }
  ]
}
```

**典型患者路径示例**：

| 病情程度 | 流转路径 | 涉及组 |
|----------|----------|--------|
| 轻症 | 大厅 → 护士分诊 → 骨科门诊 → 药房 → 离院 | Jangbo7 → littlegrass-bme |
| 中重症 | 大厅 → 护士分诊 → 急诊室（红/黄区）→ 留观/住院 | Jangbo7 → WeiJiaFiona → littlegrass-bme |
| 危重症 | 大厅 → 护士分诊 → 急诊室（抢救）→ ICU | Jangbo7 → WeiJiaFiona → XanderZhou2022 |

### 4.4 最小集成里程碑建议

| 阶段 | 目标 | 主要行动 |
|------|------|----------|
| Week 5 | **患者数据格式对齐** | 四组约定共同 JSON schema；Jangbo7 后端 triage 接口返回标准 patient 对象 |
| Week 6 | **Jangbo7 画布对接后端路由** | 分诊完成后前端按 department 字段高亮对应房间，调用各组 API |
| Week 7–8 | **双向事件集成** | WeiJiaFiona EventBus 接收来自 Jangbo7 的 patient_arrived 事件；XanderZhou2022 ICU 接收来自 ED 的 icu_transfer 事件 |
| Week 9–10 | **统一数据层** | XanderZhou2022 PostgreSQL schema 扩展，所有组写入同一库；各组 PatientManager 改为读写 DB API |
| Week 11–12 | **全院端到端 Demo** | 一个患者从大厅进入，经过分诊、急诊、ICU 全流程，Canvas 实时显示状态变化 |

---

## 五、参考文档索引

| 小组 | 关键文档路径 |
|------|-------------|
| Jangbo7 | `Week-4/Jangbo7/scene/README.md`、`Week-4/Jangbo7/backend/README.md` |
| WeiJiaFiona | `Week-4/WeiJiaFiona/week4/code/README.md`、`Week-4/WeiJiaFiona/week4/proposal/proposal.md`、`Week-4/WeiJiaFiona/week4/code/docs/milestones/week4-12.md` |
| XanderZhou2022 | `Week-4/XanderZhou2022/任务书/AI 模拟 ICU 多智能体系统任务书.md`、`Week-4/XanderZhou2022/任务书/Agent 总体数量与分层.md`、`Week-4/XanderZhou2022/system/backend/测试数据库/测试数据库.md` |
| littlegrass-bme | `Week-4/littlegrass-bme/README.md`（`hospital_w3`）、`Week-4/littlegrass-bme/w4-1/README.md`、`Week-4/littlegrass-bme/docs/plan.md` |
