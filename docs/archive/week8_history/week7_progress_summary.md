# Week6–Week7 进度梳理（客观版）

## 上周完成的内容

### 1. Week6：User Mode UI + L1 API 最小闭环
上周的核心目标是完成 **user-to-ED encounter 路径**，并冻结 **L1 API**。  
本质上，是让“真实用户作为患者进入系统”，从输入主诉开始，走完一次规则驱动的急诊 encounter 流程。

#### 后端侧
- 在 `week5_system/app/api_v1.py` 中完成 L1 API 的内存态运行时：
  - `start_encounter`
  - `chat_turn`
  - `session_status`
  - `session_reset`
  - `handoff`
  - `queue_snapshot`
- `user_mode_chat_turn()` 以 **phase 状态机** 驱动 encounter 流程。
- `week5_system/app/handoff.py` 形成独立 handoff 生命周期：
  - `REQUESTED`
  - `COMPLETED`
  - `REJECTED`
  - `TIMEOUT`
- `week5_system/app/response_generator.py` 提供模板式 response generation，用来缓和纯规则对话的僵硬感。

#### 前端侧
- `user_mode.html` 实现独立 User Mode 页面。
- `user_mode.js` 已接入：
  - `/mode/user/session/status`
  - `/mode/user/chat/turn`
  - `/mode/user/session/reset`
  - `/ed/queue/snapshot`
- `user_mode.css` 完成两栏布局与聊天区角色样式区分。

#### 这一阶段的本质结果
Week6 完成的是：
- **规则驱动的用户问诊闭环**
- **L1 API 冻结**
- **前端可交互的 User Mode 页面**

但它还不是“真实动态医院系统”，因为此时的系统重点仍然是：
- 流程能不能走通
- API 能不能调用
- 前端能不能交互

而不是：
- 患者是否按真实流量进入
- 检查资源是否形成瓶颈
- 时间与容量是否影响系统行为


---

## 本周的目标

根据 Week7 计划，推进成一个带有 **Auto Mode + Resource Realism** 的仿真系统。


### 1. 接入 Week7 真实世界约束
本周新增的配置项包括：
- `arrival_profile_mode`
- `lab_capacity`
- `lab_turnaround_minutes`
- `imaging_capacity`
- `imaging_turnaround_minutes`
- `boarding_timeout_minutes`

默认规则包括：
- `arrival_profile_mode=normal`
- `surge` 表示整体增强到诊强度
- `burst` 表示内置时段性高峰
- `boarding_timeout_minutes` 只记录 timeout event，不自动移除患者

### 2. 对应计划中的验证要求
Week7 计划要求每个功能必须走“小任务 -> 测试 -> 结果说明”的路径，重点验证：
- `normal / surge / burst` 是否能产生可观测差异
- lab/imaging 容量下降或 TAT 增加时，瓶颈指标是否上升
- boarding timeout 是否能被记录，且系统继续推进
- analysis 是否能正确输出新增指标
- 系统是否无 deadlock / livelock，且相同 seed 可复现


---

## 实际进度

---

### A. 代码层面已经实现了什么

#### 1. arrival profile（病人流入）
**本质目标**  
让 Auto Mode 下的患者到诊不再是固定、单一的节奏，而是支持不同强度模式。

**代码层面的实现逻辑**
- 新增 `arrival_profile_mode` 配置项。
- 在后端逻辑中引入 `normal / surge / burst` 三种 profile。
- 仿真主循环在计算有效到诊率时，会调用相应的 arrival profile 逻辑：
  - `normal`：按默认节奏到诊
  - `surge`：整体提高到诊强度
  - `burst`：在特定时段出现短时高峰

**这意味着什么**
- 现在系统的“患者流入”不再是写死的单一节奏。
- 仿真可以开始区分“平稳日常”和“高峰压力”场景。

**还不够的地方**
- 目前只完成了 **短链路 smoke 验证**，还没有做更长时间的 scenario run。
- 所以可以确认“profile 被接入并能进入真实运行链路”，但还不能据此下结论说：
  - surge 一定会稳定导致拥堵
  - burst 一定会在真实长时间运行中产生预期峰值曲线

---

#### 2. lab / imaging capacity（资源限制）
**本质目标**  
让 lab 和 imaging 不再是“无限资源”，而是具有真实的处理上限。

**代码层面的实现逻辑**
- 新增配置项：
  - `lab_capacity`
  - `imaging_capacity`
- 在 patient testing flow 中，检查任务要经过对应的容量限制。
- 如果资源槽位不足，患者不能立刻完成对应检查，而是会被迫等待。

**这意味着什么**
- 系统第一次具备了“资源竞争”这一层现实约束。
- 这一步非常关键，因为只有有限资源，才可能形成 bottleneck。

**还不够的地方**
- 目前 smoke run 只证明：
  - 参数写入了
  - 运行链路没断
  - analysis 能读出字段
- 还没有长时间验证：
  - capacity 降低后是否真的会造成等待累积
  - 不同 capacity 下 bottleneck 是否能清晰分离

---

#### 3. TAT（处理时间）
**本质目标**  
让 lab / imaging 不只是“有没有空位”，还要体现“处理一个人需要时间”。

**代码层面的实现逻辑**
- 新增配置项：
  - `lab_turnaround_minutes`
  - `imaging_turnaround_minutes`
- 在 patient 检查流里，每个检查任务都会占用一段持续时间，而不是瞬时完成。
- 因此系统中的等待不只是“排不上队”，还包括“前面任务还没做完”。

**这意味着什么**
- 资源约束从“空间限制”扩展成了“时间限制”。
- 这比单纯的 capacity 更接近真实医院，因为现实中的瓶颈几乎总是“资源 × 时间”共同作用。

**还不够的地方**
- 目前没有足够长的回归结果来证明：
  - 单纯提高 TAT 时，队列和等待是否明显上升
  - TAT 与 capacity 的交互作用是否符合预期

---

#### 4. boarding timeout（滞留事件）
**本质目标**  
让系统能记录“患者在 boarding 状态停留过久”的风险事件。

**代码层面的实现逻辑**
- 新增配置项：
  - `boarding_timeout_minutes`
- patient 状态机在 boarding 持续超过阈值后，会记录 timeout event。
- 按计划要求，这一步只记录事件，不自动把患者移出系统。

**这意味着什么**
- 系统开始具备“坏事件感知”能力。
- 不再只关心患者有没有推进流程，也开始记录“推进得太慢、已经异常”的情况。

**还不够的地方**
- 当前还没有构造出一个足够长、足够拥堵的真实场景来稳定触发 boarding timeout。
- 所以现在可以说“机制已接入、分析字段已支持”，但还不能说“timeout 行为已经被完整验证”。

---

### B. 验证层面已经做到什么

#### 1. 真实 auto mode / 前端链路 smoke 验证
这次不是只看代码，而是做了真实 smoke run。

**已确认结果**
- 用前端控制路径启动了真实 smoke run，目标目录为 `codex-auto-ui-smoke`
- `curr_step.json` 推进到了 `1`
- 成功写出了：
  - `movement/0.json`
  - `environment/0.json`
- `curr_sim_code.json` 指向 `codex-auto-ui-smoke`

**意味着什么**
- Auto Mode 已经不是“只在代码里存在”
- step 的确被推进了
- movement / environment 的确被真实写出了一轮

这比之前“停在 step 0”或“启动就崩”是明显进展。

---

#### 2. 前端消费链路验证
**已确认结果**
- Django client 验证：
  - `/simulator_home` 返回 200
  - `/update_environment/` 返回 200
- 响应中包含 persona 数据

**意味着什么**
- 后端写出的 movement / environment 产物，不只是存在于磁盘上。
- 它们已经能被 UI 那条链路正确读到和消费。

这一步的本质是：
- **Auto Mode 能触发**
- **step 产物能被前端链路消费**

也就是说，系统已经完成了：
> 后端推进一步 → 写出产物 → 前端接口读取 → 页面层可用

---

#### 3. start_simulation / save_simulation_settings 验证
**已确认结果**
- `start_simulation` 返回 200
- `save_simulation_settings` 返回 200
- 实测把以下 Week7 参数写入了 `meta.json`：
  - `arrival_profile_mode=burst`
  - `lab_capacity`
  - `imaging_capacity`
  - `lab/imaging TAT`
  - `boarding_timeout_minutes`
- 随后已恢复原值


- Week7 已经完成了前端配置入口的真实联调。
- 用户侧至少可以把这些配置送进系统运行态。

---

#### 4. analysis 验证
**已确认结果**
- 使用真实产物运行 `analysis/compute_metrics.py --sim codex-auto-ui-smoke`
- 成功生成：
  - `patient_time_metrics.csv`
  - `ctas_daily_metrics.csv`
  - `resource_event_metrics.json`
- 其中 Week7 字段已经写出

**意味着什么**
- analysis 这一层已经开始认识 Week7 新机制。
- Week7 的新配置与事件不再只停留在仿真运行时，也开始进入分析结果。

---

#### 5. FAIL SAFE TRIGGERED 的最新理解
**当前真实情况**
- 在沙箱内直接跑时，因为当前网络环境连不shanghaitech网关，仍可能走到 fail-safe。
- 但在沙箱外做的真实 smoke run 中：
  - 没有出现 `FAIL SAFE TRIGGERED`
  - 没有出现 `curl.exe failed`
  - 日志中能看到网关返回真实 JSON 内容

**意味着什么**
- 之前频繁 fail-safe 的主因，已经不再是当前代码路径本身。
- 至少在这次真实 smoke 中，代码级调用链已经跑通。
- 剩余的 fail-safe 风险更多与运行环境相关，而不是当前补丁后的核心逻辑问题。

---

### C. 针对输出结果的解释：这些结果说明了什么

#### 完成的部分
1. **Week7 三项核心约束已经接入真实运行链路**
   - arrival profile
   - lab/imaging capacity + TAT
   - boarding timeout

2. **最小真实 smoke 已跑通**
   - 能推进 step
   - 能生成 movement / environment
   - 能被前端接口消费

3. **analysis 已经开始输出 Week7 字段**
   - 表明运行层与分析层已经接上

4. **fail-safe 没在这次真实 smoke 中复现**
   - 说明此前卡死项目的部分调用链问题，至少在当前修复后已经明显缓解

---

#### 客观不足的部分
1. **这只是 1 step 的 smoke 验证，不是长回归**
   - 说明系统“能走第一步”
   - 但不等于“能长时间稳定运行”

2. **还没有完成 Week7 计划里要求的功能级测试**
   - surge pressure
   - doctor shortage
   - imaging bottleneck
   - boarding timeout
   - no deadlock / no livelock
   - fixed-seed reproducibility

3. **analysis 目前更接近“基础字段输出”，还不是强解释能力**
   - 现在可以看到事件和基础指标
   - 但还没有形成完整的 queue 演化、瓶颈定位、资源利用率趋势分析

4. **boarding timeout 机制已经接入，但还没有被长场景稳定触发验证**
   - 目前能说“支持记录”
   - 不能说“已在真实拥堵下充分验证”

5. **arrival surge / burst 是否在长时间运行中造成预期行为，还没有充足证据**
   - 目前只能确认参数接入与链路联通
   - 不能过度解释为“行为规律已经证明成立”

---

## 当前阶段的结论

### 可以明确确认的
- `week7_auto` 独立副本模式已经成立
- Week7 三项核心现实约束已在代码层面接入
- 真实 smoke run 已完成：
  - step 推进
  - movement / environment 写出
  - UI 消费成功
  - analysis 输出成功
- 本轮真实 smoke 中没有复现此前那种频繁 `FAIL SAFE TRIGGERED`

### 不能夸大解读的
- 这次验证仍然是 **短链路 smoke**，不是长时间 scenario 回归
- 还没完成 Week7 计划中更强的行为验证和专项测试
- 因此现在最准确的说法是：

> **Week7 已完成“实现层 + 短链路联调验证”，但尚未完成“长时间行为验证 + 测试闭环”。**


## week 8  任务说明

1. 引入 Memory v1

- 优化EpisodeMemory（事件记忆）
- HandoffMemory（交接记忆）
- ExperienceReplayBuffer（经验回放）
- Bounded Retrieval（有限记忆检索）