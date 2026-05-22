# EDmas 项目证据与叙事指南

## 证据分级规则

- `Confirmed`：可以直接从代码、测试、日志或文档中确认。
- `Partial`：repo 明确支持这个方向，但还没有完整的量化结论或闭环证明。
- `Missing Evidence`：repo 里没有足够证据，不能写成已经完成。

写简历、PS 或面试回答时建议这样用：
- 用 `Confirmed` 作为安全事实；
- 用 `Partial` 作为谨慎表述；
- 把不确定内容放进 `Missing Evidence`。

---

## 1. 项目文件地图

| 路径 | 作用 | 关键函数 / 类 / 变量 | 与项目叙事的关系 | 证据等级 |
|---|---|---|---|---|
| `app_core/rule_core/state_machine.py` | 急诊流程有限状态机 | `EncounterStateMachine`、`ALLOWED_TRANSITIONS`、`HOOK_ESCALATIONS`、`transition()`、`apply_hook()` | 说明项目不是普通聊天机器人，而是显式流程控制系统 | Confirmed |
| `app_core/rule_core/encounter.py` | 规则驱动的 encounter 执行器 | `start_user_encounter()`、`EncounterResult` | 用户模式的分诊到路由流程 | Confirmed |
| `app_core/rule_core/triage_policy.py` | 规则化分诊策略 | `TriageInput`、`TriageDecision`、`triage_cn_ad()` | 规则驱动 triage 和 acuity 路由 | Confirmed |
| `app_core/app/api_v1.py` | L1 API 和 user-mode 编排 | `start_encounter()`、`request_handoff()`、`complete_handoff()`、`queue_snapshot()`、`export_encounter_timeline()`、`export_auto_timeline()`、`user_mode_chat_turn()` | user mode、handoff、queue snapshot、timeline export 的正式接口面 | Confirmed |
| `app_core/app/mode_user.py` | user mode 入口 | `start()`、`_build_event_trace()` | 最小化但可追踪的用户 encounter 路径 | Confirmed |
| `app_core/app/handoff.py` | handoff 封装 | `request()`、`complete()`、`HANDOFF_TIMEOUT_SECONDS` | 结构化交接流程 | Confirmed |
| `app_core/app/schema.py` | 请求 payload 校验 | `validate_encounter_start_payload()`、`validate_handoff_request_payload()`、`validate_handoff_complete_payload()`、`PayloadError` | 错误输入和 malformed payload 处理 | Confirmed |
| `app_core/queue_state_primitives/snapshot.py` | 队列快照 | `queue_snapshot()` | 将负载和 occupancy 暴露给 API / 评估 | Confirmed |
| `app_core/queue_state_primitives/wait_time_utils.py` | 等待时间与资源逼真度 | `_load_ctas_wait_config()`、`_sample_wait_minutes()`、`_assign_wait_targets()` | 等待时间采样和 surge 行为 | Confirmed |
| `reverie/backend_server/week7_logic.py` | 场景逼真度辅助逻辑 | `arrival_profile_multiplier()`、`effective_arrival_rate()`、`testing_kind_for_ctas()`、`boarding_timeout_reached()` | arrival、lab/imaging 路由、timeout 逻辑 | Confirmed |
| `reverie/backend_server/reverie.py` | auto mode 后端运行器 | `ReverieServer`、`_atomic_write_json()`、`_build_safe_movement_path()`、crash logging、runtime loop | 仿真循环、movement 生成、崩溃恢复、同步骨架 | Confirmed |
| `app_core/simulation_loop/reverie.py` | 仿真循环运行时 | runtime step 推进、movement/environment/status 写入 | 更底层的运行循环 | Partial |
| `environment/frontend_server/translator/views.py` | Django 桥接层 | `home()`、`process_environment()`、`update_environment()`、`start_backend()`、`send_sim_command()`、`live_dashboard_api()`、`save_simulation_settings()` | 前后端同步、启动、健康检查、固定 seed 配置 | Confirmed |
| `environment/frontend_server/frontend_server/urls.py` | 路由表 | `/update_environment/`、`/process_environment/`、`/start_backend/.../`、`/api/live_dashboard/`、user-mode 路由 | 模拟器公开 API 面 | Confirmed |
| `environment/frontend_server/templates/home/scripts/auto_main_script.html` | auto mode 前端循环 | `render_step`、`playback_step`、`runtime_sync`、`backend_health`、`movementWaitReason`、`ROLE_STYLE`、`ROLE_SPRITE_KEY`、`ROLE_AVATAR_PATH`、`sanitizeMovementPath()` | movement 播放和运行时调试 | Confirmed |
| `environment/frontend_server/templates/home/scripts/user_main_script.html` | user mode 前端循环 | `sanitizeMovementPath`、角色/头像/sprite 辅助函数、`window.__EDSIM_DEBUG__` | 用户模式渲染和调试契约 | Confirmed |
| `environment/frontend_server/templates/home/home.html` | 首页 / 调试页 | 模式切换说明、runtime note、dashboard 入口 | 面向用户解释 runtime 链路 | Confirmed |
| `environment/frontend_server/templates/home/start_simulation.html` | 启动页 | seed 默认值、bootstrap 控件 | 可重复启动和固定 seed | Confirmed |
| `environment/frontend_server/frontend_server/settings/base.py` | Django 基础配置 | `ALLOWED_HOSTS`、`CSRF_TRUSTED_ORIGINS` | 本地和 EasyConnect 风格 host 兼容 | Confirmed |
| `environment/frontend_server/frontend_server/settings/local.py` | 本地覆盖配置 | 本地开发开关 | 稳定本地启动 | Confirmed |
| `app_core/memory/schema.py` | 记忆数据模型 | `MemoryItem`、`CurrentEncounterSummary`、`HandoffMemorySnapshot`、`AuditRecord`、`MemoryQuery` | structured memory 和 audit 能力 | Confirmed |
| `app_core/memory/storage.py` | 记忆持久化 | `JsonFileMemoryStorage`、`NullMemoryStorage`、`events.jsonl`、`audit.jsonl`、`current/`、`snapshots/` | Memory ON/OFF 和 replay 存储底座 | Confirmed |
| `app_core/memory/service.py` | 记忆服务封装 | `MemoryService`、`append_event()`、`update_current_summary()`、`write_handoff_snapshot()`、`retrieve()`、`export_replay()` | 记忆管线 | Confirmed |
| `app_core/memory/hooks.py` | 记忆构建辅助函数 | `generate_auto_run_id()`、`generate_user_run_id()`、`build_memory_event()`、`build_handoff_snapshot_id()`、`build_audit_record()` | 确定性标识和事件组装 | Confirmed |
| `app_core/memory/config.py` | 记忆开关 | `memory_v1_enabled()`、`get_runtime_root()` | Memory ON/OFF 配置 | Confirmed |
| `reverie/backend_server/auto_memory_hooks.py` | auto mode 记忆 hook | `record_encounter_started()`、`record_handoff_requested()`、`record_handoff_completed()`、`record_boarding_timeout()`、`record_resource_bottlenecks()` | runtime 事件捕获和 replay 支持 | Confirmed |
| `app_core/his/adapters/memory_adapter.py` | Memory -> HIS 映射层 | `get_memory_upgrade_plan()`、`persist_memory_item_to_his()`、`persist_current_summary_to_his()`、`map_handoff_snapshot_to_his_writes()` | runtime memory 到 HIS 的桥接 | Confirmed |
| `app_core/his/adapters/runtime_bridge.py` | runtime HIS 集成 | `reset_runtime_bridge_state()`、`register_runtime_patient()`、`_append_memory_event()`、`_persist_summary()`、`_maybe_seed_stemi_workup()` | runtime memory/HIS 同步和 STEMI bootstrap | Confirmed |
| `app_core/his/services/*.py` | HIS 服务层 | patient registry、encounter service、handoff service、audit log、document registry | 正式持久化层 | Confirmed |
| `tests_user/*.py` | user-mode / API 测试 | encounter path、handoff、queue snapshot、malformed payload | endpoint freeze 和校验证据 | Confirmed |
| `tests_backend/*.py` | 后端逼真度 / 运行时测试 | week7 features、wait times、auto memory hooks、long regression、LLM fallback | resource realism、可重复性、fallback 行为 | Confirmed |
| `tests_his/*.py` | HIS / memory / timeline 测试 | memory upgrade path、timeline export、contract alignment、STEMI smoke | Memory/HIS 桥接和 timeline export 证据 | Confirmed |
| `tests_frontend/*.py` | 前端同步 / debug contract 测试 | `test_views.py`、`test_frontend_debug_contracts.py` | 前后端同步和调试契约 | Confirmed |
| `docs/operations/week7_long_run_regression.md` | 长运行回归说明 | runtime chain、scenario runner、seed reproducibility | 固定 seed 验证叙事 | Confirmed |
| `docs/architecture/week7_auto_baseline_analysis.md` | baseline vs week7 分析 | arrival profile、lab/imaging、boarding timeout、baseline comparison | “resource realism” 叙事依据 | Confirmed |
| `docs/architecture/week9_memory_to_his_field_mapping.md` | Memory/HIS 映射说明 | frozen routes、field mapping | week9 bridge 叙事依据 | Confirmed |

---

## 2. 一句话项目定义

### 简历版
我做了一个面向急诊科场景的多智能体模拟系统，结合规则化分诊、显式状态机、结构化记忆和前后端同步，来验证工作流正确性、资源逼真度和交接连续性。

### 个人陈述版
这个项目让我意识到，医学 AI 最难的往往不是生成一个回答，而是在资源受限的医院流程中持续保持工作流连续性、状态一致性和安全交接。

### 面试开场版
这是一个急诊模拟医院系统，患者、护士、医生和运行时引擎都有显式状态。我主要做的是 user mode、auto mode、memory 和同步机制，让它可以模拟分诊、瓶颈和交接，而且不会丢状态。

---

## 3. 问题定义

### 中文版
这个项目关注的是急诊科（Emergency Department）里真实存在的流程问题：患者到达后要先分诊，再进入医生评估、检查、处置、交接或出院，而每一步都受医生数量、床位、检验和影像能力、等待时间、交接对象等约束。表面上看，它像是“人多、排队久、医生忙”；但更深层的问题是，医院系统本质上是一个受资源约束的状态机，任何一步的状态转移、交接或回写不一致，都会导致流程断裂、信息丢失或安全风险。这个项目把这些问题拆成规则化状态、事件和资源约束，并通过前后端同步、记忆结构和回归测试把流程变成可验证对象。

### English version
This project targets the workflow complexity of an emergency department: patient arrival, triage, physician assessment, diagnostics, disposition, and handoff are all constrained by doctors, nurses, beds, lab and imaging capacity, and time-sensitive transitions. The surface issue is long waiting lines and busy staff. The deeper issue is that the ED behaves like a resource-constrained state machine, where any inconsistency in state transition, handoff, or runtime synchronization can break continuity and create safety risks. The project makes these workflow constraints explicit and testable through rule-based states, events, memory, and frontend-backend synchronization.

### 导师常追问的 5 个问题
1. 为什么不是普通聊天机器人？因为核心问题是工作流控制和连续性，不是开放式对话。
2. 为什么不是普通网页动画？因为系统需要一致的状态、后端记录和运行时同步。
3. 为什么要多智能体？因为患者、护士、医生、接收科室有不同职责和约束。
4. 为什么要 memory？因为交接和随访需要跨步骤的结构化摘要和快照。
5. 什么让它算医学场景？因为实体、状态和资源都围绕 ED 流程建模。

---

## 4. 系统抽象

| 抽象层 | repo 中的实现证据 | 对应代码路径 | 简历怎么写 | 面试怎么解释 |
|---|---|---|---|---|
| Entity | patient、nurse、doctor、receiver unit、lab、imaging、bed、frontend user、backend engine | `app_core/rule_core/*`、`app_core/app/*`、`app_core/his/*`、`environment/frontend_server/*` | 模拟了带有交互关系的急诊多实体系统 | 我把临床角色和运行时角色分开了 |
| State | `ARRIVAL`、`WAITING_FOR_TRIAGE`、`TRIAGE_COMPLETE`、`ROUTED`、`WAITING_FOR_PHYSICIAN`、`UNDER_EVALUATION`、`WAITING_FOR_LAB`、`WAITING_FOR_IMAGING`、`AWAITING_DISPOSITION`、`ADMITTED`、`ICU`、`OR`、`DISCHARGED`、`TRANSFER`、`LWBS` | `app_core/rule_core/state_machine.py` | 显式 ED 状态和升级 hook | 每个患者步骤都是可追踪状态，而不是隐藏的控制流 |
| Event | arrival、triage complete、physician evaluation、lab/imaging routing、deterioration、handoff request/complete、boarding timeout | `app_core/rule_core/*`、`app_core/app/api_v1.py`、`reverie/backend_server/auto_memory_hooks.py` | 记录工作流事件以支持 replay、audit 和 continuity | 状态变化由事件驱动 |
| Resource | doctor availability、lab capacity、imaging capacity、turnaround times、bed availability、arrival profile、boarding timeout | `reverie/backend_server/week7_logic.py`、`app_core/queue_state_primitives/*` | 做了资源受限仿真 | 我关注的是吞吐量和瓶颈，而不是单次对话 |
| Metric | queue length、wait time、LOS、boarding delay、handoff latency、state consistency、sync health、test pass rate | `queue_snapshot`、`live_dashboard_api`、tests、regression scripts | 验证工作流正确性和运行稳定性 | 我可以看出系统是在推进、滞后还是卡住 |

---

## 5. 方法、模块与工具

| 类型 | repo 中的例子 | 为什么放这里 |
|---|---|---|
| 方法 / 研究设计 | rule-based state machine、multi-agent simulation、resource-constrained ED workflow simulation、structured memory for handoff、regression-based system verification、scenario-based stress testing | 这些是让项目具有研究属性的核心思想 |
| 模块 / 工程组件 | User Mode、Auto Mode、L1 API、Memory v1、frontend movement loop、queue snapshot、handoff API、temp-storage curr_step tracking | 这些是你可以在简历 bullet 里直接写的系统模块 |
| 工具 / 实现技术 | Python、Django、JavaScript、JSON/JSONL、PowerShell、pytest、本地 LLM gateway | 这些是支撑实现的技术，不应被写成研究贡献本身 |

### PS 里应该写什么
- 方法：为什么需要规则化、结构化记忆、仿真式流程控制。
- 问题：为什么急诊工作流的连续性和瓶颈很重要。
- 收获：为什么状态一致性比单次回答更关键。

### 要避免的空泛表达
- “我做了一个 AI 医生”
- “我训练了一个临床模型”
- “我部署了一个医院系统”
- “Memory 一定会提升医疗质量”

---

## 6. 我的具体贡献

### 6.1 Week 6：User Mode + L1 API

| 贡献名称 | 具体功能 | 输入 | 处理逻辑 | 输出 | 文件证据 | 测试证据 | 简历写法 | PS 写法 | 面试解释 |
|---|---|---|---|---|---|---|---|---|---|
| User encounter path | ED user-mode 入口 | encounter payload | 校验输入、运行分诊、生成 state trace | `patient_id`、`triage`、`final_state`、`event_trace` | `app_core/app/mode_user.py`、`app_core/rule_core/encounter.py`、`app_core/app/api_v1.py` | `tests_user/test_week6_user_mode_chat.py`、`tests_user/test_mode_user_contracts.py` | 实现了规则化 user encounter 工作流 | 我把 triage 到 routing 的路径写成了显式状态机 | 我把临床路径做成了可追踪的状态转移 |
| L1 API | 稳定的用户接口 | start / handoff / queue payload | schema validation + structured error handling | JSON 成功/错误包 | `app_core/app/api_v1.py`、`app_core/app/schema.py`、`tests_user/test_week6_l1_api.py` | malformed payload tests | 建了一个带校验的 user-mode API 面 | 这个 API 对输入格式和失败模式是严格的 | API 不只是返回答案，而是严格管控输入和错误 |
| Handoff mock / formal path | 交接请求和接收 | handoff request / complete payload | 创建 ticket、校验 receiver、计算 latency | handoff ticket、status、final disposition | `app_core/app/handoff.py`、`app_core/app/api_v1.py` | `tests_user/test_handoff_integration.py` | 加了结构化 handoff 流程和 timeout 语义 | 我把 handoff 当作一级工作流对象处理 | 交接不是附属逻辑，而是核心流程 |

### 6.2 Week 7：Auto Mode + Resource Realism

| 贡献名称 | 具体功能 | 输入 | 处理逻辑 | 输出 | 文件证据 | 测试证据 | 简历写法 | PS 写法 | 面试解释 |
|---|---|---|---|---|---|---|---|---|---|
| Arrival profile | `normal / surge / burst` | hour + mode | 基于倍数调整 arrival rate | effective arrival rate | `reverie/backend_server/week7_logic.py`、`docs/architecture/week7_auto_baseline_analysis.md` | `tests_backend/test_week7_features.py` | 为 ED 场景加入 arrival variability | 我开始思考高峰时段的流程压力 | 仿真不只是“来多少”，还要看“什么时候来” |
| Lab / imaging realism | capacity + turnaround | capacity、minutes | queue / turnaround sampling | wait-targets / testing mode | `app_core/queue_state_primitives/wait_time_utils.py`、`reverie/backend_server/week7_logic.py` | `tests_backend/test_wait_time_utils.py`、`tests_backend/test_week7_features.py` | 增加了 lab / imaging 容量和周转逼真度 | 资源上限会改变下游流程 | 资源限制会改变整个工作流时间 |
| Boarding timeout | timeout minutes | start time + current time | timeout threshold check | timeout events | `reverie/backend_server/week7_logic.py`、`reverie/backend_server/auto_memory_hooks.py` | week7 tests 和 auto memory hook tests | 增加了 boarding timeout 监控 | boarding 不是“在等”，而是被记录的事件 | 等待本身是一个需要建模的临床状态 |

### 6.3 前后端同步

| 贡献名称 | 具体功能 | 输入 | 处理逻辑 | 输出 | 文件证据 | 测试证据 | 简历写法 | PS 写法 | 面试解释 |
|---|---|---|---|---|---|---|---|---|---|
| 后端 movement 生成 | 仿真 step | runtime state | 写 `movement/<step>.json` 和 status 文件 | movement payload | `reverie/backend_server/reverie.py`、`app_core/simulation_loop/reverie.py` | 后端 / runtime 测试和运行日志 | 搭建了基于 step 的 runtime movement 管线 | 后端按步发布 movement | 后端一边推进，一边对前端发布 movement |
| 前端 update/execute/process 循环 | auto/user JS | movement payload | 拉取 movement、执行 path、写回 environment | 同步播放 + environment 快照 | `auto_main_script.html`、`user_main_script.html`、`views.py` | `tests_frontend/test_views.py`、`tests_frontend/test_frontend_debug_contracts.py` | 实现了前后端同步 | UI 只有在后端准备好下一步时才继续 | 前端不是自己跑，而是跟随后端 step 走 |
| `process_environment` | 环境写回 | environment payload | 校验 JSON、写文件、返回状态 | `ok`、`step`、`sim_code` 或 JSON error | `views.py` | `tests_frontend/test_views.py` | 强化了运行时写回和失败处理 | 后端能知道前端是否真的写回成功 | 我让写回失败变得可见，而不是静默失败 |
| 同步诊断 | 运行时健康状态 | live dashboard + debug contract | 暴露 `runtime_sync`、`backend_health`、`movementWaitReason` | 识别 lag / stall | `views.py`、`auto_main_script.html` | 前端 debug contract tests | 增加了运行时可观测性 | 出问题时不再是黑盒 | 现在能判断是卡住、滞后还是没消费 movement |

### 6.4 Week 8：Memory v1

| 贡献名称 | 具体功能 | 输入 | 处理逻辑 | 输出 | 文件证据 | 测试证据 | 简历写法 | PS 写法 | 面试解释 |
|---|---|---|---|---|---|---|---|---|---|
| Memory service | 结构化 memory 存储 | encounter events | append / update / retrieve / export | events、summary、snapshot、audit | `app_core/memory/service.py`、`app_core/memory/storage.py` | memory service tests 和 HIS tests | 加了结构化 memory 以支持 continuity | 我意识到 memory 是 workflow continuity 的关键 | memory 不是缓存，而是连续性工具 |
| Current summary | 当前状态摘要 | 最新 encounter state | 更新 compact summary | `CurrentEncounterSummary` | `app_core/memory/schema.py`、`app_core/memory/current_memory.py` | memory upgrade tests | 建了 current-state summaries | summary 是短期临床记忆 | 它让接收方知道“现在到哪一步了” |
| Handoff snapshot | 交接前快照 | handoff context | 写结构化 transfer snapshot | `HandoffMemorySnapshot` | `app_core/memory/schema.py`、`app_core/memory/handoff_memory.py` | handoff memory tests | 捕获了 pre-handoff snapshots | snapshot 保留了下一位接收者最需要的信息 | 交接不是一句话，而是一份结构化摘要 |
| Audit log | 操作轨迹 | memory operations | 追加 audit record | `AuditRecord` | `app_core/memory/schema.py`、`app_core/memory/audit.py`、`app_core/memory/storage.py` | audit / memory tests | 增加了 auditability | audit 告诉我们发生了什么 | 能追溯，就能 debug |
| Memory ON/OFF | 功能开关 | environment config | 启用 `JsonFileMemoryStorage` 或 `NullMemoryStorage` | fail-open memory path | `app_core/memory/config.py`、`app_core/memory/service.py` | fallback tests | 增加了可配置 memory 支持 | memory 可以关，但系统要能继续跑 | 这是一个 fail-open 设计 |
| Memory -> HIS mapping | 持久化桥接 | memory items 和 snapshots | 映射到 event registry / summaries / documents | HIS writes 和 replay exports | `app_core/his/adapters/memory_adapter.py`、`app_core/his/adapters/runtime_bridge.py` | `tests_his/test_memory_upgrade_path.py`、`tests_his/test_timeline_export.py` | 把 runtime memory 升级成正式记录 | memory 不是孤立的，它可以升级成正式病历记录 | Memory 连接了运行时和正式记录层 |

---

## 7. 工程细节

### 7.1 Backend 运行流程
1. 后端从 `reverie/backend_server/reverie.py` 启动。
2. 初始化 seed 和 runtime 状态，然后写 `curr_step.json`、`sim_status.json` 和 movement 文件。
3. 每一步推进都更新仿真状态机和资源逻辑。
4. `movement/<step>.json` 由后端 runtime loop 生成。
5. 病人状态更新通过规则化 encounter / state machine 逻辑完成。
6. 队列快照通过 `app_core/queue_state_primitives/snapshot.py` 和 `queue_snapshot()` 暴露。
7. `curr_step`、`sim_time` 和 `status` 会写到 runtime 文件里，再由 `live_dashboard_api()` 暴露给前端。

### 7.2 Frontend 运行流程
1. 前端从页面上下文和 `live_dashboard_api` 读当前 step。
2. 通过 `/update_environment/` 拉取 movement。
3. 在 `auto_main_script.html` / `user_main_script.html` 里逐格执行 movement path。
4. 执行完成后通过 `/process_environment/` 写回 environment。
5. 如果没有新的 movement，就等待或对齐 step，而不是盲目推进。
6. 如果 backend stalled，前端会看起来像冻结，因为它在等合法的下一步 movement。

### 7.3 API 运行流程
1. `start_encounter()` 接收验证过的 encounter payload，返回 encounter/triage/state-trace 数据。
2. `request_handoff()` 和 `complete_handoff()` 管理 handoff ticket 的创建和完成。
3. `queue_snapshot()` 返回队列负载和 occupancy 状态。
4. malformed payload 会被 `PayloadError` 和结构化 JSON error 拒绝。
5. API 错误不会静默消失，而是返回结构化响应。

### 7.4 Memory 运行流程
1. Memory 事件会在 encounter-start、handoff、timeout、bottleneck、close 等 hook 处写入。
2. `MemoryItem` 用结构化字段保存事件，包括 id、角色、时间、前后状态和内容。
3. `CurrentEncounterSummary` 会根据最新 encounter state 更新。
4. `HandoffMemorySnapshot` 在交接前写入，保留接收方需要的摘要。
5. `AuditRecord` 记录 memory 操作和 retrieval/export 行为。
6. Memory 是 fail-open：如果被关闭或不可用，仿真还能继续，但结构化记忆会丢失。

### 文本版数据流图
`用户/患者输入 -> API/Simulation Engine -> State Machine -> Resource Logic -> Movement/State Files -> Frontend Execution -> Process Environment -> Memory/Audit -> Evaluation Metrics`

---

## 8. 评估与验证

### Correctness Tests
- `Confirmed`：triage、state transition、handoff、queue snapshot、malformed payload 校验都有测试。
- 证据：`tests_user/*`、`tests_his/*`、`tests_frontend/*`、`tests_backend/*`。

### Robustness Tests
- `Confirmed`：malformed input、missing fields、backend stalled 检测、local fallback、path collision 检查。
- `Partial`：长运行稳定性和浏览器级鲁棒性还需要更完整的持续跑证据。

### Scenario Tests
- `Confirmed`：normal / surge / burst / imaging bottleneck / boarding timeout / doctor shortage 风格的场景测试存在。
- 证据：`tests_backend/test_week7_features.py`、`docs/architecture/week7_auto_baseline_analysis.md`、`scripts/run_week7_long_regression.py`。

### Synchronization Tests
- `Confirmed`：frontend update/process 合约、runtime sync 字段、bridge writeback 都有测试或文档支持。
- 证据：`tests_frontend/test_views.py`、`tests_frontend/test_frontend_debug_contracts.py`。

### Memory Evaluation
- `Confirmed`：memory 写入、snapshot、audit、HIS 映射都存在。
- `Missing Evidence`：完整的 ON/OFF ablation、repeated-question rate 和 memory 量化收益报告还没有。

### 安全表述
- “我们有 regression 和 smoke tests，验证了工作流和同步契约。”
- “我们有结构化 memory 和 HIS 映射支持。”
- “我们还需要正式 ablation 来量化 memory 的收益。”

---

## 9. 失败案例与调试故事

| 失败案例 | 含义 | 可能原因 | 定位方法 | 面试怎么讲 |
|---|---|---|---|---|
| `backend stalled` | 运行时停止推进 | 命令循环卡住、启动失败或写回不匹配 | 看 `live_dashboard_api`、crash log、`temp_storage/commands`、movement 文件 | 我能区分“进程还活着”和“runtime 真在推进” |
| 前端 API 正常但 movement 不更新 | UI 能连到后端，但播放没继续 | step 不对齐、movement 为空、backend stalled | 看 `runtime_sync`、`movementWaitReason`、bridge log | 我能 debug 同步问题，而不只是 HTTP 错误 |
| tile index out of range | movement path 坐标非法 | 路径构造 bug 或边界问题 | 检查 `_build_safe_movement_path()` 和 path sanitize | 我能把几何 bug 追到路径 payload |
| LLM gateway TLS EOF / request failure | 远端生成失败 | gateway / auth / 网络问题 | 检查 local fallback 和 `LLM_MODE` | 即使远端模型失效，仿真也不会直接崩 |
| `datetime.timedelta` bug | 时间算错或解析错 | 时间转换 / 字符串格式问题 | 看 wait-time 工具和 runtime 时间字段 | 我会 debug 时间逻辑，不只会看 UI 症状 |
| baseline 比 week7 更快 | week7 多了逼真度 | 更多日志、资源约束、复杂 runtime | 对比 docs 和 regression scripts | 我知道逼真度和速度是 trade-off |
| memory 写入成功但 handoff 没变好 | 有记录不代表有效果 | memory 捕获不等于 policy 改善 | 需要 ablation 和人工评估 | 我能区分 instrumentation 和 outcome |
| wall clipping / 不均匀移动 | sprite 路径穿墙或插值错 | 前端 playback 或路径生成不一致 | path sanitize + collision check | 我能同时看后端路径和前端渲染 |

---

## 10. 项目局限

### 数据真实性
- `Partial`：arrival、turnaround 和 timeout 参数存在，但 repo 并不能证明它们来自真实 ED 日志。

### 医学合理性
- `Confirmed`：triage 是确定性的、规则驱动的。
- `Missing Evidence`：没有外部临床指南对齐或医生审阅证据。

### LLM 可靠性
- `Confirmed`：有 local fallback。
- `Missing Evidence`：没有正式研究证明 LLM 结果具有临床有效性。

### 仿真方法
- `Confirmed`：rule-based state machine + multi-agent workflow 确实存在。
- `Partial`：完整 discrete-event baseline 对照还不是闭环 benchmark。

### 工程
- `Confirmed`：前后端同步、bridge logging 和 runtime health 字段已经实现。
- `Partial`：长运行稳定性有测试和日志支持，但不能证明零崩溃风险。

### 评估
- `Confirmed`：有不少 smoke / regression / scenario tests。
- `Missing Evidence`：正式 quantitative evaluation、ablation 和 expert review 还没完成。

### 不要夸大的内容
- 不要说这是可部署的临床系统。
- 不要说 memory 一定会提升医疗质量。
- 不要说 LLM 在做临床决策。

---

## 11. 未来工作

1. 用真实 ED 日志校准 arrival、lab、imaging 和 boarding 参数。
2. 加一个 discrete-event baseline，并与当前 agent-based workflow 对照。
3. 量化 Memory ON/OFF、handoff completeness 和 repeated-question reduction。
4. 加医生/护士对 triage 和 escalation rules 的审阅。
5. 做一个固定 seed 的可重复 benchmark runner，并把 JSON 结果存下来。

---

## 12. Missing Evidence

| 主题 | 缺失的证据 |
|---|---|
| Memory ON/OFF ablation | 没有完整的量化研究 |
| repeated-question rate | 没有显式指标报告 |
| 临床指南对齐 | 没有外部指南引用或医生签字 |
| 真实数据校准 | 没有证明来自真实医院日志的来源说明 |
| 部署就绪 | 这是模拟器，不是临床部署产物 |
| 每个文件的个人作者归属 | repo 无法证明哪一行是谁写的 |

