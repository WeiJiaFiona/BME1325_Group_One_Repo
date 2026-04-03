# EDMAS Week 5-12 Weekly Workflow 

## Goal
Build an Emergency Department Multi-Agent System (EDMAS) from zero to defense-ready delivery by combining:
- `Reused baseline`: copied EDSim codebase (not imported as external dependency)
- `Optimized modules`: new EDMAS features required by course goals

## Overall Implementation Steps
1. Copy full EDSim into `EDMAS/edmas/week5_workdir`.
2. Integrate Week 5 upgraded rule core directly into baseline backend (`reverie/backend_server/week5_rule_core`).
3. Add integrated app entrypoints in baseline backend for `User Mode` and `Auto Mode`.
4. Implement week-by-week incremental features with tests and weekly PR/merge.

## Week-by-Week Plan

### Week 5: Rule Core + Unified State Machine
- Target: deterministic triage and encounter flow foundation.
- Reused: baseline agents, simulation loop, existing queue/state primitives.
- Optimized: `CN_AD + CTAS_COMPAT`, escalation hooks, unified patient state machine.
- Tests: chest pain+diaphoresis, FAST-positive stroke, mild sprain, low-SpO2 override, illegal transition rejection, deterministic replay.

### Week 6: User Mode + L1 API Freeze
- Target: complete user-to-ED encounter path.
- Reused: Django frontend/backend command channel.
- Optimized: `/mode/user/encounter/start`, `/ed/handoff/request`, `/ed/handoff/complete`, `/ed/queue/snapshot`, payload schema checks.
- Tests: contract tests, malformed payload tests, ICU/Ward mock handoff integration.

### Week 7: Auto Mode + Resource Realism
- Target: autonomous run with realistic bottlenecks.
- Reused: automatic execution/checkpoint scripts, baseline analysis scripts.
- Optimized: arrival profiles (normal/surge/burst), lab/imaging capacity+TAT, boarding timeout events.
- Tests: surge pressure, doctor shortage, imaging bottleneck, no deadlock/livelock, fixed-seed reproducibility.

### Week 8: Memory v1
- Target: better continuity and handoff quality.
- Reused: baseline associative/scratch memory framework.
- Optimized: `EpisodeMemory`, `HandoffMemory`, `ExperienceReplayBuffer`, bounded retrieval checkpoints.
- Tests: Memory ON/OFF ablation on consistency, repeated-question rate, latency overhead.

### Week 9: Safety/Ethics + Recovery
- Target: safe and auditable degradation.
- Reused: baseline logs and runtime control hooks.
- Optimized: high-risk advice blocking, PHI-redacted logs, fallback-to-rule on timeout.
- Tests: dangerous suggestion injection, privacy leakage attempt, timeout recovery.

### Week 10: China Localization Deepening
- Target: Chinese ED realism and routing stability.
- Reused: baseline routing and prompt pipelines.
- Optimized: Chinese colloquial parsing rules, A-D report stratification, localized green-channel triggers.
- Tests: mixed-language input, elderly/comorbidity atypical cases, routing stability.

### Week 11: Policy Optimization Experiments
- Target: measurable system-level gains.
- Reused: baseline metrics/export infrastructure.
- Optimized: policy toggles (queue aging, memory on/off, surge control), paired experiment runner.
- Tests: same-seed paired comparisons with variance/confidence summary.

### Week 12: Freeze + Defense Package
- Target: one-click demo and defense-ready package.
- Reused: Dockerized stack, replay dashboard, test harness.
- Optimized: final runbook, fault-injection script, full-chain rehearsal.
- Tests: end-to-end critical path to ICU handoff, long-run stability, restart recovery.

## Weekly DoD (Definition of Done)
- At least one runnable demo flow (5-10 min)
- Test command list + pass/fail report
- KPI snapshot: `avg_wait`, `LOS`, `boarding_delay`, `handoff_latency`, `safety_block_rate`
- Weekly git deliverable: `feat/weekX-*` branch + PR + merge note
