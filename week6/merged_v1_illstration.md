# merged_v1 交接说明（Week6）

以下内容严格按队友建议顺序与当前实际完成度整理，便于接手同学快速了解现状。

## （1）任务自查（对照建议顺序）
**建议 1：保持 auto mode 可运行且对齐 baseline（不改核心渲染循环）**  
当前状态：未完成（0 分）  
现状：auto mode 启动时报 `meta.json not found`，页面无法进入；虽然没有改渲染循环，但运行链路不通。

**建议 2：新建独立 user_mode 前端面板组件（右侧 chat + 状态卡片）**  
部分完成（0.5 分）  
已新增独立 user mode 页面与样式、脚本，实现左右栏结构。
Python 直接调用 api_v1.py 的函数，它绕过了 HTTP 层，所以只证明逻辑可用，不代表前端能通过 HTTP 正常访问。

**建议 3：仅通过 /mode/user/ + /ed/ API 驱动 UI**  
已完成（1 分）  
前端 JS 已写好 API 调用链路；本地已完成 API 自检（Python 直调 /mode/user/* + /ed/*）。

**建议 4：增加前端状态机（INTAKE → WAITING_CALL → …）**  
部分完成（0.5 分）  
页面已显示 phase/role/queue/ETA，但没有做阶段驱动的 UI 行为差异。

**建议 5：最后做地图联动**  
未开始（0 分）  
当前未接地图，不做 movement suggestion 可视化（符合“最后再做”的顺序）。

---

## （2）当前已实现内容（按模块 + 文件路径）  
下面用“模块 → 路径 → 作用/流程”描述当前已实现功能。

### User Mode 前端入口  
- 路由：`week6/week6_interface/frontend_server/frontend_server/urls.py`  
  `/mode/user` → user mode 页面  
- View：`week6/week6_interface/frontend_server/translator/views.py`  
  `user_mode_home()` 渲染独立页面

### User Mode 页面结构  
- 模板：`week6/week6_interface/frontend_server/templates/home/user_mode.html`  
  左侧状态卡片 / 右侧聊天区  
- 样式：`week6/week6_interface/frontend_server/static_dirs/css/user_mode.css`  
- 脚本：`week6/week6_interface/frontend_server/static_dirs/js/user_mode.js`  
  调用 `/mode/user/session/status`、`/mode/user/chat/turn`、`/ed/queue/snapshot`  
  Start 按钮已改为 reset-only（走 `/mode/user/session/reset`）

### API 与对话自然化（LLM Response Layer）  
- 新模块：`week6/week5_system/app/response_generator.py`  
  `generate_response()` + `detect_language()`  
- 接入点：`week6/week5_system/app/api_v1.py`  
  将硬编码文本替换为 intent→response（不改规则/状态机）

---

## （3）出现过的 Bug 与规避方法
**Bug 1：Auto mode 启动报 meta.json not found**  
发生位置：`translator/views.py → save_simulation_settings()`  
原因：`storage/ed_sim_n5/reverie/meta.json` 不存在  
规避：从 baseline 拷贝  
`storage/ed_sim_n5/reverie/` 到  
`week6/week6_interface/frontend_server/storage/ed_sim_n5/reverie/`

**Bug 2：Django 运行时缺依赖（corsheaders / psutil）**  
规避：  
`python -m pip install -r week6/week6_interface/frontend_server/requirements.txt`  
或最小安装：  
`Django==2.2`、`django-cors-headers==2.5.3`、`psutil==7.0.0`

**Bug 3：浏览器打不开页面**  
原因：访问 `0.0.0.0:8000`  
规避：用 `http://127.0.0.1:8000/`

---

## （4）距离 Week 6 目标还差什么 + 面向 Codex 的 planning

### 还差什么（必须完成）
1. **Auto mode 可运行**  
当前卡在 meta.json，需补 baseline 数据。  
2. **前端状态机行为未落地**  
phase 显示已有，但 UI 没有按阶段切换内容/提示。  
3. **叫号流程可视化不足**  
queue/ETA 有，但缺“call-number 状态过程展示”。  
4. **角色视觉区分不足**  
已有颜色 + 标签，但缺 icon/一致性规范。  
5. **地图联动未开始**  
movement suggestion → zone 高亮尚未实现（仍需放在最后）。

### 面向 Codex 的 planning（模块级）
**A. 修复 auto mode（最高优先）**  
目标：确保 baseline auto mode 可启动  
模块/路径：  
将 baseline 数据拷贝到  
`week6/week6_interface/frontend_server/storage/ed_sim_n5/reverie/`  
验证：访问 `/start_simulation` 能成功保存配置

**B. API 自检（快速验证）**  
目标：确认 User Mode API 可用  
操作：  
`GET /mode/user/session/status`  
`POST /mode/user/chat/turn`  
`POST /mode/user/session/reset`  
不改后端，只跑接口

**C. User Mode 前端状态机落地**  
目标：phase 驱动 UI  
模块：`static_dirs/js/user_mode.js`  
增加：  
phase → 指令文本  
WAITING_CALL / DOCTOR_CALLED / BED_NURSE_FLOW 显示差异  
当前角色高亮/标识

**D. call-number 可视化**  
目标：queue/ETA + call 状态明确展示  
模块：`user_mode.html` / `user_mode.css`  
增加：  
叫号进度条或状态标识（Waiting → Called → In Consultation）

**E. 角色区分规范化**  
目标：四个角色一致性视觉  
模块：`user_mode.css` + `user_mode.html`  
增加：角色徽标 / icon / 标签色统一

**F. 地图联动（最后做）**  
目标：movement suggestion → target zone 高亮  
模块：新 `user_mode_map.js` 或扩展 `user_mode.js`  
不接 movement loop，仅静态高亮
