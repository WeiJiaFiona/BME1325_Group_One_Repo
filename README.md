# week9_v1 README

## 1. 当前实现的功能/内容

`week9_v1/` 是在 `week8` merge 系统基础上整理出的干净快照目录，目标是保留可继续开发、测试、演示和提交的核心内容，同时剥离大部分本地运行产物、缓存、日志和高重复文档。

当前保留并可继续使用的核心能力包括：

### 1.1 Auto Mode

- 基于 `reverie/backend_server/` 的自动急诊仿真主后端。
- 支持病人生成、区域流转、队列推进、资源竞争、住院滞留等流程。
- 保留了 Week 7/8 的关键扩展：
  - `arrival_profile_mode`：`normal / surge / burst`
  - `lab/imaging` 容量与周转时间
  - `boarding_timeout` 事件
  - Auto dashboard 与运行时状态同步接口
- 已接入 Auto Memory Hooks：
  - `encounter_started`
  - `resource_bottleneck`
  - `boarding_timeout`
  - `encounter_closed`
  - `disposition_decided`
  - `handoff_requested`
  - `handoff_completed`
  - `next_slot`

### 1.2 User Mode

- 基于 `app_core/app/` 的用户交互问诊主后端。
- 支持医生问诊、handoff、状态流转和结构化响应。
- 保留了 Week 8 的核心能力：
  - LLM 接入
  - 医生限定 RAG
  - Memory v1 写入
  - encounter / handoff 相关流程

### 1.3 Memory v1

- `app_core/memory/` 作为统一 memory substrate 保留。
- 支持：
  - `events.jsonl`
  - `audit.jsonl`
  - `current/`
  - `snapshots/`
  - replay / retrieval / audit
- User Mode 已完整使用这套 Memory v1。
- Auto Mode 已接入最小安全版与扩展版关键 hooks。

### 1.4 前端与可视化

- `environment/frontend_server/` 保留 Django 宿主层与主 UI。
- `templates/home/` 下保留 Auto/User 共用页面、dashboard 与脚本。
- `environment/react_frontend/` 保留 React + R3F 的 3D viewer 链路。
- 当前仓库同时保留：
  - Django 页面宿主
  - Phaser 2D 主地图/仿真界面
  - React Three Fiber 3D viewer

### 1.5 资源、协议与知识库

- 保留 `RAG/doctor_kb/` 医生知识库。
- 保留 `app_core/app/protocols/` 下的 9 套协议 YAML。
- 保留 `data/` 作为 baseline/surge 等参考数据资产。

### 1.6 测试与可运行性

当前快照保留了核心测试脚本与最小运行种子，并已作为清理分支的验收基线使用：

- `tests/`
- `tests_user/`
- `environment/frontend_server/storage/ed_sim_n5/`
- `analysis/scenario_regressions/20260423_103358/`

这意味着该目录不仅是“代码保留版”，也是“可继续验证与回归的干净基线版”。

## 2. 目录结构

下面是 `week9_v1/` 中最重要的目录说明。

```text
week9_v1/
├─ analysis/                          # 指标分析、回归分析脚本
├─ app_core/
│  ├─ app/                            # User Mode 主后端
│  └─ memory/                         # Memory v1 基础设施层
├─ data/                              # 参考数据资产
├─ docker/                            # 容器化相关文件
├─ docs/
│  └─ archive/
│     └─ week8_history/              # 归档的高重复历史文档与旧模板
├─ environment/
│  ├─ frontend_server/               # Django + Phaser 主前端
│  └─ react_frontend/                # React + R3F 3D viewer
├─ examples/                          # 示例文件
├─ RAG/
│  └─ doctor_kb/                     # 医生知识库
├─ reverie/
│  └─ backend_server/                # Auto Mode 主后端
├─ scripts/                           # 运行与回归辅助脚本
├─ static/                            # 静态资源
├─ tests/                             # 后端/前端/analysis 测试
├─ tests_user/                        # User Mode 专项回归测试
├─ week5_system/                      # 历史兼容目录，保留作来源参考
├─ README.md                          # 当前总说明
├─ MERGE_HANDOFF.md                   # merge 交接说明
├─ week8_directory_audit.md           # week8 原始目录梳理说明
└─ week9_cleanup_compare.md           # 清理前后对照说明
```

### 2.1 重点代码目录

- `reverie/backend_server/`
  - Auto Mode 主逻辑
  - 重点文件：
    - `reverie.py`
    - `auto_memory_hooks.py`
    - `maze.py`
    - `path_finder.py`
    - `persona/persona_types/patient.py`

- `app_core/app/`
  - User Mode 主逻辑
  - 重点文件：
    - `api_v1.py`
    - `llm_adapter.py`
    - `handoff.py`
    - `rag/protocol_retriever.py`
    - `protocols/*/v1.yaml`

- `app_core/memory/`
  - Memory v1 核心层
  - 重点文件：
    - `service.py`
    - `schema.py`
    - `storage.py`
    - `hooks.py`
    - `taxonomy.py`
    - `retrieval.py`
    - `current_memory.py`
    - `handoff_memory.py`
    - `replay_buffer.py`
    - `audit.py`

- `environment/frontend_server/`
  - Django 主前端宿主
  - 重点文件：
    - `translator/views.py`
    - `templates/home/home.html`
    - `templates/home/start_simulation.html`
    - `templates/home/live_dashboard.html`
    - `templates/home/scripts/auto_main_script.html`
    - `templates/home/scripts/user_main_script.html`

- `environment/react_frontend/`
  - 3D viewer 链路
  - 重点文件：
    - `src/components/ThreeFloorPlan.tsx`
    - `package.json`

### 2.2 资源与知识库目录

- `RAG/doctor_kb/`
  - 医生侧本地知识库
- `app_core/app/protocols/`
  - 9 套协议 YAML
- `data/`
  - baseline/surge 等参考数据

### 2.3 测试目录

- `tests/`
  - backend / frontend / analysis 测试
- `tests_user/`
  - User Mode 专项测试

### 2.4 保留的必要种子与代表性结果

- `environment/frontend_server/storage/ed_sim_n5/`
  - Auto Mode smoke test 所需种子 simulation
- `analysis/scenario_regressions/20260423_103358/`
  - 代表性历史回归结果样本

### 2.5 已归档而非删除的历史文档

为满足“不能删除本地文件”的要求，同时减少干净分支中的文档重复，部分历史文档和旧模板被移动归档到：

- `docs/archive/week8_history/`

其中包括：

- `Developer_A.md`
- `DeveloperA_memory_contract_freeze.md`
- `auto_mode_memory_hooks_design.md`
- `init.md`
- `INIT_CONTEXT.md`
- `week7_handoff.md`
- `week7_progress.md`
- `week7_progress_summary.md`
- `week8_conclass.md`
- `week8_proposal.md`
- `week8_report.md`
- `legacy_templates/main_script_old_dolores.html`

## 3. 当前交接进度（Week 9 HIS / Developer B）

这一部分用于 Week 9 HIS 并行开发的交接，重点说明：

- Developer A 的 HIS substrate 目前在本目录中已 fetch 到什么程度
- Developer B 已经补齐了哪些占位与验证框架
- 还有哪些关键功能尚未真正落地

### 3.1 已完成的交接基础

- 已从 `weijiafiona/week9` 分支的 `week9_v1/` 路径 fetch Developer A 当前上传内容，并在本地整理为可继续开发的工作区。
- 已补入 `app_core/his/` 基础目录，包含：
  - `schemas/`
  - `services/`
  - `auth/`
  - `exchange/`
  - `projections/`
  - `adapters/`
- 已补入 A 侧冻结材料与最小 gate 参考：
  - `docs/architecture/week9_his_contract_freeze_v1.md`
  - `sql/postgres/001_core_master_tables.sql`
  - `sql/postgres/002_encounter_tables.sql`
  - `sql/postgres/003_order_result_tables.sql`

### 3.2 Developer B 当前已完成内容

#### 3.2.1 Adapter 占位

- `app_core/his/adapters/memory_adapter.py`
  - 已建立 Memory v1 -> HIS 的目标映射计划
  - 已明确：
    - `MemoryItem -> memory_events / event_registry`
    - `CurrentEncounterSummary -> current_encounter_summaries`
    - `HandoffMemorySnapshot -> handoff_snapshots / clinical_documents`
    - replay export -> `replay_exports`
  - 当前仍为占位实现，核心函数尚未接入真实 HIS service 写入

- `app_core/his/adapters/contract_adapter.py`
  - 已建立 contract 对齐常量与字段映射说明
  - 已冻结：
    - `patient_id`
    - `encounter_id`
    - `CTAS`
    - `zone`
    - `event envelope`
    - route names
  - 当前仍为占位实现，尚未生成真实对外 payload

#### 3.2.2 Field Mapping 文档

- 已新增：
  - `docs/architecture/week9_memory_to_his_field_mapping.md`
- 该文档已经说明：
  - Memory v1 三类核心对象如何映射到 HIS 目标表
  - 哪些字段必须走 A 的 service boundary
  - 哪些内容仍然被 `storage/base.py` gate 阻塞

#### 3.2.3 测试脚手架

- 已新增 B 侧测试文件：
  - `tests_his/test_memory_upgrade_path.py`
  - `tests_his/test_contract_alignment.py`
  - `tests_his/test_his_user_flow_integration.py`
  - `tests_his/test_handoff_summary_connectivity.py`
  - `tests_his/test_timeline_export.py`
  - `tests_his/test_stemi_golden_path_smoke.py`

- 当前这些测试的状态是：
  - 一部分用于校验 frozen 常量、目标表名和占位计划是否存在
  - 真正依赖 workflow / storage / persistence 的测试仍未落地
  - `test_his_user_flow_integration.py` 会因 `app_core/his/storage/base.py` 尚未到位而跳过

#### 3.2.4 Smoke / Golden Path 规划脚本

- 已新增：
  - `scripts/run_his_contract_smoke.py`
  - `scripts/run_his_timeline_export_smoke.py`
  - `scripts/run_his_stemi_golden_path.py`

- 当前作用：
  - 固定 contract smoke 的检查面
  - 固定 timeline export 的预期组成
  - 固定 STEMI golden-path 的主链路阶段

- 当前限制：
  - 这些脚本仍属于 planning / placeholder 层
  - 尚未连到真实 HIS write path

### 3.3 当前尚未落实的关键功能

以下内容仍未进入“真实实现”阶段：

- `memory_adapter.py` 的正式写入逻辑
- `contract_adapter.py` 的真实 payload / envelope 生成逻辑
- `app_core/app/api_v1.py` 中 user-mode -> HIS service 的关键写路径
- summary / handoff / timeline 的正式 HIS 集成
- contract alignment 的真实 payload 级验证
- STEMI integrated smoke 的真实运行链路

### 3.4 当前阻塞点

按 `week9_his_developer_B_spec_v2.md` 与 `week9_his_merge_protocol_v2.md` 的要求，Developer B 深集成前需要 A 提供最小 gate。

当前已经具备：

- `schemas/*`
- `services/*`
- `sql/postgres/001~003.sql`
- contract freeze 文档

当前仍缺：

- `app_core/his/storage/base.py`

因此当前阶段最合理的状态是：

- B 的文档、adapter scaffold、tests scaffold、smoke scaffold 已搭好
- 真正的 workflow integration 仍需等待 storage/service 写路径进一步稳定

### 3.5 交接建议

如果下一位开发者继续推进 Developer B 任务，建议按下面顺序继续：

1. 确认 A 是否已经补齐 `app_core/his/storage/base.py`
2. 将 `memory_adapter.py` 从占位改为真实映射实现
3. 将 `contract_adapter.py` 从常量层改为真实 contract payload 生成层
4. 在 `app_core/app/api_v1.py` 的 user-mode checkpoint 中接入 HIS services
5. 完成 summary / handoff / timeline integration
6. 把 `tests_his/` 从 placeholder 断言升级为真实写路径验证
7. 最后跑 contract smoke 与 STEMI golden-path smoke
