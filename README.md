## Week12 说明

### （1）上周内容回顾（Week10）

上周核心目标是把系统从“能跑”推进到“稳定可解释可追踪”。对应结果如下：

1. 前端 / UI Runtime Sync 稳定化  
   - 修复 Phaser 播放链路中 pointer 与 status step 漂移导致的停帧。  
   - 在 `/start_backend/...` 启动与轮询中加入 backend health 检测与 stale runtime 自愈。  
   - 提高 `curr_step.json`、`sim_status.json`、`movement/environment` 桥接文件消费鲁棒性。

2. 后端 Auto/User 融合与确定性控制  
   - 支持 `EDSIM_MODE=auto` 运行时同时打开 `?ui_mode=user` 交互。  
   - 通过既有 command bridge 将 user-patient 注入 auto 世界。  
   - 保持边界：auto 状态机仍规则驱动；user 仅在 doctor encounter 使用 doctor LLM + doctor-only RAG。

3. HIS “Write Everything” 基线  
   - auto/user 两种流程均写入 `sqlite_dev` HIS。  
   - 内部 ID 对齐：  
     - `patient_id`: `P-xxxxxxxx`（小写十六进制）  
     - `encounter_id`: `E-YYYYMMDDHHmmss-xxxx`  
   - 旧公开 ID（如 `enc-...`、`Patient 1`）保留在 `encounters.metadata.public_encounter_id` 作为映射字段。

4. 安全与密钥治理  
   - 代码库不再存储密钥。  
   - API Key 统一走 `.env` 注入。

### （2）本周完成任务（Week12）

本周重点是“结构化可追踪”与“前后端闭环证据化”。

1. 运行态隔离 + 可复现实验机制  
   - 新 run 会重置关键运行态文件，避免旧 movement/environment 回放污染。  
   - 运行期 trace 中持续记录 run 维度关键信号（含 run_id / step / lag / blocked_reason）。

2. 前后端数据协议修复（movement ↔ environment）  
   - `movement` 明确为“后端给前端的动作剧本”。  
   - `environment` 明确为“前端演完后的执行结果回写”。  
   - 补齐 step 契约检查脚本，定位“后端已产出 vs 前端是否已消费/回写”。

3. 系统可观测性（Observability）增强  
   - 运行态从“黑盒”转为可检查：runtime trace、step contract、movement/environment 文件三套证据可交叉验证。  
   - 增加对 lag 与阻塞原因的可解释输出，支持 demo 场景定位。

4. Dashboard 指标论证能力  
   - Dashboard 不只是 UI 展示，而是把后端状态机、队列系统、资源占用映射为可解释指标：  
     - Patient State Distribution：患者处于哪个流程状态。  
     - Zone Occupancy：各区当前占用与容量。  
     - Queue Sizes：分诊、床旁护士、医生全局、Lab/Imaging 等待队列长度。  
     - Nurse Utilization：护士工作类型分布（Monitoring/Transferring/Resting/Available）。  
     - Doctor Load：各医生当前挂载患者/任务负载。  
   - 结合地图 movement 与 environment 回写，可解释“为什么某角色移动/停留”以及“当前瓶颈在哪”。

### （3）下一步优化目标

1. 系统层 step 设计（长时序）  
   - 目标：缩小 `run 100` 逻辑推进与前端渲染体感之间的差距。  
   - 方向：细化 step 粒度与播放节奏控制，让长时间线既真实又流畅可读。

2. 前端人物徘徊行为解释与优化  
   - 目标：减少“看起来无意义来回走”带来的误判。  
   - 方向：把 idle rounding / standing by / waiting 状态在 UI 侧显式化，并与 movement_path、description、scratch state 一致呈现。

3. 患者初始到达机制优化  
   - 目标：从“碎片化到达”改进为可配置、可论证的到达模式。  
   - 方向：先梳理 arrival policy（normal/surge/burst 与 CTAS 结构），再优化 auto mode 初始化参数，使资源瓶颈与系统运转更清晰可见。

---

## Removed / Pruned (Not Required for Running)

To reduce size and noise, the following non-runtime directories were removed:
- `environment/react_frontend/` (React + R3F viewer; not used by the main UI)
- `app_core/RAG/refs/` (reference repos snapshot; not needed at runtime)
- `tests/`, `tests_his/`, `tests_user/`
- `docs/`, `analysis/`, `examples/sample_statistics/`
- runtime artifacts and caches (e.g. `__pycache__/`, exported data bundles)

## How To Run

### 1) Install Python Dependencies

From the repo root (`week9/`):
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r environment/frontend_server/requirements.txt
```

### 2) Configure Secrets (.env)

Create `.env` in the repo root (already supported by the team workflow) and load it before starting:
```bash
set -a
source .env
set +a
```

Minimum required variables (example names; any one of the key variants is acceptable):
- Model key: `OPENAI_KEY` or `OPENAI_API_KEY` or `EDSIM_MODEL_KEY`
- Model endpoint: `OPENAI_ENDPOINT` or `EDSIM_MODEL_ENDPOINT`
- Model name: `OPENAI_MODEL` or `EDSIM_MODEL`
- (Optional) Embeddings: `EMBEDDINGS_KEY`, `EMBEDDINGS_ENDPOINT`, `EMBEDDINGS_MODEL`

### 3) Start Django UI Server

```bash
export EDSIM_MODE=auto
export HIS_DB_BACKEND=sqlite_dev
export ENABLE_LLM_AGENTS=1
cd environment/frontend_server
python manage.py runserver 127.0.0.1:8010
```

Open UI:
- Auto UI: `http://127.0.0.1:8010/simulator_home?ui_mode=auto`
- User UI (hosted on auto runtime): `http://127.0.0.1:8010/simulator_home?ui_mode=user`

### 4) Start Auto Simulation Backend (reverie)

From the UI, use the "start simulation" flow, or directly call:
```bash
curl -X POST "http://127.0.0.1:8010/start_backend/ed_sim_n5/curr_sim/?headless=1"
```

Notes:
- `headless=1` is recommended for reliable step progression (movement frame generation).
- The UI writes commands to `environment/frontend_server/temp_storage/commands/`.

### 5) Running Steps

In the UI command box, use:
- `run 10`
- `run 100`

If the UI does not move while the backend claims it ran steps:
- Check `environment/frontend_server/storage/curr_sim/movement/` is producing new `<step>.json` frames.
- Check `environment/frontend_server/storage/curr_sim/sim_status.json` is updating.

## HIS Output Location

Default SQLite dev DB:
- `data/his_dev.sqlite3`

Quick inspection:
```bash
sqlite3 data/his_dev.sqlite3 ".tables"
sqlite3 data/his_dev.sqlite3 "SELECT encounter_id, payload FROM encounters ORDER BY rowid DESC LIMIT 5;"
sqlite3 data/his_dev.sqlite3 "SELECT payload FROM event_registry ORDER BY rowid DESC LIMIT 10;"
```

## Repo Layout (Runtime-Relevant)

- `environment/frontend_server/`: Django + Phaser UI and runtime bridge (start backend, send commands, runtime pointers).
- `reverie/backend_server/`: Auto-mode simulation runtime (`reverie.py`, persona system, queues, movement output).
- `app_core/app/`: User-mode interactive API and doctor LLM/RAG integration.
- `app_core/his/`: HIS schemas/services/storage (SQLite dev backend by default).
- `RAG/doctor_kb/`: doctor-only local KB content used by user-mode doctor RAG.
