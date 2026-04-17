# Week 6 Interface Handover README

## 1) 交付目的
这份文档用于把 `week5_edmas/week6_interface` 交接给下一位开发者，说明：
- 已实现了什么（精确到文件路径）
- 哪些接口已经可用
- 你当时对 User Mode 的详细要求
- 实际构建步骤
- 出现过的 Bug 与规避方法
- 距离 Week 6 目标还差什么
- 现在如何运行后端和打开前端

---

## 2) 当前已实现内容（按模块 + 文件路径）

### 2.1 Week 5 核心逻辑（被 Week 6 复用）
- 分诊与状态机：
  - `week5_system/rule_core/triage_policy.py`
  - `week5_system/rule_core/state_machine.py`
  - `week5_system/rule_core/encounter.py`
- User encounter 入口：
  - `week5_system/app/mode_user.py`
- Week 6 L1 API + User session/handoff runtime：
  - `week5_system/app/api_v1.py`

核心结论：Week 6 接口并不是重写分诊系统，而是把 Week 5 的确定性规则流封装成可调用 API。

### 2.2 Week 6 前端接口工程（基于 EDSim baseline 复制）
复制并落地的 baseline 前端目录：
- `week6_interface/frontend_server/frontend_server`
- `week6_interface/frontend_server/translator`
- `week6_interface/frontend_server/templates`
- `week6_interface/frontend_server/static_dirs`

### 2.3 已实现的关键适配代码
1. 后端目录自适配（避免固定路径崩溃）
- `week6_interface/frontend_server/translator/views.py`:
  - `_resolve_backend_dir()`（约 42 行）
  - `start_backend()`（约 542 行）

2. `/simulator_home` 启动前状态保护（避免 `curr_sim_code.json` 缺失直接抛异常）
- `week6_interface/frontend_server/translator/views.py`:
  - `home()`（约 145 行起）

3. stale step 保护（避免前端一直 loading）
- `week6_interface/frontend_server/translator/views.py`:
  - `home()` 内 movement step 对齐逻辑（约 207-222 行）

4. Week 6 API HTTP 层（Django）
- `week6_interface/frontend_server/frontend_server/urls.py`:
  - 45-51 行（API 路由）
- `week6_interface/frontend_server/translator/views.py`:
  - 788 行后（各 API view 函数）

---

## 3) `week6_interface` 已实现接口清单

接口契约文档：
- `week6_interface/api_contract_week6.md`

已接入 URL：
- `POST /mode/user/encounter/start`
- `POST /mode/user/chat/turn`
- `GET /mode/user/session/status`
- `POST /mode/user/session/reset`
- `POST /ed/handoff/request`
- `POST /ed/handoff/complete`
- `GET /ed/queue/snapshot`

路由位置：
- `week6_interface/frontend_server/frontend_server/urls.py` (45-51 行)

业务实现位置：
- `week5_system/app/api_v1.py`

说明：
- `encounter/start`、`handoff/*`、`queue/snapshot` 是你明确要求的 L1 接口。
- 另外补了 `chat/turn`、`session/status`、`session/reset`，用于把 User Mode 对话态封装成 API。

---

## 4) 你当时对 User Mode 的原始要求（关键摘录）

以下摘录来自会话历史（session: `019d51d8-33f1-7be3-8869-5d7c72ac5af3`）：

1. 模式定义
- 你要求 `user mode` 是“真实用户在前端输入主诉，triage 根据症状交互”，不是纯患者状态模拟。
- 你要求 `auto mode` 保持 baseline 的多 agent 自动仿真。

2. 前端交互目标
- 右侧聊天框输入主诉。
- 信息缺失时，分诊护士追问，直到足以分诊。
- 输出下一步移动建议（用户按建议在地图移动）。
- 显示排队信息：前方人数、预计等待时间、叫号流程。
- 被叫号后切换医生对话，诊断后如需住院由 bed nurse 安排。
- 其他 agent 的话术、动作指导、诊断意见都在聊天框输出。
- 地图中患者小人同步移动。

3. 入口与布局要求
- 首页要有 `auto` / `user` 两个选项。
- 选择 `user` 才显示对话区；选择 `auto` 走 baseline 风格。
- 你明确反馈过 user 模式长宽比异常（地图太小、下方区域过长）。

4. 集成目标
- 要和 ICU / 门诊等外部子系统对接（handoff）。

### 4.1 原始 prompt 片段（原文摘录）
以下原文用于避免需求二次转述失真：

```text
我所说的user mode并不是一个患者的输入和状态模拟，而是用户可以通过前端的交互页面，模拟自己是一名患者，来到急诊室告诉triage自己的主诉，更好triage will act according to my symptoms, 而auto mode则是多agent自己交互仿真，就类似于EDSim baseline中已经实现的那样
```

```text
补前端的界面，在界面右侧出现一个聊天框，在聊天框里我需要输入自己的主诉，如果信息缺失，分诊护士需要进一步询问，指导提供能够进行分诊的完整信息，然后给出下一步的移动建议，我会根据这个建议在地图中移到相应的位置，并且聊天框里面要显示我大概还要多久才能排到，如果排到我了，就换成医生来给我对话，医生诊断好以后，假如我还要去祝病床，那就由bed nurse进行安排，我的小人同步移动，但是其他agent的所有输出，他们的说的话，指导我进行的动作，诊断意见，都应该在聊天框中进行输出，在地图中，我的患者小人会进行相应的移动
```

```text
...there should be a call-number workflow just like in real hospital...
```

```text
现在在开始的http://127.0.0.1:8000/应该有两个选项，一个是auto一个是user，如果选择user，在右栏开启对话果，如果选择auto，那么就让agent自己交互，不用显示对话框，和Baseline的效果相似，而且现在user模式的长宽比太奇怪了，下面显示loading的框非常长，上面的地图很小
```

---

## 5) 实际构建步骤（已执行过的工程路径）

1. 先复用 baseline（不从 0 重写）
- 将 EDSim baseline 的 Django 前端工程复制到 `week6_interface/frontend_server`。

2. 在 Week 5 规则核心上建立 Week 6 L1 API
- 在 `week5_system/app/api_v1.py` 增加 encounter/handoff/queue 的内存态 API 运行时。

3. 通过 Django `translator/views.py` 暴露 HTTP 接口
- API 路由统一挂到 `frontend_server/urls.py`。

4. 增补 User Mode 会话 API
- `chat_turn/status/reset` 形成会话式 API，支撑后续前端聊天窗。

5. 处理前后端目录和启动兼容
- `_resolve_backend_dir()` 支持在 `week5_edmas` 下寻找 baseline 后端。

6. 增补回归测试
- `tests/test_week6_l1_api.py`
- `tests/test_week6_user_mode_chat.py`

当前测试状态：
- 在 `week5_edmas` 根目录执行 `pytest -q` -> `19 passed`。

---

## 6) 出现过的 Bug、原因与规避办法

### Bug A: `meta.json not found`
现象：启动时保存配置失败，报 `meta.json not found`。
原因：`storage/ed_sim_n5/reverie/meta.json` 尚未准备或工作目录不对。
规避：
- 必须从 `week6_interface/frontend_server` 目录运行 Django。
- 确保 `storage/ed_sim_n5/reverie/meta.json` 存在。

### Bug B: `Backend directory not found .../week5_edmas/reverie/backend_server`
原因：硬编码路径与实际仓库布局不一致。
已做：
- `views.py::_resolve_backend_dir()` 增加多候选路径。
规避：
- 新增环境时继续把真实后端路径加入候选列表。

### Bug C: `/simulator_home` 报 `curr_sim_code.json` 缺失
原因：前端页面在后端写入 temp_state 前被访问。
已做：
- `home()` 先检查 `temp_storage/curr_sim_code.json`、`curr_step.json`，否则返回错误页。
规避：
- 必须先启动 backend，再访问 `/simulator_home`。

### Bug D: `Live: loading...` 长时间不结束
原因之一：`curr_step` 与现有 movement 帧不一致，前端轮询不到对应 step。
已做：
- `home()` 中增加 movement step 对齐逻辑。
规避：
- 重启新仿真前清理旧 temp 状态。
- 确认 `storage/<sim_code>/movement/*.json` 持续增长。

### Bug E: 代理导致本机 127.0.0.1 不通
症状：浏览器/请求走代理，访问本地端口异常。
规避：
```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
export NO_PROXY=127.0.0.1,localhost
```
（在运行服务的远程会话里设置）

### Bug F: User 模式角色渲染错乱（重复 patient、角色图标对不上）
状态：历史中出现过（如 12 个 `patient 1`、角色数量异常）。
原因：
- persona 渲染与 movement 载入状态耦合，且当时 user/auto 分支未完全隔离。
规避建议：
- 先固定 auto 模式渲染正确，再增量接入 user 层 UI。
- 明确 `persona_id -> sprite` 单一映射，不允许模板层重复渲染。
- 引入前端快照测试（至少校验唯一 persona key）。

---

## 7) 距离 Week 6 目标还差什么（必须做）

1. `auto/user` 双模式入口仍未完整落地
- 当前 `home()` 支持 `ui_mode` 参数，但 landing/start 页还没有稳定的双入口 UX。

2. User Mode 聊天框与地图联动尚未完成到你要求的粒度
- 后端 API 已有，但前端还缺：
  - 固定右栏聊天 UI
  - call-number 可视化流程
  - 会话阶段驱动的地图动作提示与角色切换展示

3. 角色可视化区分不充分
- 你要求“四个 agent 清晰区分”尚未完全达标（图标/颜色/标签一致性需要收敛）。

4. 与外部系统联调仍是 mock 层
- 目前 handoff 是本地 ticket 生命周期，不是和 ICU/门诊真实服务联调。

---

## 8) 下一位开发者建议的最小实施顺序

1. 保持 auto mode 可运行且视觉对齐 baseline（先不要改动核心渲染循环）。
2. 新建独立 `user_mode` 前端面板组件（右侧 chat + 状态卡片）。
3. 仅通过 `/mode/user/*` + `/ed/*` API 驱动 user UI，不直接改 reverie movement 内部结构。
4. 增加前端状态机：`INTAKE -> WAITING_CALL -> DOCTOR_CALLED -> BED_NURSE_FLOW -> DONE`。
5. 最后做地图联动（movement suggestion -> target zone 高亮/路径提示）。

---

## 9) 运行手册（给从未接触项目的人）

### 9.1 环境
- Python: 3.9
- Conda env: `edsim39`

### 9.2 先启动前端（Django）
```bash
cd /home/jiawei2022/BME1325/week5_progress/EDMAS/edmas/week5_edmas/week6_interface/frontend_server
source ~/.bashrc
conda activate edsim39
python manage.py runserver 0.0.0.0:8000
```
访问：
- `http://127.0.0.1:8000/`
- 启动仿真页：`http://127.0.0.1:8000/start_simulation/`

### 9.3 再启动后端（reverie）
新开终端：
```bash
cd /home/jiawei2022/BME1325/week5_progress/EDMAS/edmas/week5_edmas
source ~/.bashrc
conda activate edsim39
cd week5_system/simulation_loop
python reverie.py --frontend_ui yes --origin ed_sim_n5 --target curr_sim
```

### 9.4 前端地图页
- `http://127.0.0.1:8000/simulator_home`

### 9.5 后端交互命令
在后端终端输入：
- `run 10`（推进 10 步）
- `run 100`（推进 100 步）
- `fin`（保存并退出）

### 9.6 API 自检（可选）
```bash
# queue snapshot
curl http://127.0.0.1:8000/ed/queue/snapshot

# user chat turn
curl -X POST http://127.0.0.1:8000/mode/user/chat/turn \
  -H 'Content-Type: application/json' \
  -d '{"message":"chest pain, spo2 93 sbp 88"}'
```

### 9.7 测试
```bash
cd /home/jiawei2022/BME1325/week5_progress/EDMAS/edmas/week5_edmas
pytest -q
```

---

## 10) 关键文件索引（交接必看）
- 接口契约：`week6_interface/api_contract_week6.md`
- HTTP 路由：`week6_interface/frontend_server/frontend_server/urls.py`
- HTTP 视图：`week6_interface/frontend_server/translator/views.py`
- L1 API 业务：`week5_system/app/api_v1.py`
- User encounter 入口：`week5_system/app/mode_user.py`
- Week 6 接口测试：
  - `tests/test_week6_l1_api.py`
  - `tests/test_week6_user_mode_chat.py`
