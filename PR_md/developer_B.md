下面是一版可直接给 **Developer B / Codex** 的说明。

---

# Developer B 面向 Codex 的实现说明（Week 8 Memory v1）

## 1. 你的角色定义

你现在的角色是 **Developer B**。
你的核心职责不是搭底层 memory substrate，而是：

> **把 Week 8 的 Memory v1 接入已经合并完成的 `week8/merge` 系统，重点负责 user-mode hooks、evaluation、ON/OFF ablation、以及保证 memory 接入后不破坏 user mode 现有行为。**

Week 8 的核心目标已经明确：在 merged ED system 上实现一套 **shared-but-mode-isolated** 的 Memory v1，用于提升 continuity、handoff quality、replay/audit 和 repeated-question reduction，而不是改 planner ownership。

---

## 2. 你必须先理解的系统现状

### 2.1 唯一开发根目录

本周所有开发都必须发生在：

```text
/home/jiawei2022/BME1325/week8/merge
```

不要回到：

* `/home/jiawei2022/BME1325/week8/user_mode`
* `/home/jiawei2022/BME1325/week8/auto`

继续写运行时代码。
`merge` 已经是唯一 source of truth。merge handoff 已明确说明 merged system root 就是 `week8/merge`，并且 user runtime logic lives under `app_core/`。

### 2.2 你不能破坏的 mode 边界

当前 merge 已经实现：

* backend startup `EDSIM_MODE` 是唯一真源
* `ui_mode` 只是 UI 层，不切后端能力
* `EDSIM_MODE != user` 时，`/mode/user/*` 返回 `409 MODE_MISMATCH`。

因此你接入 memory 时必须假设：

* auto / user **共用 memory 基础设施**
* 但每次运行必须用 `run_id + mode + encounter_id` 隔离
* 不允许把 auto 和 user 的事件混进同一条 encounter timeline

### 2.3 user mode 当前已经保留的能力

merge handoff 已确认 user mode 在 merge 中已保留：

* Intake → Calling nurse vitals → Triage → Queue/wait → Doctor → Bedside nurse → Done
* calling nurse
* shared memory across roles
* `pending_messages` + phase auto-progression
* doctor-only local KB + selective RAG
* one-question-per-turn / anti-repeat
* pain-score triage fix。

这意味着你作为 B，最重要的是：

> **memory 接入后，上述 user mode 行为不能被破坏，也不能被悄悄降级。**

---

## 3. 你是否需要先 clone 什么目录

## 结论

**通常不需要再 clone auto 或 user 主代码目录。**

因为：

* collaborator auto 已经 fetch 到 `week8/auto`
* merge 已经完成到 `week8/merge`
* user 的 `app_core` 和 `RAG/doctor_kb` 也已经 graft 进 merge。

### 你开工前只需要确认这些目录存在

```text
/home/jiawei2022/BME1325/week8/merge
/home/jiawei2022/BME1325/week8/merge/app_core
/home/jiawei2022/BME1325/week8/merge/RAG/doctor_kb
/home/jiawei2022/BME1325/week8/merge/tests_user
```

### 什么时候才需要额外 clone

只有一种情况：
如果你想额外阅读 Group4 的 backend/data 分层结构，可以单独 clone：

```bash
git clone https://github.com/XanderZhou2022/BME_1325_Group4_repo.git
```

但它只作为**架构参考**，不作为 Week 8 运行时依赖。你的 memory migration proposal 已明确指出 Group4 可借的是 event bus / current state / snapshot / audit / API boundary，不建议直接迁 ICU-specific schema 或 PostgreSQL-first 强依赖。

---

## 4. 你应该先读哪些文档

按以下顺序读：

### 第一优先级

1. `week8/merge_execution_plan.md`
2. merge handoff 文档（Week8 Merge Handoff）

因为它们说明了：

* merge 是如何做的
* 哪些 auto/user 升级已保留
* mode 边界
* 如何运行与测试。

### 第二优先级

3. Week 8 memory migration proposal
   这份文档已经把：

* `MemoryItem`
* write path
* retrieval path
* `HandoffMemory`
* replay buffer
* MVP recommendation

说明得很清楚。

### 第三优先级

4. 你自己的 user-mode upgrade 相关文档 / `week6_interface/user_mode_upgrade_plan.md`
   因为你要理解哪些行为是 **绝不能在 Week 8 memory 接入时被破坏** 的。之前合并分析里已经确认 user-mode 前端并不是独立页面，而是 `home.html + main_script.html` 渲染出来的，你要记住这一点。

---

## 5. Developer B 的职责边界

## 你负责的内容

你负责的是 **integration + evaluation**，不是 substrate。

### 你应该负责：

1. 在 user mode 挂 memory write hooks
2. 在 auto mode 协助挂 memory write hooks（如果 A 已经把公共接口准备好）
3. 做 retrieval checkpoints 的接入验证
4. 做 handoff continuity 验证
5. 做 replay export 的使用验证
6. 做 memory ON/OFF ablation
7. 做 Week 8 指标评估：

   * repeated-question rate
   * handoff omission
   * continuity consistency
   * latency overhead

这些都和 proposal 里的 Week 8 test targets 一致。

## 你不能做的事情

你**不能**：

1. 另写一套 memory schema
2. 另写一套 storage backend
3. 直接在 user / auto 业务代码里绕过 memory service 做文件 IO
4. 改 planner ownership
5. 改 `next_slot` ownership
6. 改 safety floor / disposition ownership
7. 把 memory 变成 always-on retrieval
8. 把 auto/user 混进同一个 encounter timeline

---

## 6. 你和 Developer A 的协作方式

### A 负责

A 负责实现：

* `app_core/memory/schema.py`
* `taxonomy.py`
* `storage.py`
* `episode_memory.py`
* `current_memory.py`
* `handoff_memory.py`
* `retrieval.py`
* `replay_buffer.py`
* `audit.py`
* `service.py`

### 你负责

你负责在这个 substrate 上做：

* user hooks
* auto hooks（优先以 integration 方式，不重写 substrate）
* evaluation
* ablation
* replay verification

### 在你开始前，必须先冻结这 7 个 contract

如果 A 还没冻结，你必须先停下来和她一起冻结：

1. `MemoryItem`
2. `CurrentEncounterSummary`
3. `HandoffMemorySnapshot`
4. `MemoryQuery`
5. event taxonomy
6. storage interface
7. hook point list

如果这些没冻结，**不要先写 integration**，否则你后面会返工。

---

## 7. 你要使用的公共接口（假设 A 正常实现）

你只能通过 `app_core/memory/service.py` 暴露的接口接入。

你应该期待至少有这些方法：

```python
memory_service.append_event(...)
memory_service.upsert_current_summary(...)
memory_service.get_current_summary(...)
memory_service.write_handoff_snapshot(...)
memory_service.retrieve(...)
memory_service.export_replay(...)
memory_service.append_audit(...)
```

你不应该直接碰：

* JSONL 文件
* SQLite 文件
* summaries 文件
* snapshots 文件

这些都应该通过公共 service 层访问。

---

## 8. 你在 user mode 里必须挂的 hook 点

proposal 已经把 write path 描述得很清楚，你要重点把这些 user-mode 节点接到 memory service：

### user hook points

* encounter/session start
* calling nurse called
* vitals measured
* triage completed
* doctor assessment checkpoint
* test ordered
* test result ready
* handoff requested
* handoff completed
* disposition decided
* encounter/session done

### 特别说明

你最熟悉的是 user mode，所以你要特别确保这些 Week 8 hook 接入后：

* calling nurse 不被破坏
* pending_messages 还能正常工作
* phase auto-progression 不被打断
* doctor-only KB + selective RAG 的边界不被打破
* planner_trace / doctor_kb evidence 还能正常写入

---

## 9. 你在 auto mode 里要关注的 hook 点

你不是 auto 主开发，但 Memory v1 要做成 shared infrastructure，因此你也要知道 auto 哪些点应该写 memory：

* encounter spawned
* triage/doctor/test transitions
* resource bottleneck event
* boarding_started
* boarding_timeout
* handoff/disposition events
* encounter_closed

这些和 merge handoff 里强调的 auto realism feature 是一致的。

如果 A 没有主动在这些点预留 hook 接口，你需要要求她补。

---

## 10. Week 8 你要重点交付的评估内容

### 10.1 Memory ON/OFF ablation

必须能切：

* `memory_on = False`
* `memory_on = True`

并比较至少这些指标：

* repeated-question rate
* handoff omission
* continuity consistency
* latency overhead

proposal 里已经明确把这些列为 Week 8 测试目标。

### 10.2 continuity 测试

至少做：

* delayed test result after earlier assessment
* shift / role handoff continuity
* same encounter resumed with memory summary

### 10.3 handoff completeness 测试

handoff summary 至少要检查有没有：

* patient brief
* current state
* completed actions
* pending tasks
* risks
* next actions
* source memory ids

proposal 中 receiver-ready summary 模板已经给出来了。

### 10.4 replay/export 测试

至少要能导出：

* 一个 user run 的 replay
* 一个 auto run 的 replay

按 `run_id / mode / encounter_id / step range` 切片。

---

## 11. Week 8 你应该新增的测试

建议创建：

```text
week8/merge/tests_week8/
  test_memory_user_hooks.py
  test_memory_auto_hooks.py
  test_memory_retrieval.py
  test_memory_handoff.py
  test_memory_replay.py
  test_memory_ablation.py
```

### 你最该先写的

1. `test_memory_user_hooks.py`
2. `test_memory_handoff.py`
3. `test_memory_ablation.py`

因为这三项最能证明 Week 8 memory 接入后，user mode 没有被搞坏，而且 memory 真带来了收益。

---

## 12. 关于 Group4 repo：你应该怎么参考

### 你要借的

只借 **架构模式**：

* encounter/admission as episode anchor
* append-only event bus
* current state materialized summary
* snapshot
* audit log
* API/service as唯一数据访问边界

proposal 已经把这些归纳好了。

### 你不要借的

不要直接 graft：

* ICU/APACHE schema
* PostgreSQL-first 强依赖
* risk/alert taxonomy
* 完整 FastAPI 服务栈

所以你在和 A 协作时，如果她说“直接按 Group4 的数据库接口搬”，你应该提醒她：

> Week 8 只借 architecture pattern，不直接迁 ICU-specific data model 或 DB stack。

---

## 13. 你面向 Codex 可以直接使用的提示词

下面这段你可以直接发给 Codex，作为 Developer B 的执行说明：

```text
You are Developer B for Week 8 Memory v1 in the merged ED-MAS system.

Working root:
- /home/jiawei2022/BME1325/week8/merge

Read first:
1. merge_execution_plan.md and merge handoff docs
2. Week 8 memory migration proposal
3. user-mode upgrade notes to understand calling nurse, pending_messages, phase auto-progression, doctor-only local KB/RAG, and the user state machine

Your responsibility:
Implement integration + evaluation for Memory v1 on top of the shared memory substrate built by Developer A.

You own:
- user-mode hook integration
- auto-mode hook integration (through the shared memory service only)
- continuity checks
- handoff completeness checks
- replay export verification
- memory ON/OFF ablation
- repeated-question / handoff omission / latency overhead evaluation

You must preserve:
- user-mode session state machine
- calling nurse behavior
- pending_messages and phase auto-progression
- doctor-only local KB + selective RAG boundaries
- planner ownership, next_slot ownership, safety floor ownership, disposition ownership
- EDSIM_MODE as the single backend source of truth

You must NOT:
- create another memory schema
- create another storage path
- write directly to JSONL/SQLite files from user or auto code
- bypass the shared memory service
- change planner ownership
- change next_slot / safety floor / disposition ownership
- mix auto and user events into the same encounter timeline

You must wait until Developer A freezes these contracts before deep integration:
- MemoryItem
- CurrentEncounterSummary
- HandoffMemorySnapshot
- MemoryQuery
- event taxonomy
- storage interface
- hook point list

Use Group4 only as architecture reference for:
- event bus
- current state
- snapshot
- audit
- API/service boundary

Do not directly import Group4 runtime code and do not migrate PostgreSQL-first assumptions into Week 8 MVP.
```

---

## 14. 最后一句话

你作为 Developer B 的最大价值不是“再写一套 memory”，而是：

> **保证 Week 8 Memory v1 真正接入 user mode 和 merged system，而且不把你前面花很多周才调顺的 user-mode 行为、doctor-only RAG 边界和 calling nurse 流程破坏掉。**

如果你愿意，我下一条可以把 **Developer A + Developer B 的说明再压缩成一页式双人协作 runbook**，方便你们两个人直接开工。
