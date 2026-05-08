# Week7 Auto Handoff

本文只基于当前仓库里的真实实现与真实产物编写，同时反复引用的关键证据路径如下：

| 用途 | 证据路径 |
| --- | --- |
| `arrival_normal` 1000-step 深跑 | `analysis/scenario_regressions/20260419_180032/deep/arrival_normal/summary.json` |
| `arrival_surge` 1000-step 深跑 | `analysis/scenario_regressions/20260419_181903/deep/arrival_surge/summary.json` |
| `arrival_burst` 1000-step 深跑 | `analysis/scenario_regressions/20260419_183714/deep/arrival_burst/summary.json` |
| `bottleneck_imaging` 1000-step 深跑 | `analysis/scenario_regressions/20260419_215509/deep/bottleneck_imaging/summary.json` |
| `boarding_timeout` 1000-step 深跑 | `analysis/scenario_regressions/20260419_120618/deep/boarding_timeout/summary.json` |
| all-scenario 500-step 回归 | `analysis/scenario_regressions/20260420_183847/summary.json` |
| Week7 运行器 | `scripts/run_week7_long_regression.py` |
| Week7 规则函数 | `reverie/backend_server/week7_logic.py` |
| 核心主循环 | `reverie/backend_server/reverie.py` |
| 患者状态机 | `reverie/backend_server/persona/persona_types/patient.py` |
| Django gateway | `environment/frontend_server/translator/views.py` |

这里先明确一个非常重要的定义：

- 本文里的 `run500 / run1000`，本质上指的是长程回归脚本中把 `--max-chunks` 设为 `500 / 1000`。
- 在当前 Week7 scenario catalog 里，核心场景的 `chunk_steps = 1`，所以 `max_chunks = 500 / 1000` 就等价于实际跑了 `500 / 1000` 个 simulation steps。

---

# 第一部分：Week7 三个优化方向

## 1. arrival profile

### 1.1 baseline 与 Week7 的根本差异

| 维度 | baseline | Week7 |
| --- | --- | --- |
| 到达控制变量 | 基本只有 `patient_rate_modifier` | `patient_rate_modifier + arrival_profile_mode + hour` |
| 到达曲线 | 只是在原始 hourly ED visits 曲线上做常数倍缩放 | 在保留原始 hourly ED visits 的前提下，再叠加 scenario-specific multiplier |
| 代码入口 | `reverie.py` 里直接按固定 rate 累积阈值 | `week7_logic.py` 提供 `effective_arrival_rate()`，主循环调用 |
| 设计表达能力 | 只能表达“整体更忙/更闲” | 能表达“全天持续 surge”与“特定时段 burst” |

baseline 的本质是：

- `ed_visits_per_hour.csv` 给出每小时基础到诊量。
- `patient_rate_modifier` 只做一个全局乘子。
- 因此 baseline 只能表达“今天整体比平时快 2 倍”这种变化，不能表达“早高峰和晚高峰更尖”的运营现实。

Week7 的本质是：

- 保留 `ed_visits_per_hour.csv` 作为基础到诊曲线。
- 再引入 `arrival_profile_mode` 作为“场景形状修正”。
- 这样就把“规模”与“形状”拆开了：
  - `patient_rate_modifier` 决定总体强度。
  - `arrival_profile_mode` 决定一天内哪些小时更容易挤兑。

### 1.2 公式与真实实现

概念上，Week7 想表达的是：

```text
hourly_arrivals(hour) = visits_per_hour(hour) * effective_arrival_rate(patient_rate_modifier, arrival_profile_mode, hour)
```

但仿真不是“每小时一次性塞入整数病人”，而是“每 step 累加阈值，再跨过 1 时生成 patient”。因此代码里的实际 step 级公式是：

```text
threshold_increment_per_step
  = visits_per_hour(hour) / steps_per_hour
  * effective_arrival_rate(patient_rate_modifier, arrival_profile_mode, hour)
```

其中：

```text
steps_per_hour = 3600 / sec_per_step
```

在代码中的对应关系是：

- `effective_arrival_rate(...)` 定义在 `reverie/backend_server/week7_logic.py`
- 阈值累加写在 `reverie/backend_server/reverie.py`
- 关键实现是：
  - `effective_arrival_rate = max(0, base_rate * arrival_profile_multiplier(mode, hour))`
  - `self.add_patient_threshold += visits_per_hour / (3600 / self.sec_per_step) * arrival_rate`

### 1.3 每个参数到底是什么意思

| 参数 | 来源 | 含义 | 为什么需要它 |
| --- | --- | --- | --- |
| `visits_per_hour` | `data/ed_visits_per_hour.csv` | 历史基础到诊强度，按小时给出 | 不想凭空造 arrivals，而是从已有 hourly demand curve 起步 |
| `patient_rate_modifier` | `meta.json` | 基础到诊倍率 | 用来表达“整体更忙/更闲” |
| `arrival_profile_mode` | `meta.json` | 场景形状，当前支持 `normal / surge / burst` | 用来表达“全天高压”与“特定高峰” |
| `hour` | `self.curr_time.hour` | 当前仿真小时 | 让 arrival 具备昼夜变化 |
| `sec_per_step` | `meta.json` | 一个 step 代表多少 simulated seconds | 决定 hourly arrivals 如何拆到 per-step 阈值 |
| `add_patient_threshold` | runtime 状态 | arrival accumulator，跨过 1 就生成新病人 | 避免“每小时离散投放”，让到诊在 step 级更平滑 |

### 1.4 `arrival_profile_mode` 三种模式的含义

`week7_logic.py` 中的 multiplier 是明确写死的：

| 模式 | multiplier 规则 | 含义 |
| --- | --- | --- |
| `normal` | 始终 `1.0` | 与 baseline 形状一致，只受 `patient_rate_modifier` 控制 |
| `surge` | 始终 `1.75` | 全天持续高压 |
| `burst` | `07-09 => 2.2`，`11-13 => 1.15`，`16-19 => 2.6`，其他时段 `0.65` | 早高峰和晚高峰明显尖峰，其他时段回落 |

这组设计虽然简化，但它有两个优点：

1. 可解释性强。在“定义 burst”中，可以直接回答具体时段和倍率。
2. 能被回归验证。因为 multiplier 不是隐含在复杂模型里，而是显式规则，所以不同 scenario 的结果差异能够直接归因。

### 1.5 为什么这样设计

| 设计选择 | 原因 |
| --- | --- |
| 保留 `visits_per_hour` 原曲线 | 不想丢掉 baseline 已有的数据依据 |
| 再叠加 `arrival_profile_mode` | 让 Week7 的变化不是“另起一套 arrival 模型”，而是在 baseline 上做受控增强 |
| 用 threshold accumulation 而不是整点批量到达 | 避免整点瞬间产生大量病人，step 级更平滑，也更适合 agent-based runtime |
| `burst` 不做全天高倍率 | 因为现实里的急诊压力往往是“局部峰值造成系统积压”，不是全天恒定上涨 |
| `effective_arrival_rate` 用 `max(0, ...)` 截断 | 保证到达率不会因为坏配置变成负数 |

这里最值得强调的“为什么”是：

- baseline 只解决了“有病人不断来”。
- Week7 要解决的是“病人来的形状不同，会不会把系统压出不同的队列形态”。
- 因此 arrival profile 不是为了更复杂而复杂，而是为了把“运营问题”变成“可对照的实验变量”。

### 1.6 用真实 run500 / run1000 数据说明效果

证据来源：

- `arrival_normal`: `analysis/scenario_regressions/20260419_180032/deep/arrival_normal/summary.json`
- `arrival_surge`: `analysis/scenario_regressions/20260419_181903/deep/arrival_surge/summary.json`
- `arrival_burst`: `analysis/scenario_regressions/20260419_183714/deep/arrival_burst/summary.json`

#### 1.6.1 run500 对比

| 场景 | step 500 总病人数 `total_patients` | step 500 当前在 ED `current_patients` | triage queue | doctor global queue | arrival mode |
| --- | ---: | ---: | ---: | ---: | --- |
| `arrival_normal` | 187 | 182 | 24 | 151 | `normal` |
| `arrival_surge` | 255 | 249 | 88 | 154 | `surge` |
| `arrival_burst` | 214 | 208 | 47 | 154 | `burst` |

run500 的第一层结论：

- `surge` 相比 `normal`，到 step 500 时总病人数从 `187` 增到 `255`，增加 `68` 人，约 `+36.36%`。
- `burst` 相比 `normal`，到 step 500 时总病人数从 `187` 增到 `214`，增加 `27` 人，约 `+14.44%`。

这说明：

- `surge` 由于全天固定 `1.75` 倍，累积 arrivals 最快。
- `burst` 不是一直很高，所以总 arrival 不会像 `surge` 那样线性抬升。
- 但 `burst` 的 triage queue 已经从 `24` 抬到 `47`，说明峰值时段的局部冲击已经开始显现。

#### 1.6.2 run1000 对比

| 场景 | step 1000 总病人数 | step 1000 当前在 ED | triage queue | doctor global queue | avg wait minutes | avg total ED minutes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `arrival_normal` | 375 | 361 | 46 | 307 | 480.05 | 98.69 |
| `arrival_surge` | 511 | 497 | 177 | 311 | 506.27 | 143.80 |
| `arrival_burst` | 435 | 423 | 101 | 313 | 513.80 | 137.83 |

run1000 的关键解释：

1. `surge` 的总 arrival 最多。
   因为它是全天 `1.75` 倍，累积效应最强，所以 `total_patients = 511`，比 `normal` 的 `375` 多 `136` 人，约 `+36.27%`。

2. `burst` 的总 arrival 少于 `surge`，但平均等待反而更高。
   `burst` 的 `avg_wait_minutes_overall = 513.80`，高于 `surge` 的 `506.27`。

3. 说明设计有效。
   原因不是“全天病人更多”，而是“病人在高峰时段更集中地压进系统”。当 16:00-19:00 的 multiplier 到 `2.6` 时，系统已经积压，再叠加尖峰，会把排队时间进一步拉长。

#### 1.6.3

上述表格的核心意义在于：在同一个系统配置保持不变的前提下，也就是医生、护士以及流程参数都固定不动，只对 `arrival_profile_mode` 做切换，通过比较 `normal / surge / burst` 三种模式，可以直观观察病人流入模式变化对系统状态的影响。这里的重点是控制变量思路，也就是尽量不改系统资源配置，只改病人进入系统的节奏和强度，这样表格中出现的差异才更容易归因到 `arrival profile` 本身。

具体来说，不同的 arrival 模式会改变病人进入系统的节奏与强度，从而在不同环节产生不同程度的拥堵。表格里最关键的两个指标是：

| 指标 | 代表什么 | 可以回答什么问题 |
| --- | --- | --- |
| `triage queue` | 正在等待分诊的患者数量 | 分诊入口是否被短时间流量冲垮，系统最前端是否扛得住 |
| `doctor global queue` | 已完成分诊但仍在等待医生处理的患者数量 | 压力是否已经从入口继续传到系统内部，是否出现内部积压 |

把这两个队列指标放在一起看，可以进一步观察压力如何在系统中传播。如果某个 scenario 先把 `triage queue` 顶高，随后 `doctor global queue` 也开始持续上升，就说明 arrival 压力不是只停留在入口，而是在从前端逐步向下游扩散。这正是 `arrival_profile_mode` 设计的价值所在：它不只是比较“病人多了还是少了”，而是帮助我们看到不同压力形态下，系统会在哪里先出现潜在瓶颈，以及这种压力会不会继续向后传播。

不过，这里也必须明确它的使用边界。由于该表格没有显式纳入医生数量、护士配置、资源利用率或人员排班强度等信息，所以它主要适合做 arrival 模式之间的相对比较，而不能直接用于评估医院整体资源调度是否合理。换句话说，这张表更适合回答“哪一种 arrival shape 更容易把系统压出队列积压”，而不适合直接回答“医院的人手配置现在是否最优”。

---

## 2. lab / imaging capacity + TAT

### 2.1 baseline testing flow 是什么

baseline 的 testing flow 本质是一个比较粗的通用诊断流程：

- 患者进入 testing 相关状态后，
- 主要依靠 `testing_time` 和 `testing_result_time` 两段通用延迟推进，
- 空间上主要对应一个 `diagnostic room`，
- 但没有把“lab”和“imaging”拆成两个资源池，也没有分别建 capacity。

这会带来一个解释上的缺口：

- 可以说“测试慢了”，
- 但说不清到底是 lab 慢、还是 imaging 慢、还是诊断房间空间占用慢。

### 2.2 Week7 怎么拆成资源池

Week7 用 `testing_kind_for_ctas()` 先把病人分流：

| CTAS | testing_kind | 理解
| --- | --- |
| `1-2` | `imaging` | 相对轻量，像后台处理|
| `3-5` | `lab` | 更重，更占空间，更占设备|

然后分别走两条不同的资源逻辑：

| 资源池 | 关键状态推进 | 容量账本 | TAT 用法 | 空间含义 |
| --- | --- | --- | --- | --- |
| `lab` | `WAITING_FOR_TEST -> WAITING_FOR_RESULT` | `maze.lab_patients` | 进入 lab slot 后设置 `testing_end_time = now + lab_turnaround_minutes` | 更像后台处理，患者不一定长期占据诊断房 |
| `imaging` | `WAITING_FOR_TEST -> GOING_FOR_TEST -> WAITING_FOR_RESULT` | `maze.imaging_patients` + `diagnostic room.current_patients` | 进入 imaging slot 后设置 `testing_end_time = now + imaging_turnaround_minutes` | 明确占据诊断房间与 imaging capacity |

这背后的设计思路很重要：

- imaging 更像“需要特定空间和设备”的检查，所以显式占据 `diagnostic room`。
- lab 更像“采样后后台流转”，所以一旦拿到 slot，就可以把患者推进到等结果状态，而不是必须一直占着诊断空间。

### 2.3 `capacity` 和 `turnaround` 分别是什么意思

| 参数 | 含义 | 在系统里的效果 |
| --- | --- | --- |
| `lab_capacity` | 同时可处理的 lab 数量上限 | 达到上限后，新 lab 病人只能继续停在 `WAITING_FOR_TEST` |
| `lab_turnaround_minutes` | 一个 lab case 从进入 slot 到结果返回所需时间 | 决定 `testing_end_time` 的远近 |
| `imaging_capacity` | 同时可处理的 imaging 数量上限 | 同时限制 diagnostic room 占用与 imaging in progress |
| `imaging_turnaround_minutes` | imaging 完成所需时间 | 决定 imaging slot 被占多久 |

一句话总结：

- `capacity` 决定“能不能开始服务”。
- `turnaround` 决定“服务开始之后要占资源多久”。

### 2.4 排队系统的本质

如果要用运筹学语言来讲，Week7 在这里做的不是完整的解析排队论模型，而是：

- 在 agent-based runtime 里显式加入了两个 finite-server queues。
- lab 和 imaging 各自都有：
  - 进入条件，
  - 容量上限，
  - 服务占用时间，
  - 释放资源的时点。

因此它的本质可以理解为：

- “离散步进 + 显式资源占用 + 患者状态机耦合”的有限服务台排队系统。
- 把 testing 拆成两类资源成本不同的服务池，然后观察患者流入后，系统是否会因为资源容量和周转时间不同而出现拥堵、积压和传播。
- 适合作为“第一个“可解释、可复现、可跑通”的资源版本”

这比 baseline 强的地方在于：

- baseline 只有“测试需要时间”。
- Week7 则能回答“测试为什么慢，是因为房间不够，还是因为周转太久”。

### 2.5 为什么这样设计

| 设计选择 | 为什么这么做 |
| --- | --- |
| 按 CTAS 把高 acuity 倾向分到 imaging | 不是为了医学绝对真实，而是为了把高 acuity 与高资源成本关联起来，让系统更有区分度 |
| imaging 显式占据 diagnostic room | 因为 imaging 的空间/设备稀缺性更强，应该能在状态里看见 |
| lab 允许更像后台处理 | 避免所有测试都被强行压成“必须去一个房间” |
| capacity 和 TAT 分开配置 | 这样可以分别做“加设备”和“提效率”的实验 |
| 把等待显式保留在 `WAITING_FOR_TEST` | 让队列是可观测状态，而不是藏在一个模糊的长延迟里 |

### 2.6 结合 `max_imaging_waiting` 解释真实结果

证据来源：

- `analysis/scenario_regressions/20260419_215509/deep/bottleneck_imaging/summary.json`
- `analysis/scenario_regressions/20260419_215509/deep/bottleneck_imaging/resource_event_metrics.json`

该场景的配置是：

| 参数 | 值 |
| --- | ---: |
| `arrival_profile_mode` | `surge` |
| `imaging_capacity` | `1` |
| `imaging_turnaround_minutes` | `120` |
| `lab_capacity` | `2` |
| `lab_turnaround_minutes` | `30` |

真实结果如下：

| 指标 | run500 | run1000 |
| --- | ---: | ---: |
| `current_patients` | 147 | 252 |
| `total_patients` | 155 | 266 |
| `doctor_global_queue` | 141 | 244 |
| `imaging_in_progress` | 0 | 1 |
| `imaging_capacity` | 1 | 1 |
| `max_imaging_waiting` | 2 | 2 |
| `avg_wait_minutes_overall` | 见最终分析 | 405.13 |
| `avg_total_ed_minutes_overall` | 见最终分析 | 60.64 |

这里最值得讲清楚的细节是：

- `max_imaging_waiting = 2` 表明已经进入 imaging 流程并明确在排 imaging 的人，并不代表 imaging bottleneck 很轻。
- 相反，这个场景已经把 `doctor_global_queue` 顶到了 `244`，`current_patients` 顶到 `252`。

为什么会这样？

因为 `imaging_waiting` 这个指标只统计“已经明确落到 imaging waiting 条件里的病人”。它不是“所有由 imaging 瓶颈间接导致的拥堵”的总代表。

这意味着：

1. imaging capacity 变成 `1`、TAT 变成 `120` 分钟后，最先卡住的是 imaging slot。
2. imaging slot 一旦长期被占住，拥堵会逐层向上游传播。
3. 传播后的表现，不一定始终停留在 `imaging_waiting` 这个单点指标上，而更可能体现在：
   - `doctor_global_queue` 变大，医生不敢/不能推进病例，病人都在卡`doctor queue`中
   - `bedside_nurse_waiting` 变大
   - `current_patients` 持续堆高



### 2.7 后续内容优化

当前 Week7 的 `lab / imaging` 设计可以看作一个 `Version0`。它的核心思路是：先用一个简化版的 `CTAS -> testing_kind` 映射，把患者分流到两类资源成本和处理速度不同的 testing pool 中，再观察 `capacity` 和 `turnaround` 的变化是否会把系统压出新的拥堵形态。这样做的好处是，我们暂时不把“医生个人判断差异”这类高不确定性因素引进来，而是先把问题收缩成一个更容易解释和验证的资源系统实验。

从建模角度看，这种设计虽然简化，但它回答的是一个很重要的问题：如果 arrival 压力保持不变，只调整 testing 资源的处理能力，那么系统是否会因为下游检查资源不足而出现排队积压，并进一步把压力传回上游。Week7 当前的实验结果已经给出了比较清楚的信号。

从结果上看，在 arrival 压力固定的情况下，`imaging waiting` 队列本身并没有特别夸张地持续拉长，但 `doctor global queue` 和 `current_patients` 却明显上升。这说明问题不一定表现为“影像队列表面上堆很多人”，而更可能表现为系统整体吞吐变慢，导致已经进入 ED 的患者越来越多地滞留在系统中。换句话说，瓶颈虽然出现在下游的 imaging 资源上，但影响已经向上游传播，最终体现为医生等待队列和在院人数持续增长，系统逐渐走向不稳定状态。

这一点非常关键，因为它说明 `capacity` 和 `turnaround` 并不是简单的局部参数，而是直接决定系统处理能力的核心调度参数。`capacity` 决定同一时间能并行处理多少个检查请求，`turnaround` 决定每个请求要占用资源多久；两者共同决定 testing pool 的有效吞吐率。一旦吞吐率低于病人流入后产生检查需求的速度，积压就会逐步形成，并沿着 `arrival -> testing -> doctor -> overall census` 的路径传播出去。

因此，当前这一版设计的价值不只是“加了 lab 和 imaging 两个资源池”，更重要的是它让一条原本隐藏的压力传播链变得可观测：病人先进入系统，随后一部分病人被送去 testing，testing 资源变慢后，医生后续处理被拖延，最后整个系统的 `doctor global queue` 和 `current_patients` 一起抬升。这个链条越清楚，后面做瓶颈分析时就越容易解释“为什么系统会 overload”。

下一步更合理的升级方向，是引入 `doctor-guided probabilistic routing`。也就是说，不再用当前这种较硬的 CTAS 直接映射规则，而是让“是否进入 `lab` 或 `imaging`”同时受到医生建议和患者特征影响，以概率方式决定 testing request。这样做会更接近真实临床流程，因为现实里同一个 CTAS 等级并不必然对应固定检查类型；但如果把路由规则设计成“可控概率 + 可解释条件”，系统仍然可以保持可分析、可复现实验和可对比 scenario 的优点。

如果要用一句话总结 `2.7` 这一节，可以表述为：Week7 已经完成了从“有无 testing 模块”到“testing 资源是否会引发系统级拥堵”的第一步验证；而下一阶段的目标，不是单纯把规则做复杂，而是把 routing 机制升级得更接近真实医疗决策，同时继续保留模型的可控性和可解释性。

---

## 3. boarding timeout

### 3.1 baseline admission 是什么

baseline 已经有 admission / boarding 的骨架：

- 患者可以进入 `ADMITTED_BOARDING`。
- 也有 hospital admission 相关的开始/结束时间字段。

但 baseline 缺一个很关键的运营指标：

- 系统并不会在“board 过久”这件事发生时，显式记一个 timeout event。

于是 baseline 只能说：

- “这个病人还在 boarding”，

却不能清楚回答：

- “他有没有超过我们定义的 boarding threshold”。

### 3.2 Week7 的 timeout event 做了什么

Week7 在患者 `move()` 中加入了：

- `boarding_timeout_reached(start_time, current_time, timeout_minutes)`
- `boarding_timeout_recorded`
- `boarding_timeout_event`

逻辑是：

1. 病人进入 `ADMITTED_BOARDING` 后，记录 `admission_boarding_start`。
2. 每一步检查当前时间是否已经超过 `boarding_timeout_minutes`。
3. 如果超过，并且此前还没记录过，则：
   - `boarding_timeout_recorded = True`
   - `boarding_timeout_at = curr_time`
   - 在 `data_collection` 中写入 `boarding_timeout_event`
4. 同时在 `sim_status.json.resources.boarding_timeout_events` 中累计显示。

### 3.3 参数含义

| 参数 | 含义 | 作用 |
| --- | --- | --- |
| `simulate_hospital_admission` | 是否启用 admission/boarding 流程 | 不开这个，timeout 逻辑就没有业务前提 |
| `admission_probability_by_ctas` | 各 CTAS 被收住院的概率 | 决定谁会进入 boarding |
| `boarding_timeout_minutes` | 超时阈值，单位分钟 | 决定多久算 operational timeout |
| `admission_boarding_minutes_min` | boarding 持续时间下界 | 控制住院床位释放的最短时间 |
| `admission_boarding_minutes_max` | boarding 持续时间上界 | 控制住院床位释放的最长时间 |

### 3.4 为什么只记录事件，不改变患者主状态

这是 Week7 一个非常好的设计点。

超时后，系统没有把患者切换到一个新的“超时状态”，而只是记录事件，原因有三个：

| 原因 | 解释 |
| --- | --- |
| clinical state 不应被 KPI state 污染 | 患者在临床上仍然是 admitted and boarding，不会因为 KPI 超线就变成另一种医学状态 |
| 避免重复计数 | 用 `boarding_timeout_recorded` 保证每个患者只触发一次 timeout |
| 方便长期累计统计 | timeout event 更像质量指标/运营告警，而不是流程节点 |

换句话说：

- `ADMITTED_BOARDING` 是流程状态。
- `boarding_timeout_event` 是运营标签。

这种设计比“新增一个 timeout state”更稳，因为不会破坏既有 admission 流程，也不会让状态机过度膨胀。

### 3.5 长程运行中的累积效果

证据来源：

- `analysis/scenario_regressions/20260419_120618/deep/boarding_timeout/summary.json`
- `analysis/scenario_regressions/20260419_120618/deep/boarding_timeout/resource_event_metrics.json`

场景配置：

| 参数 | 值 |
| --- | ---: |
| `simulate_hospital_admission` | `True` |
| `arrival_profile_mode` | `normal` |
| `boarding_timeout_minutes` | `5` |
| `admission_probability_by_ctas` | 所有 CTAS 都设为 `1.0` |
| `admission_boarding_minutes_min` | `60` |
| `admission_boarding_minutes_max` | `240` |

真实结果：

| 指标 | run500 | run1000 |
| --- | ---: | ---: |
| `current_patients` | 71 | 119 |
| `total_patients` | 74 | 128 |
| `doctor_global_queue` | 63 | 112 |
| `boarding_timeout_events` in `sim_status.resources` | 5 | 11 |
| `max_boarding_timeout_events` | 5 | 11 |

最重要的解释是：

- timeout 不是一个“一闪而过”的值，而是累积事件数。
- 500 步时已经累计到 `5`。
- 1000 步时累计到 `11`。

这说明：

- 只要 admission 流程持续存在，
- 只要 boarding 床位释放慢于病人进入速度，
- timeout events 就会在长程运行里不断累积。

这正是 Week7 把 timeout 设计成 event 而非状态的价值：它天然适合做长期累计 KPI。

### 3.6 一个必须讲清楚的细节

为什么 `sim_status` 显示 11，但 `resource_event_metrics.json` 里只有 1；这不是错误，而是两个统计口径不同。

| 文件 | 看到的值 | 统计口径 |
| --- | ---: | --- |
| `sim_status.json.resources.boarding_timeout_events` | `11` | 运行时累计已记录的 timeout 事件总数 |
| `resource_event_metrics.json.boarding_timeout_events` | `1` | 后处理分析里，落入 `patient_time_metrics.csv` 的病人中，有多少人标记了 timeout |

为什么会出现差异：

- `sim_status.json` 是运行时主状态，谁一触发 timeout 就会被累计进去。
- `compute_metrics.py` 则是从压缩后的 movement 与 patient records 里抽可分析 patient row。
- 如果 run 结束时，很多 timeout 患者还没有完成后续离院轨迹，那么后处理 CSV 不一定完整覆盖到他们。

因此，需要说明的情况是：

- 看“实时运营压力”，优先看 `sim_status.json.resources.boarding_timeout_events`。
- 看“后处理出表结果”，看 `resource_event_metrics.json`，但要知道它偏向已形成完整 patient row 的记录。

### 3.7 后续优化说明

在急诊系统中，`boarding` 的本质可以理解为一个系统接口，也就是一个 `interface state`：它连接了 `ED`（急诊）与 `Inpatient`（住院部）两个子系统。当患者被判定为需要住院时，其流程在临床上已经完成决策，但在系统层面仍需等待下游住院资源，例如床位、转运能力等的承接。因此，`boarding` 并不是一个新的临床阶段，而是一个跨系统的过渡状态。

从系统角度看，`boarding` 的核心作用在于揭示“出口是否通畅”。如果患者能够快速从 ED 转入住院部，则系统处于良性流动状态；而如果患者长期滞留在 `boarding` 阶段，则说明 ED 的输出受阻。此时，问题不再来自分诊或医生处理能力，而是来自下游承接能力不足。因此，`boarding` 可以被视为急诊系统的出口观测点，也就是 `output bottleneck interface`，用于刻画系统是否存在“病人出不去”的结构性问题。

在该 `boarding_timeout` 场景中，系统通过开启 hospital admission 流程、将所有 CTAS 的 `admission probability` 设为 `1.0`，并设置较短的 timeout 阈值 `5` 分钟与较长的 boarding 持续时间范围 `60-240` 分钟，刻意放大了“患者决定住院后迟迟无法离开 ED”的现象。这种配置并非为了还原真实医院，而是作为一种 `stress test`，用于突出出口瓶颈。

实验结果表明，在 `arrival profile` 保持 `normal` 的情况下，`current_patients` 从 `71` 增长到 `119`，`doctor_global_queue` 从 `63` 增长到 `112`，同时 `boarding_timeout_events` 从 `5` 累积到 `11`。由于入口压力并未显著增加，这种持续增长无法归因于 arrival 变化，而只能由系统内部流动受阻解释。

进一步结合流程可以发现，患者在进入 `ADMITTED_BOARDING` 后无法及时离开 ED，导致系统库存持续增加，并逐渐反向影响上游的 `doctor queue`。这说明系统的不稳定性来源于出口承接不足，而非入口过载。因此，`boarding_timeout_event` 的价值不在于改变患者主状态，而在于作为一种运营指标，显式记录“患者出不去”的异常现象，从而揭示系统级的拥堵来源及其传播路径。

#### 3.7.1 后续可以优化的部分

##### （1）如何让 `boarding_timeout_minutes` 更鲁棒

当前版本使用的是人为设定的 `boarding_timeout_minutes = 5`。这种做法适合 demo 和 `stress test`，但不够稳健。后续更合理的升级方向，是把它改造成数据驱动阈值。

推荐方案如下：

| 方案 | 思路 | 示例 |
| --- | --- | --- |
| 分位数方法 | 用历史 boarding duration 的 `P90 / P95` 作为 timeout 线 | 最推荐，最容易解释 |
| 相对系统状态触发 | timeout 不只看绝对分钟数，还结合 occupancy、queue 或 census | 在系统高压时自动更敏感 |
| 资源驱动方法 | 让 timeout 与床位和出院速率关联 | `boarding_timeout = function(bed_capacity, discharge_rate)` |

##### （2）还可以继续思考的问题

1. 出口瓶颈 vs 中段瓶颈：当 `imaging` 和 `boarding` 同时存在时，哪个会先主导系统崩溃？
2. 系统是否存在“临界点”（`critical threshold`）：例如当 `boarding_capacity < 某个值` 时，系统会从可控状态进入 `unstable` 状态？
3. 是否存在最优资源配置：增加 `imaging capacity` 和增加 `inpatient beds` 哪个更有效？这本质上属于 `resource allocation optimization` 问题。
4. `pressure propagation` 是否可逆：如果释放出口瓶颈，系统需要多久才能恢复？这对应的是 `recovery dynamics` 问题。


---

## 4. 后端生成的关键文件与指标解释

### 4.1 四个关键文件分别干什么

| 文件 | 角色 | 谁写入 | 谁读取 | 应该怎么理解 |
| --- | --- | --- | --- | --- |
| `sim_status.json` | 主状态 | backend `reverie.py` | `live_dashboard`、回归采样器 | 这是运行时最权威的聚合状态 |
| `curr_step.json` | step 指针 / 握手信号 | backend `reverie.py` | Django UI、启动与同步逻辑 | 只说明“当前步号大致到哪”，不是完整世界状态 |
| `movement/<step>.json` | 本 step 的动作与移动输出 | backend `reverie.py` | 地图播放与 replay | 用来驱动“人物这一帧怎么动、说了什么、描述是什么” |
| `environment/<step>.json` | 环境位置快照 / 前端回传 | 前端 UI 或 headless backend | backend 下一轮读取、回放与压缩 | 这是位置层面的环境快照，不是完整运营摘要 |

### 4.2 为什么 `sim_status.json` 是主状态

因为它直接聚合了：

- `current_patients`
- `total_patients`
- `patient_states`
- `zone_occupancy`
- `queues`
- `resources`
- `nurse_status`
- `doctor_assigned`

所以它解决的是“当前系统整体怎样”，而不是“某一个人刚才怎么移动”。

`movement/<step>.json` 解决的是局部动画与行为，`sim_status.json` 解决的是整体运营状态，这两个文件职责不同。

### 4.3 用一个 all-scenario run 的结果解释这些指标代表什么

这里使用：

- `analysis/scenario_regressions/20260420_183847/summary.json`

它是一个 all-scenario 500-step 回归，包含五个场景：

- `arrival_normal`
- `arrival_surge`
- `arrival_burst`
- `bottleneck_imaging`
- `boarding_timeout`

#### 4.3.1 每个场景在 step 499 的最终状态

| 场景 | `current_patients` | `total_patients` | `triage` | `doctor_global` | `lab_waiting` | `imaging_waiting` | `boarding_timeout_events` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `arrival_normal` | 182 | 187 | 24 | 151 | 0 | 0 | 0 |
| `arrival_surge` | 249 | 255 | 88 | 154 | 0 | 0 | 0 |
| `arrival_burst` | 208 | 214 | 48 | 153 | 0 | 0 | 0 |
| `bottleneck_imaging` | 148 | 155 | 0 | 142 | 0 | 0 | 0 |
| `boarding_timeout` | 71 | 74 | 0 | 64 | 0 | 0 | 4 |

#### 4.3.2 这些指标怎么解释

| 指标 | 解释 | 汇报时怎么说 |
| --- | --- | --- |
| `current_patients` | 当前还在 ED 内的人数 | 系统瞬时负荷 |
| `total_patients` | 本次 run 到目前为止总共生成过多少患者 | 到诊累积量 |
| `triage` | 当前 triage queue 长度 | 分诊入口拥堵程度 |
| `doctor_global` | 当前医生全局待处理队列 | 医生端积压程度 |
| `lab_waiting` | 明确等待 lab slot 的人数 | lab 资源瓶颈的直接指标 |
| `imaging_waiting` | 明确等待 imaging slot 的人数 | imaging 资源瓶颈的直接指标 |
| `boarding_timeout_events` | 已累计记录的 boarding 超时事件数 | 住院衔接延迟的运营告警指标 |

#### 4.3.3 为什么 `sim_status`、`movement`、`environment` 要一起看

因为它们关注的是三个不同层次：

| 文件 | 层次 | 回答的问题 |
| --- | --- | --- |
| `sim_status.json` | 运营层 | 系统现在拥堵在哪里 |
| `movement/<step>.json` | 行为层 | 这一帧里角色打算去哪、做了什么 |
| `environment/<step>.json` | 位置层 | 当前地图坐标快照是什么 |

三个文件JSON文件同时保留的作用：

- 因为一个 JSON 很难同时兼顾 dashboard 聚合、地图播放、位置回传、回归分析这四类需求。
- Week7 选择的是职责分离，而不是把所有信息塞进单个巨型状态文件。

---

# 第二部分：运行与测试方法

## 1. `deep_fast` 与 `realism_check` 的区别

Week7 回归脚本里的执行 profile 由 `resolve_runtime_env()` 决定。

| profile | `LLM_MODE` | `EMBEDDING_MODE` | `USE_LOCAL_EMBEDDINGS` | 适用场景 |
| --- | --- | --- | --- | --- |
| `deep_fast` | `local_only` | `local_only` | `1` | 追求稳定长跑、回归速度优先 |
| `realism_check` | 默认 `remote_only`，可覆盖 | 默认 `hybrid`，可覆盖 | 若 embeddings 设为 `local_only` 则为 `1` | 更接近真实模型调用行为 |

一句话区分：

- `deep_fast` 是“为了长程回归快而稳”。
- `realism_check` 是“为了更接近真实线上调用模式”。

## 2. `smoke / deep / auto` 三种模式

| 模式 | 含义 | 适合什么时候用 |
| --- | --- | --- |
| `smoke` | 只跑短门槛验证 | 改完代码先看会不会马上炸 |
| `deep` | 直接跑深度回归 | 已知代码基本稳定，只关心长程行为 |
| `auto` | 先 smoke，再 deep | 想要一个更安全的标准流程 |

脚本里的逻辑是：

1. `smoke` 会把场景配置改写成只跑到 `smoke_steps`。
2. `auto` 只有在 smoke 全过之后才会启动 deep。
3. `deep` 可配 `--skip-smoke`，表示我明确接受直接长跑。

## 3. 常用 PowerShell 命令

### 3.1 启动 Django 前端

```powershell
cd D:\projects\BME1325Spring2026\BME1325_Group_One_Repo\week7_auto\environment\frontend_server
python manage.py runserver 8000
```

### 3.2 直接启动后端仿真

```powershell
cd D:\projects\BME1325Spring2026\BME1325_Group_One_Repo\week7_auto\reverie\backend_server
python reverie.py --origin ed_sim_n5 --target curr_sim --frontend_ui yes
```

### 3.3 跑 all-scenario 的 smoke + deep

```powershell
cd D:\projects\BME1325Spring2026\BME1325_Group_One_Repo\week7_auto
python .\scripts\run_week7_long_regression.py --scenario all --mode auto --execution-profile deep_fast --seed 1337
```

### 3.4 直接做 run500

```powershell
cd D:\projects\BME1325Spring2026\BME1325_Group_One_Repo\week7_auto
python .\scripts\run_week7_long_regression.py --scenario all --mode deep --skip-smoke --execution-profile realism_check --max-chunks 500 --seed 1337
```

### 3.5 直接做 run1000

```powershell
cd D:\projects\BME1325Spring2026\BME1325_Group_One_Repo\week7_auto
python .\scripts\run_week7_long_regression.py --scenario arrival_surge --mode deep --skip-smoke --execution-profile realism_check --llm-mode remote_only --embedding-mode hybrid --max-chunks 1000 --seed 1337
```

### 3.6 对某个已完成 run 重新做分析

```powershell
cd D:\projects\BME1325Spring2026\BME1325_Group_One_Repo\week7_auto
python .\analysis\compute_metrics.py --sim arrival_surge-deep-run --refresh-compressed
```

### 3.7 常用测试命令

```powershell
cd D:\projects\BME1325Spring2026\BME1325_Group_One_Repo\week7_auto
python -m pytest .\tests\backend\test_week7_features.py -v
python -m pytest .\tests\analysis\test_run_week7_long_regression.py -v
python -m pytest .\tests\analysis\test_compute_metrics.py -v
python -m pytest .\tests\frontend\test_views.py -v
```

## 4. 参数解释

### 4.1 `max_chunks`

| 参数 | 作用 | 这份项目里要特别注意的点 |
| --- | --- | --- |
| `max_chunks` | 覆盖场景配置中的 `chunks` | 当前 Week7 catalog 多数场景 `chunk_steps = 1`，因此 `max_chunks = 总步数` |

这也是为什么本文能把 `run500 / run1000` 直接理解为 `--max-chunks 500 / 1000`。

### 4.2 `seed`

| 参数 | 作用 |
| --- | --- |
| `seed` | 控制场景复制、病人生成与回归复现的一致性 |

- 同样的 `seed` 让我们更容易比较“改参数前后”的差异。
- 不同的 `seed` 可以用来做稳健性检查。

### 4.3 `llm_mode`

| 取值 | 含义 |
| --- | --- |
| `local_only` | 尽量全走本地 |
| `remote_only` | 尽量全走远端 |
| `hybrid` | 本地与远端混合 |

### 4.4 `embedding_mode`

| 取值 | 含义 |
| --- | --- |
| `local_only` | embedding 只用本地 |
| `remote_only` | embedding 只用远端 |
| `hybrid` | embedding 混合模式 |

## 5. 输出文件结构

一次标准回归结束后，`analysis/scenario_regressions/<timestamp>/` 下面通常会出现类似结构：

```text
analysis/scenario_regressions/<timestamp>/
  summary.json
  smoke/                  # 如果跑了 smoke
  deep/
    <scenario>/
      summary.json
      runtime.log
      patient_time_metrics.csv
      ctas_daily_metrics.csv
      resource_event_metrics.json
```

### 5.1 `summary.json` 有两层

| 层级 | 文件 | 作用 |
| --- | --- | --- |
| 顶层 | `analysis/scenario_regressions/<timestamp>/summary.json` | 记录这次批量回归跑了哪些 scenario、用什么 mode/profile、是否全部通过 |
| 场景层 | `analysis/scenario_regressions/<timestamp>/deep/<scenario>/summary.json` | 记录某个场景的 runtime sample、sample peak、final status、analysis artifacts |

### 5.2 `csv / metrics` 各自表达什么

| 文件 | 作用 |
| --- | --- |
| `patient_time_metrics.csv` | 每个病人的 arrival / PIA / disposition / leave / wait / total ED 时间 |
| `ctas_daily_metrics.csv` | 按 CTAS 汇总的平均等待、治疗、总 ED 时间 |
| `resource_event_metrics.json` | Week7 资源与事件摘要，如 arrival mode、lab/imaging 容量、boarding timeout 数 |

### 5.3 为什么要把 runtime summary 和 post-analysis 分开

因为它们回答的是两类不同问题：

- runtime summary 回答“仿真跑的时候系统峰值到哪了”。
- post-analysis 回答“病人级数据最后汇总成什么表”。

也就是对应着：

- 实时系统行为。
- 事后统计结果。

---

# 第三部分：前端 UI 与 baseline 对比

## 1. baseline（EDSim）的机制：step + handshake

baseline 的核心机制不是“纯前端动画”，而是一个 step-based handshake：

```text
frontend 写 environment/<step>.json
  -> backend 读取 environment/<step>.json
  -> backend 执行一步 agent loop
  -> backend 写 movement/<step>.json
  -> backend 写 sim_status.json
  -> frontend 再读 movement/<step>.json 做地图更新
```

这意味着 baseline 的前端并不是完全被动的 viewer，而是参与了仿真的环境同步。

在 `translator/views.py` 中，这条链路体现为：

- `/process_environment/`：前端把当前环境写回 `environment/<step>.json`
- `/update_environment/`：前端向后端要 `movement/<step>.json`
- `/send_sim_command/`：前端通过 command file 让后端执行 `run N`

## 2. Week7 的改动：Django gateway + dashboard

Week7 没有把 baseline 的 auto-mode UI 彻底推翻，而是在上面继续加了一层统一 gateway：

| 方向 | baseline | Week7 |
| --- | --- | --- |
| 自动仿真控制 | 有 | 保留 |
| 地图播放 | 有 | 保留 |
| live dashboard | 有雏形 | 明确把 `sim_status.json` 作为 dashboard source of truth |
| user mode API | 基本没有统一并进来 | 统一挂到 Django 下 |
| handoff / queue snapshot | 不完整 | 统一作为 gateway API 暴露 |

当前 Week7 在 Django gateway 层统一暴露了：

- `/start_backend/<origin>/<target>/`
- `/send_sim_command/`
- `/get_sim_output/`
- `/live_dashboard`
- `/api/live_dashboard/`
- `/mode/user/encounter/start`
- `/mode/user/chat/turn`
- `/mode/user/session/status`
- `/mode/user/session/reset`
- `/ed/handoff/request`
- `/ed/handoff/complete`
- `/ed/queue/snapshot`

所以 Week7 的前端改动，本质不是“换了一个更花哨的页面”，而是：

- 把 auto mode、user mode、handoff、dashboard 统一托管到同一个 Django host 上。

## 3. 当前 UI 已实现的功能

### 3.1 auto-mode 地图侧

- 可以启动后端。
- 可以发送 `run N` / `fin` 等命令。
- 可以基于 `movement/<step>.json` 播放地图动作。
- 首页会显示 runtime source note，提醒：
  - `sim_status.json` 是主状态
  - `curr_step.json` 只是指针

### 3.2 live dashboard 侧

- 读取 `/api/live_dashboard/`
- 展示：
  - step
  - sim time
  - 当前在 ED 人数
  - completed
  - arrival profile
  - lab waiting
  - imaging waiting
  - boarding timeout events
- 绘制：
  - patient state distribution
  - zone occupancy
  - queue sizes
  - nurse utilization
  - doctor load
- 显示 runtime sync banner，对比：
  - `sim_status.step`
  - `curr_step pointer`
  - latest `movement`
  - latest `environment`

### 3.3 gateway API 侧

- user-mode chat 已并入。
- handoff request / complete 已并入。
- queue snapshot 已并入。

也就是说，Week7 的前端不只是“地图”，还是课程展示用的统一入口。

## 4. 当前存在的问题

### 4.1 人物不连续移动

表现：

- 地图上看起来像“跳点”而不是连续走路。

### 4.2 UI 与状态不同步

表现：

- dashboard 上的 `current_patients`、`queue` 已经变化了，
- 但地图人物位置还没完全跟上，或者反过来。

### 4.3 非匀速

表现：

- 有时人物长时间不动，随后突然跳几格。
- 并不是固定 wall-clock 速度在播放。

## 5. 这些问题的本质原因

### 5.1 前端参与仿真，而不是纯 viewer

这是最根本的一点。

因为 `environment/<step>.json` 是由前端写回去的，所以前端并不是单纯读取后端结果，而是参与了环境状态同步。

这会带来两个后果：

1. 如果前端回写慢，backend 可能读到旧 environment。
2. backend 下一步计算依赖的，不只是自己的内部状态，也包括这份 environment feedback。

因此“前端参与仿真”本身就提高了不同文件之间发生短暂不同步的概率。

### 5.2 `movement` 与 `sim_status` 的同步语义不同

这也是第二个核心原因。

| 文件 | 关注点 |
| --- | --- |
| `movement/<step>.json` | 这一帧人物要怎么走、说了什么、动作描述是什么 |
| `sim_status.json` | 当前系统聚合统计是什么 |

两者本来就不是同一层信息。

所以会出现：

- `sim_status` 已经显示 queue 变化了，
- 但地图上对应角色的空间移动还没有视觉完成。

这不是单纯的“bug”，而是“聚合状态更新”和“空间动作更新”本来就是两个不同数据产品。

### 5.3 当前播放是离散 step，不是连续轨迹插值

`movement/<step>.json` 保存的是 step 级输出，而不是高帧率轨迹流。

因此 UI 播放时拿到的是：

- 第 100 步的位置/动作，
- 第 101 步的位置/动作，

而不是“100 到 101 之间每一帧怎么平滑过渡”。

所以人物天然会显得不够连续。

### 5.4 非匀速来自两层时间并存

系统同时存在：

- simulated time：由 `sec_per_step` 推进
- wall-clock time：由真实 LLM 调用、I/O、浏览器轮询速度决定

如果某一步后端花了更长时间：

- simulated time 仍然只前进一个 step，
- 但 wall-clock 上用户会感觉“卡了一下”。

再加上 step 之间并没有强制做恒速插值，于是就会出现：

- 有时慢
- 有时快
- 有时突然跳

这正是“仿真步进系统”和“动画播放器”耦合后常见的问题。

## 6. 为什么 Week7 先保留这个机制，而不是彻底重写 UI

因为 Week7 的主要目标不是做全新渲染器，而是把三条资源现实性规则：

- arrival profile
- lab / imaging capacity + TAT
- boarding timeout

安全地接到已有 auto-mode runtime 里，并且让它们能被：

- dashboard 观察
- regression 验证
- Django gateway 暴露

所以当前 UI 的策略其实是：

- 尽量复用 baseline 的 step + handshake 机制，
- 在这个基础上补 dashboard、runtime sync、gateway API。

这是一个非常典型的工程取舍：

- 如果本周目标是“做出可汇报、可回归、可解释的 Week7 规则增强”，
- 那么优先保证后端规则与证据链，而不是把所有精力都投入前端重构。

## 7. 前端UI界面总结

> baseline 的 UI 本质是一个 step-based handshake：前端回传 `environment`，后端写 `movement` 和 `sim_status`。Week7 没有推翻这条链，而是在 Django 上统一了 auto-mode、user-mode、handoff 和 dashboard。当前 UI 已经能展示主状态、地图、命令控制和实时资源指标；但因为前端仍参与环境回传，且 `movement` 与 `sim_status` 属于不同层级的数据，所以会出现人物不连续、状态不同步、速度不均匀。这些问题的根源更多是架构耦合，而不是单一页面 bug。 

> `week7_auto` 不是把 arrival、testing、boarding 三个原本只存在于“流程直觉”里的现实运营问题，正式变成了可配置、可观测、可回归、可答辩的系统变量。
---

# 第四部分：LLM 接入后的性能与稳定性

## 1. 先讲结论：Week7 为什么会“明显变慢”

Week7 接入 LLM 之后，用户感受到的“明显变慢”，并不是由某一个单独模块造成的，而是三层耗时叠加出来的结果：

1. 真实远端 LLM 请求本身需要几秒。
2. `embedding` 检索在网络不稳时会出现明显抖动，甚至比 LLM 主请求更慢。
3. 外层回归脚本采用 `chunk_steps = 1` 的一步一轮询方式，本身还会增加额外的 wall-clock 等待时间。

因此，必须先区分两种“慢”：

| 口径 | 它表示什么 | 典型来源 |
| --- | --- | --- |
| backend step time | 后端真正执行一步仿真的时间 | `persona.move()` 内部的 cognition、规则推进、写状态文件 |
| overall wall-clock time | 从外部脚本角度看，一整个实验实际花了多久 | backend 执行时间 + 外层轮询等待 + I/O + 分析链路 |

这一点非常重要，因为如果只看 `summary.json` 里的 `wall_clock_seconds`，会把“LLM 本身的推理开销”和“实验驱动脚本的一步一采样开销”混在一起，进而高估 LLM 对总时长的影响。

## 2. 到底慢在代码链路的哪个环节

从后端主循环来看，每一步仿真的核心流程是：

1. 读取当前 `environment/<step>.json`
2. 同步 persona 位置与环境状态
3. 对每个 persona 调用 `persona.move(...)`
4. 在 `move()` 内执行 `perceive -> retrieve -> plan`
5. 写出 `movement/<step>.json`、`sim_status.json`、`curr_step.json`

其中真正最容易把一步拉长的，不是 Week7 新增的 arrival / lab / boarding 三条规则，而是 `persona.move(...)` 内部的 cognition 路径，尤其是：

- `retrieve()` 中的 embedding 检索
- `plan()` 中的 LLM prompt 调用
- 某些需要较长上下文的 agent 决策

对应代码位置可以概括为：

| 环节 | 主要文件 | 说明 |
| --- | --- | --- |
| step 主循环 | `reverie/backend_server/reverie.py` | 调度每个 persona 的一步执行 |
| persona cognition 入口 | `reverie/backend_server/persona/persona.py` | `move()` 内调用 `perceive / retrieve / plan` |
| LLM / embedding 请求 | `reverie/backend_server/persona/prompt_template/gpt_structure.py` | 远端 chat、embedding、fallback、日志记录 |
| 外层回归调度 | `scripts/run_week7_long_regression.py` | 一步一发 `run 1`，再轮询 `curr_step.json` |

也就是说，如果某一步从 `0.03s` 突然跳到 `5s`、`30s` 甚至 `170s`，优先怀疑的不是 arrival rule、lab capacity 或 boarding timeout，而是 agent cognition 的 LLM / embedding 热路径。

## 3. 历史运行记录说明：这个“慢”到底有多慢

### 3.1 本地快速模式：规则本身其实不慢

证据来源：

- `analysis/scenario_regressions/20260419_123023/summary.json`
- `analysis/scenario_regressions/20260419_123023/different_seed/arrival_surge/seed_2024/arrival_surge/runtime.log`

这组运行使用的是：

| 参数 | 取值 |
| --- | --- |
| `execution_profile` | `deep_fast` |
| `LLM_MODE` | `local_only` |
| `EMBEDDING_MODE` | `local_only` |
| 总步数 | `100` |

关键结果：

| 指标 | 数值 |
| --- | ---: |
| summary 中总 wall-clock | `108.751s` |
| backend `run 1` 命令总和 | `5.168s` |
| backend 平均每步耗时 | `0.037s/step` |
| backend 最大单步耗时 | `0.085s` |
| 真实远端 LLM 成功次数 | `0` |
| local short-circuit 次数 | `12` |

这说明一件很关键的事：如果把真实 LLM 和远端 embedding 拿掉，只保留 Week7 的业务规则与本地 fail-safe 路径，那么后端本身是很快的。也就是说，Week7 新增的三条规则并没有把系统本体拖慢到不可用，纯规则推进基本是毫秒级。

### 3.2 真实远端模式：慢主要来自少数 cognition-heavy steps

证据来源：

- `analysis/scenario_regressions/20260420_183847/summary.json`
- `analysis/scenario_regressions/20260420_183847/deep/arrival_normal/runtime.log`

这组运行使用的是：

| 参数 | 取值 |
| --- | --- |
| `execution_profile` | `realism_check` |
| `LLM_MODE` | `hybrid` |
| `EMBEDDING_MODE` | `hybrid` |
| 场景 | `arrival_normal` |
| 总步数 | `500` |

关键结果：

| 指标 | 数值 |
| --- | ---: |
| summary 中总 wall-clock | `718.488s` |
| backend `run 1` 命令总和 | `213s` |
| 外层额外开销 | `505.488s` |
| 外层平均额外开销 | `1.011s/step` |
| backend 平均每步耗时 | `0.414s/step` |
| backend 最大单步耗时 | `48.125s` |
| backend 最小单步耗时 | `0.004s` |
| 成功 LLM 请求次数 | `40` |
| 成功 LLM 单次平均耗时 | `3.087s` |
| 成功 LLM 单次最大耗时 | `5.358s` |
| `embedding` fallback 次数 | `5` |

这组结果能说明两个层面的事实：

第一，系统并不是“每一步都一样慢”。500 步里：

- 大于 `1s` 的 step 只有 `17` 步
- 大于 `10s` 的 step 只有 `4` 步
- 大于 `30s` 的 step 只有 `1` 步

第二，慢主要集中在少数触发真实 cognition 的步骤上。比如前 10 步的 backend 耗时是：

```text
48.125, 0.006, 0.004, 5.408, 0.006, 0.005, 0.011, 0.031, 0.009, 0.010
```

而最后 10 步则基本回落到：

```text
0.043, 0.023, 0.039, 0.019, 0.037, 0.015, 0.019, 0.037, 0.018, 0.044
```

所以更准确的说法不是“接入 LLM 后系统每一步都很慢”，而是“接入 LLM 后，少数需要真实 cognition 的 step 会出现几秒到几十秒的 spike，从而显著抬高总体 wall-clock”。

### 3.3 网络不稳时：真正危险的是 embedding 路径

证据来源：

- `analysis/scenario_regressions/20260418_154325/arrival_burst/runtime.log`
- `analysis/scenario_regressions/20260417_223558/arrival_burst/runtime.log`
- `analysis/scenario_regressions/20260417_223558/boarding_timeout/runtime.log`

其中最典型的一组是 `20260418_154325/arrival_burst/runtime.log`。前 7 步的耗时分别是：

```text
171.241, 32.900, 5.720, 17.548, 0.021, 24.809, 0.033
```

同一组日志中的关键统计是：

| 指标 | 数值 |
| --- | ---: |
| 7 步总 step time | `252.272s` |
| 成功 LLM 请求次数 | `4` |
| 成功 LLM 平均耗时 | `3.446s` |
| 成功 LLM 总耗时 | `13.784s` |
| `embedding` fallback 次数 | `14` |
| 成功 LLM 耗时占 step 总耗时比例 | `5.5%` |

这意味着：这一次“特别慢”的主要原因并不是模型真的想了很久，而是 embedding 路径在网络波动下不断失败、重试、再 fallback。也就是说，这种慢更像是工程链路不稳定造成的慢，而不是高质量 cognition 带来的慢。

这也是为什么已有工程结论会强调：

- Week7 三条规则本身不是主要瓶颈
- 长场景成本主要来自 `LLM / embedding` 热路径
- 尤其要优先处理 embedding 的缓存与健康短路机制

## 4. 更完整地拆解：LLM 接入后每个阶段大概需要多久

下面给出一个更适合汇报时直接使用的分阶段表。

| 阶段 | 发生位置 | 典型耗时 | 说明 |
| --- | --- | --- | --- |
| 后端启动、读取 `meta.json`、初始化 agent | backend boot | 通常 `<1s` | 不是主要瓶颈 |
| 纯规则推进与状态写盘 | step 尾部 | `0.01s - 0.08s/step` | arrival / lab / boarding 规则本身很轻 |
| 远端一次成功 LLM chat | `llm chat request done` | `2.4s - 5.7s/call` | 这是“真实性”的主要代价 |
| prompt 构造与上下文拼装 | LLM 调用前 | 通常比远端请求小很多 | 但 prompt 会变长 |
| 一次真实 LLM prompt 规模 | `prompt_chars` | `768 - 3104` 字符 | 平均约 `1590` 字符 |
| embedding 本地命中 / 本地 fallback | `get_embedding()` | 通常很快 | 对 wall-clock 影响小 |
| embedding 远端超时 / 失败重试 | `get_embedding failed after retries` | 可把单步拉到 `10s - 170s` | 当前最不稳定环节 |
| 外层一步一轮询 | `wait_for_step()` | 约 `1s/step` | 属于实验脚本口径的附加耗时 |

如果把这个阶段链路按“后端一步内部发生什么”来讲，可以表述为：

1. 进入 step，backend 开始执行 `persona.move()`
2. `perceive()` 收集当前环境
3. `retrieve()` 做 memory / embedding 检索
4. `plan()` 可能触发真实 LLM 请求
5. 得到 next action 后，再执行业务规则和状态写盘
6. 外层回归脚本再等待 `curr_step.json` 更新，记录采样结果

因此，LLM 接入后的额外时间，主要加在第 `3-4` 步；而课程回归脚本的一步一采样，又额外放大了第 `6` 步的 wall-clock。

## 5. 这个 LLM 接入是否具备工程稳定性

如果“工程稳定性”的定义是“系统能不能持续跑完、不中断”，那么答案是：具备一定稳定性。

原因是当前系统已经做了多层 fallback：

- `llm_mode = local_only` 时，可以直接 short-circuit
- `embedding_mode = hybrid` 时，失败后会切到本地 embedding
- 某些安全生成接口在 `hybrid` 模式下也会回到 fail-safe response

但如果“工程稳定性”的定义是“能不能持续稳定地交付真实远端 LLM 质量”，那么答案是：当前还不够稳。

可以用下面这张表来总结：

| 能力目标 | 当前是否具备 | 说明 |
| --- | --- | --- |
| 更真实的 agent 行为 | **部分具备** | 远端健康时成立；远端不稳时会退化为 fallback |
| 更丰富的上下文 | **具备** | prompt 明显更长，包含状态、时间、角色、记忆等字段 |
| 更可解释的决策 | **部分具备** | 已能记录 request begin/done、prompt 大小、模型耗时；但 embedding 路径解释粒度仍不足 |
| 长程运行稳定复现 | **中等** | `deep_fast` 很稳；`realism_check` 受网络与 embedding 健康影响较大 |

### 5.1 更真实的 agent 行为

这一项的确是 LLM 接入带来的主要收益，但它是“条件成立”的。

- 在 `local_only` 模式下，许多请求不会真的发往远端，行为更像“结构化 fail-safe”
- 在 `hybrid` 且远端健康时，agent 才会真正基于丰富 prompt 做远端决策

所以，如果老师问“现在到底是不是一个真实 LLM agent system”，最客观的回答应该是：

> 架构上它确实是一个 LLM-driven agent system；但工程运行上采用了本地短路和 hybrid fallback，因此它更准确地说是一个“面向稳定性的 LLM-enhanced system”，而不是每一步都强依赖远端模型的纯远端系统。

### 5.2 更丰富的上下文

这一项是最明确成立的。

从 prompt 结构和运行日志都能看到，agent 在做决策时已经不只是看一个简单状态，而是会带入：

- 当前时间
- 当前 tile / 当前状态
- role description
- memory weighting 参数
- schedule constraints
- 患者或医护角色相关上下文

历史日志中，成功远端 LLM 请求的 prompt 大小范围是：

| 指标 | 数值 |
| --- | ---: |
| `prompt_chars` 最小值 | `768` |
| `prompt_chars` 最大值 | `3104` |
| `prompt_chars` 平均值 | `1590` |

这说明当前的远端决策不是“薄 prompt”，而是确实在使用 richer context。

### 5.3 更可解释的决策

这一项相比 baseline 已经明显增强，但还没有完全到位。

现在已经具备的解释性包括：

- 可以看到每次 LLM request 的 begin / done / fail
- 可以看到 prompt 规模
- 可以看到模型名与接口路径
- 可以把 step spike 和具体 request 对上
- 可以把最终 `plan` 与系统状态快照对应起来

但目前仍有两个限制：

1. `embedding` 路径的耗时与失败虽然有打印，但不像 LLM chat 那样有同等细粒度的结构化统计。
2. 解释链路目前更偏工程诊断，而不是“医生为什么这样决策”的自然语言因果解释。

因此，更准确的说法是：

> 接入 LLM 后，系统的“工程可解释性”明显增强了；但“决策语义可解释性”仍然需要继续补强。

## 6. 最后一句汇报层总结

如果只用一句话总结“LLM 接入后为什么变慢”，最合适的说法是：

> Week7 变慢的根本原因，不是 arrival / testing / boarding 这三条新规则本身，而是 agent cognition 的 `LLM + embedding` 热路径叠加在 step 主循环里；其中真实远端 LLM 单次调用大约需要 `2-6` 秒，而 embedding 在网络不稳时会引发更大的抖动；再加上外层实验脚本采用一步一轮询，最终共同放大了用户看到的 wall-clock 延迟。

如果再进一步回答“这个接入值不值得”，可以说：

> 从工程角度看，它用更高的延迟换来了更真实的 agent 行为、更丰富的上下文和更好的决策可追踪性；但目前这种收益是建立在 `hybrid fallback` 之上的，因此它已经具备实验价值和展示价值，但距离“稳定的生产级长程 LLM 仿真”还有一段工程化距离。


# 补充内容：常用powershell指令

终端 1，启动 Django frontend
```bash
conda activate edmas
cd D:\projects\BME1325Spring2026\BME1325_Group_One_Repo\week7_auto\environment\frontend_server
& 'D:\anaconda3\envs\edmas\python.exe' manage.py runserver 127.0.0.1:8000
```

终端 2，可选，用命令启动 backend：
```bash
conda activate edmas
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/start_backend/ed_sim_n5/curr_sim/
```

打开页面：
```txt
http://127.0.0.1:8000/start_simulation/
http://127.0.0.1:8000/simulator_home
http://127.0.0.1:8000/live_dashboard
http://127.0.0.1:8000
```