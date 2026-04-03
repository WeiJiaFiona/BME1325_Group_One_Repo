# ED-MAS 落地分析（第 1 轮：按你的 1-3 要求展开）

> 说明：这一版把你上传的 `README.md` 作为当前 **final proposal / implementation target**，把 **EDSim 论文+repo** 与 **MedAgentSim 论文+repo** 作为 **background / baseline**。结论尽量只基于你给的文件与可核实的仓库公开信息，不额外臆测。fileciteturn3file0 fileciteturn3file5 fileciteturn3file17 ([github.com](https://github.com/MAXNORM8650/MedAgentSim?utm_source=chatgpt.com))

---

# 1. 将两个文献 + repo 作为已知 background，作为代码实现基础

## 1.1 你的目标系统，本质上要做什么

你的 `README.md` 写得很清楚：目标不是做一个纯论文 demo，而是做一个 **可集成 ICU / ward 的、接口稳定、流程可测试、临床上有约束的 ED MAS 子系统**。核心关键词是：

- **deterministic**
- **clinically grounded**
- **testable**
- **L1 interface freeze**
- **week-by-week engineering delivery** fileciteturn3file0

所以这里不能简单把 background 仓库直接拼起来，而是要把它们拆成两类基础能力：

1. **EDSim 提供 ED 运营仿真的骨架**
2. **MedAgentSim 提供临床多轮交互与记忆增强的骨架**

这两个 background 的角色不一样。

---

## 1.2 EDSim 在整个实现里的定位

### 可以把 EDSim 视为：**ED workflow / resource / metric baseline**

EDSim 的论文明确强调，它的核心是一个 **模块化 patient journey**，从 triage 到 treatment 到 discharge，支持虚拟 patient 与 provider 的自然语言交互，同时被 clinical rules 和 global ED state 约束；它还强调 arrival pattern、acuity mix、resource allocation、LOS / wait time / throughput 这些运营层指标。fileciteturn3file5 fileciteturn3file9

论文里进一步给出：

- triage nurse / bedside nurse / physician / patient 四类角色
- arrival queue、priority、bedside transport、doctor load 等流程要素
- 资源参数、时延参数、dashboard、scenario config 这些工程要素 fileciteturn3file4 fileciteturn3file6 fileciteturn3file10

因此，对你的项目来说，**EDSim 最适合作为以下部分的背景基础**：

- ED 状态机的语义来源
- 队列 / 优先级 / 资源约束的设计来源
- metrics 定义与采集字段来源
- dashboard / scenario config 的未来增强来源 fileciteturn3file4 fileciteturn3file9 fileciteturn3file10

---

## 1.3 MedAgentSim 在整个实现里的定位

### 可以把 MedAgentSim 视为：**doctor-patient-measurement interaction + memory baseline**

MedAgentSim 的论文核心不是 ED flow，而是：

- doctor / patient / measurement 三 agent
- doctor 必须主动追问
- test result 只有 doctor 主动请求才返回
- conversation phase + experience replay phase
- records buffer / retrieval / self-improvement / ensembling fileciteturn3file17

论文对 memory 设计写得也很清楚：  
病例会进入 records buffer，后续通过 retrieval 作为 few-shot / experience 使用；同时它强调 progressive learning。fileciteturn3file17

仓库 README 也明确把它定义为：

- multi-agent architecture
- experience replay
- visual game simulation
- multi-modal capabilities ([github.com](https://github.com/MAXNORM8650/MedAgentSim?utm_source=chatgpt.com))

因此，对你的项目来说，**MedAgentSim 最适合作为以下部分的背景基础**：

- minimal consultation 的交互模式
- measurement dispatch 的原型设计
- handoff continuity 所需的 memory / replay 思路
- phase 8 的 `EpisodeMemory / HandoffMemory / ExperienceReplayBuffer` 的结构参考 fileciteturn3file1 fileciteturn3file2 fileciteturn3file17

---

## 1.4 两个 background 在你项目中的分工

| background | 最适合承接的层面 | 不适合直接拿来当主骨架的层面 |
|---|---|---|
| **EDSim** | triage/queue/resource/state/LOS/wait time/dashboard | 高质量 clinical consultation memory |
| **MedAgentSim** | doctor-patient-measurement / replay / retrieval / reasoning enhancement | ED queueing / boarding / handoff latency / surge simulation |

这个分工和你的 `README.md` 是一致的：  
Week 5-7 偏 EDSim 风格，Week 8-9 偏 MedAgentSim 风格。fileciteturn3file0 fileciteturn3file2

---

# 2. 详细阅读 README.md 后，任务需要从哪些工程角度落实

下面我按你指定的框架来讲：**LLM / tools / memory / planning / MCP / skills**。其中有些层面是这次必须做的，有些是现在不该先做大的。

---

## 2.1 LLM 层面

### 这个层面在你的 proposal 里要实现什么

你的 `README.md` 没有要求 Week 5-7 就把真实 LLM 变成主控制器。相反，它反复强调：

- deterministic
- clinically grounded
- testable
- fallback-to-rule mode during model/tool timeout fileciteturn3file0 fileciteturn3file1

所以，这里的 **LLM 层** 不是“让模型控制系统”，而是：

1. 在 **bounded checkpoints** 上参与
2. 不破坏 rule core
3. 出错时能 fallback 到 rule mode
4. 后续用于 consultation / summary / retrieval augmentation，而不是接管 state machine fileciteturn3file1

### 基础功能解释

LLM 在这个项目里应承担三种任务：

#### 1）语言理解
把用户输入的中文主诉、口语表达、噪声表达归一到结构化字段。  
例如：
- chief complaint
- symptom slots
- risk trigger cues
- possible escalation flags

这对应 README 里的：
- noisy language handling
- Chinese colloquial complaints
- mixed-language input fileciteturn3file2

#### 2）受限生成
生成：
- triage note
- consultation note
- handoff clinical_summary
- localized pathway text fileciteturn3file0 fileciteturn3file2

#### 3）受限检索增强
在 memory checkpoint 处取回 episode / handoff / replay 信息，帮助 continuity，但不直接决定非法状态跳转。fileciteturn3file1

### 基础代码如何实现

最基础可以抽成一个 `llm_service.py` 或 `model_gateway.py`，统一提供：

```python
class LLMService:
    def classify_intent(self, text: str, schema: dict) -> dict: ...
    def generate_note(self, prompt: str, structured_context: dict) -> str: ...
    def summarize_handoff(self, encounter: dict) -> dict: ...
    def retrieve_augmented_response(self, prompt: str, retrieved_memories: list) -> str: ...
```

### 需要调用什么

Phase 1-2 不要求一定调用真实 API。  
但代码层要预留适配入口，后续接：

- OpenAI / compatible chat API
- 本地 vLLM serving
- rule-based mock adapter

你自己的 MVP 文档也明确说过，**真实 LLM API 接入应放到 Phase 3**，不能在 Phase 1 让状态机依赖它。fileciteturn3file7 fileciteturn3file12

### 与 background 的对应关系

- **EDSim**：LLM 被 clinical rules 和 global state 约束，不是自由 agent。这个思想必须继承。fileciteturn3file5
- **MedAgentSim**：LLM 擅长多轮问诊、请求检查、生成 diagnosis-supporting dialogue。这个能力适合后接 consultation / measurement。fileciteturn3file17

---

## 2.2 Tools 层面

### 这个层面在你的 proposal 里要实现什么

README 里已经暗示了几类工具型操作：

- measurement dispatch
- flow coordination
- consult timeout handling
- handoff request / complete
- queue snapshot
- audit / PHI redaction
- event trace output fileciteturn3file0 fileciteturn3file2

所以这里的 **tools** 不是泛泛而谈，而是系统里一组 **可被 orchestrator 或 agent 调用的确定性服务**。

### 基础功能解释

建议把 tools 理解成 6 类：

#### 1）Triage tool
输入主诉与生命体征，输出：
- `acuity_ad`
- `ctas_compat`
- `zone`
- escalation triggers

#### 2）Queue tool
输入 case 状态，输出：
- triage queue insertion
- doctor queue排序
- boarding queue update

#### 3）Measurement tool
触发：
- lab dispatch
- imaging dispatch
- turnaround timer
- abnormal result callback

#### 4）Handoff tool
实现：
- `POST /ed/handoff/request`
- `POST /ed/handoff/complete`
- timeout event generation fileciteturn3file0

#### 5）Safety tool
实现：
- high-risk advice block
- PHI redaction
- audit trail persistence fileciteturn3file1

#### 6）Metrics tool
实现：
- wait
- LOS
- boarding_delay
- handoff_latency
- safety_block_rate fileciteturn3file1

### 基础代码如何实现

最稳的实现方式不是“工具全塞给 agent 直接调”，而是建一个 deterministic service layer：

```python
class TriageTool: ...
class QueueTool: ...
class MeasurementTool: ...
class HandoffTool: ...
class SafetyTool: ...
class MetricsTool: ...
```

然后由 `EDOrchestrator` 控制调用顺序。

### 与 background 的对应关系

- **EDSim** 已经有 resource / queue / metrics / configurable parameters 的思想，可直接参考。fileciteturn3file9 fileciteturn3file10
- **MedAgentSim** 的 measurement agent 很适合改造成 `MeasurementTool` 或 `MeasurementCoordinator`。fileciteturn3file17

---

## 2.3 Memory 层面

### 这个层面在你的 proposal 里要实现什么

README 写得很明确：

- Week 8 目标是 Memory v1
- 需要 `EpisodeMemory`
- `HandoffMemory`
- `ExperienceReplayBuffer`
- retrieval 只能在 bounded decision checkpoints 注入 fileciteturn3file1 fileciteturn3file2

这说明 memory 在你这里不是聊天历史，而是 **受控、可测试、可 ablation 的结构化记忆系统**。

### 基础功能解释

#### 1）EpisodeMemory
记录单次 ED encounter 的关键片段：
- chief complaint
- triage result
- abnormal vitals
- tests ordered / returned
- escalation path
- final disposition

作用：支持 reassessment continuity。

#### 2）HandoffMemory
记录跨班次 / 跨科室交接要点：
- current stability
- pending tasks
- required unit
- summary
- accepted / timed out state

作用：支持 shift change 与 ICU/ward handoff continuity。

#### 3）ExperienceReplayBuffer
保留“相似病例 + 成功处置路径”或“错误后修正路径”，用于 retrieval augmentation。  
这个思想直接来自 MedAgentSim 的 records buffer / experience replay。fileciteturn3file17

### 基础代码如何实现

```python
@dataclass
class EpisodeMemoryItem:
    patient_id: str
    encounter_id: str
    facts: dict
    timeline: list
    outcome: dict

@dataclass
class HandoffMemoryItem:
    handoff_ticket_id: str
    sender: str
    receiver: str | None
    summary: dict
    pending_tasks: list
    status: str

class ExperienceReplayBuffer:
    def add_case(self, case_repr: dict, outcome: dict): ...
    def retrieve_similar(self, query_repr: dict, top_k: int = 3) -> list: ...
```

### 需要调用什么

最基础不需要上向量库也能做：
- 先用 rule-based similarity / BM25 / embedding stub
- Phase 2/3 再换 FAISS / pgvector / Milvus 之类

### 与 background 的对应关系

- **EDSim**：有 memory，但 README 明确指出“not optimized for handoff continuity and replay evaluation”，说明要在你的项目里重构，不是照搬。fileciteturn3file0
- **MedAgentSim**：records buffer、experience replay、retrieval 是最直接的来源。fileciteturn3file17

---

## 2.4 Planning 层面

### 这个层面在你的 proposal 里要实现什么

你的 README 第一个大 milestone 就是：

- Week 5: Rule Core + Unified State Machine
- deterministic A-D triage / routing / escalation
- illegal transition rejection fileciteturn3file2

所以这里的 planning 不是“开放式 agent 自己想”，而是：

> **受状态机约束的流程规划**

### 基础功能解释

Planning 至少分三层：

#### 1）Encounter planning
一个患者当前下一步做什么：
- triage
- queue
- consult
- imaging
- boarding
- handoff

#### 2）Resource planning
系统当前资源怎么分：
- 哪个 doctor 接谁
- 哪个 measurement slot 分给谁
- boarding queue 如何移动

#### 3）Escalation planning
触发 green channel / ICU / surgery / consult 时，如何改变路径。fileciteturn3file2

### 基础代码如何实现

最稳的方法是：

- `EDStateMachine` 负责 **合法状态**
- `EDOrchestrator` 负责 **推进动作**
- `Planner` 只负责 **在合法动作集合里选下一步**

```python
class EncounterPlanner:
    def next_actions(self, encounter, resources, policy) -> list[str]:
        ...
```

### 与 background 的对应关系

- **EDSim** 给你的是“clinical rules + global state + role-specific constraints”的 planning 思想。fileciteturn3file5 fileciteturn3file6
- **MedAgentSim** 更适合 consultation 内的微观 planning，不适合管全 ED queue。fileciteturn3file17

---

## 2.5 MCP 层面

### 这个层面现在该怎么理解

在你当前 README 里，**没有直接写 MCP**。  
所以这里不能为了“架构时髦”硬塞一个 MCP-first 方案。

### 建议的工程解释

你现在真正需要的是：

- 稳定 API contract
- event contract
- tool invocation boundary
- subsystem integration boundary fileciteturn3file0

也就是说，**你当前最接近 MCP 的需求，其实是“统一的上下文与工具调用边界”**，但还没到必须上 MCP protocol 的阶段。

### 现阶段怎么实现

先把这几件事做好：

1. 所有外部能力都通过 service / tool 层暴露
2. 所有跨系统能力都通过 frozen API / event contract 暴露
3. context 统一挂在 encounter / patient / memory state 上

等 Week 12 前后，如果真要做跨团队 demo，再考虑是否包装成 MCP 风格适配层。

### 结论

**MCP 现在不是 Phase 1-2 阻塞项。**  
先把 API 和 tool contract 做稳，比先造 MCP 更重要。fileciteturn3file0 fileciteturn3file11

---

## 2.6 Skills 层面

### 这个层面在你的 proposal 里对应什么

虽然 README 没直接写 “skills”，但实际上已经隐含了很多“技能块”：

- triage skill
- escalation skill
- measurement dispatch skill
- handoff summarization skill
- safety blocking skill
- localization skill fileciteturn3file0 fileciteturn3file1

### 工程上该怎么理解

在这个项目里，skills 最好不要先做成独立框架，而是先做成 **可复用函数块 / agent capability blocks**。

举例：

```python
class TriageSkill: ...
class EscalationSkill: ...
class HandoffSummarySkill: ...
class SafetyBlockSkill: ...
class LocalizationSkill: ...
```

这些 skill 以后可以挂给：

- `TriageAgent`
- `FlowCoordinator`
- `DoctorAgent`
- `SafetyGuard`

### 与 background 的对应关系

- **EDSim** 已经有 role-specific behavior constraints，本质上接近“固定 skill set”。fileciteturn3file6
- **MedAgentSim** 已经有 doctor / measurement / replay 等能力块，本质上可拆成 skills。fileciteturn3file17

---

# 3. 以 README.md 为 final proposal，如何一步一步把 background 放进整个框架

下面我按你要的格式展开：

> **xxx 层面，需要实现 xxxx 操作，在 xxx 库中有 xxx 代码/思想，代码完整度 xxxx，如何嫁接过来，需要展开 xxx 修改操作。**

---

## 3.1 状态机 / Rule Core 层面

### 需要实现什么操作
需要实现：

- `CN_AD` + `CTAS_COMPAT`
- deterministic triage / routing / escalation
- shared encounter state machine
- illegal transition rejection fileciteturn3file2

### 在哪个 background 里有基础
- **EDSim** 有 patient journey、triage priority、resource flow、clinical rule constraints 的完整思想基础。fileciteturn3file4 fileciteturn3file5

### 代码完整度判断
**完整度：中高（思想完整，不能直接拷贝成你的代码）**

原因：
- 流程语义完整
- 但它默认是 CTAS 逻辑，不是中国 A-D
- 而且它的实现围绕自己的 simulator 架构，不是你现在的 Week-plan API 子系统架构

### 如何嫁接
需要自己新建：

- `utils/ed_state_machine.py`
- `utils/triage_policy.py`
- `utils/escalation_rules.py`

### 具体修改操作
1. 先定义统一 encounter states  
2. 写 `CN_AD -> CTAS_COMPAT` 映射  
3. 把 green channel / ICU required / surgery required 做成 escalation hook  
4. 所有 API 推进都必须走 `can_transition()`  

---

## 3.2 Queue / Resource Realism 层面

### 需要实现什么操作
需要实现：

- triage queue
- doctor queue
- test queue
- boarding queue
- arrival profiles
- lab/imaging capacity
- timeout events
- KPI snapshots fileciteturn3file2

### 在哪个 background 里有基础
- **EDSim** 有 queue length、zone occupancy、doctor load、resource capacities、arrival modifiers、diagnostic timing。fileciteturn3file9 fileciteturn3file10

### 代码完整度判断
**完整度：高（运营仿真思路成熟），但接口不匹配你的目标系统**

### 如何嫁接
你需要把 EDSim 的“仿真参数思想”改写成你项目里的 deterministic services：

- `QueueTool`
- `ResourceManager`
- `MeasurementCoordinator`
- `BoardingManager`

### 具体修改操作
1. 在 `ed_case_store` 中维护 queue state  
2. 在 `ed_orchestrator` 中推进资源分配  
3. 在 `metrics` 层按 encounter timeline 实时更新 KPI  
4. 后续再接 dashboard，不要 Phase 1 先做前端

---

## 3.3 Measurement / Tests 层面

### 需要实现什么操作
需要实现：

- measurement dispatch
- imaging/lab turnaround
- result callback
- delayed result reassessment fileciteturn3file0 fileciteturn3file2

### 在哪个 background 里有基础
- **MedAgentSim** 有 measurement agent，且 test result 只有在 doctor 请求后才返回。fileciteturn3file17
- **EDSim** 有 diagnostics timing 与 nurse escort / test room capacity 的运营层基础。fileciteturn3file9 fileciteturn3file10

### 代码完整度判断
**完整度：中高**

- MedAgentSim 在交互逻辑上完整
- EDSim 在流程时延上完整
- 但你自己的 measurement dispatch coordinator 仍然需要自己写

### 如何嫁接
建议组合式嫁接：

- 从 **MedAgentSim** 借“doctor 请求 -> measurement 返回”交互模式
- 从 **EDSim** 借“capacity / turnaround / waiting”仿真逻辑

### 具体修改操作
1. 新建 `measurement_coordinator.py`
2. 区分 `requested / running / result_ready / abnormal_result`
3. 在 result ready 时触发 `reassessment checkpoint`
4. future 再接真正多模态结果

---

## 3.4 Memory 层面

### 需要实现什么操作
需要实现：

- `EpisodeMemory`
- `HandoffMemory`
- `ExperienceReplayBuffer`
- bounded checkpoint retrieval
- ablation: memory on/off fileciteturn3file1 fileciteturn3file2

### 在哪个 background 里有基础
- **MedAgentSim** 有 records buffer / replay / retrieval / self-improvement，是最直接来源。fileciteturn3file17
- **EDSim** 虽然也有 memory 思想，但你 README 已经明确指出它对 handoff continuity 不够。fileciteturn3file0

### 代码完整度判断
**完整度：MedAgentSim 高，EDSim 低到中**

### 如何嫁接
这一层优先从 MedAgentSim 借思想，不直接搬 EDSim。

### 具体修改操作
1. 在 memory store 中拆三类 memory  
2. retrieval 只允许发生在：
   - reassessment
   - handoff summary
   - consult continuation  
3. 不允许 retrieval 改写状态机合法性  
4. 用 memory on/off 做 ablation

---

## 3.5 Handoff / L1 Interface 层面

### 需要实现什么操作
需要实现：

- `POST /ed/handoff/request`
- `POST /ed/handoff/complete`
- queue snapshot
- event contracts
- ICU/ward integration-ready interface fileciteturn3file0

### 在哪个 background 里有基础
- **EDSim** 有 disposition / boarding / flow transition 的运营语义
- **MedAgentSim** 有 summary / continuity / memory 的语义
- 但 **两个 background 都没有你 README 里这组 frozen L1 handoff contract 的现成实现**

### 代码完整度判断
**完整度：低（只能借思想，主代码必须自己写）**

### 如何嫁接
这层要自己做成你项目独有的 integration layer。

### 具体修改操作
1. 新建 `handoff_service.py`
2. 维护 `handoff_ticket`
3. 调用 `HandoffMemory`
4. 发出事件：
   - `ED_PATIENT_READY_FOR_ICU`
   - `ED_PATIENT_READY_FOR_WARD`
   - `ED_HANDOFF_TIMEOUT` fileciteturn3file0

---

## 3.6 Safety / Governance 层面

### 需要实现什么操作
需要实现：

- high-risk advice block
- PHI redaction
- audit trail
- model/tool timeout fallback
- safe degradation fileciteturn3file1

### 在哪个 background 里有基础
- **EDSim** 强调 clinical rule constraint 和 behavior bounding，能借“受控 agent”思想。fileciteturn3file5 fileciteturn3file6
- **MedAgentSim** 强调 reasoning enhancement，但不是 safety-first 架构

### 代码完整度判断
**完整度：低到中**

这一层你 README 自己的要求比两个 baseline 都更强，所以得自己补。

### 如何嫁接
把 safety 放成系统外围 guard，而不是塞进每个 agent 里到处写 if。

### 具体修改操作
1. 新建 `safety_guard.py`
2. 所有 note/handoff/LLM output 出口前先过 guard
3. 所有 timeout 统一 fallback 到 rule mode
4. 所有高风险 block 都要写审计日志

---

## 3.7 Localization / China-first 层面

### 需要实现什么操作
需要实现：

- `CN_AD`
- `CTAS_COMPAT`
- 中文口语 complaint 理解
- localized pathway text
- chest pain / stroke / trauma green-channel localized triggers fileciteturn3file0 fileciteturn3file1

### 在哪个 background 里有基础
- **EDSim** 提供 CTAS 与 ED flow，但不是中国本地化
- **MedAgentSim** 提供多轮语言交互，但不是中国急诊本地化

### 代码完整度判断
**完整度：低**

### 如何嫁接
这层基本不能照搬，必须你自己本地化实现。

### 具体修改操作
1. 建 `cn_triage_policy.py`
2. 建 `localized_terms.py`
3. 建 `green_channel_rules_cn.py`
4. 做 mixed-language robustness tests

---

## 3.8 API / Orchestrator 层面

### 需要实现什么操作
需要实现：

- `/mode/user/encounter/start`
- handoff APIs
- event trace output
- schema validation
- 可演示、可冻结、可联调的接口层 fileciteturn3file2

### 在哪个 background 里有基础
- 两个 background 都有“系统流程”基础
- 但都不是你当前 README 所要求的接口 contract

### 代码完整度判断
**完整度：低，必须自写**

### 如何嫁接
这层应该以你自己的主骨架仓库为中心，把 background 的能力变成内部模块，而不是反过来按 baseline 的目录结构改整个项目。

### 具体修改操作
建议主线是：

- `web_app.py` / `api/`
- `ed_orchestrator.py`
- `ed_case_store.py`
- `memory_system.py`
- `triage_agent.py`
- `flow_coordinator.py`
- `measurement_coordinator.py`
- `handoff_service.py`
- `safety_guard.py`

这个方向和你之前的 MVP 文档也是一致的：Phase 1 先把 `ed_sim` 单一状态源、ED 状态机、case store、orchestrator、API 做出来。fileciteturn3file7 fileciteturn3file11 fileciteturn3file12

---

# 最后的工程结论

## 一句话总结

你的项目最合理的落地方式不是“选一个 baseline 全盘复用”，而是：

- **用 EDSim 作为 ED 流程 / 资源 / 指标 / 状态机背景**
- **用 MedAgentSim 作为 consultation / measurement / memory replay 背景**
- **以你自己的 README 作为真正的 implementation contract**
- **真正需要冻结的代码主干，必须自己写在当前主骨架仓库里** fileciteturn3file0 fileciteturn3file2 fileciteturn3file7

## 当前最值得先做的顺序

1. **Week 5 先做 Rule Core + Unified State Machine**
2. **Week 6 冻结 L1 API**
3. **Week 7 做 queue/resource realism**
4. **Week 8 再接 memory**
5. **Week 9 再补 safety**
6. **Week 10 再做 localization deepening** fileciteturn3file2

---

下一条我建议直接进入你最需要的版本：

# 第 2 轮输出建议
我可以继续按你要的“逐个返回”方式，直接给你一份：

**《README.md → 文件级实现映射表》**

格式会是：

- `LLM层` → 新增/修改哪些文件
- `memory层` → 新增/修改哪些文件
- `planning层` → 新增/修改哪些文件
- `tools层` → 新增/修改哪些文件
- 每个文件里要写哪些 class / method
- 哪些方法借 EDSim，哪些借 MedAgentSim，哪些必须自写

这样你就能直接拿去喂 Codex。
