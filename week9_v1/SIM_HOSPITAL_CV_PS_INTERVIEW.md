# SIM Hospital CV / PS / Interview Package

## Usage Note
This file is evidence-based. If a bullet is not clearly backed by repo files or tests, keep the wording conservative or move it to `SIM_HOSPITAL_MISSING_EVIDENCE.md`.

## CV Bullets

### Version 1: High-signal research bullets
- Built a simulated emergency-department workflow system with rule-based triage, explicit state transitions, and resource realism for lab/imaging capacity, turnaround time, and boarding timeout.
- Implemented user-mode and auto-mode runtime paths, including frontend-backend synchronization through movement/update/process files and runtime health checks.
- Designed structured memory and handoff persistence for encounter continuity, including current summaries, handoff snapshots, audit logs, and replay exports.
- Added schema validation, malformed-input handling, and regression tests across user mode, timeline export, queue snapshots, and frontend/backend sync.

### Version 2: If you want to emphasize engineering
- Built a Django + Phaser ED simulator that keeps `curr_step`, `sim_status`, `movement`, and `environment` synchronized during runtime.
- Added backend health checks, bridge logging, and debug-contract fields to make runtime failures observable instead of silent.
- Integrated memory-to-HIS mapping so encounter events, summaries, handoff snapshots, and audit records can be persisted in a structured form.

### Version 3: Short version
- Simulated ED multi-agent workflows with triage, handoff, memory, and synchronization tests.

## PS Versions

### 200-word Chinese version
我参与了一个面向急诊科流程的模拟医院项目。这个项目把患者、护士、医生、检验、影像和床位等对象抽象成多智能体与资源约束系统，通过规则化状态机、分诊策略、交接接口和结构化记忆，把急诊中“分诊、等待、检查、交接、出院”的流程变成可追踪、可回放、可测试的系统。对我触动最大的是，这个问题并不只是“回答对不对”，而是“状态是否持续一致、信息是否在交接中丢失、资源瓶颈是否被正确暴露”。因此我在项目中重点关注了前后端同步、运行时健康检查、handoff snapshot、current summary 和 audit log 等机制，也逐渐意识到医疗 AI 的关键不只是生成能力，而是流程安全、连续性和可验证性。这段经历让我更明确地对医学流程智能化、结构化记忆和可解释系统产生兴趣。

### 250-word English version
I worked on a simulated emergency-department project that turns patient triage, physician evaluation, lab/imaging constraints, and handoff into an explicit multi-agent workflow. Instead of treating the system as a chat interface, we modeled it as a resource-constrained state machine with structured events, runtime synchronization, and memory-backed continuity. What I found most important was that the core challenge in medical AI is often not generating a response, but preserving state consistency across transitions, handoffs, and runtime boundaries. In this project, I focused on the user-mode and auto-mode pipelines, the frontend-backend movement loop, and the structured memory components such as current summaries, handoff snapshots, and audit logs. I also worked with regression and smoke tests to verify malformed payload handling, queue snapshots, and synchronization between `movement`, `environment`, and `curr_step` files. This project made me interested in workflow intelligence for healthcare: how to build systems that are not only intelligent, but also traceable, resource-aware, and safe under failure. It also pushed me to think about how memory, rules, and simulation can complement each other in medical systems, especially when the goal is to model clinical workflow rather than simply generate text.

## Interview Versions

### 1-minute version
这是一个急诊模拟医院项目。我主要做的是把患者分诊、医生评估、检查资源、交接和前后端同步这些流程做成可追踪的状态机和运行时链路。它的重要性在于，急诊的难点不是“能不能回答”，而是“状态会不会断、信息会不会丢、资源瓶颈会不会被看见”。我在里面重点看了 user mode、auto mode、memory 和记日志/测试，保证系统能回放、能校验，也能在出错时定位问题。

### 3-minute version
这个项目是一个面向急诊科流程的模拟医院系统。它不是普通聊天机器人，而是把患者、护士、医生、检验和影像资源放进一个规则化的多智能体模拟里。系统一边用状态机描述分诊、评估、检查、交接和出院，一边用 memory、audit 和 timeline 记录流程连续性，再通过前后端同步把运行状态可视化出来。我在其中主要关注 user mode、auto mode、前后端 movement 回写、以及 structured memory 和 HIS 映射这几条链路。这个项目让我更清楚地看到，医疗 AI 的关键不是单点生成能力，而是如何在资源约束下保持流程安全、状态一致和信息连续性。

## 10-Minute Presentation Outline
1. Clinical scenario: emergency department workflow and bottlenecks.
2. Problem statement: triage, handoff, and state continuity under resource constraints.
3. System architecture: entities, states, events, resources, metrics.
4. User mode: rule-based triage and handoff path.
5. Auto mode: multi-agent simulation and movement synchronization.
6. Frontend-backend sync: `update_environment`, `process_environment`, `curr_step`, `sim_status`.
7. Memory v1: events, summaries, snapshots, audit logs.
8. HIS bridge: memory-to-HIS mapping and timeline export.
9. Validation: malformed inputs, sync tests, scenario tests, regression tests.
10. Limitations and future work.

## 20 Advisor Questions and Answer Points

| Question | Answer point |
|---|---|
| Why is this not just a chatbot? | The core problem is workflow continuity and state transitions, not open-ended conversation. |
| Why is this not just a web animation? | The UI reflects a backend state machine and persistent records, not just visual motion. |
| What is the real scenario? | Emergency department triage, evaluation, diagnostics, disposition, and handoff. |
| What makes the problem hard? | Resource constraints, state consistency, and information continuity. |
| Why multi-agent simulation? | Different actors have different constraints and responsibilities. |
| Why rule-based? | The repo uses explicit policies and state transitions, which are inspectable and testable. |
| Why memory? | Handoff and continuity need structured summaries and snapshots across steps. |
| What is `curr_step` for? | It is the runtime pointer used to keep backend and frontend aligned. |
| What is `sim_status` for? | It exposes runtime progress and health to the UI and tests. |
| What is `movement`? | It is the step-by-step motion payload consumed by the frontend. |
| What is `environment`? | It is the frontend-written state snapshot after playback. |
| What is `queue_snapshot`? | It summarizes load, occupancy, and handoff queues. |
| What is the strongest evidence of correctness? | Schema validation, timeline export, sync tests, and scenario tests. |
| What is the strongest evidence of realism? | Arrival profile, lab/imaging capacity, turnaround, and boarding timeout logic. |
| What is the strongest evidence of memory? | `MemoryItem`, current summary, handoff snapshot, and audit log persistence. |
| Did LLM control the workflow? | No strong evidence says so; LLM fallback exists, but the workflow is rule/state driven. |
| Is memory always on? | The code supports ON/OFF, but full ablation evidence is missing. |
| What failed during debugging? | Frontend sync bugs, backend stalled runtime, and bridge/file-write mismatches. |
| Can this run like a hospital system? | No, it is a simulator and research platform, not a clinical deployment. |
| What would you do next? | Add real data calibration, expert review, and quantitative ablation studies. |
