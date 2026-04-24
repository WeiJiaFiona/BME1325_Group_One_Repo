# Week 8 Codex Implementation Spec — Memory v1 on Merged ED-MAS

## 0. Purpose

This spec defines **Week 8 Memory v1** for the merged ED system at:

```text
/home/jiawei2022/BME1325/week8/merge
```

The merged system already preserves:

* collaborator’s **auto mode** upgrades: arrival profiles, resource realism, boarding timeout, analysis outputs, and runtime robustness in the Django frontend/backend stack; and
* Jiawei’s **user mode** upgrades: user-mode state machine, calling nurse, shared memory across roles, `pending_messages`, doctor-only local KB + selective RAG, and LLM adapter behavior. 

Week 8 is **not** a planner rewrite and **not** another merge task.
Week 8 is a **shared memory substrate upgrade** on top of the merged system, focused on:

* continuity,
* handoff quality,
* replay / audit,
* repeated-question reduction,
* memory ON/OFF ablation.

The memory design should borrow the **architecture pattern** from the Group4 ICU backend analysis:

* episode anchor,
* append-only event bus,
* current materialized state,
* snapshots,
* audit logs,
* API-style access boundary,

while remaining **ED-compatible** and **MVP-lightweight**.

---

## 1. Week 8 Target Definition

### Primary Goal

Implement a **shared-but-mode-isolated Memory v1 substrate** for the ED merged system.

### What “shared-but-mode-isolated” means

* **Shared**:

  * one common memory schema,
  * one common storage abstraction,
  * one common retrieval interface,
  * one common replay/audit format,
  * one common evaluation protocol.
* **Mode-isolated**:

  * runtime data from `auto` and `user` must **never** be mixed in the same encounter timeline,
  * every memory record must be keyed by at least:

    * `run_id`
    * `mode`
    * `encounter_id`
    * `patient_id`

### Required Week 8 outcomes

1. Better continuity across ED phases and roles.
2. Better handoff completeness and lower omission risk.
3. Lower repeated-question rate in user mode.
4. Reproducible replay/export capability for both auto and user runs.
5. Memory ON/OFF ablation with measurable metrics.

### Explicit non-goals for Week 8

Do **not**:

* rewrite doctor planner ownership,
* change the hard-rule > RAG > LLM boundary,
* migrate to PostgreSQL as a required runtime dependency,
* add embedding retrieval as MVP,
* redesign auto/user mode boundaries,
* re-merge UI.

These boundaries are already established in the merged system and must remain stable.

---

## 2. Current System Baseline (What already exists)

### 2.1 Auto mode already has

* arrival profiles (`normal / surge / burst`),
* lab/imaging capacity and turnaround timing,
* boarding timeout event recording,
* analysis outputs such as `resource_event_metrics.json`,
* runtime robustness in Django view/path resolution.

### 2.2 User mode already has

* intake → calling nurse → triage → waiting/call → doctor → bedside nurse → done flow,
* calling nurse,
* shared memory across roles,
* `pending_messages` + phase auto-progression,
* doctor-only local KB + selective RAG,
* one-question-per-turn guard and anti-repeat fixes,
* tolerant LLM adapter. 

### 2.3 Merged mode rule

* Backend startup `EDSIM_MODE` is the single source of truth.
* Frontend `ui_mode` must not switch backend runtime behavior.
* If mode mismatches, user endpoints return `409 MODE_MISMATCH`.

---

## 3. Memory v1 Scope

### 3.1 Modules to implement in Week 8

Week 8 MVP must implement exactly these core modules:

1. `EpisodeMemoryEventLog`
2. `CurrentEncounterMemory`
3. `HandoffMemorySnapshot`
4. bounded retrieval at decision checkpoints
5. replay export / audit trail
6. memory ON/OFF ablation hooks

This is aligned with the current migration analysis and MVP recommendation.

### 3.2 Do not implement yet

* embedding/vector memory retrieval
* PostgreSQL-first persistence
* ICU-specific APACHE / vital schema migration
* FastAPI service extraction as a hard dependency
* learned experience retrieval

The migration analysis already marks these as out of MVP scope.

---

## 4. Memory Sharing Semantics: Does auto and user share memory?

## Answer

**Yes, they share the memory infrastructure; no, they do not share runtime encounter memory instances.**

### Shared

Auto and user must share:

* memory schema,
* event taxonomy,
* storage abstraction,
* summary builder,
* handoff snapshot builder,
* replay export format,
* audit format,
* ablation hooks.

### Not shared

Auto and user must **not** share:

* one encounter timeline,
* one run state,
* one active scratch summary,
* one replay segment.

### Required isolation keys

Every memory record must include at least:

* `memory_id`
* `run_id`
* `mode`
* `encounter_id`
* `patient_id`
* `step`
* `sim_time`
* `agent_role`
* `event_type`

This is consistent with your Week 8 analysis of the minimal ED memory record. 

---

## 5. Borrowed Reference Design from Group4

Use Group4 as an **architecture reference**, not as a direct runtime dependency.

### Borrow these ideas

1. **Admission/encounter as the episode anchor**
2. **append-only event bus**
3. **detail fact vs current summary separation**
4. **checkpoint snapshots**
5. **audit logs**
6. **API/service boundary for data access**

These are the most transferable ideas identified in the migration analysis.

### Do not directly copy

* ICU-specific schema,
* APACHE-specific fields,
* PostgreSQL as mandatory dependency,
* full FastAPI stack as Week 8 prerequisite.

---

## 6. Code Structure

All new Week 8 work must go under the merged system root.

### New module layout

```text
week8/merge/
  app_core/
    memory/
      __init__.py
      schema.py
      taxonomy.py
      storage.py
      episode_memory.py
      current_memory.py
      handoff_memory.py
      retrieval.py
      replay_buffer.py
      audit.py
      hooks.py
      config.py
      service.py
```

### Why here

`user` runtime logic already lives under `app_core/`, and the merged system preserved `app_core` as the user-mode source-of-truth runtime layer. Memory v1 should become a **shared app-core service layer**, not a separate mode-specific subtree. 

---

## 7. Core Data Contracts

## 7.1 MemoryItem

Use this as the canonical raw event record:

```python
MemoryItem = {
    "memory_id": str,
    "run_id": str,
    "mode": str,              # "auto" | "user"
    "encounter_id": str,
    "patient_id": str,
    "step": int,
    "sim_time": float | int | None,
    "wall_time": str | None,
    "agent_role": str,
    "event_type": str,
    "source": str,
    "priority": str | int,
    "content": str,
    "structured_facts": dict,
    "state_before": dict | None,
    "state_after": dict | None,
    "tags": list[str],
    "salience": float | int | None,
    "retrieval_scope": list[str] | None,
    "created_at": str,
}
```

This is aligned with your migration analysis of the ED-compatible memory record. 

---

## 7.2 CurrentEncounterSummary

Derived view only. Not source of truth.

```python
CurrentEncounterSummary = {
    "run_id": str,
    "mode": str,
    "encounter_id": str,
    "patient_id": str,
    "current_state": str,
    "current_zone": str | None,
    "acuity": str | None,
    "latest_vitals": dict,
    "active_risks": list[dict],
    "pending_tasks": list[dict],
    "completed_actions": list[dict],
    "latest_doctor_findings": dict,
    "latest_test_status": dict,
    "source_memory_ids": list[str],
    "updated_at_step": int,
}
```

Rule:

* raw events are append-only;
* current summary is derived and rebuildable.

That principle is explicitly part of your migration suitability and MVP guidance.

---

## 7.3 HandoffMemorySnapshot

Receiver-ready, fixed-template object.

```python
HandoffMemorySnapshot = {
    "snapshot_id": str,
    "run_id": str,
    "mode": str,
    "encounter_id": str,
    "patient_id": str,
    "from_role": str,
    "to_role": str,
    "handoff_stage": str,     # requested | completed
    "patient_brief": str,
    "current_state": dict,
    "completed_actions": list[dict],
    "pending_tasks": list[dict],
    "active_risks": list[dict],
    "next_actions": list[dict],
    "source_memory_ids": list[str],
    "created_at_step": int,
}
```

This follows your requirement that handoff memory be a fixed receiver-ready summary generated from current state + salient memory + pending tasks.

---

## 7.4 MemoryQuery

Bounded retrieval only.

```python
MemoryQuery = {
    "run_id": str,
    "mode": str,
    "encounter_id": str,
    "checkpoint": str,
    "agent_role": str | None,
    "event_types": list[str] | None,
    "tags": list[str] | None,
    "top_k": int,
    "max_age_steps": int | None,
    "include_snapshots": bool,
}
```

Bounded retrieval rules from your proposal:

* same `encounter_id` first,
* checkpoint-scoped event filtering,
* `top_k <= 5`,
* bounded age window,
* no cross-encounter retrieval by default.

---

## 8. Event Taxonomy (Freeze before parallel work begins)

Create:

```text
app_core/memory/taxonomy.py
```

Minimum required event types:

* `encounter_started`
* `calling_nurse_called`
* `vitals_measured`
* `triage_started`
* `triage_completed`
* `doctor_assessment_started`
* `doctor_assessment_checkpoint`
* `test_ordered`
* `test_result_ready`
* `handoff_requested`
* `handoff_completed`
* `disposition_decided`
* `boarding_started`
* `boarding_timeout`
* `patient_deterioration`
* `resource_bottleneck`
* `encounter_closed`

These align with:

* your user-mode stage transitions and calling nurse flow,
* collaborator auto-mode resource/boarding realism,
* your identified Week 8 write/checkpoint locations.

---

## 9. Storage Strategy

## Week 8 MVP storage rule

Do **not** make PostgreSQL mandatory.

### Required implementation

Implement a backend-neutral storage interface with at least:

```python
class MemoryStorage:
    def append_event(self, item): ...
    def upsert_current_summary(self, summary): ...
    def get_current_summary(self, run_id, mode, encounter_id): ...
    def write_snapshot(self, snapshot): ...
    def retrieve(self, query): ...
    def append_audit(self, audit_record): ...
```

### MVP backend recommendation

1. **Primary**: JSONL event log + JSON current summary + JSON snapshot files
2. **Optional secondary**: SQLite backend if easy
3. **Explicitly not required**: PostgreSQL backend in Week 8

This matches your own migration guidance: keep the API/data boundary idea, but use in-memory / JSON / lightweight persistence first.

---

## 10. Write Path (Hook Points)

## 10.1 User mode hook points

Developer integrating user mode must add memory writes at:

* encounter/session start
* calling nurse call
* vitals measured
* triage completed
* doctor assessment checkpoint
* test ordered
* test result ready
* handoff requested
* handoff completed
* disposition decided
* encounter/session done

These points are consistent with user-mode behavior already preserved in merge. 

## 10.2 Auto mode hook points

Developer integrating auto mode must add memory writes at:

* encounter spawned
* triage/doctor/test state transitions
* resource bottleneck event
* boarding start
* boarding timeout
* handoff/disposition events
* encounter closed

These points correspond to collaborator’s auto mode features and analysis targets.

---

## 11. Retrieval Path

### Retrieval must only happen at bounded checkpoints

Allowed retrieval checkpoints:

* post-triage
* doctor assessment start/checkpoint
* test result ready
* handoff requested
* handoff completed
* replay export

### Retrieval must not be always-on

Do not retrieve memory on every utterance or every simulation step.

### Retrieval policy

* current summary lookup is O(1)
* event retrieval uses checkpoint-specific filtering
* `top_k <= 5`
* `max_age_steps <= 20` by default
* handoff retrieval prioritizes:

  * risks
  * pending tasks
  * latest completed actions
  * current state

These are directly aligned with your bounded retrieval design.

---

## 12. Replay and Audit

## 12.1 ExperienceReplayBuffer

Week 8 replay buffer must support slicing by:

* `run_id`
* `mode`
* `scenario_tag`
* `encounter_id`
* `step range`

### Required outputs

* raw events
* summaries
* snapshots
* audit logs
* handoff summaries

## 12.2 Audit log

Every memory write and retrieve should emit audit records containing at least:

* `op_id`
* `run_id`
* `mode`
* `encounter_id`
* `op_type` (`write_event`, `update_summary`, `write_snapshot`, `retrieve`)
* `checkpoint`
* `source_ids`
* `top_k`
* `latency_ms`
* `timestamp`

This follows your replay/audit design goals.

---

## 13. Parallel Development Scaffold (Two Developers)

## Developer A — Memory substrate owner

Owns:

* `app_core/memory/schema.py`
* `taxonomy.py`
* `storage.py`
* `episode_memory.py`
* `current_memory.py`
* `handoff_memory.py`
* `retrieval.py`
* `replay_buffer.py`
* `audit.py`
* `service.py`

### A must not

* modify user planner ownership
* modify auto simulation policies
* create a second schema elsewhere
* hardcode mode-specific behavior into substrate

---

## Developer B — Integration and evaluation owner

Owns:

* user hook integration
* auto hook integration
* ON/OFF ablation plumbing
* replay export CLI/tests
* continuity / handoff / repeated-question evaluation
* docs and runbook updates

### B must not

* invent a second memory schema
* bypass storage abstraction
* patch substrate contract locally inside user or auto code

---

## Shared freeze before coding

Before implementation begins, freeze:

1. `MemoryItem`
2. `CurrentEncounterSummary`
3. `HandoffMemorySnapshot`
4. `MemoryQuery`
5. event taxonomy
6. storage interface
7. hook point list

No developer should proceed until these contracts are accepted.

---

## 14. File and Branch Discipline

### Required code location

All new Week 8 code must live in:

```text
/home/jiawei2022/BME1325/week8/merge
```

### No cross-import rule

Do not import runtime logic back from:

* `/home/jiawei2022/BME1325/week8/user_mode`
* `/home/jiawei2022/BME1325/week8/auto`

Merge is the only source of truth for Week 8 development. This follows the prior merge rules. 

### Recommended branch/work split

* Branch A: `week8-memory-substrate`
* Branch B: `week8-memory-integration`

If working locally without branches, at least split commits by ownership.

---

## 15. Tests and Acceptance

## 15.1 Required tests

Create:

```text
tests_week8/
  test_memory_schema.py
  test_episode_memory.py
  test_current_memory.py
  test_handoff_memory.py
  test_memory_retrieval.py
  test_memory_replay.py
  test_memory_user_hooks.py
  test_memory_auto_hooks.py
  test_memory_ablation.py
```

## 15.2 Minimum acceptance criteria

### A. Schema/stability

* all memory records validate
* summaries are rebuildable from raw events
* no cross-mode mixing in one encounter

### B. User-mode continuity

* delayed test result still updates current summary
* doctor handoff can see pending tasks / risks
* repeated-question rate decreases or at minimum does not worsen with memory ON

### C. Auto-mode continuity

* boarding timeout events are captured in memory
* resource bottleneck events are replayable
* replay export works on at least one surge/bottleneck run

### D. Handoff completeness

* snapshot includes:

  * patient brief
  * current state
  * completed
  * pending
  * risks
  * next actions
  * source memory ids

### E. ON/OFF ablation

Must support:

* memory OFF baseline
* memory ON comparison
* metrics:

  * repeated-question rate
  * handoff omission rate
  * continuity consistency
  * latency overhead

This is directly aligned with your Week 8 target and replay plan.

---

## 16. Runbook Requirements for Codex

Codex must also update documentation with:

* where Memory v1 code lives
* how to enable/disable memory
* how to export replay
* how to run user-mode continuity checks
* how to run auto-mode continuity checks
* what is intentionally **not** implemented yet

---

## 17. Explicit Constraints for Codex

```text
You are implementing Week 8 Memory v1 on top of the already merged ED system.

You must preserve:
- collaborator auto mode realism and analysis behavior
- Jiawei user mode state machine, calling nurse, doctor-only RAG, and mode gating
- EDSIM_MODE as the single backend source of truth

You must implement:
- EpisodeMemoryEventLog
- CurrentEncounterMemory
- HandoffMemorySnapshot
- bounded retrieval
- replay export
- memory ON/OFF ablation hooks

You must not:
- rewrite doctor planner ownership
- change next_slot ownership
- change safety floor ownership
- change disposition ownership
- make PostgreSQL mandatory
- add embedding retrieval in MVP
- mix auto and user encounter data in one memory timeline

Use one shared memory substrate for both modes, but isolate records by run_id + mode + encounter_id.
```

---

## 18. About `XanderZhou2022/BME_1325_Group4_repo`: does it really have no database/storage content?

**No — it does have database/storage-related content, but it is not just a lightweight in-memory demo.**

What can be verified from the public repo:

* The public repo exists, and the currently visible branch in the web UI is `week3_0320`. ([GitHub][1])
* Under `system/backend`, it contains:

  * `api/`
  * `测试数据库/`
  * `requirements.txt`
  * `.env`
  * `数据规范/` ([GitHub][2])
* Inside `system/backend/api/README.md`, the repo explicitly describes:

  * a **unified FastAPI data entry point**,
  * that external modules should access data through the API rather than directly connecting to PostgreSQL,
  * an environment variable `ICU_PG_DSN` for PostgreSQL connection,
  * example startup with `uvicorn app.main:app`,
  * DB health endpoint references. ([GitHub][3])

So the accurate conclusion is:

### What it **does** have

* backend API layer
* database-oriented architecture
* PostgreSQL connection expectations
* test database/setup-related directory
* data specification docs

### What it **does not yet prove** from what is publicly visible

* that it already contains a fully mature, production-grade ED/ICU memory subsystem ready to graft directly into your project
* that its current public branch is later than early-stage week3 and stable enough to reuse wholesale

### Therefore

It is correct to say:

> **Group4 repo has real database/storage-related design and backend API infrastructure.**
> It is **not** correct to say it has “no database-related content.”
> But it is still better used in Week 8 as an **architecture reference**, not as a direct dependency to import wholesale.

---

## 19. Final instruction to Codex

Implement Week 8 Memory v1 in the merged system as a **shared infrastructure layer** with **mode-isolated runtime data**, preserving all current auto/user boundaries and using the Group4 design only as an architecture reference.

[1]: https://github.com/XanderZhou2022/BME_1325_Group4_repo "GitHub - XanderZhou2022/BME_1325_Group4_repo · GitHub"
[2]: https://github.com/XanderZhou2022/BME_1325_Group4_repo/tree/week3_0320/system/backend "BME_1325_Group4_repo/system/backend at week3_0320 · XanderZhou2022/BME_1325_Group4_repo · GitHub"
[3]: https://github.com/XanderZhou2022/BME_1325_Group4_repo/tree/week3_0320/system/backend/api "BME_1325_Group4_repo/system/backend/api at week3_0320 · XanderZhou2022/BME_1325_Group4_repo · GitHub"
