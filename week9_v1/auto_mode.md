# Auto Mode 渲染与 Debug 说明

## 1. 渲染总链
auto mode 的页面不是一个“纯静态地图页”，而是一条由 Django 模板、Phaser 渲染和 backend movement 文件共同驱动的回放链。

完整链路是：

1. 浏览器打开 `/simulator_home?ui_mode=auto`
2. `translator/views.py -> home()` 读取：
   - `temp_storage/curr_sim_code.json`
   - `temp_storage/curr_step.json`
   - `storage/<sim_code>/environment/*.json`
   - `storage/<sim_code>/movement/*.json`
   - `storage/<sim_code>/sim_status.json`
3. `home()` 把以下上下文注入模板：
   - `persona_init_pos`
   - `render_step`
   - `playback_step`
   - `runtime_sources`
4. `home.html` 负责：
   - 命令输入框 `run 100`
   - Command Console
   - runtime 说明区
   - 注入 `auto_main_script.html`
5. `auto_main_script.html` 用 Phaser：
   - 先按 `persona_init_pos` 画出当前环境快照
   - 再轮询 `live_dashboard_api`
   - 当 `latest_movement_step >= playback_step` 时才请求 `/update_environment/`
   - 收到 `movement/<playback_step>.json` 后执行 `execute -> process`
6. backend `reverie.py` 负责：
   - 读取 `/send_sim_command/` 写入的命令
   - 执行 `run N`
   - 写出 `movement/<step>.json`
   - 更新 `sim_status.json`
   - 在 run 命令结束后更新 `curr_step.json`

## 2. 关键文件分别做什么
- `environment/frontend_server/translator/views.py`
  - 负责决定页面初始上下文
  - 决定 `render_step` 和 `playback_step`
  - 暴露 `live_dashboard_api`

- `environment/frontend_server/templates/home/home.html`
  - 负责 UI 外壳、命令行、状态说明、终端输出
  - `run 100` 通过 `/send_sim_command/` 发给 backend

- `environment/frontend_server/templates/home/scripts/auto_main_script.html`
  - 负责 Phaser 地图、人物创建、movement_path 回放
  - 负责 runtime status gating
  - 负责 `window.__EDSIM_DEBUG__`

- `reverie/backend_server/reverie.py`
  - 真正消费 `run 100`
  - 写 `movement/*.json`、`sim_status.json`、`sim_output.json`

## 3. 角色 PNG、profile 头像、walking sprite 的关系
- `assets/characters/*.png`
  - 这是地图主人物本体使用的 spritesheet
  - 现在 Doctor / Triage Nurse / Bedside Nurse / Patient 都直接用这些 PNG 在地图里走动
- `assets/characters/profile/*.png`
  - 这是侧边面板和头顶小徽标用的头像资源
  - 不负责 walking 动画
- 当前映射规则：
  - `doctor -> Doctor_1`
  - `triage_nurse -> Triage_Nurse_1`
  - `calling_nurse -> Triage_Nurse_1`
  - `bed_nurse -> Bedside_Nurse_1`
  - `patient -> Patient_1`
  - 额外 patient fallback -> `Patient_2`

## 4. 为什么以前一打开页面人物就会动
旧规则里，`home()` 会把前端 step 强行对齐到已有 `movement/*.json` 的最新 step。  
而 `auto_main_script.html` 一加载就立刻进入：

`update -> execute -> process`

所以只要磁盘里已经存在旧的 `movement/<step>.json`，页面就会把它再播放一遍，看起来像“还没 run 100，人自己先动了”。

这次修复后：

- 页面打开时只渲染 `environment/<render_step>.json`
- `playback_step = render_step + 1`
- 只有 backend 真正产出下一步 movement 时才继续动画

## 5. 为什么 `run 100` 时只看到 `/update_environment 200 14`
这通常不是 HTTP 错误，而是“前端请求成功了，但当前 step 没有 movement 文件”。

`/update_environment/` 的默认返回体类似：

```json
{"<step>": -1}
```

长度很小，所以终端里只看到反复的 `200 14`。

这背后的根因通常是：

- 前端盯错了 playback step
- backend 还没把 movement 写到这个 step
- backend 在跑，但前端只看 `curr_step.json`

正确理解是：

- `sim_status.json`：主进度源
- `movement/<step>.json`：地图执行源
- `environment/<step>.json`：位置快照
- `curr_step.json`：指针 / 启动握手，不是 live progress 真来源

## 6. 为什么有时 `run 100` 完全不动
如果当前页面里输入了 `run 100`，但：

- `temp_storage/commands/` 里命令文件一直堆着
- `sim_status.json` 不推进
- `movement/1.json+` 没出现

那就不是前端动画问题，而是 backend 没有真正消费命令。

现在页面会通过 `live_dashboard_api -> backend_health` 区分两种状态：

- `waiting for backend progress`
  - backend 活着，但新 movement 还没到当前 playback step
- `backend not consuming commands`
  - 命令在 `commands/` 里积压，但没有健康 reverie backend 在消费

## 7. 现在的初始化规则
- `render_step = latest_environment_step`
- `playback_step = render_step + 1`
- 首屏只画环境，不重播历史 movement
- 前端先看 `live_dashboard_api.runtime_sync`
- 只有当 `latest_movement_step >= playback_step` 时才请求 `movement/<playback_step>.json`

## 8. Debug 时优先看什么
先按这个顺序排查：

1. `live_dashboard`
   - 看 `status_step`
   - 看 `latest_movement_step`
   - 看 `curr_step_pointer`
   - 看 `in_sync`

2. 浏览器控制台里的 `window.__EDSIM_DEBUG__`
   - `renderStep`
   - `playbackStep`
   - `runtimeSync`
   - `personas`
   - `movement`

3. `sim_output.json`
   - backend 是否真的消费了 `run 100`

4. 磁盘文件是否同步
   - `movement/<step>.json`
   - `environment/<step>.json`
   - `sim_status.json`

## 9. 目前修复后的预期行为
- 打开 auto mode 页面时：
  - 人物应静止在当前环境快照
  - 不应自动重播历史 movement

- 输入 `run 100` 后：
  - 前端应先从 runtime status 看 backend 是否推进
  - movement 到达对应 step 后再开始动画
  - 如果 backend 还没推进，页面会显示 waiting for backend progress，而不是只刷空轮询

- 打开 user / auto mode 地图时：
  - Doctor / TN / BN / Patient 会直接使用对应角色 PNG 当地图主体
  - 面板头像、地图主体、头顶徽标都由同一个 `roleKey` 驱动



```bash
# 启动网关
cd D:\projects\BME1325Spring2026\BME1325_Group_One_Repo\_tmp_week9_cleanup\week9_v1\environment\frontend_server
conda activate edmas

$env:LLM_MODE="local_only"
$env:EMBEDDING_MODE="local_only"
$env:ENABLE_LLM_AGENTS="0"

python manage.py runserver 127.0.0.1:8010 --noreload
```


```txt
http://127.0.0.1:8010/simulator_home?ui_mode=auto
http://127.0.0.1:8010/simulator_home?ui_mode=user
```

```bash
cd D:\projects\BME1325Spring2026\BME1325_Group_One_Repo\_tmp_week9_cleanup\week9_v1
conda activate edmas
# 启动backend
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8010/start_backend/ed_sim_n5/curr_sim/?headless=1"

# 跑命令
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8010/send_sim_command/" `
  -ContentType "application/json" `
  -Body '{"command":"run 10"}'
```