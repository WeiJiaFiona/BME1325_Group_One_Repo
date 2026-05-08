# Week 9 清理前后目录对照清单

## 1. 说明

本次清理基于 `week8` 合并系统目录完成，目标是在**不改动原始本地 `week8/` 目录文件**的前提下，整理出一份适合继续开发、测试和提交的干净分支。

清理策略：

- 保留核心源码、测试代码、资源/知识库、必要种子数据。
- 剔除运行产物、临时快照、缓存、日志、视频。
- 保留一套代表性的历史回归结果作为参考样本。
- 将高冗余文档归档到 `docs/archive/week8_history/`，而不是直接删除。

## 2. 清理前目录特征

清理前的 `week8` 目录同时混合了以下内容：

- 核心源码：
  - `reverie/`
  - `app_core/app/`
  - `app_core/memory/`
  - `environment/frontend_server/`
  - `environment/react_frontend/`
- 资源与知识库：
  - `RAG/doctor_kb/`
  - `app_core/app/protocols/`
  - `data/`
- 测试代码：
  - `tests/`
  - `tests_user/`
- 运行产物与缓存：
  - `runtime_data/`
  - `environment/frontend_server/storage/` 下多组模拟结果
  - `environment/frontend_server/temp_storage/`
  - `.pytest_cache/`
  - `__pycache__/`
  - `verify_backend.out.log`
  - `verify_backend.err.log`
- 历史实验结果：
  - `analysis/scenario_regressions/` 下多组时间戳回归目录
- 多份高重叠文档：
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

## 3. 清理后保留的主目录

清理后的 `week9` 分支根目录保留：

- 核心源码
  - `reverie/`
  - `app_core/`
  - `environment/`
  - `analysis/`
  - `scripts/`
  - `static/`
- 资源/知识库
  - `RAG/`
  - `data/`
- 测试代码
  - `tests/`
  - `tests_user/`
- 历史兼容代码
  - `week5_system/`
- 必要文档
  - `README.md`
  - `MERGE_HANDOFF.md`
  - `week8_directory_audit.md`
- 归档文档
  - `docs/archive/week8_history/`

## 4. 清理前后对照

### 4.1 核心源码

保留不变：

- `reverie/backend_server/`
- `app_core/app/`
- `app_core/memory/`
- `environment/frontend_server/`
- `environment/react_frontend/`
- `analysis/compute_metrics.py`

### 4.2 资源/知识库

保留不变：

- `RAG/doctor_kb/`
- `app_core/app/protocols/`
- `data/`

### 4.3 测试代码

保留不变：

- `tests/`
- `tests_user/`

新增或同步保留的重要测试：

- `tests/backend/test_auto_memory_hooks.py`
- `tests/backend/test_memory_schema.py`
- `tests/backend/test_memory_storage.py`
- `tests/backend/test_memory_service.py`
- `tests/backend/test_memory_retrieval.py`

### 4.4 运行产物与缓存

从干净分支中剔除：

- `runtime_data/`
- `environment/frontend_server/temp_storage/`
- `environment/frontend_server/storage/` 中的大多数运行态 simulation 目录
- `.pytest_cache/`
- `__pycache__/`
- `verify_backend.out.log`
- `verify_backend.err.log`
- `*.mp4`

例外保留：

- `environment/frontend_server/storage/ed_sim_n5/`

保留原因：

- `ed_sim_n5` 是 auto mode 启动和 smoke test 需要的种子 simulation。

### 4.5 历史实验结果

清理前：

- `analysis/scenario_regressions/` 下有多组时间戳目录。

清理后：

- 仅保留 `analysis/scenario_regressions/20260423_103358/`

保留原因：

- 作为一套代表性的历史回归结果样本，便于后续说明和复核。

### 4.6 文档整理

根目录继续保留：

- `README.md`
- `MERGE_HANDOFF.md`
- `week8_directory_audit.md`

归档到 `docs/archive/week8_history/`：

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

## 5. 额外保留的关键种子与基线

保留：

- `environment/frontend_server/storage/ed_sim_n5/`
- `analysis/scenario_regressions/20260423_103358/`

原因：

- 前者是 auto mode 必需的 seed simulation。
- 后者是历史实验结果中最具代表性的一组，可用于说明回归分析框架。

## 6. 测试验证结果

在清理后的 `week9` 工作区中完成了以下验证：

- Django 前端检查通过
  - `manage.py check`
- 核心测试通过
  - `python -m pytest -v`
  - 结果：`107 passed`
- User mode 回归通过
  - `python -m pytest tests_user -v`
  - 结果：`60 passed`
- Auto mode smoke test 通过
  - `run 20`
  - 结果：成功完成

## 7. 最终结论

`week9` 分支相较于原始 `week8`：

- 保留了核心源码、测试和资源；
- 去除了运行时噪音和大部分历史快照；
- 把高冗余文档移到归档目录；
- 保证了 user mode 与 auto mode 的基本验证仍然通过；
- 同时不影响你原始本地 `week8/` 目录中的任何文件。
