# Part A. baseline vs week7_auto：功能与流程差异

本分析把 baseline 拆成两层来看：

- 后端与真实自动运行主线，以 `EDSim-main` 为准，核心在 `reverie/backend_server/` 与 `environment/frontend_server/`。
- 前端 UI 事实补充，以 `EDSim-threejs` 为准。它没有替换 auto-mode 后端，而是在保留 Django UI 的同时，新增了 `environment/react_frontend/` 与 `run_map_viewer.sh` 这一条 React + Three.js 地图查看链路。

因此，baseline 不是“完全没有 UI 的老版本”，而是“已经有 Django 可视化、命令桥接、单一 diagnostic room 测试流、admission/boarding 状态骨架”的版本；`week7_auto` 则是在这条主线上继续加入 Week7 三条资源现实性规则，并把它们贯穿到 Django gateway、status 输出与 long regression runner。

| 维度 | baseline (`EDSim-main` + `EDSim-threejs`) | week7_auto |
| --- | --- | --- |
| 运行目标 | 跑通一个基础 auto-mode ED simulator，驱动 doctor / triage nurse / bedside nurse / patient 的多智能体流程，并把移动与状态暴露给 Django UI | 在 baseline 上继续做“资源现实性”增强，把 arrival / testing / boarding 规则变成可配置、可回归、可监控的 auto-mode 版本 |
| step 主循环做什么 | 读取环境快照，逐 persona 调 `move()`，做基础队列修复与 patient arrival，写 movement / environment / sim_status | 沿用 baseline 主循环，但在 patient arrival 前插入 arrival profile，在 patient 状态推进里插入 lab/imaging 容量与 TAT，在患者 boarding 上记录 timeout event，并输出更丰富的资源状态 |
| 是否有 arrival profile | 否。只有 `patient_rate_modifier`，到达率按平坦倍率放大，`self.add_patient_threshold += visits_per_hour * patient_rate` | 是。`arrival_profile_mode = normal / surge / burst`，通过 `effective_arrival_rate()` 按小时改写每步到达阈值增量 |
| 是否有 lab/imaging capacity + TAT | 否。测试本质上只有一个 `diagnostic room`，靠 `testing_time` 与 `testing_result_time` 两段通用延迟推进 | 是。`testing_kind_for_ctas()` 把患者分到 `lab` 或 `imaging`，并分别受 `lab_capacity` / `imaging_capacity` 和 `lab_turnaround_minutes` / `imaging_turnaround_minutes` 约束 |
| 是否有 boarding timeout event | 否。虽然有 `ADMITTED_BOARDING` 状态和 hospital admission 流程，但没有 timeout event 指标 | 是。`boarding_timeout_reached()` + `boarding_timeout_recorded` + `boarding_timeout_event` 会在超时后记事件 |
| 是否有 Django auto/user bridge | 部分有。Django 侧有 auto-mode command bridge，`/start_backend`、`/send_sim_command`、`/live_dashboard` 都存在；但没有 week7 的 `/mode/user/*` 与 `/ed/*` user bridge | 有。除了 auto-mode command bridge，还增加 `/mode/user/encounter/start`、`/mode/user/chat/turn`、`/ed/handoff/*`、`/ed/queue/snapshot` 等统一 gateway |
| 是否有 long regression scenario runner | 没有专门的 Week7 场景 runner。只有 `automatic_execution.py` 和 `run_simulation.py` 这类通用自动运行器 | 有。`scripts/run_week7_long_regression.py` 把 arrival / bottleneck / boarding_timeout 场景、采样、分析输出串成完整回归链 |
| 每步主要写哪些状态文件 | `temp_storage/curr_sim_code.json`、`temp_storage/curr_step.json`、`storage/<sim>/movement/<step>.json`、`environment/<step>.json`、`sim_status.txt`、`sim_status.json` | 同 baseline，但 `sim_status.json.resources` 会额外写 arrival profile、lab/imaging in-progress、capacity、turnaround、boarding timeout events；regression 还会把采样与分析结果写到 `analysis/scenario_regressions/*` |
| 主要瓶颈在哪里 | `persona.move()` 驱动的 agent loop、记忆检索/embedding、movement/environment/status I/O、单一 diagnostic flow 的状态推进 | agent loop 仍是主瓶颈；Week7 额外增加 rule checks、资源账本维护、更丰富的 status 输出、gateway 命令轮询、regression 采样与分析链路 |

## A1. baseline 的运行流程

baseline 的核心入口是 `EDSim-main/reverie/backend_server/reverie.py`。真正的“auto mode + 前端 UI”文件链路是：

- auto mode: `run_backend_automatic.sh` -> `automatic_execution.py` -> `reverie.py`
- Django UI: `environment/frontend_server/frontend_server/urls.py` -> `translator/views.py` -> `templates/home/main_script.html`
- headless batch: `run_simulation.py`
- agent 角色实现: `persona_types/patient.py`、`doctor.py`、`triage_nurse.py`、`bedside_nurse.py`
- cognitive 模块: `persona.py`、`cognitive_modules/plan.py`、`converse.py`、`reflect.py`、`perceive.py`、`execute.py`

baseline step:

```text
meta/config read
  -> initialise maze/personas/resources
  -> publish curr_sim_code / curr_step
  -> receive run command
  -> sync environment snapshot
  -> persona cognitive loop
  -> rescue / queue maintenance
  -> write sim_status
  -> baseline patient arrival threshold update or create patient
  -> write movement / environment
  -> advance curr_time and step
  -> publish curr_step
```

### 1. `meta/config read`

代码位置：

- `EDSim-main/reverie/backend_server/reverie.py`
- `EDSim-main/environment/frontend_server/storage/<origin>/reverie/meta.json`

本质在做什么：

- 读取 simulation 的时钟、`sec_per_step`、`patient_rate_modifier`、`testing_time`、`testing_result_time`、角色初始数量、walkout/linger 配置等。
- 初始化 `Maze`，并把全局参数下发给 `Patient`、`Doctor`、`Bedside_Nurse`、`Triage_Nurse` 这些类级静态字段。
- 这里定义了 step 的“物理世界规则”：一轮 step 代表多少 simulated seconds、人物每步能走多少 tile、诊断与出院延迟怎么计算。

### 2. `initialise maze/personas/resources`

代码位置：

- `EDSim-main/reverie/backend_server/reverie.py`
- `EDSim-main/reverie/backend_server/persona/persona.py`

本质在做什么：

- 把 fork 出来的 simulation folder 作为本次运行的工作目录。
- 从 persona bootstrap memory 中恢复每个 agent 的 scratch、memory、tile 位置。
- 初始化 `self.personas`、`self.personas_tile`、`self.maze.triage_queue`、`self.maze.patients_waiting_for_doctor` 等运行期容器。

### 3. `publish curr_sim_code / curr_step`

代码位置：

- `EDSim-main/reverie/backend_server/reverie.py`
- `EDSim-main/environment/frontend_server/translator/views.py`

本质在做什么：

- 向 Django 前端暴露“当前正在跑哪个 simulation、当前 step 到了哪里”。
- `curr_sim_code.json` 让 dashboard 与 replay 页面知道该读哪个 `storage/<sim>`。
- `curr_step.json` 是 auto-mode 与前端同步的最小握手文件。它不是完整世界状态，只是“当前跑到哪一步”的指针。

### 4. `receive run command`

代码位置：

- baseline auto runner: `EDSim-main/reverie/backend_server/automatic_execution.py`
- Django command bridge: `EDSim-main/environment/frontend_server/translator/views.py`
- backend command loop: `EDSim-main/reverie/backend_server/reverie.py`

本质在做什么：

- CLI 模式下，`open_server()` 直接收 `run N` / `fin`。
- Django 模式下，前端调用 `/send_sim_command/`，把 `{"command": "run 10"}` 写到 `temp_storage/commands/cmd_*.json`。
- 后端轮询 command 文件夹，把“推进多少步”变成后端实际执行的 step 数。

### 5. `sync environment snapshot`

代码位置：

- `EDSim-main/reverie/backend_server/reverie.py`
- `EDSim-main/environment/frontend_server/translator/views.py`
- `EDSim-main/environment/frontend_server/templates/home/main_script.html`

本质在做什么：

- UI 模式下，前端先把当前位置与地图状态通过 `/process_environment/` 写入 `environment/<step>.json`。
- 后端读取该 environment snapshot，把前端 tile 位置对齐回 backend 内部的 `personas_tile`。
- headless 模式下，后端直接从当前 tile 状态构造 environment，不依赖浏览器先写文件。

### 6. `persona cognitive loop`

代码位置：

- 统一 cognitive 框架：`EDSim-main/reverie/backend_server/persona/persona.py`
- 具体 ED 角色状态机：`patient.py`、`doctor.py`、`triage_nurse.py`、`bedside_nurse.py`
- 认知子模块：`plan.py`、`converse.py`、`reflect.py`

本质在做什么：

- 对每个 persona 调一次 `persona.move()` 或角色特化后的 `move()`。
- 在通用 `persona.py` 里，链路是 `perceive()` -> `retrieve()` -> `plan()` -> `execute()` -> `reflect()`。
- 在 ED 角色类里，这条通用链路又被套上一层“临床状态机”：
  - `triage_nurse.py` 决定谁先分诊、谁进入哪类 injuries zone。
  - `doctor.py` 决定谁进入初评、谁进入 disposition。
  - `bedside_nurse.py` 负责搬运与 bedside 协调。
  - `patient.py` 维护患者状态，如 `WAITING_FOR_TRIAGE`、`WAITING_FOR_FIRST_ASSESSMENT`、`WAITING_FOR_TEST`、`WAITING_FOR_DOCTOR`、`ADMITTED_BOARDING`。

这一步本质上是在做两层决策：

- 通用 agent cognition：角色看到什么、回忆什么、怎么决定下一动作。
- ED-specific state transition：这个动作在急诊流程里意味着状态推进到哪里。

### 7. `rescue / queue maintenance`

代码位置：

- `EDSim-main/reverie/backend_server/reverie.py`

本质在做什么：

- 在一整轮 `persona.move()` 完成后，统一做患者修复与队列整理，例如 orphaned patient 修复、doctor global queue aging、priority boost、triage timeout 检查等。
- 这一步不是“产生新业务逻辑”，而是保证系统不会因为 agent 决策或人员离场而留下坏状态。

### 8. `write sim_status`

代码位置：

- `EDSim-main/reverie/backend_server/reverie.py`

本质在做什么：

- 把当前世界状态汇总成 `sim_status.txt` 和 `sim_status.json`。
- 这些文件本质上是“对外监控接口”，而不是仿真推进本身。
- 这里会聚合 patient states、zone occupancy、triage queue、doctor queue、护士状态、医生负载等信息，供 dashboard 和 batch 观察脚本读取。

### 9. `baseline patient arrival threshold update or create patient`

代码位置：

- `EDSim-main/reverie/backend_server/reverie.py`

本质在做什么：

- baseline 不是每步都硬塞一个病人，而是维护 `self.add_patient_threshold`。
- 当阈值 `>= 1` 时，创建新 patient，给他抽取 symptom、ICD、CTAS、injuries zone，然后放入 `triage_queue`。
- 当阈值 `< 1` 时，按小时就诊量表 `ed_visits_per_hour.csv` 与固定 `patient_rate_modifier` 继续积累阈值。

关键点：

- baseline 的到达率只有“平坦倍率”，没有按 hour 或 scenario 改写。
- 所以 baseline 的 patient arrival 是“按 base arrival curve 乘一个常数”。

### 10. `write movement / environment`

代码位置：

- `EDSim-main/reverie/backend_server/reverie.py`

本质在做什么：

- 把本轮每个 persona 的 `movement`、`pronunciatio`、`description`、`chat` 写到 `movement/<step>.json`。
- headless 模式会直接把当前 tile 状态写回 `environment/<step>.json`，供 replay 和压缩脚本使用。
- 这一步的本质是“把内部世界状态序列化出来”，让 UI、replay、analysis 可以消费。

### 11. `advance curr_time and step -> publish curr_step`

代码位置：

- `EDSim-main/reverie/backend_server/reverie.py`

本质在做什么：

- `self.step += 1`
- `self.curr_time += timedelta(seconds=self.sec_per_step)`
- 再把新的 `curr_step.json` 写出去

这一步的本质是“提交本轮 step”。前端与回归脚本观察到的 step 前进，都是这一步之后才成立。

## A2. week7_auto 的运行流程

week7 的主循环入口仍然是 `week7_auto/reverie/backend_server/reverie.py`，但 Week7 在两个层面做了增强：

- 在 `ReverieServer.__init__` 中，把 `arrival_profile_mode`、`lab_capacity`、`lab_turnaround_minutes`、`imaging_capacity`、`imaging_turnaround_minutes`、`boarding_timeout_minutes` 等 Week7 参数正式纳入 runtime config。
- 在 `patient.py` 与 `sim_status.json` 中，把“到达、测试、boarding”从一般流程骨架变成显式的资源规则与事件指标。

week7 step:

```text
meta/config read
  -> initialise maze/personas/resources
  -> publish curr_sim_code / curr_step
  -> receive run command
  -> sync environment snapshot
  -> persona cognitive loop
  -> rescue / queue maintenance
  -> write richer sim_status
  -> apply arrival profile / effective_arrival_rate
  -> maybe generate new patient
  -> enforce lab/imaging capacity + turnaround
  -> check boarding timeout event
  -> write movement / environment
  -> advance curr_time and step
  -> publish curr_step
```

### 1. `meta/config read` 增加了 Week7 参数绑定

代码位置：

- `week7_auto/reverie/backend_server/reverie.py`
- `week7_auto/reverie/backend_server/week7_logic.py`

week7 相比 baseline 多出来的字段：

- `arrival_profile_mode`
- `lab_capacity`
- `lab_turnaround_minutes`
- `imaging_capacity`
- `imaging_turnaround_minutes`
- `boarding_timeout_minutes`
- `status_interval_steps`

为什么 baseline 没有：

- baseline 只知道“测试总共要多久”和“结果多久回来”，不知道 test 是 lab 还是 imaging，也不知道两类资源各自的容量约束。
- baseline 也没有 arrival scenario 概念，所以到达率不会按 `hour + scenario` 动态变化。

它解决了什么现实问题：

- 让系统从“通用测试流程”变成“有区分度的资源流转”。
- 让 status 和 regression 能观察到资源瓶颈，而不是只能看到患者最终延迟。

### 2. `write richer sim_status`

代码位置：

- `week7_auto/reverie/backend_server/reverie.py`

week7 相比 baseline 的新增内容：

- `queues.lab_waiting`
- `queues.imaging_waiting`
- `resources.arrival_profile_mode`
- `resources.lab_in_progress`
- `resources.lab_capacity`
- `resources.lab_turnaround_minutes`
- `resources.imaging_in_progress`
- `resources.imaging_capacity`
- `resources.imaging_turnaround_minutes`
- `resources.boarding_timeout_events`
- `resources.boarding_timeout_minutes`

为什么 baseline 没有：

- baseline 的 `sim_status.json` 主要是 general flow 监控，还没有把 Week7 资源约束变成第一类指标。

它解决了什么现实问题：

- 让 dashboard 与 regression 直接读到“资源瓶颈到底发生在 lab、imaging、还是 boarding”，而不必人工回推。

### 3. `apply arrival profile / effective_arrival_rate`

代码位置：

- `week7_auto/reverie/backend_server/week7_logic.py`
- `week7_auto/reverie/backend_server/reverie.py`

真实逻辑：

- `arrival_profile_multiplier(mode, hour)` 定义 profile 对到达率的乘子。
- `effective_arrival_rate(base_rate, mode, hour)` 返回 `base_rate * multiplier`。
- 在 step 主循环的 patient generation 分支里，week7 用 `effective_arrival_rate()` 替代 baseline 的固定 `self.patient_rate`。

为什么 baseline 没有：

- baseline 只有“平坦调倍率”的 `patient_rate_modifier`。

它解决了什么现实问题：

- 急诊到达流量不是恒定的。`surge` 和 `burst` 把“不同小时的不同入院压力”显式建模出来。

### 4. `maybe generate new patient`

代码位置：

- `week7_auto/reverie/backend_server/reverie.py`

这一节点本身 baseline 也有，但 week7 改了“生成阈值积累公式”：

- baseline: 用 `visits_per_hour * patient_rate_modifier`
- week7: 用 `visits_per_hour * effective_arrival_rate(patient_rate_modifier, arrival_profile_mode, hour)`

因此同样是 `add_patient_threshold` 机制，week7 的阈值增长速度会被 scenario 和时段放大或缩小。

### 5. `enforce lab/imaging capacity + turnaround`

代码位置：

- `week7_auto/reverie/backend_server/persona/persona_types/patient.py`
- `week7_auto/reverie/backend_server/week7_logic.py`

week7 相比 baseline 多出来的环节：

- `testing_kind_for_ctas()` 把 `CTAS <= 2` 分配到 `imaging`，把其余分配到 `lab`。
- `WAITING_FOR_TEST` 不再统一进入一个 generic diagnostic flow，而是分两条路：
  - lab path: 如果 `len(maze.lab_patients) < lab_capacity`，直接占用 lab slot，进入 `WAITING_FOR_RESULT`，并把 `testing_end_time = curr_time + lab_turnaround_minutes`
  - imaging path: 如果 diagnostic room / imaging slot 可用，进入 `GOING_FOR_TEST`，并把 `testing_end_time = curr_time + imaging_turnaround_minutes`
- 测试结束后，week7 还会显式释放 `lab_patients` 或 `imaging_patients/current_patients` 资源账本

为什么 baseline 没有：

- baseline 的 `patient.py` 只有一个 diagnostic room 容量，测试计时用 `testing_time` / `testing_result_time` 两个通用时长。

它解决了什么现实问题：

- 现实中 lab 和 imaging 不是同一类资源，也不是同样的 TAT。
- 这样才能在回归中看见 `imaging_waiting`、`lab_waiting`、`imaging_in_progress` 这类资源信号。

### 6. `check boarding timeout event`

代码位置：

- `week7_auto/reverie/backend_server/week7_logic.py`
- `week7_auto/reverie/backend_server/persona/persona_types/patient.py`

week7 多出来的逻辑：

- 在 `patient.move()` 一开始，如果患者状态是 `ADMITTED_BOARDING`，且 `boarding_timeout_recorded` 还没置位，就调用 `boarding_timeout_reached(admission_boarding_start, curr_time, boarding_timeout_minutes)`。
- 一旦超时，设置：
  - `boarding_timeout_recorded = True`
  - `boarding_timeout_at = curr_time`
  - `data_collection["boarding_timeout_event"] = {...}`

为什么 baseline 没有：

- baseline 有 boarding 状态，但没有“超时事件”这一层 instrumentation。

它解决了什么现实问题：

- 真实 ED 里 boarding delay 是一个单独运营问题。Week7 不是只关心“病人最终是否离开”，还关心“是否已经形成 boarding timeout”。

### 7. `Django gateway` 也比 baseline 更统一

代码位置：

- `week7_auto/environment/frontend_server/frontend_server/urls.py`
- `week7_auto/environment/frontend_server/translator/views.py`
- `week7_auto/environment/frontend_server/templates/home/start_simulation.html`

week7 相比 baseline 多出来的点：

- `start_simulation.html` 直接暴露了 `Arrival Profile`、`Lab Capacity`、`Lab Turnaround`、`Imaging Capacity`、`Imaging Turnaround`、`Boarding Timeout Event` 等输入控件。
- URL 层新增 `/mode/user/*`、`/ed/handoff/*`、`/ed/queue/snapshot`，把 auto mode 和 user mode 放到一个 Django host 下。

为什么 baseline 没有：

- baseline Django 前端主要服务 auto-mode 可视化与 command bridge。

它解决了什么现实问题：

- Week7 不只是“后端多几个 if 分支”，而是把这些规则正式接入可配置网关，方便课程演示、场景切换和统一入口管理。

## A3. baseline 与 week7_auto 的本质差异

### baseline 是什么

baseline 本质上是一个基础 auto-mode hospital simulator：

- 主体是 `reverie.py` 驱动的多智能体循环。
- 每步通过 `persona.move()` 让 doctor / nurse / patient 在 ED 流程里推进。
- Django 前端通过 `process_environment` / `update_environment` / `send_sim_command` 观察与控制仿真。
- 患者测试流仍然是“单一 diagnostic room capacity + `testing_time/testing_result_time`”。

### week7_auto 是什么

week7_auto 本质上是 baseline 上的“资源现实性 + 统一 Django gateway”版本：

- arrival 侧：把 patient arrival 从固定倍率变成 `hour + profile` 驱动的到达率。
- testing 侧：把 generic test flow 拆成 lab / imaging 两类资源流，并引入容量与 TAT。
- boarding 侧：把 `ADMITTED_BOARDING` 从普通状态变成可记录 timeout event 的运营指标。
- gateway 侧：把这些参数暴露给 Django 设置面板与 long regression runner。

### 为什么 week7 会更慢

核心结论：

- 大 O 没有质变，主要是每步常数项和调用链长度变大。
- 真正最重的部分仍然是 agent loop，而不是 Week7 规则本身。

可以把 step 成本写成：

- baseline step cost ≈ `persona.move()` loop + basic queue maintenance + movement/environment/status I/O
- week7 step cost ≈ baseline + arrival profile calculation + lab/imaging resource bookkeeping + timeout event bookkeeping + richer JSON/status logging + regression sampling

更具体地说：

- 两个版本都要对 active personas 逐个调用 `move()`，所以主循环仍然近似是对活跃 agent / patient 的线性扫描。
- `_write_sim_status()` 在两边都要扫描患者与资源；week7 只是额外统计了 `lab_waiting`、`imaging_waiting`、`boarding_timeout_events` 等字段。
- Week7 没有引入一个新的“患者两两比较”的二次复杂度算法，也没有把主循环改成更高阶的全局优化过程。
- 变慢的根源主要是：
  - 每个 patient 在 `WAITING_FOR_TEST` / `GOING_FOR_TEST` / `ADMITTED_BOARDING` 上多了分支判断
  - `sim_status.json` 更大、字段更多
  - Django / regression 读取的状态面更广
  - runtime log 更丰富

### 真实 step 时间证据

本仓库里可直接引用的 step 级 wall-clock 证据来自：

- `week7_auto/analysis/scenario_regressions/20260417_223558/arrival_burst/runtime.log`
- `week7_auto/analysis/scenario_regressions/20260417_223558/boarding_timeout/runtime.log`

已观测到的真实 step-1 耗时：

| 场景 | 运行日志证据 | 观测到的 step | 观测到的 step 耗时 |
| --- | --- | --- | --- |
| `arrival_burst` | runtime log 中 `step cycle done` | 第 1 步 | 约 `69.632s` |
| `boarding_timeout` | runtime log 中 `step cycle done` | 第 1 步 | 约 `73.970s` |

对应的结果分析：

- `arrival_burst`
  - runtime log 同时记录了 `effective_arrival_rate = 8.8`，因为 `patient_rate_modifier = 4.0`，而 `burst` 在 `07:00` 的乘子是 `2.2`。
  - 但 `summary.json` 显示该场景在 step 2 前 timeout，稳定证据只覆盖了 step 1。
  - 因此可以说“burst profile 已被正确应用”，但不能把后续 steady-state patient growth 说成已在这轮回归中完整观察到。
- `boarding_timeout`
  - runtime log 在 step 1 期间记录了 `boarding timeout event recorded`。
  - `summary.json` 里 `resources.boarding_timeout_events = 1`，且 `patient_states` 仍然保留 `ADMITTED_BOARDING = 1`。
  - 这说明 timeout event 的记录逻辑是生效的，而且它不会自动把患者移出系统。

还要特别澄清一个常见误读：

- `summary.json` 里的 `wall_clock_seconds ≈ 971 ~ 978s` 不是“单步时间”，而是 regression runner 在 step 2 迟迟未完成后整个场景的总等待时间。
- 能代表“单步到底算了多久”的，是 runtime log 里的 `step cycle done elapsed=...s`。

综合来看，week7 变慢更多是“agent loop 仍然很重，Week7 规则又把每步的状态判断和 I/O 变厚了”，而不是某条 Week7 规则单独从算法阶数上把系统拖慢。

# Part B. Week7 三条规则：代码级解释

## B1. arrival profile

### what

arrival profile 是一层“按场景和小时动态调整 patient arrival rate”的规则。

核心枚举值：

- `arrival_profile_mode = normal`
- `arrival_profile_mode = surge`
- `arrival_profile_mode = burst`

核心函数：

- `arrival_profile_multiplier(mode, hour)`
- `effective_arrival_rate(base_rate, mode, hour)`

### why

它解决的问题是：急诊到达流量不是一个恒定常数。

- baseline 只有 `patient_rate_modifier`，最多表达“整体高一点或低一点”。
- Week7 要表达“某些小时 surge，某些小时 burst”，所以必须把 arrival logic 从静态常数升级成动态 profile。

### where

代码落点：

- `week7_auto/reverie/backend_server/week7_logic.py`
  - `arrival_profile_multiplier()`
  - `effective_arrival_rate()`
- `week7_auto/reverie/backend_server/reverie.py`
  - 读取 `arrival_profile_mode`
  - 在 step 主循环里调用 `effective_arrival_rate()`
- `week7_auto/environment/frontend_server/templates/home/start_simulation.html`
  - 提供 `Arrival Profile` 选择框
- `week7_auto/environment/frontend_server/translator/views.py`
  - `save_simulation_settings()` 把 `arrival_profile_mode` 写回 `meta.json`
- `week7_auto/scripts/run_week7_long_regression.py`
  - `scenario_catalog()` 为 `arrival_normal`、`arrival_surge`、`arrival_burst` 写入不同 profile

### how

step 运行时的触发方式：

1. `reverie.py` 在初始化时读取 `arrival_profile_mode`
2. step 主循环来到 patient arrival 阶段
3. 如果 `add_patient_threshold >= 1`，就直接创建新 patient
4. 否则计算：

```text
arrival_rate = effective_arrival_rate(patient_rate_modifier, arrival_profile_mode, curr_time.hour)
add_patient_threshold += visits_per_hour[hour] / steps_per_hour * arrival_rate
```

以现有 regression 证据为例：

- `arrival_burst` 场景中，`patient_rate_modifier = 4.0`
- 当前 hour = `07:00`
- `burst` 在 7-9 点的 multiplier = `2.2`
- 所以 `effective_arrival_rate = 4.0 * 2.2 = 8.8`

简化状态图：

```text
hour + profile
  -> arrival_profile_multiplier(mode, hour)
  -> effective_arrival_rate(base_rate, mode, hour)
  -> add_patient_threshold accumulation
  -> if threshold >= 1: new patient creation
```

### effect

它对系统行为的影响是：

- `effective_arrival_rate` 越高，`add_patient_threshold` 越快跨过 1
- 新病人生成越快，`total_patients`、`current_patients`、`triage queue` 越容易上升
- 它不是直接把病人“塞进系统”，而是通过 threshold accumulation 改写“每步新增病人的概率/频率”

因此 arrival profile 的本质是：

- 它作用在“新病人进入系统的速率”
- 不直接改 patient state machine
- 但会通过更高的输入压力间接放大所有下游队列

## B2. lab / imaging capacity + TAT

### what

这一条规则把 baseline 的“单一 diagnostic room 测试流”拆成了两种资源通道：

- `lab`
- `imaging`

并为两者分别配置：

- `lab_capacity`
- `imaging_capacity`
- `lab_turnaround_minutes`
- `imaging_turnaround_minutes`

同时，患者的 test 类型由：

- `testing_kind_for_ctas(ctas_score)`

决定。当前实现是：

- `CTAS <= 2` -> `imaging`
- 其余 -> `lab`

### why

它解决的问题是：现实里检查不是“瞬时完成的统一动作”。

- lab 和 imaging 占用的是不同资源
- 二者容量不同
- turnaround time 不同
- 当 capacity 满时，会形成 waiting queue 和 bottleneck

baseline 只有：

- 一个 `diagnostic room`
- 一个通用 `testing_time`
- 一个通用 `testing_result_time`

这对 Week7 想表达的“检查资源现实性”还不够。

### where

代码落点：

- `week7_auto/reverie/backend_server/week7_logic.py`
  - `testing_kind_for_ctas()`
- `week7_auto/reverie/backend_server/reverie.py`
  - 初始化 `lab_capacity`、`imaging_capacity`
  - 初始化 `lab_turnaround_minutes`、`imaging_turnaround_minutes`
  - 把这些参数下发给 `Patient` 和 `Maze`
  - 在 `sim_status.json` 中输出 `lab_waiting`、`imaging_waiting`、`lab_in_progress`、`imaging_in_progress`
- `week7_auto/reverie/backend_server/persona/persona_types/patient.py`
  - `WAITING_FOR_TEST`
  - `GOING_FOR_TEST`
  - `WAITING_FOR_RESULT`
  - `testing_kind`
  - `testing_end_time`
- `week7_auto/scripts/run_week7_long_regression.py`
  - `bottleneck_imaging` 场景设定 `imaging_capacity = 1`、`imaging_turnaround_minutes = 120`

### how

step 运行时的触发方式分三段：

1. 患者在 first assessment 后被决定是否需要 test

- `do_first_assessment()` 里按 `testing_probability_by_ctas` 决定是否进入 `WAITING_FOR_TEST`
- 一旦需要 test，就先用 `testing_kind_for_ctas()` 设定 `testing_kind`

2. `WAITING_FOR_TEST` 根据 test 类型走不同资源通道

- lab path:
  - 如果 `len(maze.lab_patients) < lab_capacity`
  - 占用一个 lab slot
  - 直接进入 `WAITING_FOR_RESULT`
  - `testing_end_time = curr_time + lab_turnaround_minutes`
- imaging path:
  - 如果 `diagnostic room` / `imaging_patients` 有空位
  - 占用 imaging slot
  - 进入 `GOING_FOR_TEST`
  - `testing_end_time = curr_time + imaging_turnaround_minutes`

3. `testing_end_time` 到达后释放资源并回到后续流程

- imaging 完成后：
  - 释放 `imaging_patients` 与 diagnostic room occupancy
  - 返回 bed
  - 进入 `WAITING_FOR_RESULT`
- lab 完成的逻辑更像“在后台完成”，当结果 ready 时释放 lab 资源，再等待 doctor/disposition

简化状态机：

```text
WAITING_FOR_TEST
  -> assign testing_kind (lab/imaging)
  -> if lab and slot available:
       occupy lab slot
       set testing_end_time
       -> WAITING_FOR_RESULT
  -> if imaging and slot available:
       occupy imaging slot
       set testing_end_time
       -> GOING_FOR_TEST
  -> else:
       remain WAITING_FOR_TEST (queue grows)

GOING_FOR_TEST
  -> if current_time >= testing_end_time:
       release imaging resource
       return to bed
       -> WAITING_FOR_RESULT
```

### effect

它对系统行为的影响有三层：

1. 资源占用不再是瞬时动作

- `turnaround_minutes` 把检查变成“跨多个 step 占用资源”的过程

2. capacity 会制造 waiting queue

- 当 `lab_capacity` 或 `imaging_capacity` 不足时，患者会停留在 `WAITING_FOR_TEST`
- `_write_sim_status()` 会把这些患者分别统计到 `lab_waiting` 或 `imaging_waiting`

3. bottleneck 会反向放大 doctor queue 与整体滞留

- 在 `bottleneck_imaging` 回归场景中，`summary.json` 已经能观察到：
  - `imaging_capacity = 1`
  - `imaging_waiting = 2`
  - `doctor_global_queue = 2`

这说明 week7 已经把“检查资源不足导致后续临床推进堵住”显式建模出来了。

## B3. boarding timeout

### what

boarding timeout 规则是：

- 当患者已被 disposition 为 admitted
- 并进入 `ADMITTED_BOARDING`
- 如果从 `admission_boarding_start` 起已经超过 `boarding_timeout_minutes`
- 就记录一个 timeout event

这里的 timeout 是“事件指标”，不是自动移除患者的动作。

### why

它解决的问题是：现实里 boarding patient 会长期占床，运营上关心的不是只有“最后离没离开”，还关心“是否已经超出可接受 boarding 时间”。

因此 Week7 需要一个独立的 boarding timeout 指标。

### where

代码落点：

- `week7_auto/reverie/backend_server/reverie.py`
  - 初始化 `simulate_hospital_admission`
  - 初始化 `boarding_timeout_minutes`
  - 在 `sim_status.json.resources` 输出 `boarding_timeout_events`
- `week7_auto/reverie/backend_server/week7_logic.py`
  - `boarding_timeout_reached()`
- `week7_auto/reverie/backend_server/persona/persona_types/patient.py`
  - `do_disposition()` 把 admitted patient 送进 `ADMITTED_BOARDING`
  - `move()` 在 boarding 态下检查 timeout，并写 `boarding_timeout_event`
- `week7_auto/scripts/run_week7_long_regression.py`
  - `seed_boarding_timeout()` 预置一个已经在 `ADMITTED_BOARDING` 的 patient
  - `boarding_timeout` 场景把 `boarding_timeout_minutes` 设为 5

### how

运行时触发顺序：

1. `do_disposition()` 判定该患者需要 hospital admission
2. 写入：
  - `admitted_to_hospital = True`
  - `admission_boarding_start = curr_time`
  - `admission_boarding_end = curr_time + random(boarding_minutes)`
  - `state = ADMITTED_BOARDING`
  - `boarding_timeout_recorded = False`
3. 后续每次 `patient.move()`，只要患者仍在 `ADMITTED_BOARDING`，就检查：

```text
boarding_timeout_reached(
  admission_boarding_start,
  curr_time,
  boarding_timeout_minutes
)
```

4. 一旦超时，记录：
  - `boarding_timeout_recorded = True`
  - `boarding_timeout_at = curr_time`
  - `data_collection["boarding_timeout_event"] = {...}`

状态图：

```text
WAITING_FOR_DOCTOR
  -> do_disposition()
  -> ADMITTED_BOARDING
  -> if boarding duration > timeout threshold:
       record timeout event
       stay ADMITTED_BOARDING
  -> if current_time >= admission_boarding_end:
       -> LEAVING
```

### effect

它对系统行为的影响是：

- 会增加 `boarding_timeout_events` 这个独立运营指标
- 不会在 timeout 发生时自动移除 patient
- 患者仍然继续占系统资源，直到 `admission_boarding_end` 才会离开

这点已经被现有 regression 证据直接验证：

- `boarding_timeout` 场景的 `summary.json` 显示：
  - `patient_states.ADMITTED_BOARDING = 1`
  - `resources.boarding_timeout_events = 1`

也就是说，timeout event 已经被记录，但 patient 仍留在系统里继续推进。这正是“只记录事件，不自动移除患者”的 Week7 设计。

# Part C. 关键代码位置与建议阅读顺序

下面的顺序适合第一次读代码时建立整体心智模型。建议先读 baseline 的 `reverie.py` 主骨架，再带着这个骨架去看 week7 的增量点。

1. `reverie.py`
   最重要看什么：`ReverieServer.__init__()`、`open_server()`、step 主循环、`_write_sim_status()`、patient arrival threshold。
   它在系统中的角色是什么：整个模拟的总调度器，负责把 meta、persona、environment、movement、status、command bridge 串成一条可运行主链。

2. `week7_logic.py`
   最重要看什么：`arrival_profile_multiplier()`、`effective_arrival_rate()`、`testing_kind_for_ctas()`、`boarding_timeout_reached()`。
   它在系统中的角色是什么：Week7 三条资源现实性规则的最小纯函数层，把“规则”从主循环里抽出来。

3. `patient.py`
   最重要看什么：`move()`、`do_first_assessment()`、`do_disposition()`，以及 `WAITING_FOR_TEST` / `GOING_FOR_TEST` / `WAITING_FOR_RESULT` / `ADMITTED_BOARDING` 的迁移分支。
   它在系统中的角色是什么：患者状态机的真正落地点，也是 Week7 三条规则最直接生效的文件。

4. `doctor.py` / `bedside_nurse.py` / `triage_nurse.py`
   最重要看什么：谁把患者拉进 queue、谁把患者从 queue 取走、谁负责 first assessment、谁触发 disposition、谁负责 bed/room 转运。
   它们在系统中的角色是什么：把 patient state machine 连接到临床角色分工上，决定患者何时被谁处理。

5. `plan.py` / `converse.py` / `reflect.py`
   最重要看什么：`plan()` 如何生成行动地址，`converse.py` 如何生成对话，`reflect.py` 如何把经历写回记忆。
   它们在系统中的角色是什么：提供 generative agents 的认知层，让 ED 角色不是死板规则机，而是“有记忆、有检索、有计划”的 agent。

6. `Django gateway / views.py / send_sim_command / live_dashboard`
   最重要看什么：`send_sim_command()` 如何把前端命令落成 `temp_storage/commands/*.json`，`live_dashboard_api()` 如何读取 `sim_status.json`，`save_simulation_settings()` 如何把 Week7 参数写回 `meta.json`。
   它在系统中的角色是什么：前后端握手层，也是 auto mode 和 user mode 的统一入口。

7. `run_week7_long_regression.py`
   最重要看什么：`scenario_catalog()`、`seed_imaging_bottleneck()`、`seed_boarding_timeout()`、`sample_status()`、`summarise_samples()`。
   它在系统中的角色是什么：把 Week7 规则配置、运行、采样、分析串成可重复的 long regression 场景。

8. `analysis/compute_metrics.py`
   最重要看什么：`ensure_compressed()`、`load_inputs()`、`find_pia_step()`、`find_disposition_step()`，以及输出 `patient_time_metrics.csv`、`ctas_daily_metrics.csv`、`resource_event_metrics.json` 的逻辑。
   它在系统中的角色是什么：把 movement/data_collection/meta 变成汇报与运营分析可用的表格和资源指标。

---

## 补充结论

如果要把一句话讲清楚 baseline 与 week7_auto 的差异，可以这样说：

- baseline 是“能跑起来、能看见、能回放”的基础多智能体急诊仿真系统。
- week7_auto 是“把 arrival、testing、boarding 三个现实运营问题正式参数化、指标化、回归化”的版本。

如果要把一句话讲清楚 week7 为什么更慢，可以这样说：

- 它不是算法阶数突然变高了，而是每一步在 baseline 的 agent loop 上叠加了更多规则判断、更多资源账本、更多状态输出和更多回归观察链路。
