# SIM Hospital Narrative Framework

## One-Sentence Project Definitions

### A. Resume version
I built a simulated emergency-department multi-agent system for triage, handoff, and resource-constrained patient flow, using rule-based state machines, structured memory, and frontend-backend synchronization to verify workflow correctness, scenario realism, and replayability.

### B. Personal statement version
This project showed me that in medical AI, the hard problem is often not generating answers but preserving state continuity, resource-aware routing, and safe handoff across workflow boundaries, which deepened my interest in workflow intelligence and structured clinical memory.

### C. Interview opener
This is a simulated emergency department where patients, nurses, doctors, and backend runtime all have explicit states. I worked on the user/auto modes, synchronization, memory, and validation so the system can model triage, resource bottlenecks, and handoff without losing state consistency.

## Problem Definition

### 中文解释
这个项目关注的是急诊科（Emergency Department）里真实存在的流程问题：患者到达后要先分诊，再进入医生评估、检查、处置、交接或出院，而每个步骤都受医生数量、床位、检验和影像能力、等待时间、交接对象等约束。表面上看，它像是“人多、排队久、医生忙”；但更深层的问题是，医院系统本质上是一个受资源约束的状态机，任何一步的状态转移、交接或回写不一致，都会导致流程断裂、信息丢失或安全风险。这个项目把这些问题拆成规则化状态、事件和资源约束，并通过前后端同步、记忆结构和回归测试把流程变成可验证对象。

### English version
This project targets the real workflow complexity of an emergency department: patient arrival, triage, physician assessment, diagnostic testing, disposition, and handoff are all constrained by doctors, nurses, beds, lab and imaging capacity, and time-sensitive transitions. The surface problem is long waiting lines, overloaded staff, and frequent bottlenecks. The deeper problem is that the ED behaves like a resource-constrained state machine, where any inconsistency in state transition, handoff, or runtime synchronization can break continuity and create safety risks. The project makes these workflow constraints explicit and testable through rule-based states, events, memory, and frontend-backend synchronization.

### Why it is worth doing
1. It is a real workflow system, not just a chatbot.
2. It has explicit state transitions, which makes errors observable.
3. It includes resource realism, so throughput and delays matter.
4. It requires memory because handoff and continuity are cross-step problems.
5. It supports regression testing, so runtime safety can be checked repeatedly.

### 5 likely advisor follow-ups
1. Why not just use a chat model?  
   Because the core task is workflow control and continuity, not open-ended dialogue.
2. Why not just animate a web page?  
   Because the system needs consistent states, step sync, and back-end record keeping.
3. Why multi-agent?  
   Because patients, nurses, doctors, and downstream receivers each have different roles and constraints.
4. Why memory?  
   Because handoff and follow-up require persistent summaries and structured prior state.
5. What makes it “medical AI”?  
   Because the entities, states, and constraints are framed around ED care delivery, not generic gaming logic.

## System Abstraction

| Layer | Repo evidence | Code paths | How to say it in a resume | How to explain it in an interview |
|---|---|---|---|---|
| Entity | patient, nurse, doctor, receiver unit, lab, imaging, bed, frontend user, backend engine | `app_core/rule_core/*`, `app_core/app/*`, `app_core/his/*`, `environment/frontend_server/*` | “Built an ED simulator with multiple interacting agent and resource entities.” | “I separated clinical actors from infrastructure and runtime actors.” |
| State | `ARRIVAL`, `WAITING_FOR_TRIAGE`, `TRIAGE_COMPLETE`, `ROUTED`, `WAITING_FOR_PHYSICIAN`, `UNDER_EVALUATION`, `WAITING_FOR_LAB`, `WAITING_FOR_IMAGING`, `AWAITING_DISPOSITION`, `ADMITTED`, `ICU`, `OR`, `DISCHARGED`, `TRANSFER`, `LWBS` | `app_core/rule_core/state_machine.py` | “Implemented explicit ED state transitions and escalation hooks.” | “Every patient step is a tracked state rather than hidden control flow.” |
| Event | arrival, triage complete, physician evaluation, lab/imaging routing, deterioration, handoff request/complete, boarding timeout | `app_core/rule_core/*`, `app_core/app/api_v1.py`, `reverie/backend_server/auto_memory_hooks.py` | “Captured workflow events for replay, audit, and continuity.” | “State changes are driven by events, not by opaque prompts.” |
| Resource | doctor availability, lab capacity, imaging capacity, turnaround times, bed availability, arrival profile, boarding timeout | `reverie/backend_server/week7_logic.py`, `app_core/queue_state_primitives/*`, `docs/architecture/week7_auto_baseline_analysis.md` | “Modeled resource constraints and bottlenecks.” | “The simulator isn’t just about sequence, but about throughput and capacity.” |
| Metric | queue length, wait time, LOS, boarding delay, handoff latency, state consistency, sync health, test pass rate | `queue_snapshot`, `live_dashboard_api`, test suites, regression scripts | “Verified workflow correctness and runtime stability.” | “I can show whether the system is progressing, lagging, or broken.” |

## Method vs Tool

| Type | Examples in repo | Why it belongs here |
|---|---|---|
| Method / Research design | rule-based state machine, multi-agent simulation, resource-constrained ED workflow simulation, structured memory for handoff, regression-based system verification, scenario-based stress testing | These are the ideas that make the project research-like |
| Module / Engineering component | User Mode, Auto Mode, L1 API, Memory v1, frontend movement loop, queue snapshot, handoff API, temp-storage curr_step tracking | These are the system pieces you can describe in a bullet |
| Tool / Implementation tech | Python, Django, JavaScript, JSON/JSONL, PowerShell, pytest, local LLM gateway | These support the implementation but should not be framed as the research contribution |

### What to put in PS
- The method: why a rule-based, memory-backed simulation was needed.
- The problem: why ED workflow continuity and resource bottlenecks matter.
- The insight: why state consistency is more important than surface-level responses.

### What to avoid
- “I built an AI doctor”  
- “I trained a clinical model”  
- “I deployed a hospital-ready system”  
- “Memory always improves care quality”  

## Evaluation

### Confirmed in repo
- malformed payload handling
- state-transition tests
- queue snapshot structure tests
- wait-time realism tests
- resource/scenario tests
- frontend/backend sync tests
- memory/HIS mapping tests
- timeline export tests
- local LLM fallback tests

### Partially supported
- fixed-seed reproducibility
- long-run backend stability
- browser sync under auto mode

### Missing Evidence / Need Verification
- quantitative memory ON/OFF ablation
- repeated-question rate
- clinical expert review
- real hospital calibration

## Limitation
- This is a simulator and workflow research platform, not a clinical decision system.
- Triage is rule-based and heuristic in the repo; it is not validated as a guideline-compliant clinical policy.
- LLM output is not the clinical truth source; the state machine and runtime records are.

## Future Work
1. Calibrate arrival, lab, and imaging distributions with real ED logs.
2. Add a discrete-event baseline and compare against the current agent-based workflow.
3. Quantify memory ON/OFF, handoff completeness, and repeated-question reduction.
4. Add clinician review for triage rules and safety escalation boundaries.
