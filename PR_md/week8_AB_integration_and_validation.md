可以。下面给你一版**面向 Codex 的整合联调文档**，适合你现在的角色：
你已经把 A 的 substrate 拉到本地，也已经有 B 的 user-side 集成结果，现在你要做的是：

> **对接 A 和 B 的开发，完成连通性测试、验收、收口优化，并把系统整理到可展示/可交付状态。**

你可以把下面这份内容直接保存成例如：

```text
PR_md/week8_AB_integration_and_validation.md
```

然后交给 Codex 执行。

---

# Week 8 Memory v1 — A/B Integration, Connectivity Validation, and Final Polish Spec

## 0. Purpose

You are no longer acting purely as Developer A or Developer B.
You are now acting as the **integration owner** for Week 8 Memory v1 in the merged ED-MAS system at:

```text
/home/jiawei2022/BME1325/week8/merge
```

Developer A has already delivered the shared memory substrate under `app_core/memory/`.
Developer B has already completed the main user-side integration goals:

* lazy memory getter in `api_v1.py`
* stable `memory_encounter_id`
* user-mode hooks
* `CurrentEncounterSummary` updates
* `HandoffMemorySnapshot` writes
* `MEMORY_V1_ENABLED=0/1` ablation
* fail-open integration tests
* `tests_week8` passing on the user side

At this stage, the goal is **not** to add another large feature.
The goal is to:

1. validate end-to-end connectivity between A-side substrate and B-side integration,
2. confirm that Week 8 objectives are truly met,
3. fix any contract mismatches or weak spots,
4. add a small amount of high-value polish for demo/readiness,
5. defer large new features unless they are clearly low-risk.

---

## 1. Current Baseline (Assume Already Present)

### 1.1 A-side substrate already delivered

Under:

```text
app_core/memory/
```

Expected modules already exist:

* `schema.py`
* `taxonomy.py`
* `storage.py`
* `service.py`
* `config.py`
* `hooks.py`
* `episode_memory.py`
* `current_memory.py`
* `handoff_memory.py`
* `retrieval.py`
* `replay_buffer.py`
* `audit.py`

### 1.2 B-side user integration already delivered

Expected user-side integration already exists in `app_core/app/api_v1.py`:

* lazy getter for memory service
* stable `memory_encounter_id`
* event hooks for user-mode clinical flow
* summary update checkpoints
* handoff snapshot writes
* fail-open behavior
* `tests_week8` user-side integration coverage

### 1.3 Boundaries that must remain unchanged

Do **not** break:

* doctor planner ownership
* `next_slot` ownership
* safety floor ownership
* disposition ownership
* `EDSIM_MODE` as the single backend source of truth
* current user-mode calling nurse / pending_messages / phase auto-progression behavior
* collaborator auto-mode realism / week7 behavior

---

## 2. Primary Goal of This Step

This step is a **connectivity + validation + polish** step.

You must ensure that:

1. A-side substrate and B-side integration are truly connected end-to-end.
2. Week 8 memory artifacts are produced correctly.
3. ON/OFF ablation is reproducible.
4. fail-open is real, not just claimed.
5. replay/snapshot outputs are usable for demo and reporting.
6. only low-risk improvements are added.

This step is **not** a planner rewrite, not a new merge, and not a PostgreSQL/vector-memory expansion.

---

## 3. Required Reading Before Coding

Read these first:

1. `app_core/memory/*`
2. `app_core/app/api_v1.py`
3. `PR_md/developer_A.md`
4. `PR_md/developer_B.md`
5. `PR_md/developer_B_memory_prework.md`
6. `PR_md/developer_B_hook_inventory.md`
7. `tests_week8/*`
8. `tests/backend/test_memory_schema.py`
9. `tests/backend/test_memory_storage.py`
10. `tests/backend/test_memory_service.py`
11. `tests/backend/test_memory_retrieval.py`

Do a quick consistency check between:

* A’s actual method names and config names
* B’s integration assumptions
* current tests and runbook

---

## 4. What You Must Validate End-to-End

## 4.1 A → B service connectivity

Confirm that B-side code uses only the A-side substrate entrypoints.

Required checks:

* user integration does **not** create another schema
* user integration does **not** write JSON/JSONL directly
* all user memory writes go through `app_core/memory/service.py`
* helper usage comes from `app_core/memory/hooks.py`

## 4.2 User flow → memory event connectivity

Confirm that the following event types are actually emitted in real user-mode flow:

* `encounter_started`
* `calling_nurse_called`
* `vitals_measured`
* `triage_completed`
* `doctor_assessment_started`
* `doctor_assessment_checkpoint`
* `disposition_decided`
* `handoff_requested`
* `handoff_completed`
* `encounter_closed`

## 4.3 Summary connectivity

Confirm that `CurrentEncounterSummary` is updated at the intended checkpoints and contains current facts from runtime/session/shared_memory.

## 4.4 Snapshot connectivity

Confirm that `HandoffMemorySnapshot` is written at both:

* `requested`
* `completed`

and includes the full key set.

## 4.5 Replay/export connectivity

Confirm that replay export contains:

* raw events
* summaries
* snapshots
* audits

for a user-mode run.

## 4.6 Fail-open connectivity

Confirm that if memory calls fail:

* the user clinical flow still continues,
* no planner/rule ownership is changed,
* the system remains usable.

---

## 5. Required Connectivity Test Commands

Run these commands and collect results.

## 5.1 A-side substrate tests

```bash
pytest -q tests/backend/test_memory_schema.py \
          tests/backend/test_memory_storage.py \
          tests/backend/test_memory_service.py \
          tests/backend/test_memory_retrieval.py
```

## 5.2 Week 8 integration tests

```bash
pytest -q tests_week8
```

## 5.3 Key user regression tests

Run at least the user tests already known to be important/stable, for example:

```bash
pytest -q tests_user
```

or the specific subtests previously used for user regression if full suite is too large.

## 5.4 Memory OFF ablation

```bash
MEMORY_V1_ENABLED=0 pytest -q tests_week8
```

## 5.5 Memory ON ablation

```bash
MEMORY_V1_ENABLED=1 pytest -q tests_week8
```

If tests use temp roots, ensure `MEMORY_V1_ROOT` points to a temporary directory during tests.

---

## 6. Artifact Inspection (Manual Validation)

After running at least one user-mode flow with memory enabled, manually inspect the runtime artifacts.

Expected root (unless overridden):

```text
runtime_data/memory/
```

Check:

* `events.jsonl`
* `audit.jsonl`
* `current/<mode>/<run_id>/<encounter_id>.json`
* `snapshots/<mode>/<run_id>/<encounter_id>/<snapshot_id>.json`

Manually confirm:

1. event order looks sensible
2. `step` is monotonically increasing
3. all records include:

   * `run_id`
   * `mode`
   * `encounter_id`
   * `patient_id`
4. summary reflects real runtime/session facts
5. snapshots include the full template keys
6. OFF mode does not create live artifacts (or produces empty/no-op output, according to A’s design)

---

## 7. Immediate Low-Risk Optimizations You May Implement

Only implement optimizations that are clearly low-risk and improve usability, testability, or demo-readiness.

## 7.1 Compatibility alias for summary update

A-side public method is `update_current_summary(...)`, while some earlier assumptions used `upsert_current_summary(...)`.

Low-risk improvement:

* optionally add a compatibility alias in `service.py`:

  * `upsert_current_summary = update_current_summary`

This is optional but useful.

## 7.2 Config/readme consistency

Unify docs and runbooks around:

* `MEMORY_V1_ENABLED`
* `MEMORY_V1_ROOT`

Make sure old `MEMORY_ENABLED` wording is removed or explicitly marked legacy (use `MEMORY_V1_ENABLED`).

## 7.3 Handoff snapshot completeness hardening

Ensure snapshots always include the full template keys:

* `patient_brief`
* `current_state`
* `completed_actions`
* `pending_tasks`
* `active_risks`
* `next_actions`
* `source_memory_ids`

Missing keys should be treated as a defect; empty lists are acceptable.

## 7.4 Replay export usability

If easy and low-risk, add one of:

* a tiny CLI wrapper
* or a small analysis/export helper

so replay can be exported more easily for demo.

This is a good polish item if it does not widen scope too much.

## 7.5 Getter/test reset ergonomics

If not already clean, improve testing ergonomics for the lazy memory getter:

* easy reset hook for tests
* clean monkeypatch path
* no stale singleton across test cases

---

## 8. What to Defer Unless Everything Is Green

Defer these unless all user-side tests and validations are already green:

1. auto-mode import-path shim
2. generalized auto runtime logger bridge
3. broad auto-mode hook integration
4. SQLite backend
5. PostgreSQL/backend service expansion
6. embedding/vector memory retrieval

If you attempt any auto work, limit it to **one minimal safe hook** only, such as `boarding_timeout`, and only after all user-side work is green.

---

## 9. Success Criteria for This Integration Step

This step is successful only if all of the following are true:

### 9.1 Substrate validation

* A-side substrate tests pass

### 9.2 User integration validation

* key user events are actually written
* `CurrentEncounterSummary` updates at intended checkpoints
* `HandoffMemorySnapshot` is generated at requested/completed stages
* replay export includes user events, summaries, snapshots, audits

### 9.3 Ablation validation

* `MEMORY_V1_ENABLED=0/1` both run successfully
* clinical flow / hard-rule outcomes do not change because of memory ON/OFF
* memory artifacts differ in the expected way

### 9.4 Fail-open validation

* forced memory exceptions do not crash user flow
* planner/rule ownership remains unchanged

### 9.5 Readiness

* docs/runbook are aligned with actual A-side implementation
* runtime artifact paths are ignored by git
* results are clear enough for classroom demo/reporting

---

## 10. Reporting Format

At the end, produce a concise integration report with:

1. **What was validated**
2. **What failed initially and how it was fixed**
3. **What remains deferred**
4. **Exact commands used**
5. **Which artifacts were manually inspected**
6. **Whether Week 8 can be considered complete for A/B combined delivery**

---

## 11. Explicit Constraints

```text
You are now integrating and validating the combined A+B Week 8 Memory v1 work.

You must preserve:
- collaborator auto-mode week7 behavior
- Jiawei user-mode state machine and doctor-only RAG boundaries
- EDSIM_MODE as the single backend source of truth
- planner/next_slot/safety floor/disposition ownership

You must validate:
- substrate ↔ integration connectivity
- user-mode hooks
- summary updates
- handoff snapshots
- replay/export
- ON/OFF ablation
- fail-open behavior

You may add only low-risk optimizations:
- naming/documentation consistency
- service compatibility alias
- handoff completeness hardening
- replay export usability
- lazy getter test ergonomics

You must not:
- create another schema or storage path
- directly write JSONL/SQLite from business code
- start a large new auto-mode integration effort unless all user-side validation is already green
- broaden scope into PostgreSQL/vector-memory/planner rewrite
```

---

## 12. Final Goal

By the end of this step, the Week 8 Memory v1 work should no longer be “A substrate + B integration in parallel,” but a **connected, validated, and demo-ready combined delivery**.
