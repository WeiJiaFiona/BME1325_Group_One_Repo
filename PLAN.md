# Week7 独立副本实施计划

## Summary
本周的唯一原则已经锁定：**直接复制 baseline 和 week6 的文件到 `week7_auto`，不自己重写，不保留任何对原始 `resources` 目录的运行时依赖，也不使用外部路径导入。**  
执行目标分成两段：

- 第一段先把 `week7_auto` 做成一个**完整独立副本**，仅靠 `week7_auto` 自己就能启动 baseline auto mode，并叠加 week6 的 UI / 接口增强。
- 第二段再在这个独立副本里继续做 Week7 的 Auto Mode + Resource Realism 功能。

后续实施必须按“小任务 -> 对应测试 -> 结果说明”的节奏推进。每一小任务完成后，都要立即运行该任务对应的最小验证，并记录：
- 测试命令或测试方式
- 预期结果
- 实际结果
- 若失败，阻塞点和下一步修复动作

## Implementation Changes
### 1. 先把 `week7_auto` 变成独立运行副本
第一批任务只做“复制与落位”，不做功能开发。

- 清理 `week7_auto` 当前的占位目录，使它不干扰最终运行结构。
- 从 `EDSim-main` 直接复制完整运行骨架到 `week7_auto`：
  - `analysis/`
  - `environment/frontend_server/`
  - `reverie/`
  - `tests/`
  - `run_backend.sh`
  - `run_backend_automatic.sh`
  - `run_frontend.sh`
  - `requirements.txt`
  - `pytest.ini`
- 从 `EDSim-threejs` 直接复制到 `week7_auto`：
  - `environment/react_frontend/`
  - `run_map_viewer.sh`
- 从 `week6_final_ui/week6` 直接复制到 `week7_auto`：
  - `week5_system/`

这一阶段的结果要求是：  
`week7_auto` 内部已经有 baseline 主干、threejs 参考前端、week6 逻辑模块，且它们都已经是本地副本，不再依赖原目录。

对应小任务测试：
1. 目录结构检查  
   结果说明要确认 `week7_auto` 下是否已经存在上述目录和脚本。
2. 外部依赖扫描  
   结果说明要确认 `week7_auto` 内部没有硬编码引用原始 `D:\projects\...\resources\...` 路径。

### 2. 把 week6 的增强前端覆盖到 `week7_auto`
这一阶段只允许“复制覆盖”，不允许手写重构。

需要直接从 `week6_final_ui/week6/week6_interface/frontend_server` 复制覆盖到 `week7_auto/environment/frontend_server` 的增强文件包括：

- `translator/views.py`
- `frontend_server/urls.py`
- `templates/landing/landing.html`
- `templates/home/start_simulation.html`
- `templates/home/home.html`

如果这些文件在运行时还依赖 week6 中的少量配套文件，也必须继续采取同样策略：
- 先发现依赖
- 直接从 week6 对位复制进 `week7_auto`
- 不自己新写替代逻辑
- 不让运行时回去读取 week6 原目录

这一阶段的结果要求是：  
`week7_auto` 的 Django 前端已经带上 week6 的 `ui_mode=user`、`/mode/user/*`、`/ed/*` 等增强入口，但运行根仍然是 `week7_auto/environment/frontend_server`。

对应小任务测试：
1. 路由与模板文件存在性检查  
   结果说明要确认覆盖文件已经在 `week7_auto` 对位位置。
2. 静态导入检查  
   结果说明要确认这些覆盖文件没有残留对原始 week6 外部目录的运行时依赖。
3. Django 最小导入检查  
   结果说明要确认前端模块至少可以完成最小导入或 URL 配置加载，不出现立刻的模块缺失错误。

### 3. 固定 `storage/` 和 `temp_storage/` 只在 `week7_auto` 内部使用
这一部分是运行成败关键，必须单独作为任务处理。

唯一合法的运行态目录位置固定为：

- `week7_auto/environment/frontend_server/storage/`
- `week7_auto/environment/frontend_server/temp_storage/`

它们必须来自 baseline 的直接复制，并作为 week7 的正式运行态目录。  
week6 中对应目录只用于识别 week6 是否有额外依赖文件；如果有需要，也必须复制进 `week7_auto/environment/frontend_server/`，不能保留外链。

这一阶段的结果要求是：

- `storage/curr_sim`
- `storage/ed_sim_n5`
- `temp_storage/commands`
- `temp_storage/curr_sim_code.json`
- `temp_storage/curr_step.json`
- `temp_storage/sim_output.json`

这些都已经位于 `week7_auto` 内部，并且 baseline / week6 增强链路读取的都是这一份。

对应小任务测试：
1. 运行态目录完整性检查  
   结果说明要确认关键文件和子目录是否齐全。
2. 相对路径检查  
   结果说明要确认 backend 和 frontend 的默认相对路径都能解析到 `week7_auto` 内部。
3. 启动前资源存在性检查  
   结果说明要确认 `meta.json`、`curr_step.json`、`curr_sim_code.json` 等关键文件不会因为缺失导致启动前即失败。

### 4. 更新 `INIT_CONTEXT.md`，把说明切换为“独立副本模式”
`INIT_CONTEXT.md` 必须改成面向 week7 工作流的正式说明，明确写清：

- `week7_auto` 是唯一运行根目录
- baseline / threejs / week6 文件都已经复制进 `week7_auto`
- 后续所有开发、测试、调试只针对 `week7_auto`
- `storage/` 和 `temp_storage/` 的 canonical 位置在 `week7_auto/environment/frontend_server/`
- 严禁新增对原始 `resources` 目录的运行时依赖

这一阶段的结果要求是：  
以后任何 `/init` 或后续协作都能直接把 `week7_auto` 视为完整项目副本，而不是“连接外部 baseline 的拼装壳”。

对应小任务测试：
1. 文档内容检查  
   结果说明要确认 `INIT_CONTEXT.md` 中没有“运行时引用外部 baseline”的表述。
2. 工作约束检查  
   结果说明要确认文档已明确“只复制、不导入、只改 `week7_auto`”。

### 5. 先跑通 baseline，再进入 Week7 功能开发
只有前四个任务全部通过，才能进入 Week7 功能实现。

Week7 功能开发位置固定为：

- `week7_auto/reverie/backend_server/`
- `week7_auto/environment/frontend_server/`
- `week7_auto/analysis/`
- `week7_auto/tests/`

本周新增或扩展的外部配置项固定为：

- `arrival_profile_mode`
- `lab_capacity`
- `lab_turnaround_minutes`
- `imaging_capacity`
- `imaging_turnaround_minutes`
- `boarding_timeout_minutes`

默认行为固定为：

- `arrival_profile_mode=normal`
- `surge` 表示整体增强到诊强度
- `burst` 表示内置时段性高峰
- `boarding_timeout_minutes` 只记录 timeout 事件，不自动移除患者

Week7 实现时继续沿用“小任务 -> 测试 -> 结果说明”的拆分方式：

1. 到诊 profile 功能  
   测试：`normal / surge / burst` 下到诊差异可观测，固定 seed 可复现。
2. lab/imaging 容量与 TAT  
   测试：容量降低或 TAT 提高时，相关瓶颈指标上升。
3. boarding timeout 事件  
   测试：超过阈值后记录 timeout，系统仍能继续推进。
4. analysis 扩展  
   测试：新增指标可以被分析脚本读取与输出。
5. 稳定性  
   测试：无 deadlock / livelock，相同 seed 结果一致。

## Test Plan
### 阶段 A：独立副本搭建完成后的测试
必须逐项记录结果：

- 目录复制测试  
  检查 `week7_auto` 是否已经拥有完整主干、参考前端、week6 模块。
- 外部路径污染测试  
  搜索 `week7_auto` 内是否残留指向原始 `resources` 的硬编码路径。
- baseline 前端最小启动测试  
  验证 Django 前端可以从 `week7_auto/environment/frontend_server` 启动。
- baseline 后端最小启动测试  
  验证 backend 可以从 `week7_auto/reverie/backend_server` 启动。
- auto mode 最小推进测试  
  验证能读取 `week7_auto` 内部的 `storage/` 与 `temp_storage/`，并产生 step / movement / environment 输出。

### 阶段 B：week6 覆盖后的回归测试
必须逐项记录结果：

- `ui_mode=auto` 页面链路测试
- `ui_mode=user` 页面显示测试
- `/mode/user/*` 接口测试
- `/ed/*` 接口测试
- queue snapshot / handoff / session reset 回归测试
- baseline auto mode 未被覆盖破坏的回归测试

### 阶段 C：Week7 功能测试
必须逐项记录结果：

- surge pressure
- doctor shortage
- imaging bottleneck
- boarding timeout
- no deadlock / no livelock
- fixed-seed reproducibility
- analysis regression

每个测试结果说明格式统一为：

- 测试项
- 执行方式
- 预期结果
- 实际结果
- 结论：通过 / 失败 / 阻塞
- 若失败：下一步修复任务

## Assumptions
- `week7_auto` 是唯一合法运行副本，后续所有实现都发生在这里。
- 允许对 `week7_auto` 做复制、覆盖和功能修改；不允许在运行时依赖外部 baseline 或 week6 目录。
- “不要自己写”在这里的优先含义是：  
  对 baseline 主干和 week6 增量的接入，优先使用直接复制，不用自己重新实现等价文件。
- 如果覆盖 week6 文件后发现缺少直接依赖，处理原则不是改路径指回原目录，而是把缺少的依赖文件继续复制进 `week7_auto`。
- 只有在 baseline 独立跑通之后，才进入 Week7 的功能开发与测试阶段。
