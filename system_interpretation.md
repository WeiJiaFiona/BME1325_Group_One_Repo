# Executive Summary

- 已确认 `week9` 目前同时存在两条主线。
- Auto mode / 仿真主线：Django 前端在 [`environment/frontend_server/translator/views.py`](/home/jiawei2022/BME1325/week9/environment/frontend_server/translator/views.py) 发命令，`reverie/backend_server/reverie.py` 读取 `temp_storage/commands/cmd_*.json` 推进 step，输出 `storage/<sim_code>/movement/*.json`、`environment/*.json`、`sim_status.json`。
- User mode / 规则对话主线：Django 同样经 [`translator/views.py`](/home/jiawei2022/BME1325/week9/environment/frontend_server/translator/views.py) 暴露 `/mode/user/*`，核心逻辑在 [`app_core/app/api_v1.py`](/home/jiawei2022/BME1325/week9/app_core/app/api_v1.py)、[`app_core/app/mode_user.py`](/home/jiawei2022/BME1325/week9/app_core/app/mode_user.py)、[`app_core/rule_core/*`](/home/jiawei2022/BME1325/week9/app_core/rule_core/triage_policy.py)。
- 当前最重要的接入风险是 ID 体系分裂。
- Auto mode 主要使用 `"Patient 1"` / `"Patient_1"` / `auto_auto_<run>_Patient_1`。
- User mode 主要使用 `patient_id`、`encounter_id`，并额外生成 HIS `P-xxxxxxxx` / `E-...`。
- Auto mode 已有真实 movement、床位、分诊、检查、出院/住院 boarding 状态；但 ICU/ward 真正空间与跨科移动尚未在仿真地图内实现。
- User mode 已有 calling_nurse / doctor / bedside_nurse 的文本流程、handoff ticket、HIS 事件；但更接近“流程编排与对话状态机”，不是地图驱动仿真。

# Confirmed Findings

- Django 路由入口在 [`environment/frontend_server/frontend_server/urls.py`](/home/jiawei2022/BME1325/week9/environment/frontend_server/frontend_server/urls.py)。
- `start_backend`、`send_sim_command`、`save_simulation_settings`、`mode/user/session/status` 都定义在 [`environment/frontend_server/translator/views.py`](/home/jiawei2022/BME1325/week9/environment/frontend_server/translator/views.py)。
- Reverie backend 主入口是 [`reverie/backend_server/reverie.py`](/home/jiawei2022/BME1325/week9/reverie/backend_server/reverie.py)，批量运行脚本是 [`reverie/backend_server/run_simulation.py`](/home/jiawei2022/BME1325/week9/reverie/backend_server/run_simulation.py)。
- 当前运行中的 auto sim 目录是 `environment/frontend_server/storage/curr_sim`，当前临时目录是 `environment/frontend_server/temp_storage`。
- `movement/<step>.json` 是前端回放/播放数据流；`environment/<step>.json` 是前端/后端同步位置快照；`sim_status.json` 是 dashboard 状态源。
- Rule triage 在 [`app_core/rule_core/triage_policy.py`](/home/jiawei2022/BME1325/week9/app_core/rule_core/triage_policy.py) 明确使用 A/B/C/D 映射到 CTAS 1/2/3/4；CTAS 5 只在 auto 仿真和诊断 CSV 中出现。
- Auto patient 状态机主要在 [`reverie/backend_server/persona/persona_types/patient.py`](/home/jiawei2022/BME1325/week9/reverie/backend_server/persona/persona_types/patient.py) 和 [`patient_scratch.py`](/home/jiawei2022/BME1325/week9/reverie/backend_server/persona/memory_structures/scratch_types/patient_scratch.py)。
- User mode disposition 逻辑在 [`app_core/app/api_v1.py`](/home/jiawei2022/BME1325/week9/app_core/app/api_v1.py) 中：A/B -> ICU，C -> WARD，其他 -> DONE/门诊。

# Architecture and Entry Points

## 架构表

| 模块 | 文件路径 | 关键函数/类 | 作用 | 备注 |
| -- | ---- | ------ | -- | -- |
| Django 路由入口 | `environment/frontend_server/frontend_server/urls.py` | `urlpatterns` | 统一注册前端页、仿真接口、user mode 接口 | 已确认 |
| Django 视图主入口 | `environment/frontend_server/translator/views.py` | `home`, `start_backend`, `send_sim_command`, `save_simulation_settings`, `api_mode_user_*`, `live_dashboard_api` | 前端页面渲染、仿真桥接、user mode API | 已确认 |
| 前端启动脚本 | `start_user_frontend_8011.sh` | shell 脚本 | 启动 Django/frontend server | 已确认 |
| 用户模式后端启动脚本 | `start_user_backend_edsim39.sh`, `start_user_backend_curr_sim.sh` | shell 脚本 | 启动 reverie backend | 已确认 |
| auto 模式启动脚本 | `start_auto_backend_edsim39.sh`, `run_auto_all_in_one_edsim39.sh` | shell 脚本 | 启动 auto backend / all-in-one | 已确认 |
| Reverie backend 主入口 | `reverie/backend_server/reverie.py` | `ReverieServer`, `open_server`, `start_server` | 仿真主循环、读命令、推进 movement/status | 已确认 |
| 仿真批处理入口 | `reverie/backend_server/run_simulation.py` | main block | 头less 批量 `run N` | 已确认 |
| User mode 规则入口 | `app_core/app/mode_user.py` | `start` | 调用规则分诊，返回 `triage` / `state_trace` | 已确认 |
| User mode 编排入口 | `app_core/app/api_v1.py` | `start_encounter`, `user_mode_chat_turn`, `user_mode_session_status`, `request_handoff`, `complete_handoff`, `queue_snapshot` | 对话式分诊、医生问答、handoff、session 状态 | 已确认 |
| Auto 仿真地图/容量 | `reverie/backend_server/maze.py` | `Maze`, `_initialize_beds`, `assign_bed` | 房间、坐标、容量、床位分配 | 已确认 |
| Auto agent 基类 | `reverie/backend_server/persona/persona.py` | `Persona`, `add_persona_to_sim` | persona 创建、初始移动 | 已确认 |
| Auto patient 逻辑 | `reverie/backend_server/persona/persona_types/patient.py` | `Patient.move`, `do_initial_assessment`, `do_disposition` | auto patient 状态与检查/出院/boarding | 已确认 |
| Auto triage nurse 逻辑 | `reverie/backend_server/persona/persona_types/triage_nurse.py` | `Triage_Nurse.move` | 从 triage_queue 拉患者，写 doctor/bedside 队列 | 已确认 |
| Auto doctor 逻辑 | `reverie/backend_server/persona/persona_types/doctor.py` | `Doctor.move`, `assign_patient` | 取队列、做初评、触发 disposition | 已确认 |
| Auto bedside nurse 逻辑 | `reverie/backend_server/persona/persona_types/bedside_nurse.py` | `Bedside_Nurse.move`, `set_to_resting` | 运送到床位/检查区 | 已确认 |
| 规则分诊策略 | `app_core/rule_core/triage_policy.py` | `triage_cn_ad`, `TriageDecision` | user mode 规则分诊 | 已确认 |
| user mode 状态机 | `app_core/rule_core/state_machine.py` | `EncounterStateMachine`, `HOOK_ESCALATIONS` | user mode 状态推进 | 已确认 |
| HIS ID/事件适配 | `app_core/his/config.py`, `app_core/his/adapters/contract_adapter.py` | `generate_patient_id`, `generate_encounter_id`, `build_event_envelope` | 生成稳定外部 ID 与事件 envelope | 已确认 |

## 主要接口位置

| 接口/入口 | 定义文件 | 关键函数 |
| -- | -- | -- |
| `/start_backend/<origin>/<target>/` | `translator/views.py` | `start_backend(request, origin, target)` |
| `/send_sim_command/` | `translator/views.py` | `send_sim_command` |
| `/save_simulation_settings/` | `translator/views.py` | `save_simulation_settings` |
| `/get_sim_output/` | `translator/views.py` | `get_sim_output` |
| `/process_environment/` | `translator/views.py` | `process_environment` |
| `/update_environment/` | `translator/views.py` | `update_environment` |
| `/api/live_dashboard/` | `translator/views.py` | `live_dashboard_api` |
| `/mode/user/encounter/start` | `translator/views.py` | `api_mode_user_encounter_start` |
| `/mode/user/chat/turn` | `translator/views.py` | `api_mode_user_chat_turn` |
| `/mode/user/session/status` | `translator/views.py` | `api_mode_user_session_status` |
| `/mode/user/session/reset` | `translator/views.py` | `api_mode_user_session_reset` |
| `/ed/handoff/request` | `translator/views.py` | `api_ed_handoff_request` |
| `/ed/handoff/complete` | `translator/views.py` | `api_ed_handoff_complete` |
| `/ed/queue/snapshot` | `translator/views.py` | `api_ed_queue_snapshot` |

## 目录与运行路径

| 项 | 当前值 | 来源 |
| -- | -- | -- |
| 项目根目录 | `/home/jiawei2022/BME1325/week9` | `translator/views.py` 中 `PROJECT_ROOT` |
| frontend root | `/home/jiawei2022/BME1325/week9/environment/frontend_server` | `translator/views.py` 中 `FRONTEND_ROOT` |
| backend root | `/home/jiawei2022/BME1325/week9/reverie/backend_server` | `translator/views.py` 中 `_resolve_backend_dir()` |
| storage 目录 | `/home/jiawei2022/BME1325/week9/environment/frontend_server/storage` | `translator/views.py` 中 `STORAGE_ROOT` |
| 当前 sim 目录 | `/home/jiawei2022/BME1325/week9/environment/frontend_server/storage/curr_sim` | `temp_storage/curr_sim_code.json` + 实际目录 |
| movement 目录 | `storage/<sim_code>/movement` | `translator/views.py`, `reverie.py` |
| environment 目录 | `storage/<sim_code>/environment` | `translator/views.py`, `reverie.py` |
| temp_storage 目录 | `/home/jiawei2022/BME1325/week9/environment/frontend_server/temp_storage` | `translator/views.py` 中 `TEMP_ROOT` |

# Patient Identity

## patient_id 生成与保存表

| EDMAS 字段/名称 | 示例 | 生成位置 | 保存位置 | 是否适合作为 FullView patient_id |
| ----------- | -- | ---- | ---- | -------------------------- |
| Auto persona 名称 | `Patient 1` | `reverie/meta.json` 的 `persona_names`；新增患者由 `ReverieServer.add_persona_to_sim` / `Patient N` 递增，来源文件为 `reverie.py`、`persona.py` | `reverie/meta.json`、`movement/*.json`、`personas/<name>/bootstrap_memory/scratch.json` | 不适合，名称型且可能重置 |
| Auto memory patient_id | `Patient_1` | `runtime_data/memory/events.jsonl` 中 auto memory hook 写入；来源 `auto_memory_hooks.py` 与 `events.jsonl` 实例 | `runtime_data/memory/events.jsonl` | 不适合，格式与前端名称不同 |
| Auto memory encounter_id | `auto_auto_curr_sim_20260521_062827_Patient_1` | auto memory hook 运行时构造，见 `runtime_data/memory/events.jsonl` | `runtime_data/memory/events.jsonl` | 可作为临时 case id，不适合作为跨系统 patient_id |
| User mode patient_id | `Patient 1` 或 `patient-ab12cd` | `api_v1.py:start_encounter`；若 payload 未给则 `patient-<uuid6>` | `_USER_MODE_SESSION`、`_ENCOUNTERS`、HIS 同步时作为 `public_patient_id` | 不直接适合，外部输入不稳定 |
| User mode encounter_id | `enc-1a2b3c4d5e` | `api_v1.py:start_encounter` | `_ENCOUNTERS`、session、handoff ticket、HIS payload 中 `public_encounter_id` | 适合作为 `context.edmas_case_id` |
| HIS patient_id | `P-1a2b3c4d` | `app_core/his/config.py:generate_patient_id` | HIS storage、事件 envelope | 适合作为 FullView patient_id 候选 |
| HIS encounter_id | `E-20260612010101-abcd` | `app_core/his/config.py:generate_encounter_id` | HIS storage、事件 envelope | 适合作为 FullView encounter/case id 候选 |
| patient scratch user_patient_id | 未见样例，字段存在 | `patient_scratch.py` 定义 `user_patient_id`；`api_v1.py:_sync_user_patient_to_auto` 用于 `inject_user_patient` | auto patient scratch，若 user patient 注入成功 | 推测可作为 user->auto 映射桥字段 |
| patient scratch user_encounter_id | 未见样例，字段存在 | 同上 | auto patient scratch | 推测适合作为 FullView context 字段 |
| external_id / case_id / encounter_id | `enc-...` / `E-...` | user mode 与 HIS 已存在 `encounter_id`；`external_id` / `case_id` 未找到 | `_ENCOUNTERS` / HIS | 建议优先新增或统一 `external_patient_id`，并保留 `encounter_id` |

## 结论

- `Patient 1`、`Patient 2` 这类编号在 auto 仿真中是 persona 名称，不是稳定外部 patient_id。
- Auto 仿真中未找到单独稳定的内部 patient UUID。
- User mode 与 HIS 已有更稳定的 `patient_id` / `encounter_id` 体系。
- 若接入 FullView，最合适方案是：
- FullView `patient_id` 使用 HIS `P-xxxxxxxx`。
- FullView `context.edmas_case_id` 使用 user/HIS `encounter_id`。
- Auto mode 需要新增 `external_patient_id` 字段写入 `patient_scratch`、movement、memory、status。

# Agent Roles and Responsibilities

## 角色总表

| agent role | 示例名称 | 定义文件 | 数量来源 | 初始位置来源 | 主要职责 | 是否需要映射到 FullView staff |
| ---------- | ---- | ---- | ---- | ------ | ---- | ---------------------- |
| doctor | `Doctor 1` | `reverie/backend_server/persona/persona_types/doctor.py` | `meta.json: doctor_starting_amount`，`reverie.py` 读取 | `Doctor.get_spawn_loc` -> `major injuries zone` | 取医生队列、初评、决定检查/出院/boarding | 是 |
| triage_nurse | `Triage Nurse 1` | `reverie/.../triage_nurse.py` | `meta.json: triage_starting_amount` | `Triage_Nurse.get_spawn_loc` -> `triage room:chair` | 拉 triage queue、分诊后写入 doctor/bedside 队列 | 是 |
| bedside_nurse | `Bedside Nurse 1` | `reverie/.../bedside_nurse.py` | `meta.json: bedside_starting_amount` | `Bedside_Nurse.get_spawn_loc` -> `minor injuries zone` | 护送患者到床位/检查区 | 是 |
| patient | `Patient 1` | `reverie/.../patient.py` | 初始 `persona_names` + 运行时新增患者 | waiting room / exit / bed | 在状态机驱动下移动、接受检查、出院/boarding | 否 |
| calling_nurse | `CALLING_NURSE` | `app_core/app/api_v1.py` | 无实体 persona，只有 user mode 逻辑角色 | 无独立地图位置；通过 `movement_suggestion.target_zone` 指向 `vitals_station`/等待区 | 测生命体征、叫号、把 user mode 患者送到 triage/doctor | 是，建议映射 staff role，但当前非 auto persona |
| bed_nurse | `BEDSIDE_NURSE` | `app_core/app/api_v1.py` | 无实体 persona，只有 user mode 逻辑角色 | 无独立地图位置 | 完成 handoff 后给床位指引 | 是 |
| system/auto_runtime | `auto_runtime` | `auto_memory_hooks.py`, `events.jsonl` | 非 persona | 无 | 记录自动记忆事件 | 否 |
| receptionist / bed manager / diagnostic staff | 未找到 | 未找到 | 未找到 | 未找到 | 未找到 | 未找到 |

## 四类重点角色调用链

| 角色 | 触发时机 | 输入 | 输出 | 状态修改 | movement 修改 | 相关文件 |
| -- | ---- | -- | -- | ---- | ----------- | ---- |
| doctor | 患者进入 `patients_waiting_for_doctor` 且到达 `WAITING_FOR_FIRST_ASSESSMENT`/`WAITING_FOR_DOCTOR` 等 ready states | `assigned_patients_waitlist`, patient scratch, triage/CTAS | 初评、检查决定、disposition | `do_initial_assessment`, `do_disposition` 改 patient state | 间接；通过 patient `next_step` 改 movement | `doctor.py`, `patient.py` |
| triage_nurse | `triage_queue` 非空且 `triage_patients < triage_capacity` | `maze.triage_queue`, patient scratch | 把患者放入医生/床旁护士队列，CTAS 1 走 pager | 患者从 `TRIAGE` 结束后进入等待后续阶段 | 不直接写 movement 文件，但通过 patient `to_triage`/next_step 影响 | `triage_nurse.py` |
| calling_nurse | user mode intake 完成后 | chief complaint, vitals, session | 测量生命体征、送到 triage、等待叫号通知 | `phase` 从 `INTAKE` -> `CALL_NURSE_MEASURE` -> `WAITING_CALL` / `DOCTOR_CALLED` | 仅写 `movement_suggestion`，不写 auto movement | `api_v1.py` |
| bedside_nurse | auto 中 bedside queue / pager 非空；user mode 中 handoff 后 | `bedside_nurse_waiting`, `pager`, patient next_room | 护送到床位或检查区；user mode 中生成床位文本 | auto: `WAITING_FOR_NURSE` -> `WAITING_FOR_FIRST_ASSESSMENT`；user: `BED_NURSE_FLOW` -> `DONE` | auto: 是；user: 仅 `movement_suggestion` | `bedside_nurse.py`, `api_v1.py` |

## doctor

- 何时接诊患者：`Doctor.move` 从 `maze.patients_waiting_for_doctor` 按优先级取患者，且仅接受 `WAITING_FOR_FIRST_ASSESSMENT`、`WAITING_FOR_TEST`、`GOING_FOR_TEST`、`WAITING_FOR_RESULT`、`WAITING_FOR_DOCTOR`，来源 [`doctor.py`](/home/jiawei2022/BME1325/week9/reverie/backend_server/persona/persona_types/doctor.py)。
- 如何读取分诊结果：auto mode 直接读取 patient scratch 的 `CTAS`、`injuries_zone`；user mode 通过 `session["shared_memory"]["triage"]` 和 `_doctor_opening_from_memory`，来源 [`api_v1.py`](/home/jiawei2022/BME1325/week9/app_core/app/api_v1.py)。
- 如何生成问诊问题：user mode 由 `retrieve_protocols`、`build_evidence_package`、`build_doctor_plan`、`validate_plan`、`_build_doctor_followup_line` 生成；RAG 桥接在 `run_bridge`，来源 [`api_v1.py`](/home/jiawei2022/BME1325/week9/app_core/app/api_v1.py) 与 [`app_core/doctor_llm`](/home/jiawei2022/BME1325/week9/app_core/doctor_llm/prompts.py)。
- 是否会给出诊断/检查/住院/ICU/出院建议：
- auto mode：会触发检查、出院、admit boarding；ICU/ward 未找到真实 auto disposition。
- user mode：A/B -> ICU，C -> WARD，其他 -> 门诊/完成。
- 是否会触发 movement：会，主要通过修改 patient `next_step` / `state`，来源 `Patient.do_initial_assessment`、`Patient.do_disposition`。
- 当前自然问答逻辑：集中在 `api_v1.py` 的 `DOCTOR_CALLED` 分支；auto doctor 聊天更多是 flavor，对真实推进不起决定作用。

## triage_nurse

- 如何进行分诊：
- auto mode：主要依赖 patient 预先带入的 `CTAS` / `injuries_zone`，triage nurse 更像流程搬运与排队分发，来源 `triage_nurse.py`。
- user mode：规则分诊由 `triage_cn_ad` 执行。
- CTAS 或急诊等级如何计算：`triage_policy.py` 用主诉、症状、SpO2、SBP、pain_score、关键词规则决定 A/B/C/D，再映射 CTAS 1/2/3/4。
- 是否根据主诉、生命体征、规则或 LLM 判断：user mode 是规则，不是 LLM；auto mode 初始 CTAS 多来自 `diagnosis.csv` / 预生成症状。
- 分诊结果保存在哪里：user mode 保存到 `_ENCOUNTERS[encounter_id]["triage"]`、session shared_memory、HIS triage record；auto mode 保存在 patient scratch `CTAS`、`injuries_zone`。

## calling_nurse

- 何时测量生命体征：user mode `CALL_NURSE_MEASURE` 阶段，`_nurse_measured_vitals` 补全 vitals。
- 何时叫号：`WAITING_CALL` 阶段 `_maybe_auto_progress` 里队列归零时进入 `DOCTOR_CALLED`。
- 如何把患者送到分诊/医生：通过 session `movement_suggestion.target_zone` 设为 `vitals_station`、`triage_waiting_area`、`doctor_assessment_zone`。
- 是否在后端 movement 中体现：未找到；user mode 不写 auto movement 文件。

## bedside_nurse

- 何时安排床位：auto mode 在 `Bedside_Nurse.move` 内从 `bedside_nurse_waiting` / `pager` 取患者，并调用 `reserve_bed` / `Patient._target_bed`。
- 如何把患者带到床边：写 patient `next_step` 为具体床位 `<tile> [x,y]` 或房间 bed 地址。
- 是否参与急诊观察、治疗或转运：参与 auto mode 的床边转运与检查区转运；user mode 参与 handoff 完成后的床位文本通知。

# Rooms, Beds, and Locations

## 当前急诊空间表

| EDMAS room/location | 显示名 | 来源文件 | 坐标/区域 | 用途 | 容量/床位 | 推荐 FullView room_id |
| ------------------- | --- | ---- | ----- | -- | ----- | ------------------- |
| `waiting room` | Waiting Room | `maze_visuals.json`, `patient.py`, `movement/*.json` | 例：`Patient 1` 在 `[1,8]` | 候诊 | 未找到显式容量 | `ED_WAITING` |
| `triage room` | Triage Room | `maze.py`, `triage_nurse.py` | `address_tiles["ed map:emergency department:triage room:chair"]` | 分诊 | `triage_capacity = chair 数` | `ED_TRIAGE` |
| `major injuries zone` | Major Injuries Zone | `maze.py`, `maze_status.json` | 可用床 `[11,2],[15,2],[19,2],[23,2],[27,2]` | 较重患者床位区 | 5 床 | `ED_MAJOR` |
| `minor injuries zone` | Minor Injuries Zone | `maze.py`, `maze_status.json` | 可用床 `[27,9],[27,11],[27,13],[27,15],[27,17]` | 轻中症床位区 | 5 床 | `ED_MINOR` |
| `trauma room` | Trauma Room | `maze.py`, `maze_status.json` | 可用床 `[16,14]` | CTAS 1/危重 | 1 床 | `ED_TRAUMA` |
| `diagnostic room` | Diagnostic Room | `maze.py`, `patient.py`, `maze_status.json` | diagnostic table 区域 | 检查 | 2 | `ED_DIAGNOSTIC` |
| `exit` | Exit | `patient.py`, `reverie.py` | `<spawn_loc>exit`，终点 `ed map:emergency department:exit` | 出院/离开 ED | 无 | `ED_EXIT` |
| `doctor_assessment_zone` | 未找到实体地图 | `api_v1.py` movement_suggestion | user mode 虚拟 zone | user mode 医生接诊引导 | 未找到 | `ED_DOCTOR_ASSESS` |
| `vitals_station` | 未找到实体地图 | `api_v1.py` movement_suggestion | user mode 虚拟 zone | 测量生命体征 | 未找到 | `ED_VITALS` |
| `triage_waiting_area` | 未找到实体地图 | `api_v1.py` movement_suggestion | user mode 虚拟 zone | 等待叫号 | 未找到 | `ED_WAITING` |
| ICU / Ward room | 未找到 | 未找到 | 未找到 | user mode 只做外部 handoff 文本 | 未找到 | 需接入 FullView ICU/WARD 房间 |

## 说明

- 可进入者主要由逻辑控制，不是显式 ACL。
- doctor 主要在 major/minor/diagnostic；
- triage nurse 在 triage room；
- bedside nurse 在 major/minor/diagnostic；
- patient 在 waiting/triage/各 injuries zone/diagnostic/exit。
- ICU/ward 目标房间在 EDMAS auto 地图中未找到。

# Patient States and Triage Levels

## 状态字段表

| 状态字段 | 示例值 | 产生位置 | 更新位置 | 前端读取位置 | 可映射的 FullView status |
| ---- | --- | ---- | ---- | ------ | -------------------- |
| `patient.scratch.state` | `WAITING_FOR_NURSE` | `patient_scratch.py` | `patient.py`, `bedside_nurse.py`, `doctor.py`, `reverie.py` | auto 通过 `movement/*.json.description`、`sim_status.json.patient_states` 间接读取 | `waiting_nurse` |
| `sim_status.patient_states` | `{"WAITING_FOR_NURSE":2}` | `reverie.py:_write_sim_status` | 每 step 更新 | `/api/live_dashboard/` | `aggregate_status` |
| `session["phase"]` | `INTAKE`, `WAITING_CALL`, `DOCTOR_CALLED`, `BED_NURSE_FLOW`, `DONE` | `_ensure_user_session` | `api_v1.py:user_mode_chat_turn`, `_maybe_auto_progress` | `/mode/user/session/status` | `workflow_phase` |
| `session["call_status"]` | `WAITING_FOR_TRIAGE`, `MEASURING_VITALS`, `WAITING_CALL`, `CALLED`, `IN_CONSULTATION`, `COMPLETED` | `_ensure_user_session` | `api_v1.py` | `/mode/user/session/status` | `call_status` |
| `session["current_agent"]` | `TRIAGE_NURSE`, `CALLING_NURSE`, `DOCTOR`, `BEDSIDE_NURSE` | `_ensure_user_session` | `api_v1.py` | `/mode/user/session/status` | `current_staff_role` |
| `_ENCOUNTERS[enc]["final_state"]` | `WAITING_FOR_PHYSICIAN`, `UNDER_EVALUATION`, `WARD`, `ICU` | `start_encounter` | `request_handoff`, `complete_handoff` 等 | `/ed/queue/snapshot` 间接；user session 也引用 | `encounter_state` |

## 常见 auto patient 状态

- `WAITING_FOR_TRIAGE`
- `TRIAGE`
- `WAITING_FOR_NURSE`
- `WAITING_FOR_FIRST_ASSESSMENT`
- `WAITING_FOR_TEST`
- `GOING_FOR_TEST`
- `WAITING_FOR_RESULT`
- `WAITING_FOR_DOCTOR`
- `WAITING_FOR_EXIT`
- `DISCHARGED_WAITING`
- `ADMITTED_BOARDING`
- `LEAVING`

来源：[`patient.py`](/home/jiawei2022/BME1325/week9/reverie/backend_server/persona/persona_types/patient.py)、[`patient_scratch.py`](/home/jiawei2022/BME1325/week9/reverie/backend_server/persona/memory_structures/scratch_types/patient_scratch.py)。

## 分诊等级表

| 字段 | 示例 | 来源文件 | 说明 |
| -- | -- | ---- | -- |
| `acuity_ad` | `A/B/C/D` | `triage_policy.py` | user mode 规则分级 |
| `level_1_4` | `1/2/3/4` | `triage_policy.py` | A-D 对应 1-4 |
| `ctas_compat` | `1/2/3/4` | `triage_policy.py` | CN_AD_TO_CTAS_COMPAT |
| `zone` | `red/yellow/green` | `triage_policy.py` | user mode 合同字段 |
| `Patient.scratch.CTAS` | `1..5` | auto patient scratch | auto mode 真实流转优先级 |
| `Patient.scratch.injuries_zone` | `trauma room` / `major injuries zone` / `minor injuries zone` | auto patient scratch / `diagnosis.csv` | auto mode 去向房间 |
| `diagnosis.csv.Zone` | `major injuries zone` 等 | `reverie/backend_server/data/diagnosis.csv` | auto 新患者初始化区域 |

## 当前 CTAS 逻辑总结

- user mode 明确使用 CTAS 兼容值，但只完整覆盖 1-4。
- auto mode 明确使用 1-5，且可由 `diagnosis.csv`、预置 patient、等待时间分布共同影响。
- chest pain、headache redflag、dyspnea、stroke、shock、anaphylaxis 等在 `triage_policy.py` 有特异规则。
- vitals 里已明确使用 `spo2`、`sbp`、`pain_score`。
- calling nurse 在 user mode 会补测 vitals，来源 `_nurse_measured_vitals` 调用链。
- 结论：当前 CTAS 逻辑足够支持 ED 内优先级，但不足以直接支持 FullView 跨科室规则，因为：
- 缺少统一 CTAS 1-5 全覆盖输出；
- auto / user 分诊标准不完全统一；
- ICU/ward/diagnostic 的跨科资源规则仍较弱。

# Movement Mechanism

## movement 推进链路

| 环节 | 文件路径 | 关键函数/变量 | 输入 | 输出 |
| -- | ---- | ------- | -- | -- |
| 前端发命令 | `translator/views.py` | `send_sim_command` | `{"command":"run 10"}` | `temp_storage/commands/cmd_<id>.json` |
| backend 轮询命令 | `reverie.py` | `open_server`, `cmd_dir.glob("cmd_*.json")` | command json | `sim_command` |
| 执行 run N | `reverie.py` | `open_server -> start_server(int_count)` | `run 10` | 推进 10 个 step |
| 每 step 读取前端位置 | `reverie.py` | `start_server`, `environment/<step>.json` / headless 构造 `new_env` | environment snapshot | backend tile 同步 |
| agent 推理/行动 | `patient.py`, `doctor.py`, `triage_nurse.py`, `bedside_nurse.py` | `move` | maze/personas/current tile | `next_tile`, state, next_step |
| 生成 movement payload | `reverie.py` | `_build_movement_persona_payload` | `persona`, `movement_path`, chat | `movements["persona"][name]` |
| movement 落盘 | `reverie.py` | `_atomic_write_json(curr_move_file, movements)` | `movements` | `movement/<step>.json` |
| curr_step 发布 | `reverie.py` | `_atomic_write_json(temp_storage/curr_step.json)` | 当前 step | `curr_step.json` |
| 前端取 movement | `translator/views.py` | `update_environment` | `{"step":x,"sim_code":"curr_sim"}` | 对应 movement json |
| 前端回写环境 | `translator/views.py` | `process_environment` | `{"step", "sim_code", "environment"}` | `environment/<step>.json` |

## movement 文件字段摘要

最新样例 `movement/9999.json` 顶层字段：

- `persona`
- `meta`

`persona.<name>` 关键字段：

- `schema_version`
- `role`
- `role_key`
- `badge`
- `movement`
- `movement_path`
- `path_length`
- `pronunciatio`
- `description`
- `chat`
- `dialogue_provenance`

`meta` 已确认至少包含：

- `curr_time`

## user mode 与 auto mode 是否共用 movement

- 不共用。
- auto mode 使用真实 `movement/*.json` 数据流。
- user mode 只返回 `movement_suggestion` 文本/虚拟 zone，没有写入 auto movement 文件。

## movement 是否反向影响 agent 状态

- 是。
- Reverie 每 step 会先把前端 `environment/<step>.json` 同步回 backend tile，再执行 persona `move`。
- 因此 movement 不只是可视化，也参与下一步状态推进。

## ICU/住院 movement 表达

- auto mode：未找到真实 `ED -> ICU` 或 `ED -> Ward` 地图 movement。
- auto mode 只有 `ADMITTED_BOARDING` 后再 `LEAVING -> exit`。
- user mode：有 `movement_suggestion` 指向 `bedside_transfer_zone`，但不是地图 movement。

# Disposition / Transfer / Discharge Logic

| 去向 | 当前是否实现 | 触发条件 | 相关文件 | 是否产生 movement | 是否可直接接入 FullView |
| ---------------- | ------ | ---- | ---- | ------------- | ---------------- |
| ED -> Diagnostic | 已实现 | `Patient.do_initial_assessment` 根据 `testing_probability_by_ctas` 决定 | `patient.py`, `doctor.py`, `meta.json` | 是 | 可以 |
| Diagnostic -> ED | 已实现 | `GOING_FOR_TEST` 到时后返回原 injuries zone bed | `patient.py` | 是 | 可以 |
| ED -> ICU | 部分实现 | user mode 中 `acuity A/B` 时 `request_handoff(target=ICU)`；auto 仿真未找到真实 ICU 地图 | `api_v1.py` | user mode 无真实 movement | 需适配 |
| ED -> Ward | 部分实现 | user mode 中 `acuity C` 时 `request_handoff(target=WARD)` | `api_v1.py` | user mode 无真实 movement | 需适配 |
| ED -> Discharge | 已实现 | auto `do_disposition` 非 admit 时 `WAITING_FOR_EXIT -> LEAVING -> exit`；user mode 低危完成 | `patient.py`, `api_v1.py` | auto 有；user mode 无真实 movement | 可以，但需统一事件 |
| Ward -> ICU | 未找到 | 未找到 | 未找到 | 未找到 | 不可直接接入 |
| ICU -> Ward | 未找到 | 未找到 | 未找到 | 未找到 | 不可直接接入 |

## 额外说明

- bed assignment 已实现，但仅限 ED 内床位，来源 `maze.py:assign_bed`。
- ICU/ward 目标房间未找到。
- user mode 的 ICU/ward 多是 handoff 文本 + HIS 事件，不是地图状态。
- auto mode 的“住院”是 `ADMITTED_BOARDING`，本质仍在 ED 床位等待。

# Resource and Bed State

| 资源/参数 | 示例值 | 来源 | 保存位置 | 是否动态变化 | 接入 FullView 时如何使用 |
| ----- | --- | -- | ---- | ------ | ----------------- |
| `doctor_starting_amount` | `30` | `meta.json`，可由 `save_simulation_settings` 覆盖 | `reverie/meta.json` | 启动时读取 | 映射 ED doctor 资源池 |
| `triage_starting_amount` | `20` | 同上 | 同上 | 启动时读取 | 映射 triage 护士资源池 |
| `bedside_starting_amount` | `1` | 同上 | 同上 | 启动时读取 | 映射 bedside nurse 资源池 |
| `add_patient_threshold` | `0.0` | `meta.json` / `save_simulation_settings` | 同上 | 运行时递增递减 | 可作为到诊流入率内部参数 |
| `preload_waiting_room_patients` | `0` | `meta.json` | 同上 | 启动时消费并清零 | 可用于初始候诊加载 |
| `fill_injuries` | `0` | `meta.json` | 同上 | 启动时消费 | 初始占床率 |
| major injuries zone capacity | `5` | `maze_status.json` / map tiles | `maze_status.json` | 可因 remove_beds / 分配变化 | 映射 ED major beds |
| minor injuries zone capacity | `5` | 同上 | 同上 | 动态 | 映射 ED minor beds |
| trauma room capacity | `1` | 同上 | 同上 | 动态 | 映射 resus bed |
| diagnostic room capacity | `2` | `meta.json: diagnostic_room_capacity/imaging_capacity`, `maze.py` | `meta.json`, `maze_status.json` | 动态 | 映射诊断室容量 |
| `lab_capacity` | `2` | `meta.json` | `meta.json`, `maze_status.json`, `sim_status.json.resources` | 动态占用 | 映射 lab 资源 |
| `imaging_capacity` | `2` | `meta.json` | 同上 | 动态占用 | 映射 imaging 资源 |
| `boarding_timeout_minutes` | `240` | `meta.json` | `meta.json`, `sim_status.json.resources` | 运行时用于 boarding 超时 | 映射 ED boarding SLA |
| `queues.triage` | `0` | `reverie.py:_write_sim_status` | `sim_status.json` | 动态 | 前端队列指标 |
| `queues.bedside_nurse_waiting` | `2` | 同上 | `sim_status.json` | 动态 | 床旁转运排队 |
| `queues.doctor_global` | `2` | 同上 | `sim_status.json` | 动态 | 医生候诊排队 |
| `nurse_status` | `Available:1` | `reverie.py` | `sim_status.json` | 动态 | staff resource status |
| `doctor_max_patients` | `5` | `meta.json` 默认，`reverie.py` 读取 | 运行内存 / `sim_status.json` | 动态使用 | 医生并发上限 |
| `simulate_hospital_admission` | `false` | `meta.json` | `meta.json` | 启动时读取 | 决定是否开启 admit boarding |

# EDMAS -> FullView Mapping Proposal

以下内容是建议，不是最终实现。

## patient 映射建议

- EDMAS auto `Patient N` 仅作为显示名。
- EDMAS user/HIS `P-xxxxxxxx` 作为 FullView `patient_id`。
- EDMAS `enc-...` 或 `E-...` 作为 FullView `context.edmas_case_id`。
- 建议新增字段：
- `external_patient_id`
- `external_encounter_id`
- `display_name`

## room 映射建议

| EDMAS room/location | 推荐 FullView room_id |
| -- | -- |
| waiting room | `ED_WAITING` |
| triage room | `ED_TRIAGE` |
| trauma room | `ED_TRAUMA` |
| major injuries zone | `ED_MAJOR` |
| minor injuries zone | `ED_MINOR` |
| diagnostic room | `ED_DIAGNOSTIC` |
| exit | `ED_EXIT` |
| doctor_assessment_zone | `ED_DOCTOR_ASSESS` |
| vitals_station | `ED_VITALS` |
| bedside_transfer_zone | `ED_TRANSFER_AREA` |

## event 映射建议

| EDMAS 事件/状态变化 | 推荐 FullView event_id | 说明 |
| ------------- | ------------------------------------ | -- |
| 患者进入急诊 | `admit` 或 `ED_PATIENT_ARRIVAL` | auto memory `encounter_started` 可映射 |
| 等待到分诊 | `ED_REGISTRATION_TO_TRIAGE_OR_WAITING` | `WAITING_FOR_TRIAGE` / user mode intake |
| 分诊到医生 | `ED_WAITING_TO_CONSULT_ROOM` | `DOCTOR_CALLED` 或进入 doctor queue |
| 医生开检查 | `ED_TO_DIAGNOSTIC_MOVE` | `WAITING_FOR_TEST` / `GOING_FOR_TEST` |
| 检查返回 | `ED_DIAGNOSTIC_RETURN` | `WAITING_FOR_RESULT` 返回床位 |
| 急诊转 ICU | `TRANSFER_ED_TO_ICU` | 目前主要来自 user mode handoff |
| 急诊转住院 | `TRANSFER_ED_TO_WARD` | 目前主要来自 user mode handoff |
| 急诊出院 | `ED_PATIENT_EXIT_HOSPITAL` | `WAITING_FOR_EXIT` / `LEAVING` |

# Missing Information and Risks

- 缺少稳定统一 patient_id：已确认。
- 缺少统一 external request adapter：已确认，当前只有 Django API + HIS adapter，未见专门 EDMAS -> FullView adapter。
- ICU/ward 没有真实 auto 地图状态：已确认。
- user mode 有 disposition 事件，但多为文本+handoff ticket；auto mode 更多是 ED 内 boarding：已确认。
- movement 与 clinical state 在 auto mode 强耦合，在 user mode 脱耦：已确认。
- user mode / auto mode 状态字段不一致：已确认。
- FullView 若要接入，需要新增 patient upsert：推测。
- FullView 若要接入，需要新增 EDMAS -> FullView adapter：推测。
- 需要补充临床规则，尤其 CTAS 5、跨科转运、ICU/ward 资源占用：已确认。
- `calling_nurse` 在 user mode 是逻辑角色，不是 auto persona：已确认。
- `receptionist`、`bed manager`、`diagnostic staff` 独立角色：未找到。
- ICU/ward 房间坐标、床位容量、可进入 agent：未找到。

# Files Inspected

- `environment/frontend_server/frontend_server/urls.py`
- `environment/frontend_server/translator/views.py`
- `environment/frontend_server/storage/curr_sim/reverie/meta.json`
- `environment/frontend_server/storage/curr_sim/reverie/maze_status.json`
- `environment/frontend_server/storage/curr_sim/reverie/maze_visuals.json`
- `environment/frontend_server/storage/curr_sim/sim_status.json`
- `environment/frontend_server/storage/curr_sim/personas/Patient 1/bootstrap_memory/scratch.json`
- `reverie/backend_server/reverie.py`
- `reverie/backend_server/run_simulation.py`
- `reverie/backend_server/maze.py`
- `reverie/backend_server/persona/persona.py`
- `reverie/backend_server/persona/persona_types/patient.py`
- `reverie/backend_server/persona/persona_types/doctor.py`
- `reverie/backend_server/persona/persona_types/triage_nurse.py`
- `reverie/backend_server/persona/persona_types/bedside_nurse.py`
- `reverie/backend_server/persona/memory_structures/scratch_types/patient_scratch.py`
- `app_core/app/api_v1.py`
- `app_core/app/mode_user.py`
- `app_core/rule_core/triage_policy.py`
- `app_core/rule_core/encounter.py`
- `app_core/rule_core/state_machine.py`
- `app_core/his/config.py`
- `app_core/his/adapters/contract_adapter.py`
- `runtime_data/memory/events.jsonl`

