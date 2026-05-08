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

## 3. 这份 README 与其他说明文件的关系

本 README 是 `week9_v1/` 的统一入口说明，主要吸收并整合了两份说明文件的信息：

- `week8_directory_audit.md`
  - 负责解释 week8 原始目录的组成、重要代码、缓存、测试与冗余文档
- `week9_cleanup_compare.md`
  - 负责解释清理前后保留了什么、归档了什么、为什么这样整理

如果你需要：

- 看“原始 week8 为什么显得杂”，优先读 `week8_directory_audit.md`
- 看“week9_v1 为什么这样保留与归档”，优先读 `week9_cleanup_compare.md`
- 看“现在这份干净版本能做什么、目录怎么理解”，优先读本 README
