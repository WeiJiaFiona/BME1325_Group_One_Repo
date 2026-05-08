# Week8 目录梳理结论

## Summary

- 我对本地 `D:\projects\BME1325Spring2026\BME1325_Group_One_Repo\week8` 目录以及远端 `WeiJiaFiona/BME1325_Group_One_Repo` 的 `week8` 分支进行了对照梳理。
- 结论上，`week8` 是一个“**双运行时 + 多文档 + 较多本地运行产物**”的 merged 目录。
- 阅读和维护时，建议优先区分两层：
  - **代码与文档层**：真正需要继续维护、开发、交接的内容
  - **运行产物与缓存层**：本地调试、测试、演示过程中生成的内容
- 远端 GitHub `week8` 分支与本地 `week8` 的主结构是一致的，但本地还包含不少运行期附加文件，这些不应被等同看作远端核心源码。

## 一、本地 `week8` 目录怎么分

### 1. 最重要的代码目录

这些目录是 `week8` 的核心实现部分，也是后续阅读和继续开发时最优先关注的代码区域。

#### `week8/reverie/backend_server/`

Auto mode 主后端，负责仿真主循环、人物行为、路径规划、资源队列、boarding timeout、auto memory hooks 等逻辑。

最关键文件：

- `reverie.py`
- `auto_memory_hooks.py`
- `maze.py`
- `path_finder.py`
- `wait_time_utils.py`
- `week7_logic.py`
- `persona/persona_types/patient.py`

#### `week8/app_core/app/`

User mode 主后端，负责问诊状态机、协议检索、handoff、LLM/RAG 接入和 API 行为。

最关键文件：

- `api_v1.py`
- `mode_user.py`
- `llm_adapter.py`
- `handoff.py`
- `schema.py`
- `rag/protocol_retriever.py`
- `protocols/*/v1.yaml`

#### `week8/app_core/memory/`

Memory v1 基础设施层，是 user/auto 两侧未来统一 memory 写入、审计、回放的入口。

关键文件：

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

#### `week8/environment/frontend_server/`

Django 宿主层与主前端 UI 所在位置，负责 `EDSIM_MODE`、模板渲染、接口转发、live dashboard 和 Phaser 播放链路。

最关键文件：

- `translator/views.py`
- `templates/home/home.html`
- `templates/home/start_simulation.html`
- `templates/home/live_dashboard.html`
- `templates/home/main_script.html`
- `templates/home/scripts/auto_main_script.html`
- `templates/home/scripts/user_main_script.html`

#### `week8/environment/react_frontend/`

React + Three.js / R3F 的 3D floor-plan viewer 子系统。它不是当前 Django 主运行界面的唯一入口，但确实是仓库内真实存在的另一套前端链路。

最关键文件：

- `src/components/ThreeFloorPlan.tsx`
- `package.json`

#### `week8/analysis/`

分析脚本与回归分析支持目录。

最关键文件：

- `compute_metrics.py`

与之最常配套使用的脚本：

- `scripts/run_week7_long_regression.py`

### 2. 重要但偏“资源/知识库”的目录

这些目录不是主执行逻辑，但对系统能力很关键。

#### `week8/RAG/doctor_kb/`

医生专用本地知识库。

- `sources/`：原始知识源
- `compiled/`：编译后的 chunk
- `indices/`：检索索引
- `normalized/`：归一化中间结果
- `manifests/`、`ontologies/`：结构定义

#### `week8/app_core/app/protocols/`

9 套协议 YAML，是 user mode 协议检索与结构化问诊逻辑的基础。

当前协议目录包括：

- `abdominal_pain`
- `anaphylaxis`
- `chest_pain`
- `dyspnea`
- `headache`
- `labor`
- `sepsis`
- `stroke`
- `trauma`

#### `week8/data/`

存放 baseline/surge 等 CSV 对照数据，更像“参考数据资产”，而不是主逻辑代码。

### 3. 测试代码目录

这些目录是“之前的测试案例”，不是测试结果。

#### `week8/tests/`

包含 backend / frontend / analysis 测试。

代表性文件：

- `tests/backend/test_auto_memory_hooks.py`
- `tests/backend/test_memory_*.py`
- `tests/backend/test_path_finder.py`
- `tests/frontend/test_views.py`
- `tests/analysis/test_compute_metrics.py`

#### `week8/tests_user/`

是 user mode 的专门回归测试。

代表性文件：

- `test_handoff_integration.py`
- `test_mode_user_contracts.py`
- `test_week6_user_mode_chat.py`
- `test_doctor_kb_*`

### 4. 本地运行产物 / 缓存 / 临时结果

这些内容不是核心源码，更偏本地调试、验证和演示残留。

#### 缓存类

- `.pytest_cache/`
- 各目录下的 `__pycache__/`

#### 本地运行时数据

- `runtime_data/memory/`
  - `events.jsonl`
  - `audit.jsonl`
  - `current/...`
  - `snapshots/...`
- `environment/frontend_server/storage/`
  - `curr_sim`
  - `debug_run20`
  - `week8_run100`
  - `verify_auto_*`
  - 以及其他以 `sim_code` 命名的目录
- `environment/frontend_server/temp_storage/`
- `environment/frontend_server/db.sqlite3`

#### 本地日志 / 验证文件

- `verify_backend.out.log`
- `verify_backend.err.log`

#### 本地清单 / 辅助文件

- `modified_files_upload_list.txt`

#### 视频 / 演示产物

- `week8_auto.mp4`
- `week8_auto_修改后.mp4`

这些文件中：

- `runtime_data/memory/` 是真实运行写出的 memory 数据
- `storage/` 和 `temp_storage/` 是 auto/frontend 的运行态文件
- `verify_backend*.log`、`*.mp4` 属于验证或展示结果

它们都不应被当成“需要长期维护的核心代码”。

### 5. 历史实验结果 / 测试得到的结果

这些内容更像“之前的测试结果”，不是测试代码。

#### `analysis/scenario_regressions/`

- 内含多批时间戳目录，例如 `20260423_103358`
- 目录内通常包含 `summary.json`、`deep/...` 等输出
- 本质上属于历史回归实验结果

#### `runtime_data/memory/`

- 可以视为 Memory v1 的真实运行结果或功能测试产物

#### `environment/frontend_server/storage/<sim_code>/`

- 每个 `sim_code` 基本都对应某次 auto run 的运行结果快照

## 二、哪些文件“冗杂”或表达重复意思

### 1. 明显内容重叠的说明文档

这些文档不一定都没用，但表达范围有明显重叠，后续维护时很容易反复重复。

- `README.md`
  - 面向外部读者的总说明
- `MERGE_HANDOFF.md`
  - 偏 merge 交接与 auto/user 保留说明
- `week8_proposal.md`
  - 偏设计提案与任务规划
- `Developer_A.md`
  - 偏 Developer A 的任务边界与开发要求
- `DeveloperA_memory_contract_freeze.md`
  - 偏 Memory v1 contract 交接说明
- `auto_mode_memory_hooks_design.md`
  - 偏 auto memory hooks 的专项设计说明
- `week8_conclass.md`
  - 偏课程总结/汇报说明
- `week8_report.md`
  - 偏报告稿
- `init.md`
  - 偏当前项目初始化与工作约束
- `INIT_CONTEXT.md`
  - 同样承担初始化上下文作用

最明显的重复组：

- `init.md` 和 `INIT_CONTEXT.md`
- `Developer_A.md` 和 `DeveloperA_memory_contract_freeze.md`
- `README.md`、`MERGE_HANDOFF.md`、`week8_conclass.md`、`week8_report.md`
- `week8_proposal.md` 与若干已落地设计文档之间也有交叉

结论不是“这些都应该删除”，而是：

- **它们表达对象不完全相同，但信息重叠较多，属于文档冗余高的区域。**

### 2. 旧版或旁支文件

#### `templates/home/main_script_old_dolores.html`

- 明显属于旧脚本备份或历史遗留
- 语义上与 `main_script.html + scripts/auto_main_script.html + scripts/user_main_script.html` 重叠

#### `week5_system/`

- 属于历史 user/system 版本残留
- 对理解 merge 来源有帮助
- 但不是当前主运行逻辑

#### `docs/architecture/week7_auto_baseline_analysis.md`

- 对历史来源有帮助
- 但不是 week8 主操作文档

### 3. README 与现实目录不完全一致的地方

远端 `README.md` 中提到：

- `tests_week8`

但本地 `week8` 目录下并没有真实的 `tests_week8/` 目录。

这说明 README 有一部分内容属于：

- 阶段性文档残留
- 或命名尚未同步到当前目录结构

这类文件不能简单说是“错误”，但可以判断为：

- **文档表达先于或滞后于实际目录的赘余信息**

## 三、远端 GitHub `week8` 分支怎么理解

### 1. 远端主干结构与本地一致的部分

已直接核对远端以下关键文件：

- `README.md`
- `MERGE_HANDOFF.md`
- `environment/frontend_server/translator/views.py`
- `app_core/app/api_v1.py`
- `reverie/backend_server/reverie.py`
- `environment/react_frontend/package.json`

可以确认远端 `week8` 分支的主结构就是：

- `environment/frontend_server`：Django + Phaser UI
- `environment/react_frontend`：React + R3F 3D viewer
- `reverie/backend_server`：auto mode
- `app_core/app`：user mode
- `app_core/memory`：Memory v1
- `RAG/doctor_kb`：医生知识库
- `analysis`：指标与回归分析
- 多份 merge / proposal / handoff / report 文档

因此，对于“哪些是重要代码文件、哪些是文档冗余”的判断，远端和本地是一致的。

### 2. 远端不会等同于你本地所有文件

本地还有大量运行期生成内容：

- `runtime_data/memory/...`
- `environment/frontend_server/storage/...`
- `temp_storage/...`
- `verify_backend*.log`
- `db.sqlite3`
- `*.mp4`
- `.pytest_cache`
- `__pycache__`

这些都不应被当成“GitHub 上需要长期阅读的仓库主体”。

所以远端部分更适合按下面四类理解：

#### 重要源码

- `reverie/backend_server/*`
- `app_core/app/*`
- `app_core/memory/*`
- `environment/frontend_server/translator/views.py`
- `environment/frontend_server/templates/home/*`
- `environment/react_frontend/src/*`

#### 知识资源

- `RAG/doctor_kb/*`
- `app_core/app/protocols/*`

#### 测试代码

- `tests/*`
- `tests_user/*`

#### 说明文档

- `README.md`
- `MERGE_HANDOFF.md`
- `Developer_A.md`
- `week8_proposal.md`
- `week8_conclass.md`
- `week8_report.md`

### 3. 远端里更像“冗余 / 赘余”的部分

如果从 GitHub 分支长期维护的角度看，优先会被认为冗余的是：

#### 多份高重叠文档

- `README.md`
- `MERGE_HANDOFF.md`
- `week8_proposal.md`
- `week8_conclass.md`
- `week8_report.md`
- `Developer_A.md`
- `DeveloperA_memory_contract_freeze.md`
- `auto_mode_memory_hooks_design.md`
- `init.md`
- `INIT_CONTEXT.md`

#### 历史脚本 / 旧模板

- `main_script_old_dolores.html`

#### 历史兼容目录

- `week5_system/`

这里更准确的判断应是：

- **这些内容的信息重叠高、历史包袱重，但不一定都应当立刻删除。**
- 如果将来做仓库整理，它们会是第一批需要合并、归档或精简的对象。

## 四、可直接使用的分类结论

### 本地目录中最重要的代码文件

- `week8/reverie/backend_server/reverie.py`
- `week8/reverie/backend_server/persona/persona_types/patient.py`
- `week8/reverie/backend_server/auto_memory_hooks.py`
- `week8/reverie/backend_server/maze.py`
- `week8/reverie/backend_server/path_finder.py`
- `week8/app_core/app/api_v1.py`
- `week8/app_core/app/llm_adapter.py`
- `week8/app_core/app/rag/protocol_retriever.py`
- `week8/app_core/memory/service.py`
- `week8/app_core/memory/schema.py`
- `week8/app_core/memory/storage.py`
- `week8/environment/frontend_server/translator/views.py`
- `week8/environment/frontend_server/templates/home/home.html`
- `week8/environment/frontend_server/templates/home/start_simulation.html`
- `week8/environment/frontend_server/templates/home/scripts/auto_main_script.html`
- `week8/environment/frontend_server/templates/home/scripts/user_main_script.html`
- `week8/environment/react_frontend/src/components/ThreeFloorPlan.tsx`

### 更像缓存 / 本地运行态文件

- `.pytest_cache/`
- `__pycache__/`
- `environment/frontend_server/temp_storage/`
- `environment/frontend_server/storage/`
- `runtime_data/memory/`
- `environment/frontend_server/db.sqlite3`
- `verify_backend.out.log`
- `verify_backend.err.log`

### 更像历史测试案例

- `tests/`
- `tests_user/`

### 更像历史测试结果 / 回归结果

- `analysis/scenario_regressions/`
- `runtime_data/memory/`
- `environment/frontend_server/storage/<sim_code>/`

### 更像文档重叠 / 冗余区

- `README.md`
- `MERGE_HANDOFF.md`
- `week8_proposal.md`
- `week8_report.md`
- `week8_conclass.md`
- `Developer_A.md`
- `DeveloperA_memory_contract_freeze.md`
- `auto_mode_memory_hooks_design.md`
- `init.md`
- `INIT_CONTEXT.md`

## Assumptions

- 远端 GitHub 分支的结构判断，基于已直接读取的远端关键文件和本地 `week8` 主目录结构，结论对“核心代码与文档分类”是可靠的。
- 本地 `runtime_data/`、`storage/`、`temp_storage/`、日志和视频文件，属于本地运行 / 验证附加层，不应与远端核心源码等量齐观。
- 如果下一步要做“清理仓库”，最适合先从 **文档去重 + 缓存/运行产物隔离 + 历史模板归档** 三块开始。
