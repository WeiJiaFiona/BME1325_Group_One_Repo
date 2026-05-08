# Week7 Auto README

本 README 面向三类场景：

1. 课程汇报时快速说明 Week7 到底改了什么。
2. 老师追问设计原因时，能直接定位到变量、指标、结果与代码路径。
3. 小组交接时，区分哪些文件是核心代码，哪些只是运行产物。

更细的中文长文档请看 [week7_handoff.md](/d:/projects/BME1325Spring2026/BME1325_Group_One_Repo/week7_auto/week7_handoff.md)。

## 1. System Overview

Week7 的核心目标不是“重写一个新模拟器”，而是在 baseline EDSim 主循环上，加入三类更像真实 ED 运营约束的规则：

- `Arrival Profile`：让病人进入系统的节奏不再只有一个全局倍率，而是能区分 `normal / surge / burst`。
- `Lab / Imaging Capacity + TAT`：把 testing 从单一流程拆成两类资源池，并显式建模 capacity 与 turnaround。
- `Boarding Timeout Event`：把住院承接受阻变成可观测的出口瓶颈指标。

因此，Week7 更准确地说是：

- 对 baseline 的 `rule-driven extension`
- 仍然是 `agent-based simulation`
- 有 stochastic 成分，但不是完整统计建模系统
- 目标是让“压力如何进入系统、如何传播、最后堵在哪里”变得可观测

### 1.1 主要控制变量

| 变量类别 | 关键变量 | 作用 |
| --- | --- | --- |
| Arrival | `visits_per_hour`, `patient_rate_modifier`, `arrival_profile_mode`, `sec_per_step` | 决定单位 step 新病人的生成速度 |
| Testing | `lab_capacity`, `lab_turnaround_minutes`, `imaging_capacity`, `imaging_turnaround_minutes` | 决定中段资源能否及时消化患者 |
| Boarding | `simulate_hospital_admission`, `admission_probability_by_ctas`, `boarding_timeout_minutes` | 决定是否显式放大出口阻塞 |
| Runtime | `max_chunks`, `seed`, `llm_mode`, `embedding_mode`, `execution_profile` | 决定实验长度、复现性、以及 LLM 链路的真实度与耗时 |

### 1.2 主要观测指标

| 指标 | 含义 | 适合回答什么问题 |
| --- | --- | --- |
| `current_patients` | 当前仍在 ED 内的患者总数 | 系统库存是否在持续累积 |
| `total_patients` | 截止当前 step 已进入系统的患者总数 | 不同场景的入口压力是否真的不同 |
| `queues.triage` | 分诊入口等待人数 | 前端入口是否被冲垮 |
| `queues.doctor_global` | 已进入系统但仍等待医生处理的人数 | 压力是否已传播到系统内部 |
| `queues.lab_waiting` / `queues.imaging_waiting` | 等待测试资源的患者数 | 某类 testing 资源是否显式排队 |
| `resources.lab_in_progress` / `resources.imaging_in_progress` | 正在占用 testing slot 的数量 | 容量是否被打满 |
| `avg_wait_minutes_overall` | 平均等待时间 | 作为整体拥堵水平的粗指标 |
| `avg_total_ed_minutes` | 平均总停留时长 | ED 周转效率是否恶化 |
| `boarding_timeout_events` | 超过 boarding timeout 阈值的事件数 | 出口承接是否失效 |
| `wall_clock_seconds` | 真实运行耗时 | LLM 接入后系统是否还能工程上跑得动 |

## 2. Arrival Profile（入口）

### 2.1 设计目的

baseline 只有一个较粗的病人到达倍率，能表达“整体更忙”或“整体更闲”，但不容易表达“全天都忙”和“局部时段爆峰”这两种本质不同的压力形态。

Week7 引入 `arrival_profile_mode`，目的不是做严格统计拟合，而是先把入口压力拆成更容易解释的三类实验条件：

- `normal`：保留原始小时曲线
- `surge`：整天整体放大
- `burst`：改变形状，让某些时段出现尖峰

这样做的价值在于：在医生、护士、testing capacity 都不变的前提下，只改病人进入系统的节奏，就能观察拥堵从入口向内部传播的方式。

### 2.2 三种模式差异

Week7 使用的核心公式是：

```text
hourly_arrivals(hour) =
  visits_per_hour(hour) * effective_arrival_rate(patient_rate_modifier, arrival_profile_mode, hour)
```

但仿真不是“每小时一次性塞入整数病人”，而是 step-based arrival：

这一小时原本该来多少人，先按 step 均匀拆开；再根据 `normal / surge / burst` 场景把它放大或缩小；每一步把这部分“到达量”加进一个累计器里，累计器一旦达到 `1`，就真正生成一个病人。

可以类比成接水桶：

- `visits_per_hour` = 水龙头一小时应该放多少水
- `steps_per_hour = 3600 / sec_per_step` = 你把这一小时切成多少小段
- 每个 step 往桶里滴一点水
- `add_patient_threshold` = 桶里的水量
- 滴满了就触发一次 arrival

对应 step 级增量是：

```text
threshold_increment_per_step =
  visits_per_hour(hour) / steps_per_hour
  * effective_arrival_rate(patient_rate_modifier, arrival_profile_mode, hour)
```

### 2.3 模式与参数表

在启动仿真的时候选择一种模式，然后一整天按照该规则运行：

- `normal` 像平常工作日，早晚会有自然变化，但没有极端高峰。
- `surge` 像流感爆发或持续高压日，所有时间段患者流量整体上升。
- `burst` 表示明显峰值的一天，例如早上和傍晚突然挤入很多患者，中间稍缓。

| 模式 | 本质 | 参数 | 含义 |
| --- | --- | --- | --- |
| `normal` | 保持原始到达曲线 | `1.0` | 只保留 baseline 的小时级 arrival curve |
| `surge` | 整体放大 `scale` | `1.75` | 所有时段统一放大 |
| `burst` | 改变形状 `reshape` | `07-09 => 2.2`, `11-13 => 1.15`, `16-19 => 2.6`, 其余 `0.65` | 不是全天都高，而是高峰更高、低谷更低 |

一个通俗的数值例子：

- 假设上午 9 点 baseline 为 `12` 人/小时
- `normal`: `12 x 1.0 = 12`
- `surge`: `12 x 1.75 = 21`
- `burst`: `12 x 2.2 = 26.4`
- 假设凌晨 3 点 baseline 为 `4`
- `burst`: `4 x 0.65 = 2.6`

### 2.4 为什么这样设计

这套 arrival 设计更偏“工程规则”，不是严格的 NHPP 统计建模。

原因有三点：

1. 课程阶段的重点是先让系统对不同压力形态有可解释响应，而不是先做复杂参数估计。
2. `normal / surge / burst` 容易和老师、队友、实验报告对齐，因为它们对应的是直观业务语义。
3. 这样设计后，拥堵传播链条更容易解释为“入口形态变化”而不是“底层随机数刚好波动”。

它的边界也要说清楚：

- 这不是对真实 ED arrival process 的严格统计拟合。
- `1.75 / 2.2 / 2.6 / 0.65` 目前属于可解释的 stress-test 参数，不是从医院原始 arrival 数据反推出来的估计值。
- 后续更合理升级方向是：用真实小时级 arrival 数据做 `data-driven multiplier`，甚至升级到 NHPP。

### 2.5 真实结果：run500 / run1000

以下结果来自已保存的 Week7 回归结果：

- `arrival_normal`: `analysis/scenario_regressions/20260419_180032/deep/arrival_normal/summary.json`
- `arrival_surge`: `analysis/scenario_regressions/20260419_181903/deep/arrival_surge/summary.json`
- `arrival_burst`: `analysis/scenario_regressions/20260419_183714/deep/arrival_burst/summary.json`

#### step 500

| 场景 | `total_patients` | `current_patients` | `triage queue` | `doctor_global_queue` |
| --- | ---: | ---: | ---: | ---: |
| `arrival_normal` | 187 | 182 | 24 | 151 |
| `arrival_surge` | 255 | 249 | 88 | 154 |
| `arrival_burst` | 214 | 208 | 47 | 154 |

#### step 1000

| 场景 | `total_patients` | `current_patients` | `triage queue` | `doctor_global_queue` | `avg_wait_minutes_overall` | `avg_total_ed_minutes` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `arrival_normal` | 375 | 361 | 46 | 307 | 480.05 | 98.69 |
| `arrival_surge` | 511 | 497 | 177 | 311 | 506.27 | 143.80 |
| `arrival_burst` | 435 | 423 | 101 | 313 | 513.80 | 137.83 |

### 2.6 如何解释这些结果

这里最值得汇报的点，不只是“surge 人更多”，而是“为什么 burst 也很危险”。

- `surge` 把全天 arrival 都抬高，所以 `total_patients` 增长最大。
- `burst` 的总人数没有 `surge` 多，但因为高峰更尖、时间更集中，会在局部时段把入口和中段同时压爆，所以 `avg_wait_minutes_overall` 反而略高于 `surge`。
- 换句话说，`surge` 更像持续高负荷，`burst` 更像瞬时冲击。

#### 2.6.3 后续优化内容说明

上述表格的核心意义在于：在同一个系统配置保持不变的前提下，通过对比不同 `arrival_profile_mode`（`normal / surge / burst`），可以直观观察病人流入模式变化对系统状态的影响。具体来说，不同的 arrival 模式会改变病人进入系统的节奏与强度，从而在不同环节产生不同程度的拥堵。

例如：

- `triage queue` 可以反映分诊入口是否被冲垮，体现系统最前端的承载能力。
- `doctor global queue` 则反映已经完成分诊但仍等待医生处理的患者数量，用于刻画系统内部是否出现积压。

通过这两个关键队列指标的变化，可以进一步观察压力如何在系统中传播，从入口逐步向下游扩散，从而揭示不同压力形态下的潜在瓶颈位置。

但也需要强调：

- 这组表没有显式包含医生数量、护士配置或资源利用率。
- 因此它更适合做 arrival 模式之间的相对比较。
- 它不能单独用来判断医院整体资源调度是否合理。

## 3. Imaging + Lab 层

### 3.1 设计目的与设计说明

baseline 的 testing flow 更像一个统一诊断流程：病人进入 testing 相关状态后，主要体现“需要做检查”和“结果何时回来”，但没有显式拆开不同 testing pool 的资源成本。

Week7 做的事情是把 testing 拆成两个资源池：

- `lab`
- `imaging`

然后显式加入两类参数：

- `capacity`：同一时刻能并发处理多少个测试
- `turnaround_minutes`：从占用 slot 到结果返回需要多长时间

CTAS 到 testing 的 Version0 映射是：

| CTAS | `testing_kind` | 解释 |
| --- | --- | --- |
| `1-2` | `imaging` | 高 acuity 患者更容易需要影像类检查，先用此规则放大重资源需求 |
| `3-5` | `lab` | 较低 acuity 先走轻资源 testing pool |

这不是“现实医院唯一正确映射”，而是一个有意简化的 Version0：先把资源异质性拉出来，再观察容量不足是否会引发系统堵塞。

### 3.2 bottleneck 是如何产生的

关键场景：

- `analysis/scenario_regressions/20260419_215509/deep/bottleneck_imaging/summary.json`

配置特征：

| 参数 | 值 |
| --- | ---: |
| `arrival_profile_mode` | `surge` |
| `imaging_capacity` | `1` |
| `imaging_turnaround_minutes` | `120` |
| `lab_capacity` | `2` |
| `lab_turnaround_minutes` | `30` |

结果：

| 指标 | run500 | run1000 |
| --- | ---: | ---: |
| `current_patients` | 147 | 252 |
| `total_patients` | 155 | 266 |
| `doctor_global_queue` | 141 | 244 |
| `imaging_in_progress` | 0 | 1 |
| `imaging_capacity` | 1 | 1 |
| `max_imaging_waiting` | 2 | 2 |

这里最容易被追问的问题是：为什么 imaging 明明是瓶颈，但 `imaging_waiting` 不一定很高？

原因是 Week7 当前更像一个“有限缓冲 + 上游回压”的系统：

- imaging slot 少、TAT 长，导致下游消化能力不足。
- 但患者不一定都已经成功走到 imaging 等待队列里。
- 一部分压力会更早滞留在 `doctor_global_queue`、`WAITING_FOR_TEST` 或系统库存里。

所以：

- 队列不一定堆在真正的瓶颈点上。
- 真正的瓶颈，常常表现为“下游处理能力不足，上游库存持续上升”。

### 3.3 现存问题与后续方向

当前 Week7 的 lab / imaging 设计可以看作一个 Version0：通过简化的 CTAS 映射，将患者分流到两类资源成本不同的 testing pool 中，从而在不引入医生决策不确定性的前提下，验证 capacity 和 turnaround 是否会引起系统拥堵与积压传播。

从实验结果可以观察到，在 arrival 压力固定的情况下，虽然 imaging waiting 队列本身并不显著增长，但 `doctor_global_queue` 和 `current_patients` 明显上升，这说明系统瓶颈已经由下游 imaging 资源向上游传播，表现为队列和在院人数持续增长，从而进入不稳定状态。结果表明：资源调度参数，特别是 `capacity` 与 `turnaround`，直接决定系统处理能力。

同时，该设计使得“arrival -> testing -> doctor -> system overload”的压力传播路径可观测，为后续分析资源瓶颈提供了清晰的因果链。

下一步更合理的升级方向是引入 `doctor-guided probabilistic routing`，即由医生建议和患者特征共同决定是否进入 lab 或 imaging，让 testing request 更接近真实临床流程，同时保留系统的可控性和可解释性。

## 4. Boarding（出口）

### 4.1 设计目标、系统接口含义与具体实施

在急诊系统里，boarding 的本质更像一个系统接口状态 `interface state`：它连接 ED 和 Inpatient 两个子系统。患者一旦被判定需要住院，临床决策本身已经完成，但系统层面仍需要等待床位、转运和下游承接能力。

因此，boarding 不是新的临床阶段，而是一个跨系统过渡状态。

Week7 通过以下方式把这个问题显式化：

- 打开 `simulate_hospital_admission`
- 将 `admission_probability_by_ctas` 设为高值，stress test 场景中甚至设为 `1.0`
- 设置较短的 `boarding_timeout_minutes`
- 设置较长的 boarding 停留区间，让患者长期滞留在 `ADMITTED_BOARDING`

这里 `boarding_timeout_event` 被设计成事件而不是状态切换，原因是：

- 它的核心用途是做运营告警与系统观测
- 不是为了让模拟器自动替医院做升级处置
- 这样可以把“出口阻塞是否发生”与“系统后来如何处理患者”分开

### 4.2 结果说明

典型场景：

- `analysis/scenario_regressions/20260419_221345/deep/boarding_timeout/summary.json`

在 `arrival_profile_mode = normal` 的前提下，实验结果显示：

| 指标 | run500 | run1000 |
| --- | ---: | ---: |
| `current_patients` | 71 | 119 |
| `doctor_global_queue` | 63 | 112 |
| `boarding_timeout_events` | 5 | 11 |

解释逻辑是：

- 入口压力并没有显著增加。
- 但系统库存和 doctor queue 仍持续上升。
- 因此，更合理的解释不是“arrival 太多”，而是“患者出不去”。

换句话说，出口承接失败会反向拖累上游。

## 5. System Behavior Analysis

这一部分建议在汇报中把不同 case 统一解释成“压力传播图”。

### 5.1 四类场景如何堵住系统

| 场景 | 主要改动 | 先出问题的地方 | 传播路径 | 最终表现 |
| --- | --- | --- | --- | --- |
| `arrival_normal` | 正常入口 | 入口温和积压 | triage -> doctor | 系统可运行，但等待时间已偏长 |
| `arrival_surge` | 全天整体放大 arrival | triage 入口 | triage -> doctor -> 全系统库存 | `total_patients` 和 `current_patients` 同时快速上升 |
| `arrival_burst` | 局部高峰冲击 | 高峰时段入口和中段同时受压 | triage 高峰 -> doctor backlog | 总量略低于 surge，但局部等待更差 |
| `bottleneck_imaging` | imaging capacity 降低、TAT 拉长 | 中段 testing 消化能力 | imaging resource -> doctor queue -> system inventory | 队列不一定堆在 imaging_waiting，但整体库存持续上升 |
| `boarding_timeout` | 出口承接故障 | 出口 | boarding -> doctor queue -> system inventory | 系统“病人出不去”，库存持续上升 |

### 5.2 后端四类关键文件各代表什么

Week7 回放与 dashboard 主要依赖以下文件：

| 文件 | 角色 | 是否是 source of truth |
| --- | --- | --- |
| `sim_status.json` | 主状态快照，dashboard 直接读取 | 是，主状态源 |
| `curr_step.json` | 当前 step 指针、运行握手文件 | 不是，只是同步信号 |
| `movement/<step>.json` | 当前 step 的动作执行与人物移动 | 不是主状态，但驱动地图播放 |
| `environment/<step>.json` | 当前 step 的环境回传快照 | 不是主状态，用于 UI 对齐与回放 |

`translator/views.py` 里已经明确写了这层语义：

- `sim_status.json is the dashboard source of truth`
- `curr_step.json is a runtime pointer and startup handshake signal`
- `movement/<step>.json drives map execution`
- `environment/<step>.json captures map position snapshots`

### 5.3 用一个 all-scenario run 理解这些指标

可参考：

- `analysis/scenario_regressions/20260420_183847/summary.json`

这个 all-scenario run 的意义不是只看某一个数字，而是按同一套采样框架去比较不同场景下：

- `status.current_patients` 是否持续增大
- `queues.triage` 是否先升高
- `queues.doctor_global` 是否在入口之后继续扩大
- `resources.lab_in_progress / imaging_in_progress` 是否长期贴着 capacity
- `resources.boarding_timeout_events` 是否持续累积

因此，老师如果问“哪个地方堵了”，不能只看一个 queue，而要看：

1. 入口队列有没有先爆
2. 中段资源是否持续打满
3. 出口事件是否持续出现
4. 整体库存 `current_patients` 是否单调增长

## 6. LLM 接入后的性能与稳定性

### 6.1 baseline step 链路 vs Week7 auto mode 链路

不接 LLM 时，单步主要成本是：

- `persona.move()` 主循环
- 基础状态推进
- movement / environment / status 写文件

接入 LLM 后，单步链路变成：

1. 读取当前环境与状态
2. `persona.move()` 中进行 perceive / retrieve / plan
3. 可能触发 embedding
4. 可能触发 LLM request
5. 完成状态推进
6. 写 `sim_status.json`
7. 写 `movement/<step>.json`
8. 写 `environment/<step>.json`
9. 回归 runner 再用 1 秒轮询检查 `curr_step.json`

所以 Week7 的“明显变慢”其实来自两层：

- `backend in-step latency`：LLM / embedding 让某一步内部真的更慢
- `orchestration latency`：每次只跑 `run 1`，外层脚本 1 秒轮询一次，天然带来约 `1s/step` 的等待

### 6.2 真实耗时数据

#### A. `deep_fast`，本地模式，100 step

来源：

- `analysis/scenario_regressions/20260419_123023/summary.json`

| 指标 | 数值 |
| --- | ---: |
| execution profile | `deep_fast` |
| `LLM_MODE` | `local_only` |
| `EMBEDDING_MODE` | `local_only` |
| `wall_clock_seconds` | `108.751` |
| backend command sum | `5.168s` |
| backend avg step | `0.037s/step` |
| backend max step | `0.085s` |
| `llm_short_circuit` | `12` |
| successful remote LLM calls | `0` |

解释：

- 这基本证明不是真实 LLM 在慢。
- 真正主要开销是外层 step-by-step orchestration。
- `108.751 - 5.168 = 103.583s`，约等于 `1.036s/step`。

#### B. `realism_check`，hybrid，500 step

来源：

- `analysis/scenario_regressions/20260420_183847/deep/summary.json`

| 指标 | 数值 |
| --- | ---: |
| execution profile | `realism_check` |
| `wall_clock_seconds` | `718.488` |
| backend command sum | `213s` |
| outer orchestration overhead | `505.488s` |
| backend avg step | `0.414s/step` |
| backend max step | `48.125s` |
| successful LLM calls | `40` |
| successful LLM avg latency | `3.087s` |
| successful LLM max latency | `5.358s` |
| successful LLM total time | `123.461s` |
| LLM time share in backend compute | about `58%` |

解释：

- 这时 LLM 确实成为 backend compute 的主要开销之一。
- 但总耗时依然不只由 LLM 决定，因为外层轮询还在吃掉约 `1.011s/step`。

#### C. 网络不稳定时的 realism run

来源：

- `analysis/scenario_regressions/20260419_154713/deep/summary.json`

| 指标 | 数值 |
| --- | ---: |
| backend avg step | `0.182s` |
| backend max step | `7.692s` |
| successful LLM calls | `0` |
| failed LLM calls | `12` |
| embedding failures | `3` |

结论：

- 系统具备 fallback，能跑完。
- 但“能跑完”不等于“具有稳定的真实 LLM 行为”。
- 如果远程链路不稳定，行为真实性和解释性都会下降。

### 6.3 工程稳定性应该怎么客观评价

从现有数据看，Week7 接入 LLM 后具备“可运行性”，但还没有达到“高吞吐生产级稳定性”。

可以客观表述为：

| 能力 | 当前结论 |
| --- | --- |
| 更真实的 agent 行为 | 有帮助，尤其在远程 LLM 成功时更明显 |
| 更丰富的上下文 | 有，但代价是 prompt 更长、调用更慢 |
| 更可解释的决策 | 有，因为日志里能看到 prompt / response / retry |
| 工程稳定性 | 可做课程实验与回归，不适合高频大规模批量运行 |
| 性能瓶颈 | 远程 LLM、embedding、以及 step-by-step orchestration 共同构成瓶颈 |

### 6.4 每个阶段大概慢在哪里

| 阶段 | 是否可能成为主要耗时 | 说明 |
| --- | --- | --- |
| `persona.move()` 基础逻辑 | 中等 | 没有远程调用时通常较快 |
| `perceive / retrieve / plan` | 高 | LLM 相关逻辑主要发生在这里 |
| embedding | 高 | 尤其在远程或失败重试时 |
| LLM request | 很高 | 单次成功调用平均约 `3.087s` |
| movement / environment / status 写盘 | 低到中等 | 每步都有，但通常不是最大头 |
| runner 轮询 `curr_step.json` | 很高 | 由于 `chunk_steps = 1`，天然约 `1s/step` 外层等待 |

## 7. 前端 UI 与 baseline 对比

### 7.1 baseline 机制

baseline 的核心机制是 `step + handshake`：

- 前端发出 `run N`
- 后端推进 step
- 后端写 `curr_step.json`
- 前端再读 movement / environment / status 更新画面

### 7.2 Week7 的改动

Week7 保留了 Django 老前端，但在其上加了：

- Django gateway
- live dashboard
- 更多 runtime sync 诊断信息

关键位置：

- `environment/frontend_server/translator/views.py`
- `environment/frontend_server/templates/home/home.html`
- `environment/frontend_server/templates/home/live_dashboard.html`

### 7.3 当前 UI 已实现功能

- 读取 `sim_status.json` 做 live dashboard
- 读取 `movement/<step>.json` 做地图动作播放
- 读取 `environment/<step>.json` 做位置回传
- 诊断 `status_step / movement_step / environment_step` 是否同步

### 7.4 当前现象与本质原因

当前已知问题：

- 人物移动不连续
- UI 与状态不同步
- 视觉上不是匀速移动

本质原因有两个：

1. 前端仍然参与仿真，因为 `environment/<step>.json` 是前端回传的一部分，不只是纯显示层。
2. `movement/<step>.json` 与 `sim_status.json` 的语义不同步。

更具体地说：

- `sim_status.json` 是状态真相
- `movement/<step>.json` 是动作帧
- `environment/<step>.json` 是位置快照

这三者更新时机不同，就容易出现“状态已经更新，但动作帧还没跟上”或者“动作帧到了，但环境回传滞后”的现象。

## 8. 测试与运行指令

### 8.1 `deep_fast` vs `realism_check`

| 模式 | 含义 | 适合场景 |
| --- | --- | --- |
| `deep_fast` | 本地优先，尽量绕开真实远程 LLM 成本 | 快速回归、长程压测 |
| `realism_check` | 远程 / hybrid，更接近真实 agent 行为 | 做真实性抽样验证 |

### 8.2 `smoke / deep / auto`

| 模式 | 含义 |
| --- | --- |
| `smoke` | 先跑短程健康检查 |
| `deep` | 直接跑长程 |
| `auto` | 先 smoke，再 deep |

### 8.3 常用 PowerShell 命令

```powershell
# 进入 week7_auto
Set-Location D:\projects\BME1325Spring2026\BME1325_Group_One_Repo\week7_auto

# 运行 all-scenario smoke + deep
python scripts\run_week7_long_regression.py --mode auto

# 指定 deep only，并限制步数
python scripts\run_week7_long_regression.py --mode deep --max-chunks 500

# 指定 realism_check
python scripts\run_week7_long_regression.py --mode deep --execution-profile realism_check --max-chunks 500

# 指定 seed
python scripts\run_week7_long_regression.py --mode deep --max-chunks 500 --seed 1337

# 指定 LLM / embedding 模式
python scripts\run_week7_long_regression.py --mode deep --execution-profile realism_check --llm-mode remote_only --embedding-mode hybrid

# 计算分析指标
python analysis\compute_metrics.py

# 跑测试
python -m pytest week7_auto\tests\analysis\test_compute_metrics.py -v
python -m pytest week7_auto\tests\analysis\test_run_week7_long_regression.py -v
python -m pytest week7_auto\tests\frontend\test_views.py -v
```

### 8.4 参数解释

| 参数 | 含义 |
| --- | --- |
| `max_chunks` | deep 模式下跑多少个 chunk；当前 catalog 里 `chunk_steps = 1`，所以基本等于总 step 数 |
| `seed` | 控制可复现实验；会影响 arrival、CTAS 和部分随机链路 |
| `llm_mode` | 是否用本地短路、远程调用或其他 LLM 路径 |
| `embedding_mode` | 控制 embedding 是本地、远程还是 hybrid |

### 8.5 输出文件结构

一次长程回归通常会生成：

| 文件 | 含义 |
| --- | --- |
| `summary.json` | 总结每个 scenario 的 wall clock、采样状态、运行是否成功 |
| `summary.md` | 给人读的 Markdown 摘要 |
| `patient_time_metrics.csv` | 每个患者的阶段时长 |
| `ctas_daily_metrics.csv` | 按 CTAS 聚合后的统计 |
| `resource_event_metrics.json` | 资源与事件类指标，例如 boarding timeout |

## 9. `week7_auto` 目录梳理

### 9.1 核心代码目录

| 路径 | 作用 | 是否必不可少 |
| --- | --- | --- |
| `reverie/backend_server/reverie.py` | 主循环、step 推进、状态写出 | 是 |
| `reverie/backend_server/week7_logic.py` | Week7 arrival / resource 规则 | 是 |
| `reverie/backend_server/persona/` | agent 行为、patient state、LLM prompt 链路 | 是 |
| `environment/frontend_server/translator/views.py` | Django gateway、dashboard API、前后端握手 | 是 |
| `analysis/compute_metrics.py` | 将运行产物转成可汇报指标 | 是 |
| `scripts/run_week7_long_regression.py` | 长程回归实验入口 | 是 |
| `tests/` | 回归与功能验证 | 建议保留 |

### 9.2 重要文档与配置

| 路径 | 作用 |
| --- | --- |
| `week7_handoff.md` | 详细交接文档 |
| `README.md` | 汇报入口文档 |
| `docs/architecture/week7_auto_baseline_analysis.md` | baseline 与 Week7 结构对比 |
| `docs/operations/week7_long_run_regression.md` | 回归实验链路说明 |
| `requirements.txt` | Python 依赖 |
| `pytest.ini` | 测试配置 |
| `docker-compose.yml`, `Dockerfile.*` | 容器运行配置 |

### 9.3 结果文件与运行产物

| 路径 | 类型 | 是否必须提交 |
| --- | --- | --- |
| `analysis/scenario_regressions/<timestamp>/...` | 长程回归结果 | 不一定，按需保留代表性结果 |
| `analysis/resource_event_metrics.json` | 最近一次分析输出 | 不建议当源码提交依据 |
| `0421.mp4` | 演示视频 | 可选 |
| `tmp_video_frames/` | 临时帧 | 否 |
| `environment/frontend_server/storage/<sim>/...` | 仿真存储与回放数据 | 大多属于运行产物，按需保留 |

## 10. 哪些文件必须给组员共享

### 10.1 必须共享

这些文件决定别人能不能真正复现和理解 Week7：

- `week7_auto/README.md`
- `week7_auto/week7_handoff.md`
- `week7_auto/reverie/backend_server/reverie.py`
- `week7_auto/reverie/backend_server/week7_logic.py`
- `week7_auto/reverie/backend_server/persona/persona_types/patient.py`
- `week7_auto/reverie/backend_server/persona/prompt_template/gpt_structure.py`
- `week7_auto/environment/frontend_server/translator/views.py`
- `week7_auto/analysis/compute_metrics.py`
- `week7_auto/scripts/run_week7_long_regression.py`
- `week7_auto/tests/`
- `week7_auto/requirements.txt`

### 10.2 建议共享

- `docs/architecture/week7_auto_baseline_analysis.md`
- `docs/operations/week7_long_run_regression.md`
- `analysis/scenario_regressions/20260420_183847/`
- `0421.mp4`

其中，`analysis/scenario_regressions/20260420_183847/` 是当前最完整的一组 all-scenario 回归结果，包含：

- `arrival_normal`
- `arrival_surge`
- `arrival_burst`
- `bottleneck_imaging`
- `boarding_timeout`
- 顶层与 `deep/` 层的汇总 `summary.json` / `summary.md`

如果后续需要进一步精简仓库，优先保留这组 all-scenario 结果；它比零散单场景结果更适合做汇报、交接和老师追问时的统一证据包。

建议优先共享的代表性场景包括：

- `arrival_normal`
- `arrival_surge`
- `arrival_burst`
- `bottleneck_imaging`
- `boarding_timeout`
- 一个 all-scenario summary

视频 `0421.mp4` 建议一并共享，因为它能补足静态 JSON / CSV 无法直观看到的 UI 表现，例如：

- 人物移动是否连续
- 前后端同步是否稳定
- dashboard 与地图播放是否一致

### 10.3 不建议默认大范围共享

- 所有时间戳回归目录
- 大量 `_temp/` 中间文件
- `tmp_video_frames/`
- 重复的本地实验失败结果

原因是这些文件体积大、重复高，而且会让交接仓库变得很噪。

## 11. 一句话总结

Week7 的价值不在于把 ED 完全真实地复制出来，而在于把三类真实世界里最常见的拥堵来源显式化：

- 入口流量形态变化
- 中段 testing 资源不足
- 出口 boarding 承接失败

它让“系统为什么堵、堵在哪里、压力如何传播”变成了可观测、可实验、可汇报的对象。
