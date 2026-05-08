# Week 8 总结说明

## 一、本周的目标

在 merge 之后，本周的目标是构建 Memory v1 模块，用于提升系统的连续性（continuity）和交接质量（handoff quality）。通过引入结构化事件记录、当前状态摘要和有边界的检索机制，使系统能够记住关键医疗过程，并支持后续复盘和评估。

## 二、说明

我们借鉴数据库设计，把 memory 从“随意记录”变成“结构化存储 + 可检索 + 可复盘”的系统。

换句话说，Week 8 的重点不是简单增加几条日志，而是把 memory 建成一个有统一 schema、有明确事件分类、有固定存储路径、并且能支持后续 replay 与评估的数据基础设施层。这样无论后面接入 user mode 还是 auto mode，都可以复用同一套 memory contract，而不需要再分别设计两套不兼容的记录方式。

## 三、本周完成的内容

### 1. Developer A 完成的部分

A 完成的是 Memory v1 的底层实现（infrastructure），构建统一的记忆系统基础。

Developer A 负责的是 shared memory substrate 的 contract-freeze 和基础设施层，而不是直接改动 user/auto 的运行主线。对应地，本周已经完成的内容主要包括：

- `schema.py`：冻结 `MemoryItem`、`CurrentEncounterSummary`、`HandoffMemorySnapshot`、`MemoryQuery` 等统一数据结构。
- `taxonomy.py`：冻结 Week 8 MVP 需要的关键事件分类名称。
- `storage.py`、`service.py`、`config.py`：实现 JSON-first、mode-isolated 的存储路径和统一服务访问入口。
- `hooks.py`：提供 run_id、encounter_id、step 追踪和 memory event 构造所需 helper。
- `audit.py`、`replay_buffer.py` 及其他 supporting modules：为 handoff、replay、audit 和后续 ablation 做基础设施准备。

这一部分的结果是，Week 8 已经具备了统一的 Memory v1 基座，后续可以在同一套 schema、同一套 storage path 和同一套 service 接口上继续推进。

### 2. Developer A 实施流程图

下图用于说明 Developer A 在 Week 8 中完成的 Memory v1 基础设施搭建流程：

![Developer A Memory v1 实施流程图](./developer_a_memory_v1_flow.png)

注：当前文档中已经预留图片插入位置；若本地预览未显示，说明该流程图图片文件尚未单独保存到 `week8/` 目录。

### 3. Developer B 负责推进的部分

B 负责把 A 提供的 helper 和 service 真正接入业务主线，也就是把 user mode 和 auto mode 中的关键 phase transition 与 runtime event 写入 Memory v1。

- 把 memory hooks 接入 `api_v1.py`、`reverie.py`、`patient.py` 等业务代码。
- 完成 ON/OFF ablation plumbing。
- 完成 continuity / handoff / repeated-question evaluation。
- 完成 replay export CLI。
- 完成 docs / runbook 的集成说明。

因此，Week 8 当前已经完成的是 memory 的基础设施层；而真正的业务主线接线、实验对比和评估链路，属于 Developer B 继续推进的部分。

## 四、下一周的计划

下一周我们将重点关注系统的安全性和鲁棒性，包括高风险建议拦截、隐私保护和异常恢复机制。

- 目标：安全且可审计的降级 / safe and auditable degradation
- 复用：基础日志与运行控制钩子 / baseline logs and runtime control hooks
- 优化：高风险建议拦截 / high-risk advice blocking
- 优化：隐私脱敏日志 / PHI-redacted logs
- 优化：超时回退规则 / fallback-to-rule on timeout
- 测试：危险建议注入 / dangerous suggestion injection
- 测试：隐私泄露尝试 / privacy leakage attempt
- 测试：超时恢复 / timeout recovery

前端 UI
```bash
cd D:\projects\BME1325Spring2026\BME1325_Group_One_Repo\week8\environment\frontend_server
conda activate edmas
$env:EDSIM_MODE="auto"
python manage.py runserver 0.0.0.0:8010
```

后端
```bash
cd D:\projects\BME1325Spring2026\BME1325_Group_One_Repo\week8\reverie\backend_server
conda activate edmas
$env:EDSIM_MODE="auto"
$env:LLM_MODE="local_only"
$env:EMBEDDING_MODE="local_only"
python reverie.py --frontend_ui yes --origin ed_sim_n5 --target curr_sim
```

```txt
http://127.0.0.1:8010/start_simulation?ui_mode=auto
http://127.0.0.1:8010/simulator_home?ui_mode=auto
```