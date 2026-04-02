# ED-MAS Week 5-12 Weekly Workflow

## Project Target
Build a production-ready Emergency Department MAS subsystem that is integration-ready with ICU and ward teams via stable L1 interfaces, while keeping ED workflow deterministic, clinically grounded, and testable.

## Baseline Gap and Optimization Strategy

### Current baseline gaps (EDSim)
- CTAS-first logic is not fully aligned to the China A-D triage standard.
- Role set is limited for realistic ED operations under resource pressure.
- Memory exists but is not optimized for handoff continuity and replay evaluation.
- Safety and governance evidence is insufficient for final course-stage requirements.

### Practical optimizations (low-risk, high-value)
- Add China-first triage policy: `CN_AD` with `CTAS_COMPAT` mapping.
- Add bounded coordinators: measurement dispatch, flow coordination, consult timeout handling.
- Add memory layers: episode memory + handoff memory + experience replay retrieval.
- Add auditable safety layer: deterministic risk block + PHI-safe logs + fallback behavior.

## Interface Freeze for Cross-Subsystem Integration (L1)
1. `POST /ed/handoff/request`
- Input: `patient_id, acuity_ad, zone, stability, required_unit, clinical_summary, pending_tasks`
- Output: `handoff_ticket_id, status, reason`

2. `POST /ed/handoff/complete`
- Input: `handoff_ticket_id, receiver_system, accepted_at, receiver_bed`
- Output: `final_disposition_state, transfer_latency_seconds`

3. `GET /ed/queue/snapshot`
- Output: triage/doctor/test/boarding queues + wait/occupancy snapshot.

4. Event contracts
- `ED_PATIENT_READY_FOR_ICU`
- `ED_PATIENT_READY_FOR_WARD`
- `ED_GREEN_CHANNEL_TRIGGERED`
- `ED_HANDOFF_TIMEOUT`

## Week-by-Week Plan (Week 5-12)

## Week 5: Rule Core + Unified State Machine
### Target
- Deliver A-D triage/routing/escalation in a deterministic way for both modes.

### Implementation Plan
- Add triage standards: `CN_AD`, `CTAS_COMPAT`.
- Add escalation hooks: `green_channel`, `abnormal_vitals`, `deterioration`, `consult_required`, `icu_required`, `surgery_required`.
- Expand shared encounter state machine with explicit ED stages.

### Test Plan (clinical scenarios)
- Chest pain + diaphoresis -> urgent path.
- FAST-positive stroke-like presentation -> escalation path.
- Mild sprain -> low-acuity fast-track path.
- Vitals override: low SpO2 upgrades acuity.

### Robustness Evidence
- Deterministic output under fixed input.
- Transition invariants and illegal transition rejection.

### Milestone (verifiable)
- Unit + integration tests pass for triage/state/user encounter.
- Demo of 3 Chinese ED cases with traceable outputs.

## Week 6: Mode-U + L1 Interface Freeze
### Target
- User-to-ED flow is fully demonstrable and integration-ready.

### Implementation Plan
- Finalize `/mode/user/encounter/start` and handoff APIs.
- Add event trace output and schema validation.

### Test Plan
- Walk-in chest pain, ambulance trauma, dyspnea/fever.
- Incomplete payload and noisy language handling.
- Handoff request/complete mock integration.

### Robustness Evidence
- No crash on malformed input.
- Contract-level compatibility with ICU/ward mock server.

### Milestone
- L1 APIs frozen and documented.

## Week 7: Mode-A + Resource Realism
### Target
- Autonomous ED simulation with queue/resource bottlenecks.

### Implementation Plan
- Arrival profiles (normal/surge/burst).
- Lab/imaging capacity and turnaround timing.
- Boarding queue and timeout events.

### Test Plan
- Surge pressure, doctor shortage, imaging bottleneck.

### Robustness Evidence
- No queue deadlock/livelock.
- Reproducible KPI output under fixed seed.

### Milestone
- Stable auto-run with KPI snapshots.

## Week 8: Memory v1 (Innovation Core)
### Target
- Memory improves continuity and handoff quality with bounded latency.

### Implementation Plan
- `EpisodeMemory`, `HandoffMemory`, `ExperienceReplayBuffer`.
- Inject retrieval only at bounded decision checkpoints.

### Test Plan
- Reassessment after delayed test result.
- Shift change handoff continuity.
- Recurrent similar case retrieval.

### Robustness Evidence
- Memory ON/OFF ablation on consistency and repeated-question rate.

### Milestone
- Quantified memory benefit report.

## Week 9: Safety/Ethics + Recovery
### Target
- Risk control is testable and auditable.

### Implementation Plan
- High-risk advice block rules.
- PHI redaction and audit trail.
- Fallback-to-rule mode during model/tool timeout.

### Test Plan
- Dangerous dosage suggestion injection.
- Sensitive info leakage attempt.
- Timeout during active encounter.

### Robustness Evidence
- Safe degradation without workflow collapse.

### Milestone
- Safety test suite and audit logs pass review.

## Week 10: China Localization Deepening
### Target
- Chinese ED realism beyond translation.

### Implementation Plan
- Replace English-only salience/prompt assumptions.
- A-D report stratification and localized pathway text.
- Green-channel localized triggers (chest pain/stroke/trauma).

### Test Plan
- Chinese colloquial complaints and mixed-language input.
- Elderly/comorbidity atypical cases.

### Robustness Evidence
- Routing stability under language variation.

### Milestone
- Localized scenario replay package.

## Week 11: Policy Optimization Experiments
### Target
- Demonstrate measurable operational gains.

### Implementation Plan
- Policy toggles: queue aging, memory on/off, surge control variants.
- Experiment runner for paired comparison.

### Test Plan
- Same arrival stream and seed across strategies.
- Compare wait, LOS, boarding delay, handoff latency.

### Robustness Evidence
- Variance and confidence summary across multiple runs.

### Milestone
- Optimization dashboard and conclusions.

## Week 12: Freeze + Defense Package
### Target
- Deliver a defense-ready ED subsystem and reproducible demo.

### Implementation Plan
- Freeze contracts and perform cross-team drill.
- Prepare final report, runbook, and demo script.

### Test Plan
- End-to-end critical case path to ICU handoff.
- Long-run stability check.
- Fault injection and restart recovery.

### Robustness Evidence
- Full chain green checks and no interface breaks.

### Milestone
- One-click demo package accepted for final defense.

## Weekly DoD Checklist
- A runnable demo flow (5-10 min).
- Test commands + pass/fail summary.
- KPI snapshot (`avg_wait`, `LOS`, `boarding_delay`, `handoff_latency`, `safety_block_rate`).
- Risk log + rollback notes.
- Next-week dependency and interface notes.
