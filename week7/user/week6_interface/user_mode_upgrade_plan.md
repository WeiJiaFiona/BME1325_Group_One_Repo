# User Mode Upgrade Plan (Phase 1 + Phase 2)

## Overview
This plan implements the ED user-mode upgrade in two implementation stages.
- Stage 1 (Phase 1): fix core realism/flow issues and stabilize hybrid orchestration.
- Stage 2 (Phase 2): introduce protocol-grade RAG for richer, safer clinical QA.

Each stage includes:
1. implementation scope,
2. test protocol,
3. acceptance gate before moving to next stage.

---

## Phase 1 - Core Flow, Shared Memory, Hybrid Agents

### Objectives
- Remove rigid patient-side vital self-report blocking; use a new **calling nurse** for call-number + physiological measurement.
- Make agent handoffs immediate (no extra "hello" needed after state transitions).
- Keep non-user patients moving autonomously during user mode.
- Align user-patient map movement with dialogue phase and target zone.
- Introduce backend shared memory so all agents read/write the same patient state.
- Differentiate agents visually with role-specific figures (not only tint color).

### Implementation Scope
1. **Hybrid backend orchestration (`week5_system/app/api_v1.py`)**
- Keep deterministic triage/handoff guards.
- Keep LLM as reasoning/communication brain for adaptive prompts.
- Add calling nurse role (`calling_nurse`) with responsibilities:
  - number calling,
  - vitals measurement,
  - handoff trigger to next role.
- Add shared memory object in session state:
  - chief complaint, symptoms timeline, measured vitals,
  - triage result, doctor findings, handoff/bed result,
  - movement target and status history.
- Add pending message queue so phase changes can push immediate prompts.
- Add background progression on status polling:
  - waiting -> called -> doctor prompt without waiting for user text.

2. **Frontend behavior (`week6_interface/frontend_server/templates/home/home.html`)**
- Poll user session status periodically.
- Render pending messages automatically when returned.
- Keep world stepping in user mode via lightweight background run ticks.
- Replace manual-only progression by event-driven handoff rendering.

3. **Map and role visualization (`.../templates/home/main_script.html`)**
- Keep baseline movement engine.
- Add role-specific figure mapping for key roles:
  - calling nurse, triage nurse, doctor, bedside nurse, user patient, other patients.
- Use role key mapping for stable rendering across dynamic persona add/remove.

4. **API shape extensions (`translator/views.py` passthrough from api_v1)**
- Session/chat payload includes:
  - `pending_messages`,
  - `phase_changed`,
  - `memory_version`,
  - server-authoritative movement target fields.

### Phase 1 Test Protocol
1. **Unit/logic tests (pytest)**
- calling nurse measurement path unblocks progression.
- immediate handoff prompt emitted without extra user message.
- shared memory updates are visible across roles.
- doctor questioning adapts by complaint severity context.

2. **Integration tests (pytest)**
- full path: intake -> calling nurse -> triage -> waiting/call -> doctor -> bedside nurse.
- waiting queue transitions can auto-advance via status polling.
- movement target changes with phase.

3. **Regression tests (pytest)**
- L1 strict encounter contract remains valid where expected.
- existing handoff/queue API tests remain passing.

4. **Manual frontend validation**
- launch user mode and enter complaint only; no deadlock on manual spo2/sbp.
- when queue reaches turn, next-agent message appears automatically.
- other patients continue moving while user waits/diagnoses.
- user patient movement target follows phase semantics.

### Phase 1 Acceptance Gate
- all Phase 1 tests pass,
- no critical regression in existing test suite,
- manual user-mode flow works end-to-end.

---

## Phase 2 - Medical Protocol RAG + Clinical Depth

### Objectives
- Make questioning and scenario coverage more clinically diverse (mild -> critical) with protocol grounding.
- Preserve deterministic safety transitions while using RAG-guided LLM planning.

### Implementation Scope
1. **Protocol corpus and retrieval**
- Add local curated guideline bundles (versioned):
  - chest pain, stroke, sepsis, trauma, dyspnea.
- Retrieval API/tool layer for agent role-specific context fetch.

2. **Structured agent planning contract**
- LLM output split into:
  - structured plan fields (`required_next_questions`, `risk_flags`, `urgency_hint`),
  - patient-facing utterance.
- deterministic validator enforces legal state transitions.

3. **Enhanced scenario behavior**
- Improve adaptive questioning and prioritization under shared memory + retrieved guidance.
- Add observability traces for retrieval hit/fallback/guardrail override.

### Phase 2 Test Protocol
1. **RAG correctness tests**
- correct pathway retrieval for representative complaints.
- negative retrieval tests (avoid wrong pathway injection).

2. **Safety tests**
- LLM cannot bypass illegal deterministic transitions.
- red-flag triggers still enforce urgent routing.

3. **Scenario evaluation tests**
- mild/moderate/severe/critical scenarios with expected behavior envelopes.
- compare Phase 2 diversity against Phase 1 baseline.

4. **Manual frontend validation**
- richer complaint-specific dialogue,
- stable handoff/movement behavior,
- concurrent background patient behavior preserved.

### Phase 2 Acceptance Gate
- all Phase 2 tests pass,
- no safety regressions,
- manual end-to-end validation confirmed.

---

## Delivery Order
1. Implement Phase 1.
2. Run and report Phase 1 tests.
3. User manual frontend/backend check.
4. Implement Phase 2.
5. Run and report Phase 2 tests.
6. User manual frontend/backend check.
7. Final handoff with change summary + test evidence + known limitations.
