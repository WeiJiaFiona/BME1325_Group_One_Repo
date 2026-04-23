# Week7 长场景稳定性改造优先级计划

## Summary
目标是把 `week7_auto` 从“能跑通少量 step”推进到“默认稳定跑 `run 100`，并为 `run 1000 / 10000` 做结构准备”。本文件不是泛泛的想法清单，而是面向后续工程实施的优先级方案，覆盖：

- 优先级排序
- 每一项为什么排在这个位置
- 具体修改点与建议接口
- 验证标准
- 当前代码入口

基于现有代码与 runtime 证据，优先级按“可行性从高到低”排序如下：

1. `7-step smoke + 单场景 deep run` 回归拆分与硬门禁
2. `embedding fallback` 缓存与远程健康短路
3. `对话触发从 step-level 改 event-level` 的保守收敛改造

排序依据：

- 第 1 项主要集中在 `week7_auto/scripts/run_week7_long_regression.py` 和命令入口，局部改动、收益直接、风险最低。
- 第 2 项主要集中在 `week7_auto/reverie/backend_server/persona/prompt_template/gpt_structure.py` 的 embedding 热路径，改动边界清晰，能直接减少首步长时间卡顿。
- 第 3 项最能决定长期吞吐，但横跨 `plan.py`、角色 `move()`、scratch 状态和对话副作用，必须保守落地。

## 现状证据
当前代码和运行证据说明，长场景成本主要不是 Week7 三条规则本身，而是 LLM / embedding 热路径叠加在 step 主循环里：

- `week7_auto/analysis/scenario_regressions/20260417_223558/arrival_burst/runtime.log`
  - 第 1 步约 `69.632s`
  - 同步出现多次 `get_embedding failed after retries, switching to local embeddings`
- `week7_auto/analysis/scenario_regressions/20260417_223558/boarding_timeout/runtime.log`
  - 第 1 步约 `73.970s`
  - boarding timeout 事件已经在 step 内记录成功，但整步依旧被 embedding / cognition 拉长
- `week7_auto/analysis/scenario_regressions/20260418_154325/arrival_burst/runtime.log`
  - step 1 约 `171.241s`
  - step 2 约 `32.900s`
  - step 3 约 `5.720s`
  - step 4 约 `17.548s`
  - step 5 约 `0.021s`
  - step 6 约 `24.809s`
  - step 7 约 `0.033s`

这说明：

- 系统不是“每一步都一样慢”，而是会在某些 LLM/embedding 密集步显著抖动。
- 当前最值得优先处理的是“如何更早发现不稳定版本”和“如何减少重复远程 embedding 尝试”。
- 对话事件化是长期收益最大的方向，但不应先于 smoke gate 和 embedding 短路实施。

## P1. 回归流程先改成 `smoke first`

### 目标
把现在“直接长跑、失败后再看日志”的方式改成“两阶段回归”：

- `smoke`：固定 7 step，快速验证是否能持续推进
- `deep`：单场景长跑
- `auto`：默认先跑 `smoke`，通过后才允许进入 `deep`

### 当前代码入口

- `week7_auto/scripts/run_week7_long_regression.py`
  - `scenario_catalog()`
  - `parse_args()`
  - `expand_selection()`
  - `run_single_scenario()`
  - `main()`

当前这个脚本已经具备：

- 按场景分组执行的基础
- `--scenario`
- `--max-chunks`
- scenario-specific seed
- runtime log / summary 输出

因此它非常适合先承接 smoke-first 改造。

### 修改说明

#### 1. 运行模式拆分
在 `run_week7_long_regression.py` 中新增运行模式：

- `--mode smoke`
  - 固定跑短场景验证
- `--mode deep`
  - 只跑选定场景的长跑
- `--mode auto`
  - 默认模式，先 smoke 再 deep

建议默认值：

- `--mode auto`

#### 2. smoke 硬门禁
默认行为改成脚本硬门禁：

- `auto` 或默认命令先跑 7-step smoke
- smoke 任一场景未达到目标 step、出现进程异常、状态文件异常、卡死超时，则直接返回非零码
- 只有 smoke 通过，才进入 deep run

这里的“通过”要落成明确判定条件，而不是人工看日志：

- 后端进程正常退出或保持存活到该 chunk 完成
- `curr_step` 达到预期目标
- `runtime.log` 中没有明显异常中止
- `sim_status.json` 成功写出

#### 3. 场景选择解耦
场景选择拆开，不再把 `arrival / bottleneck / boarding` 绑死：

- `arrival` 组只跑 `arrival_normal / arrival_surge / arrival_burst`
- `bottleneck` 组只跑 `bottleneck_imaging`
- `boarding_timeout` 单独跑

这部分当前脚本已经基本具备，只需要在 `smoke/deep/auto` 逻辑里显式复用。

#### 4. CLI 变化
建议新增：

- `--mode smoke|deep|auto`
- `--smoke-steps`
  - 默认 `7`
- `--skip-smoke`
  - 仅对显式 `deep` 调用开放

#### 5. 输出行为
建议在 `summary.json` / `summary.md` 增加：

- `run_mode`
- `smoke_passed`
- `smoke_failed_reason`
- `deep_started`
- `deep_completed`

### 为什么它优先级最高

- 基本不碰临床状态机，不改变业务行为。
- 可以最快把“明显不稳定的版本”挡在 deep run 之前。
- 对 nightly / 手工验证都立即有帮助。
- 即使 P2/P3 还没做完，也能先改善研发反馈回路。

## P2. embedding fallback 改成“缓存 + 健康短路”，但保留混合模式

### 目标
保持现在“远程优先、失败 fallback 到本地”的主思路，但减少无意义重试和重复计算。

### 当前代码入口

- `week7_auto/reverie/backend_server/persona/prompt_template/gpt_structure.py`
  - `get_embedding(...)`
  - `_deterministic_local_embedding(...)`
  - `_RETRY_DELAYS`
  - `_FORCE_LOCAL_EMBEDDINGS`
- 触发热点：
  - `week7_auto/reverie/backend_server/persona/cognitive_modules/perceive.py`
  - `week7_auto/reverie/backend_server/persona/cognitive_modules/retrieve.py`
  - `week7_auto/reverie/backend_server/persona/cognitive_modules/reflect.py`
  - `week7_auto/reverie/backend_server/persona/cognitive_modules/converse.py`
  - `week7_auto/reverie/backend_server/persona/cognitive_modules/plan.py`

### 修改说明

#### 1. 增加文本级 embedding cache
在 `gpt_structure.py` 增加 embedding cache：

- key 使用归一化后的文本
  - 去掉换行
  - 统一空白
- 命中后直接返回
- 不再重复请求远程或重复计算本地哈希 embedding

重点覆盖：

- 高频状态描述
- 重复 prompt 片段
- 重复 memory/event 描述

#### 2. 增加远程健康状态短路
在 embedding 层增加远程健康状态：

- 记录最近连续 embedding 失败次数
- 记录最近失败时间
- 当连续失败达到阈值后，未来 N 分钟直接走本地 embedding
- 冷却结束后再允许一次远程探测

建议新增配置字段：

- `embedding_remote_failure_threshold`
- `embedding_remote_cooldown_minutes`
- `embedding_cache_enabled`
- `embedding_cache_max_entries`

#### 3. 明确 embedding 模式
把 fallback 从“只能失败后切换”改成显式配置：

- `embedding_mode = hybrid | remote_only | local_only`

默认值：

- `hybrid`

第一版原则：

- 全局默认不改成本地
- smoke/deep 脚本只在显式参数下切 `local_only`
- 不改变普通交互 / 普通运行的默认模式

### 为什么它排第二

- 改动集中，热路径明确。
- 不改变患者状态机，只优化基础设施成本。
- 现有日志已经明确表明它是长步耗时的重要来源之一。

### 第一版边界

- 不做跨进程持久化 cache，先做进程内 cache。
- 不碰 chat completion 策略，只处理 embedding。
- 不把所有 auto mode 默认切到 local，只提供配置能力。

## P3. 对话触发从 step-level 收敛到 event-level，采用“保守收敛”

### 目标
不是“尽量不聊天”，而是“只有值得触发新决策 / 新信息 / 新交接时才聊天”。

### 当前代码入口

- `week7_auto/reverie/backend_server/persona/cognitive_modules/plan.py`
  - `_should_react(...)`
  - `_chat_react(...)`
  - `_wait_react(...)`
- `week7_auto/reverie/backend_server/persona/persona.py`
  - `move(...)`
  - `_should_skip_cognition(...)`
- 角色逻辑：
  - `week7_auto/reverie/backend_server/persona/persona_types/patient.py`
  - `week7_auto/reverie/backend_server/persona/persona_types/triage_nurse.py`
  - `week7_auto/reverie/backend_server/persona/persona_types/bedside_nurse.py`
  - `week7_auto/reverie/backend_server/persona/persona_types/doctor.py`
- scratch：
  - `week7_auto/reverie/backend_server/persona/memory_structures/scratch_types/patient_scratch.py`
  - `doctor_scratch.py`
  - `bedside_nurse_scratch.py`
  - `triage_nurse_scratch.py`

### 关键观察
现有系统已经不是“所有推进都依赖对话”：

- triage nurse 已经把 patient 入 doctor queue 的推进放在规则分支里。
- doctor 已经把 `do_initial_assessment()` / `do_disposition()` 提前到规则分支。
- bedside nurse 已经把部分转运和状态切换改成 deterministic transition。

所以第一版最合理的方向不是重写整个对话系统，而是把等待态的重复触发进一步裁掉。

### 第一版关键事件定义

#### `TRIAGE_FIRST_CONTACT`
- 患者从 `WAITING_FOR_TRIAGE` 进入 `TRIAGE`
- 首次与 triage nurse 建立接触

#### `BEDSIDE_FIRST_CONTACT`
- 患者从 `WAITING_FOR_NURSE` 被 bedside nurse 首次接走
- 或首次形成床旁接触

#### `DOCTOR_FIRST_ASSESS`
- 患者首次进入 `WAITING_FOR_FIRST_ASSESSMENT` 后
- 被 doctor 首次正式评估

#### `TEST_ORDERED`
- doctor 决定进入检查流
- 患者被赋值 `testing_kind`

#### `TEST_RESULT_READY`
- `WAITING_FOR_RESULT` 到达结果时间点
- doctor 需要基于新信息做下一步决策

#### `DISPOSITION_CHANGED`
- 处置从继续观察切到 discharge / admission / boarding

#### `HANDOFF_OCCURRED`
- 责任方变化
- 例如 triage 完成后进入 doctor queue，或 doctor 指令交给 bedside nurse 执行

### 第一版明确改成纯规则推进的等待态

- `WAITING_FOR_TRIAGE`
- `WAITING_FOR_NURSE`
- `WAITING_FOR_TEST`
- `WAITING_FOR_RESULT`

这些状态在大多数 step 里不再触发 LLM，只判断：

- 是否轮到自己
- 是否有资源空位
- 是否到达 `time_to_next` / `*_ready_at`
- 是否发生 state / owner / result 变化

### scratch 统一字段
建议补充以下字段，并统一在 patient 相关 scratch 中维护：

- `last_conversation_step`
- `conversation_cooldown_steps`
- `last_conversation_event`
- `last_handoff_step`
- `last_result_notified_at`

### 触发策略

- 同一患者-同一事件只允许触发一次，除非发生新的 clinical event
- 同一患者在 cooldown 内，即使相邻 step 反复相遇，也不重新开对话
- 若只是继续等待、继续行走、继续排队，不触发对话

### 副作用处理原则

- 现有 doctor / triage / bedside 的关键状态推进，已经有不少是“先规则推进、聊天只做 flavor”
- 第一版继续沿这个方向，把“状态推进必须依赖 `react_to_chat()` 才能发生”的地方统一搬到显式规则分支
- 对话仅保留信息表达和记忆写入，不再作为等待态推进的门

### 为什么它排第三

- 这是长期收益最大的方向，但改动面最广。
- 一旦收敛过猛，可能会漏掉必要沟通，影响临床流程可解释性。
- 第一版必须保守：只砍掉重复等待态，不砍掉首次 triage、首次 assess、结果返回、处置变化这些必要沟通。

## Test Plan

### 回归脚本验证

- `--mode smoke` 默认 7 step，分别验证：
  - `arrival`
  - `bottleneck`
  - `boarding_timeout`
- `--mode auto` 必须先 smoke 成功，再进入 deep
- smoke 失败时返回非零码，且不进入 deep

### embedding 验证

- 构造连续远程失败场景，确认达到阈值后进入 cooldown，后续直接本地
- 对重复文本调用 embedding，确认 cache 命中，远程调用次数显著下降
- 保证 `hybrid`、`local_only`、`remote_only` 三种模式行为可预测

### 对话收敛验证

- `WAITING_FOR_TRIAGE / WAITING_FOR_NURSE / WAITING_FOR_TEST / WAITING_FOR_RESULT` 连续多 step 不应重复触发对话
- 首次 triage、首次 nurse 接触、首次 doctor assess、test result ready、disposition 改变必须仍能触发
- 同一事件在 cooldown 内不得重复触发

### 稳定性验收

- 以现有 long regression 为基线，比较每 step wall-clock 和日志中的 LLM / embedding 热点
- 目标不是先追求医学行为变化，而是先追求“连续推进能力”和“平均 step 成本下降”

第一阶段验收标准：

- smoke 7-step 全场景稳定通过
- 至少一个单场景 deep run 能稳定明显超过当前常见卡点
- `run 100` 作为下一阶段目标，以 smoke + 单场景 deep 的日志指标为准逐步推进

## 实施顺序
优先实现顺序固定为：

1. `P1 回归门禁`
2. `P2 embedding 降耗`
3. `P3 对话事件化`

只有 P1/P2 落地并验证后，再做 P3 的跨模块改造。

## Assumptions

- 第一版不追求完全移除对话，而是保留关键 clinical communication，只去掉等待态重复触发。
- 第一版不把全局 embedding 默认改成本地，继续采用 `hybrid`，但加入 cache 和远程健康短路。
- 第一版 smoke 采用脚本硬门禁，默认 7 step。
- 第一版优先处理“反馈回路”和“基础设施热路径”，而不是直接重写整套状态机。
