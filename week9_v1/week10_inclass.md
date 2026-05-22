# Week10 In-class Progress (Auto Mode + UI/HIS)


## 2. 本周前端 UI 输出进度（前后端如何推动与交互）

### 2.1 前后端实时链路（Auto/User 共通核心）
1. 后端写 `movement/<step>.json`（含 `movement_path`）。
2. 前端 `update` 阶段请求 `/update_environment/` 拉取该 step movement。
3. 前端 `execute` 阶段按 `movement_path` 逐格移动并播放 walk 动画。
4. 前端 `process` 阶段回写 `/process_environment/`，产出 `environment/<step>.json`。
5. 进入下一步循环。

### 2.2 本周已落实的关键修复
- `process_environment` 接口硬化：
  - 非 POST -> `405 JSON`
  - 非法 JSON -> `400 JSON`
  - 缺字段/类型不合法 -> `400 JSON`
  - 写盘失败 -> `500 JSON`
  - 成功 -> `200 {"ok":true,"step":...,"sim_code":...}`
- 前端状态机修复（auto + user）：
  - `process_environment` 请求统一 `Content-Type: application/json`
  - `load` 回调不再“无条件推进”，必须检查 HTTP 状态和 `ok:true`
  - 失败时停留在 `process` 并短退避重试
- 可观测性增强：
  - `window.__EDSIM_DEBUG__` 增加：
    - `lastProcessStatus`
    - `lastProcessError`
    - `processRetryCount`
  - Auto 页面增加“environment write-back lag”提示（movement 步号持续领先 environment 时告警）

## 3. Auto mode 如何写入 HIS（工程实现）

### 3.1 运行事件产生
- Auto runtime 在 `reverie/backend_server/reverie.py` 驱动模拟步进。
- `auto_memory_hooks.py` 在关键节点写 Memory v1 事件：
  - `encounter_started`
  - `resource_bottleneck`
  - `handoff_requested`
  - `handoff_completed`
  - `encounter_closed`

### 3.2 Memory -> HIS 持久化桥接
- `app_core/his/adapters/runtime_bridge.py` 负责把 runtime 事件与快照写入 HIS 服务层。
- `app_core/his/adapters/memory_adapter.py` 负责结构映射与写入计划，落到：
  - `event_registry`
  - `handoff_snapshots`
  - `clinical_documents`
  - `audit_logs`

### 3.3 导出链路
- user-mode: `export_timeline_bundle(encounter_id)`
- auto-mode: `export_auto_timeline_bundle(...)`
- 导出同时写 timeline document + registry + audit，确保可追溯。

## 4. 还有哪些内容（本周剩余风险与下一步）

### 4.1 当前剩余风险（你现在看到的核心）
- 当 `backend_health.stalled=true` / `backend_alive=false` 时：
  - 前端即使接口正常，也会“等不到新 movement”，人物不会继续动。
- 这不是 UI 渲染 bug，而是 runtime 消费命令链中断。

### 4.2 什么时候算“回到同步阶段”
- 需要同时满足：
  - `backend_health.backend_alive = true`
  - `backend_health.stalled = false`
  - `pending_command_count` 不持续积压
  - `runtime_sync.latest_environment_step` 跟随 movement 持续增长

### 4.3 本周测试进度
- 新增/扩展 Django 端点与同步测试（`tests/frontend/test_views.py`）。
- 本地快速回归结果：`16 passed`（目标用例已通过）。

---

## 附：你关心的“能力边界”一句话版
- **通信层修复**：已完成（不再 Debug HTML 500，改为结构化 JSON）。
- **角色图区分**：代码已接入（Doctor/Triage/Bedside/Patient PNG spritesheet + avatar 映射）。
- **不穿墙**：依赖 `movement_path` 逐格回放，机制已在前端消费层启用。
- **是否“现在一定能看见稳定移动”**：取决于 backend 是否健康消费命令；若 runtime stalled，前端只能等待。

