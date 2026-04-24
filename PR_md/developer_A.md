# Developer A 面向 Codex 的实现说明（Week 8 Memory v1）

## 1. 你的角色定义

你现在的角色是  **Developer A** 。
你的工作重点不是继续扩 user-facing UI，也不是去改 doctor planner 的 ownership，而是：

> **在已经完成的 `week8/merge` 系统上，实现一套可供 auto 和 user 共用的 Memory v1 基础设施层（shared infrastructure），同时保证它对 Developer B 的 user-mode 接入友好，并且不破坏整个 merged system 的运行边界。**

Week 8 的 Memory v1 目标已经在现有 proposal 中明确：
要在现有 associative/scratch memory 之上增加：

* `EpisodeMemoryEventLog`
* `CurrentEncounterMemory`
* `HandoffMemorySnapshot`
* `ExperienceReplayBuffer`
* bounded retrieval checkpoints

用来提升 continuity、handoff quality，并支持 replay / ablation。

---

## 2. 你必须先理解的系统现状

在开始写任何代码前，你必须先明确：

### 2.1 现在唯一的开发根目录

本周所有 Week 8 开发都应基于：

```text
/home/jiawei2022/BME1325/week8/merge
```

不要回去在：

* `/home/jiawei2022/BME1325/week8/user_mode`
* `/home/jiawei2022/BME1325/week8/auto`

里继续开发。
`merge` 才是 Week 8 的唯一运行与交付根目录。merge handoff 文档已经明确这一点，而且 user runtime logic lives under `app_core/`。

### 2.2 当前 merged system 的 mode 规则

当前系统已经实现：

* backend startup `EDSIM_MODE` 是唯一真源
* frontend 的 `ui_mode` 不能切换后端能力
* `/mode/user/*` 在 `EDSIM_MODE != user` 时返回 `409 MODE_MISMATCH`。

这意味着你写 memory 时必须假设：

* auto 和 user **共享基础设施**
* 但**不共享同一个运行态实例**
* 每次运行必须通过 `run_id + mode + encounter_id` 隔离

### 2.3 你不能破坏的现有能力

merge handoff 已确认保留：

#### auto mode

* arrival profiles
* lab/imaging capacity & turnaround
* boarding timeout
* analysis outputs
* runtime robustness in Django frontend/backend。

#### user mode

* calling nurse
* shared memory across roles
* pending_messages + phase auto-progression
* doctor-only local KB + selective RAG
* one-question-per-turn / anti-repeat
* `app_core` 作为 user-mode runtime logic 主体。

---

## 3. 你是否需要先 clone 什么目录

## 结论

**通常不需要再 clone auto/user 主代码目录。**

因为：

* collaborator auto 已经 fetch 到 `week8/auto`
* merged system 已经生成在 `week8/merge`
* user source-of-truth 也已经 graft 进 `merge/app_core` 和 `merge/RAG/doctor_kb`。

### 你真正应该先检查的目录

你开工前请先在本地确认这几个目录存在：

```text
/home/jiawei2022/BME1325/week8/merge
/home/jiawei2022/BME1325/week8/merge/app_core
/home/jiawei2022/BME1325/week8/merge/RAG/doctor_kb
/home/jiawei2022/BME1325/week8/merge/environment/frontend_server
/home/jiawei2022/BME1325/week8/merge/reverie/backend_server
/home/jiawei2022/BME1325/week8/merge/analysis
```

### 什么时候才需要额外 clone

只有一种情况建议额外 clone：

#### 如果你要参考 Group4 的数据库/API 分层

你可以单独 clone：

```bash
git clone https://github.com/XanderZhou2022/BME_1325_Group4_repo.git
```

但它只用于 **架构参考** ，不是运行时依赖。
理由见第 9 节。

---

## 4. 你必须先读哪些文档

开始编码前，按这个顺序读：

### 第一优先级

1. `week8/merge_execution_plan.md`
2. `week8/merge` 根目录下的 merge handoff 文档
   你们已经整理了一份 Week8 Merge Handoff，里面写清楚了：
   * merge 如何做
   * auto/user 哪些能力已保留
   * mode 边界
   * 如何运行与测试。

### 第二优先级

3. 你们本周的 Week 8 memory migration/proposal 文档
   这份文档已经把 Group4 的最值得迁移的 5 个设计、MemoryItem schema、write path、retrieval path、handoff snapshot 和 MVP recommendation 说明得很清楚。

### 第三优先级

4. collaborator auto tree 中的 `PLAN.md`
   之前探索结果确认，`week7/auto` 顶层里包含 `PLAN.md`。
   你要读它，不是为了照搬实现，而是为了理解：
   * auto mode 的运行主线
   * realism / analysis 关注点
   * 哪些事件最值得挂 memory hook

---

## 5. 你应该如何参考 `PLAN.md`

你对 `PLAN.md` 的使用方式应当是：

### 5.1 把它当成 auto mode 的“行为地图”

你要从里面提取：

* auto mode 的主要阶段
* arrival / triage / doctor / test / boarding / disposition 关键节点
* 哪些事件已经有日志或 metrics
* 哪些事件是 Week 7 realism 的核心证据

### 5.2 不要把它当成 Week 8 需求源

Week 8 需求源还是你们自己的 memory proposal，不是 collaborator 的 `PLAN.md`。
`PLAN.md` 只决定：

* auto hooks 应该挂在哪里
* 你的 Memory v1 如何不干扰 auto realism

### 5.3 你最终要做的是“读 PLAN → 提取 hook points”

例如你应该把 auto hook 点整理成这样的固定列表：

* encounter spawned
* triage/doctor/test transitions
* resource bottleneck event
* boarding_started
* boarding_timeout
* handoff_requested / handoff_completed
* encounter_closed

这些点和 merge handoff 里列出的 auto realism feature 是一致的。

---

## 6. Developer A 的职责边界

## 你负责的内容（A）

你负责实现  **memory substrate** ，也就是公共内存基础设施层。

建议你创建：

```text
week8/merge/app_core/memory/
  __init__.py
  schema.py
  taxonomy.py
  storage.py
  episode_memory.py
  current_memory.py
  handoff_memory.py
  retrieval.py
  replay_buffer.py
  audit.py
  hooks.py
  config.py
  service.py
```

### 你必须实现的核心模块

1. `EpisodeMemoryEventLog`
2. `CurrentEncounterMemory`
3. `HandoffMemorySnapshot`
4. bounded retrieval
5. replay/audit export
6. ON/OFF ablation hooks 的基础设施部分

这些都是 proposal 里已经确定的 MVP。

---

## 7. 你不能做的事情

你 **不能** ：

1. 改 doctor planner ownership
2. 改 `next_slot` ownership
3. 改 safety floor ownership
4. 改 disposition ownership
5. 改 `EDSIM_MODE` 单一真源
6. 把 memory 直接写死到 user 或 auto 某一侧
7. 另起一套 schema / storage / retrieval，不走共享 substrate
8. 让 PostgreSQL 成为 Week 8 MVP 的强依赖

这些都和现有 Week 8 proposal 的边界相冲突。

---

## 8. 你和 Developer B 的协作方式

## 8.1 你们共享什么

A 和 B 必须共享：

* memory schema
* event taxonomy
* storage abstraction
* retrieval contract
* replay format
* audit format

## 8.2 你们不共享什么

你们不应该各自写自己的：

* `MemoryItem`
* `CurrentEncounterSummary`
* `HandoffMemorySnapshot`
* storage backend contract

这些必须先冻结，再开始并行开发。

## 8.3 你的侧重点

你是  **A** ，所以你更偏：

* substrate
* contract
* storage
* replay
* audit
* retrieval

而 B 更偏：

* user hook integration
* evaluation
* ablation
* continuity / repeated-question / handoff omission 指标
* user correctness 守门

---

## 9. 关于 `XanderZhou2022/BME_1325_Group4_repo`：到底有没有数据库/存储相关内容？

## 结论

**有，而且不只是“有一点点”。**

我刚核过公开仓库，可以确认：

### 9.1 仓库确实存在，并且公开页面当前可见分支是 `week3_0320`

仓库主页显示：

* repo: `XanderZhou2022/BME_1325_Group4_repo`
* public
* visible branch: `week3_0320`
* 顶层有 `scripts/`、`system/`、`任务书`、`数据协议`、`日志` 等。 ([GitHub](https://github.com/XanderZhou2022/BME_1325_Group4_repo "GitHub - XanderZhou2022/BME_1325_Group4_repo · GitHub"))

### 9.2 backend 下确实有数据库/API 相关结构

根据公开可见路径，`system/backend` 和 `system/backend/api` 都存在。 ([GitHub](https://github.com/XanderZhou2022/BME_1325_Group4_repo/tree/week3_0320/system/backend "BME_1325_Group4_repo/system/backend at week3_0320 · XanderZhou2022/BME_1325_Group4_repo · GitHub"))

你之前的 migration proposal 之所以判断它更像“backend API + data boundary”而不是纯 in-memory demo，是有依据的。proposal 已明确总结了 Group4 可借鉴的是：

* event bus
* current state
* snapshot
* audit log
* API as the only data access boundary

而不是 chat history 式 memory。

### 9.3 但它不适合本周直接拿来 graft

原因不是“它没有数据库”，而是：

* 当前公开分支看起来还偏早期
* 它更像一个 ICU/backend-first 架构原型
* 你们 Week 8 要的是 **ED-compatible MVP**
* proposal 已明确不建议直接迁移：
  * ICU/APACHE-specific schema
  * PostgreSQL-first 强依赖
  * 完整 FastAPI 服务硬接。

### 因此正确说法应该是

> Group4 repo  **有数据库/存储相关的设计与 backend API 分层** ，不是“完全没有数据库内容”；
> 但它目前更适合作为  **架构参考** ，不适合在 Week 8 直接作为运行时依赖整块搬进来。

---

## 10. Week 8 对你（A）的明确实现要求

### 10.1 先冻结这些 contract

在开始编码前，你要和 B 一起冻结：

1. `MemoryItem`
2. `CurrentEncounterSummary`
3. `HandoffMemorySnapshot`
4. `MemoryQuery`
5. event taxonomy
6. storage interface
7. hook point list

### 10.2 你必须先产出的文件

至少先提交这些空壳 + dataclass/interface：

* `schema.py`
* `taxonomy.py`
* `storage.py`
* `service.py`

这样 B 才能开始接 user hooks，而不会等你把所有实现都写完。

### 10.3 MVP 的实现顺序

推荐顺序：

#### Phase A1

* `schema.py`
* `taxonomy.py`
* `storage.py`

#### Phase A2

* `episode_memory.py`
* `current_memory.py`
* `handoff_memory.py`

#### Phase A3

* `retrieval.py`
* `audit.py`
* `replay_buffer.py`

#### Phase A4

* `hooks.py`
* `config.py`
* `service.py`

---

## 11. 你应该预留给 B 的 hook 接口

你要给 B 一个尽量稳定的调用接口，例如：

```python
memory_service.append_event(...)
memory_service.update_current_summary(...)
memory_service.write_handoff_snapshot(...)
memory_service.retrieve(...)
memory_service.export_replay(...)
memory_service.append_audit(...)
```

B 不应该直接碰底层 JSONL / SQLite / file IO。
B 的接入应只通过 `service.py`。

---

## 12. 存储后端建议

### Week 8 MVP 建议

先实现：

* JSONL event log
* JSON current summary
* JSON snapshot / audit

可选再加：

* SQLite backend

不要先做：

* PostgreSQL mandatory backend

这点和 proposal 一致。

---

## 13. 面向 Codex 的直接提示词

下面这段你可以直接贴给 Codex，作为 Developer A 的执行说明：

```text
You are Developer A for Week 8 Memory v1 in the merged ED-MAS system.

Working root:
- /home/jiawei2022/BME1325/week8/merge

Read first:
1. merge handoff / merge_execution_plan documents under week8
2. Week 8 memory migration proposal
3. collaborator auto PLAN.md only to understand auto hook points and realism invariants

Your responsibility:
Implement the shared memory substrate under:
- app_core/memory/

You own:
- schema.py
- taxonomy.py
- storage.py
- episode_memory.py
- current_memory.py
- handoff_memory.py
- retrieval.py
- replay_buffer.py
- audit.py
- hooks.py
- config.py
- service.py

You must preserve:
- collaborator auto-mode realism and analysis behavior
- Jiawei user-mode app_core behavior
- EDSIM_MODE as the single backend source of truth
- existing hard-rule > RAG > LLM ownership

You must NOT:
- rewrite doctor planner ownership
- modify next_slot / safety floor / disposition ownership
- make PostgreSQL mandatory
- add embedding retrieval in MVP
- create a second schema or storage path outside app_core/memory

Week 8 MVP scope:
1. EpisodeMemoryEventLog
2. CurrentEncounterMemory
3. HandoffMemorySnapshot
4. bounded retrieval
5. replay export
6. audit log hooks

Important collaboration rule:
Developer B will integrate user-mode and evaluation logic later.
So before writing deep implementation, first freeze and expose stable contracts for:
- MemoryItem
- CurrentEncounterSummary
- HandoffMemorySnapshot
- MemoryQuery
- event taxonomy
- storage interface

Group4 repo usage:
- use it only as architecture reference for event bus / current state / snapshot / audit / API boundary
- do not import it as runtime dependency
- do not migrate ICU-specific schemas or PostgreSQL-first assumptions into Week 8 MVP
```

---

## 14. 最后一句话

你作为 Developer A，最重要的不是“尽快把 memory 写出来”，而是：

> **先把共享 contract 和基础设施层做稳，让 Developer B 可以在不踩你内部实现的情况下，把 user-mode hooks 和 Week 8 评估接进去。**

如果你愿意，我下一条可以继续给你写一版  **Developer B 面向 Codex 的说明** ，这样你们两边的 prompt 就成对了。