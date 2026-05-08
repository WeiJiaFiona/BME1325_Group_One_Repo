# Stage 2 RAG 部署计划（面向 Codex）

## 1. RAG 在此处是什么

在本项目中，**RAG 不是一个面向互联网的通用问答系统**，也**不是**让 LLM “背更多医学知识”的模块。
这里的 RAG 定义为：

> **一个面向 doctor agent 的、离线本地的、可版本化的临床协议检索层**。
> 它根据当前主诉、症状、生命体征和既往多轮对话状态，从本地急诊协议知识库中检索最相关的 protocol / chunk / rule，再把这些证据交给 planner 生成**本轮唯一主问题**、患者可见解释、风险标记和建议的处置方向。

因此，此处 RAG 的本质角色是：

* **knowledge grounding**：让追问建立在协议证据上，而不是 LLM 自由发挥
* **protocol routing**：让系统按当前主诉动态切换协议
* **question planning support**：辅助决定“下一轮最该问什么”
* **traceability**：让每轮追问都能追溯到哪条协议、哪条规则、哪段证据
* **scalability**：把“扩场景”从“改大量代码”转为“补知识库 + 补规则”

---

## 2. 为什么要引入 RAG

### 2.1 当前系统的问题

如果没有 RAG，doctor agent 很容易退化为：

* 一个靠 prompt 驱动的胸痛/单主诉追问器
* 一个对相似表达不稳定的问答器
* 一个在多主诉、模糊表述、否定表达下容易漏问红旗的系统
* 一个输出看似专业、但依据不透明、难调试、难审计的系统

### 2.2 引入 RAG 的核心动机

引入 RAG 以后，系统会从：

> “固定胸痛脚本 / LLM 自由发挥”

变成：

> “根据当前 complaint pattern 检索对应协议，再在协议约束下做下一问规划”

这能使系统更贴近 **diverse 的临床急诊场景**，因为急诊不是单一胸痛场景，而是：

* chest pain
* dyspnea
* stroke-like symptoms
* sepsis-like presentation
* trauma
* dizziness / syncope / altered mental status 等可继续扩展的 complaint family

换言之，**RAG 的目标不是只让系统更广，而是先让它更“有依据地变广”**。

---

## 3. 要实现的目标

## 3.1 近期目标（Stage 2）

1. 将系统从**单一硬编码问诊路径**升级为**协议驱动的 complaint-conditioned 问诊**
2. 支持本地协议库检索，优先覆盖：

   * chest pain
   * dyspnea
   * stroke
   * sepsis
   * trauma
3. 每轮只输出：

   * 一个主问题
   * 一句面向患者的话术
   * 内部结构化 plan contract
4. 保持现有 Stage 1 状态机与 API 外部响应结构不变
5. 所有结构化计划与 trace 仅写入 internal shared memory

## 3.2 中期目标（Stage 2.5）

1. 在 protocol-only 的基础上扩展到 **protocol + local case bank**
2. 增强在模糊、多症状、语言混杂场景中的鲁棒性
3. 对 under-triage / over-triage 做系统评估

近期一项 2026 年的急诊分诊研究采用了**双源 RAG**：同时检索本地分诊指南与历史真实分诊案例，相比 prompt-only 基线显著提高了一致性与准确性，并把 undertriage 维持在较低水平；这说明你当前的 protocol-only 方案是合理起点，但预留 case-bank 扩展接口是值得的。

---

## 4. RAG 在系统中的角色

RAG 在此处**不是最终决策者**，而是 doctor agent 的**证据层与规划辅助层**。

角色边界如下：

* **RAG 负责**

  * 检索相关协议
  * 返回证据片段
  * 为 planner 提供 protocol context
  * 为 validator 提供 rule hits / evidence refs

* **Planner 负责**

  * 根据 evidence 生成结构化草案
  * 产出本轮主问题与患者话术
  * 给出 proposed urgency / disposition

* **Validator 负责**

  * 做 schema 校验
  * 做安全边界检查
  * 决定是否 fallback / soft override / hard override

* **State machine 负责**

  * 维持阶段推进
  * 决定 handoff 与流程流转
  * 保留现有外部 API 结构

因此，**RAG 是 doctor agent 的“证据与路由中枢”，不是独立的诊断引擎**。

---

## 5. 为什么它能让系统更贴近 diverse 的临床急诊场景

在急诊中，同一个“胸痛”背后可能有完全不同的风险方向；同时，很多真实患者不会直接说标准术语，而会使用：

* “胸口闷”
* “喘不上来”
* “头有点晕”
* “浑身发冷发抖”
* “摔了一跤现在有点糊涂”
* “一边胳膊没劲”

这类表达具有：

* 非标准化
* 多主诉并存
* 描述零散
* 语言混杂
* 风险层级差异大

纯模板或纯规则系统通常覆盖不全，纯 LLM 系统又不稳定。
RAG 的作用正是在这两者之间搭桥：

1. **把自由表述映射到协议空间**
2. **把协议空间再转回本轮最需要的一个问题**
3. **让系统在多 complaint family 间动态切换**
4. **使扩充场景时主要新增知识，而不是重写控制逻辑**

所以这里引入 RAG 的核心理由可以概括为：

> **让系统从“单场景脚本问诊”升级为“协议证据驱动的多场景急诊问诊系统”。**

---

## 6. 总体架构

```text
User input
   ↓
Existing triage / calling / state machine
   ↓
Doctor agent entry
   ↓
[Stage 2 RAG Layer]
   ├─ Complaint normalization
   ├─ Protocol retrieval
   ├─ Evidence assembly
   ↓
Planner (LLM -> strict JSON draft)
   ↓
Validator / Safety envelope
   ├─ schema check
   ├─ safety floor check
   ├─ one-question-per-turn check
   ├─ override / fallback
   ↓
Renderer
   ├─ patient_utterance
   └─ one primary question
   ↓
Shared memory trace update
```

---

## 7. 推荐的部署原则

### 7.1 离线优先，不接 live website RAG

本阶段采用：

* **offline local knowledge**
* **versioned protocol YAML / JSON**
* **local retrieval only**

原因：

* 结果可复现
* 更便于课堂 demo
* 便于审计与回放
* 减少网络不稳定和站点变化带来的不确定性
* 便于严格控制 guideline version

### 7.2 不是 rigid template-only，而是“受约束的本地混合 RAG”

建议采用：

1. **规则层**：高危红旗、生命体征阈值、强制升级
2. **检索层**：主诉归一化 + sparse retrieval + semantic rerank
3. **规划层**：LLM 只在 evidence 约束下生成本轮问题
4. **验证层**：保证 planner 不能把高危判断降级

---

## 8. 知识库设计

## 8.1 协议来源

首批采用本地 curated protocol files，覆盖：

* chest_pain
* dyspnea
* stroke
* sepsis
* trauma

后续可扩展：

* syncope
* altered_mental_status
* abdominal_pain
* fever
* palpitations

## 8.2 建议目录

```text
week5_system/
  app/
    protocols/
      chest_pain/
        v1.yaml
      dyspnea/
        v1.yaml
      stroke/
        v1.yaml
      sepsis/
        v1.yaml
      trauma/
        v1.yaml
    rag/
      protocol_compiler.py
      protocol_retriever.py
      reranker.py
      evidence_builder.py
    planning/
      doctor_planner.py
      plan_validator.py
      fallback_templates.py
    schemas/
      protocol_schema.py
      plan_contract.py
```

## 8.3 建议的 protocol YAML 结构

```yaml
protocol_id: chest_pain
version: v1
chief_complaint_aliases:
  - chest pain
  - chest pressure
  - chest tightness
  - 胸痛
  - 胸闷
  - 胸口压迫感

trigger_keywords:
  - retrosternal
  - radiating pain
  - diaphoresis
  - exertional
  - 突发胸痛
  - 放射痛

red_flags:
  - hypotension
  - hypoxia
  - severe diaphoresis
  - syncope
  - new neuro deficit

required_slots:
  - onset
  - duration
  - severity
  - location
  - radiation
  - associated_dyspnea
  - syncope
  - diaphoresis

questions:
  - question_id: cp_onset
    slot: onset
    priority: 100
    ask_if: ["slot_missing:onset"]
    answer_type: text
    zh: "这种胸部不适是从什么时候开始的？"
    en: "When did this chest discomfort start?"
  - question_id: cp_dyspnea
    slot: associated_dyspnea
    priority: 95
    ask_if: ["slot_missing:associated_dyspnea"]
    answer_type: boolean
    zh: "现在有没有同时觉得喘不过气或呼吸困难？"
    en: "Are you also feeling short of breath right now?"

urgency_rules:
  - rule_id: cp_hypoxia
    if_all: ["spo2<90", "complaint:chest_pain"]
    urgency_floor: RESUS
    disposition_floor: ICU

disposition_hints:
  - condition: high_risk_cp
    value: OBSERVE_OR_WARD
```

---

## 9. 检索设计

## 9.1 不建议只做 keyword-only

为了应对急诊场景中的口语表达、多主诉和同义表达，检索应分三步：

### Step A. Complaint normalization

将自然语言表述映射到 complaint / symptom slots，例如：

* “胸口闷、压得慌” → chest_pain / pressure-like discomfort
* “喘不上来” → dyspnea
* “突然嘴歪手麻” → stroke-like neuro deficit
* “发冷发抖、意识差” → sepsis-like concern

### Step B. Sparse retrieval

基于：

* keywords
* aliases
* symptom slots
* vitals abnormalities
* negation-aware matching

先召回 top-k candidate protocols

### Step C. Semantic rerank

对 top-k 的 protocol chunks 做本地轻量语义重排，输出：

* primary protocol
* secondary protocols
* evidence refs
* retrieval score

## 9.2 推荐输出格式

```python
{
  "primary_protocol_id": "chest_pain",
  "secondary_protocol_ids": ["dyspnea"],
  "matched_keywords": ["chest tightness", "shortness of breath"],
  "normalized_complaints": ["chest_pain", "dyspnea"],
  "red_flag_union": ["hypoxia"],
  "evidence_refs": [
    {"protocol_id": "chest_pain", "section": "red_flags", "score": 0.92},
    {"protocol_id": "dyspnea", "section": "required_slots", "score": 0.81}
  ],
  "fallback_used": false
}
```

---

## 10. Planner 设计

Planner 输入：

* current user utterance
* dialogue state
* normalized complaints
* retrieved evidence
* safety floor
* session language

Planner 输出严格 JSON，不直接输出最终前端文本。

## 10.1 建议的 `plan_contract`

```python
{
  "primary_question": {
    "id": "cp_onset",
    "text": "这种胸部不适是从什么时候开始的？",
    "slot": "onset",
    "answer_type": "text"
  },
  "patient_utterance": "我先确认几个关键情况，以便判断风险高低。",
  "risk_flags": ["possible_high_risk_chest_pain"],
  "urgency_floor": "URGENT",
  "urgency_proposed": "URGENT",
  "disposition_floor": "OBSERVE",
  "disposition_proposed": "OBSERVE",
  "missing_critical_slots": ["onset", "associated_dyspnea", "syncope"],
  "evidence_refs": [...],
  "language": "zh",
  "override_allowed_fields": ["patient_utterance", "question_wording"]
}
```

---

## 11. Validator / Safety Envelope

## 11.1 软覆盖与硬覆盖规则

不建议把 “soft override with warning” 用作全局策略。

推荐：

### 允许 soft override 的字段

* `patient_utterance`
* `question_wording`
* `question_order`（限同优先级内）
* `secondary wording`

### 必须 hard override 的字段

* `urgency_floor`
* `disposition_floor`
* `must_escalate`
* `red_flag_hits`
* 与低氧、低压、神经功能缺失、严重外伤等直接相关的安全判断

## 11.2 Validator 检查项

1. JSON 是否可解析
2. 字段是否齐全
3. 枚举值是否合法
4. 本轮是否只问一个主问题
5. 是否违反 safety floor
6. 是否重复询问已完成关键 slot
7. 是否与已知 denied red flags 冲突
8. 是否需要 fallback

---

## 12. 和现有系统的结合方式

## 12.1 保持最小侵入

保留：

* 现有 state machine
* 现有 API 路由
* 现有外部响应结构
* triage / calling 阶段

只在 `DOCTOR_CALLED` 分支中引入 RAG-aware planning：

```text
DOCTOR_CALLED
  ├─ collect current dialogue state
  ├─ run complaint normalization
  ├─ run protocol retrieval
  ├─ build evidence package
  ├─ call planner
  ├─ run validator
  ├─ update shared_memory.doctor_assessment
  └─ return patient_utterance + one primary question
```

## 12.2 shared_memory 建议新增字段

```python
shared_memory.doctor_assessment = {
  "active_protocol_ids": [],
  "normalized_complaints": [],
  "filled_slots": {},
  "missing_critical_slots": [],
  "asked_question_ids": [],
  "denied_red_flags": [],
  "safety_floor": None,
  "plan_contract": {},
  "planner_trace": []
}
```

## 12.3 `planner_trace` 建议结构

```python
{
  "ts": "...",
  "primary_protocol_id": "chest_pain",
  "secondary_protocol_ids": ["dyspnea"],
  "retrieval_score": 0.92,
  "evidence_refs": [...],
  "llm_plan_raw": "...",
  "validator_result": "soft_override",
  "warning_codes": ["QUESTION_REORDERED"],
  "override_applied": true,
  "fallback_used": false
}
```

---

## 13. 参考仓库与借鉴策略

## 13.1 TriageAI —— 借安全架构，不直接当底座

```text
https://github.com/pdaxt/triage-ai
```

TriageAI 明确采用了 **deterministic guardrails + LLM** 的混合思路，并把流程拆成红旗关键词、临床规则、LLM 推理和 safety envelope，还强调 audit trail 和 validation。这非常适合参考你当前的 `planner + validator + trace` 设计；但它的技术栈是 **Node.js / TypeScript / React**，更适合借“架构模式”，不适合直接并入你当前 Python doctor agent。

**建议借鉴部分：**

* safety envelope 的层级化思路
* warning / override / audit trace 的设计
* validator 的角色边界
* 高危场景不可降级的安全原则

---

## 13.2 Symptom-Guide-AI —— 借本地 RAG 骨架

```text
https://github.com/AhmedAbdelhamed01/Symptom-Guide-AI
```

Symptom-Guide-AI 已经包含你最需要的本地问诊型 RAG 要素：**Emergency Check、Symptom Accumulation、Stage Detection、Selective RAG**，并使用 **LangChain + Chroma + local Ollama/HuggingFace** 来完成知识库构建与检索。它自述为 research / educational prototype，因此不要直接照搬输出逻辑，但非常适合借它的 **ingestion pipeline、vector store 组织方式、selective retrieval 思路**。

**建议借鉴部分：**

* 本地知识库 ingestion 流程
* retrieval-only when needed 的 selective RAG 策略
* symptom accumulation / stage detection 的中间状态设计
* 本地 embedding / vector store 组织方式

---

## 13.3 Yale MedTutor / medical-rag —— 借检索基础设施

```text
https://github.com/yale-nlp/medical-rag
```

Yale 的 medical-rag（MedTutor）提供了**本地知识库索引、可选 live retrieval、reranker、配置驱动实验**等能力，更适合作为“本地检索实验框架”和“评测支架”，而不是直接作为你的 doctor dialogue engine。它的价值在于帮助你把 retrieval 做得更规范：chunking、indexing、reranking、config-based ablation。

**建议借鉴部分：**

* 本地 index 构建方式
* reranker 接口组织
* retrieval config 管理
* 离线评测结构

---

## 13.4 PreTriage —— 借交互约束

```text
https://github.com/chrisegener22/conuhacks-2026
```

PreTriage 的价值不在于完整架构，而在于它强调 **one focused question at a time** 和 conservative triage。这一点非常适合你的 Stage 2，因为你当前系统最需要的是“每轮一个主问题”的强约束，否则 planner 与 validator 会频繁冲突。

**建议借鉴部分：**

* 单轮单主问题约束
* 保守型分诊语气
* 患者可见输出的节制表达

---

## 14. 不建议直接采用的方向

### 14.1 不建议本阶段做 live website RAG

理由：

* guideline version 难锁定
* 结果不稳定
* 不利于 debug 和回放
* 不利于课堂 demo

### 14.2 不建议本阶段直接切到复杂多智能体 triage repo

有些研究型仓库会引入多智能体分工、置信度汇总、早停等机制，但你当前阶段的最优目标不是“更复杂”，而是“更稳、可控、可测”。

---

## 15. 建议的实现步骤

## Step 1. 建协议库

* 写首批 5 类 protocol YAML
* 建 complaint aliases / red flags / required slots / urgency rules

## Step 2. 写 protocol compiler

* YAML -> chunks
* YAML -> question graph
* YAML -> rules index

## Step 3. 写 protocol retriever

* complaint normalization
* sparse retrieval
* semantic rerank
* output evidence package

## Step 4. 写 planner

* 读取 evidence + dialogue state
* 输出 strict JSON plan contract

## Step 5. 写 validator

* schema check
* safety floor check
* one-question-per-turn check
* override / fallback

## Step 6. 接入 `api_v1.py`

* 只改 `DOCTOR_CALLED` 分支
* 外部 API 不变

## Step 7. 写 regression tests

覆盖：

* chest pain
* dyspnea
* stroke
* sepsis
* trauma
* 普通低风险主诉
* 多主诉场景
* code-switching
* planner JSON failure
* critical override

---

## 16. 验收标准

### 功能验收

* 能正确命中首批协议
* 每轮只问一个主问题
* 中文/英文输出与 session language 一致
* planner JSON 失败时能 fallback
* 安全关键冲突时必定 hard override

### 工程验收

* 不改变外部 API 结构
* 不破坏 Stage 1 回归测试
* planner_trace 可完整回放
* protocol files 可版本化管理

### 临床场景验收

* 对 chest pain / dyspnea / stroke / sepsis / trauma 能区分不同问诊重点
* 不因 top1 检索误差漏掉 secondary protocol 的高危红旗
* under-triage 风险优先被压低

---

## 17. 一句话交付目标

> 在不改现有外部接口和状态机主干的前提下，为 doctor agent 增加一个**离线本地、协议证据驱动、可追踪、可扩展**的 RAG 层，使系统从单场景脚本问诊升级为更贴近 diverse 急诊 complaint family 的受约束自适应问诊系统。

---

## 18. 给 Codex 的执行指令摘要

```text
Goal:
Implement an offline protocol-grounded RAG layer for the doctor agent only.

Do NOT:
- add live web retrieval
- change external API response schema
- expose internal plan contract to frontend
- replace existing state machine

Must implement:
- local protocol store (YAML/JSON)
- complaint normalization
- sparse retrieval + rerank
- evidence package builder
- strict JSON planner
- validator with hard safety floor
- shared_memory trace
- one-primary-question-per-turn policy

Primary integration point:
- week5_system/app/api_v1.py -> DOCTOR_CALLED branch

Initial protocol scope:
- chest_pain
- dyspnea
- stroke
- sepsis
- trauma
```

如果你接下来要真正交给 Codex 执行，最顺手的下一步不是继续补概念，而是把这份计划再压缩成一版 **implementation spec**：包括文件树、Pydantic schema、函数签名、伪代码和测试样例。
