# Week 8 汇报：Memory v1

## (1) 本周的目标

在将auto mode以及 user mode进行merge 之后，本周的核心目标是构建 **Memory 模块**，用于提升系统的连续性（continuity）和交接质量（handoff quality）。

通过引入：
- 结构化事件记录（structured event logging）
- 当前状态摘要（current summary）
- 有边界的检索机制（bounded retrieval）

使系统能够：
- 记住关键医疗过程
- 在交接时提供有效信息
- 支持后续的复盘（replay）和评估（evaluation）

---

## (2) 核心思路

我们借鉴数据库设计思想，将 memory 从：

> “随意记录的聊天历史”

升级为：

> **“结构化存储 + 可检索 + 可复盘”的系统**

核心转变在于：
- 从非结构化 → 结构化（MemoryItem）
- 从不可控 → 可查询（retrieval）
- 从不可分析 → 可复盘（replay）

---

## (3) 本周完成内容

### A

A 本周完成的是 **Memory v1 的底层实现（infrastructure）**，即构建统一的 memory 基础系统，而不是直接修改 user/auto 的业务流程。

本质上，A 负责的是：

> **shared memory substrate 的 contract-freeze 和基础设施层**

具体完成内容包括：

- **`schema.py`**
  - 冻结统一数据结构：
    - `MemoryItem`（事件记录）
    - `CurrentEncounterSummary`（当前状态摘要）
    - `HandoffMemorySnapshot`（交接快照）
    - `MemoryQuery`（检索请求）

- **`taxonomy.py`**
  - 定义并冻结 Week 8 所需的关键事件类型（如 `triage_completed`, `handoff_requested` 等）

- **`storage.py` / `service.py` / `config.py`**
  - 实现 JSON-first 存储方案
  - 实现 mode 隔离（auto / user 不互相污染）
  - 提供统一的 memory 访问入口（service 层）

- **`hooks.py`**
  - 提供 helper 函数：
    - `run_id` 生成
    - `encounter_id` 生成
    - `step` 追踪
    - memory event 构造

- **`audit.py` / `replay_buffer.py` 等 supporting modules**
  - 支持：
    - handoff 快照
    - replay（复盘）
    - audit（日志记录）
    - 后续 ablation 实验

---

###  B

B 的任务是：

> 将 A 提供的 memory substrate 真正接入业务主线

具体包括：

- 将 memory hooks 接入：
  - `api_v1.py`（user mode）
  - `reverie.py`（auto mode）
  - `patient.py` 等核心流程

- 在关键 phase transition 处写入 memory，例如：
  - `triage_completed`
  - `test_ordered`
  - `handoff_requested`
  - `encounter_closed`

- 完成以下系统集成：

  - **ON/OFF ablation plumbing**
    - 支持 Memory 开关对比实验

  - **evaluation 指标实现**
    - continuity（一致性）
    - handoff 完整性
    - repeated-question rate（重复询问率）

  - **replay export CLI**
    - 支持导出运行过程用于分析

  - **docs / runbook**
    - 编写系统使用说明和实验流程

---

## (4) 下周计划（Week 9）

下一周我们将重点关注系统的：

> **安全性（Safety）和鲁棒性（Recovery）**

主要方向包括：

- **高风险建议拦截（High-risk advice blocking）**
  - 防止系统输出危险或不当医疗建议

- **隐私保护（Privacy / PHI Redaction）**
  - 对日志中的敏感信息进行脱敏处理

- **异常恢复机制（Recovery）**
  - 在 LLM 超时或失败时，自动 fallback 到规则系统

---

## 总结一句话

Week 8 的核心工作是：

> **把系统从“没有记忆”升级为“有结构化记忆、可检索、可复盘的系统”，为后续评估和优化打下基础。**