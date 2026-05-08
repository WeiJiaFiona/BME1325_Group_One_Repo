## week5工程细节补充（agents + simulation_loop + queue_state_primitives）

**（1）不同 agent 的作用与交互**
1. Patient（`week5/edmas/week5_edmas/week5_system/agents/patient.py`）
作用：承载患者状态与就诊流程执行，自动推进候诊、检查、结果等待与离院等阶段。
关键变量：`CTAS`（分诊等级）、`injuries_zone`（分区）、`state`（当前状态）、`testing_time`/`testing_result_time`（检查/结果耗时）、`walkout_probability`（离院概率）、`bed_assignment`（床位占用）。
交互：进入 `maze.triage_queue` 由 Triage Nurse 拉取；进入 `patients_waiting_for_doctor` 与 `bedside_nurse_waiting`；由 Bedside Nurse 转运；由 Doctor 触发确定性状态转移。

2. Triage Nurse（`week5/edmas/week5_edmas/week5_system/agents/triage_nurse.py`）
作用：处理分诊队列，完成分诊后将患者加入医生队列与护士队列。
关键变量：`maze.triage_queue`（分诊等待队列）、`maze.triage_patients`（分诊区在位数量）、`maze.triage_capacity`（分诊容量）、`priority_factor`（CTAS 权重系数）。
交互：从 `triage_queue` 拉患者 → 触发患者 `to_triage()` → 分诊完成后将患者放入 `patients_waiting_for_doctor` 与 `bedside_nurse_waiting` 或 `pager` 队列。

3. Bedside Nurse（`week5/edmas/week5_edmas/week5_system/agents/bedside_nurse.py`）
作用：将患者从等待区转运到床位或检查室，并管理检查过程中的陪护与回程。
关键变量：`occupied`（当前任务状态，例如 `Transfer|patient`/`Testing|patient`/`Resting`）、`maze.injuries_zones`（分区容量与队列）、`available_beds`（床位可用表）、`testing_time`（检查耗时）。
交互：从 `bedside_nurse_waiting` 或 `pager` 拉患者 → 预占床位/转运 → 更新患者状态（如 `WAITING_FOR_FIRST_ASSESSMENT`）→ 触发检查流程。

4. Doctor（`week5/edmas/week5_edmas/week5_system/agents/doctor.py`）
作用：按优先级接诊并触发初评与处置的确定性状态转移。
关键变量：`max_patients`（同时可管理患者上限）、`assigned_patients_waitlist`（待诊队列）、`queue_aging_interval_minutes`（队列老化间隔）、`priority_factor`（CTAS 权重）。
交互：从 `maze.patients_waiting_for_doctor` 选择患者 → 触发 `do_initial_assessment()` 与 `do_disposition()` → 更新患者状态与队列。

**交互主链路（简述）**
1. Patient 进入 `triage_queue`。
2. Triage Nurse 拉取患者 → 完成分诊 → 放入医生队列与护士队列。
3. Bedside Nurse 转运患者到床位或检查室。
4. Doctor 按优先级接诊并推进状态机。
5. Patient 在检查与结果等待中自主管理，最终离院或转入住院流程。

**（2）Week5 代码文件（分工/命名：工程细节 + 变量说明 + 作用）**
1. `week5/edmas/week5_edmas/week5_system/agents/patient.py`
工程细节：`move()` 负责状态推进、离院、检查、结果等待与床位释放；`do_initial_assessment()` 与 `do_disposition()` 是确定性状态转移入口。
变量说明：`walkout_states`（允许离院状态集合）、`testing_probability_by_ctas`（按 CTAS 决定是否检查）、`admission_boarding_minutes_min/max`（住院留床时长区间）。
作用：把患者从“规则层状态”变成“可执行实体”，保证流程可运行与可统计。

2. `week5/edmas/week5_edmas/week5_system/agents/triage_nurse.py`
工程细节：从 `triage_queue` 取患者进入分诊；结束后按 CTAS 优先级分配医生/护士队列。
变量说明：`maze.triage_patients`（分诊区人数）、`priority_factor`（CTAS 排序权重）、`pager`（CTAS1 紧急队列）。
作用：完成“分诊入口 → 候诊队列”的关键转换。

3. `week5/edmas/week5_edmas/week5_system/agents/bedside_nurse.py`
工程细节：处理转运、床位预占与检查陪护；记录详细日志（状态时长、动作日志、交互日志）。
变量说明：`occupied_since`（占用开始时间）、`State_Durations`/`Action_Log`/`Interactions`（行为日志）。
作用：把“候诊 → 床位/检查”的流程落到可执行转运层。

4. `week5/edmas/week5_edmas/week5_system/agents/doctor.py`
工程细节：队列老化机制防止低优先级患者长期等待；接诊时立即触发患者确定性状态转移。
变量说明：`queue_aging_interval_minutes`/`queue_aging_decrement`（队列公平性参数）、`TERMINAL_STATES`（不再占用医生名额的状态）。
作用：将规则层优先级转化为实际接诊顺序。

5. `week5/edmas/week5_edmas/week5_system/simulation_loop/reverie.py`
工程细节：读取 meta.json 初始化仿真参数；构建 `Maze`、加载 personas；按时间步驱动全局循环。
变量说明：`sec_per_step`（每步秒数）、`patient_rate`（到达率）、`surge_multiplier`（高峰拥挤系数）、`triage_starting_amount`/`doctor_starting_amount`/`bedside_starting_amount`（初始角色数）。
作用：提供全局时间推进与资源约束，是 Week5 规则运行的基础环境。

6. `week5/edmas/week5_edmas/week5_system/simulation_loop/run_simulation.py`
工程细节：安全模式批量运行脚本，按 `hours_to_run` 与 `steps_per_save` 分段执行，并带失败退避与熔断。
变量说明：`write_movement`（是否生成回放文件）、`_BACKOFF_DELAYS`（失败退避间隔）。
作用：用于压力测试与批量仿真，不依赖前端交互。

7. `week5/edmas/week5_edmas/week5_system/queue_state_primitives/maze.py`
工程细节：解析 Tiled 地图与 block 配置，构建网格、事件、床位与队列系统；维护 `triage_queue`、`patients_waiting_for_doctor` 与 `injuries_zones`。
变量说明：`address_tiles`（位置反向索引）、`triage_capacity`（分诊容量）、`bed_assignments`/`available_beds`（床位分配与空闲表）。
作用：统一维护空间 + 队列 + 床位资源，是所有 agent 共享的状态容器。

8. `week5/edmas/week5_edmas/week5_system/queue_state_primitives/wait_time_utils.py`
工程细节：按 CTAS 与阶段抽样等待时间，支持截断对数正态与 hurdle-lognormal 分布；生成分阶段等待目标。
变量说明：`stage1_minutes`/`stage2_minutes`/`stage3_minutes`（分阶段等待时长）、`stage1_surge_extra`/`stage2_surge_extra`（拥挤额外延时）。
作用：提供可控等待时间机制，让仿真更接近真实 ED 时序。
