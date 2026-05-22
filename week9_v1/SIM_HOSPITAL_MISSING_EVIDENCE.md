# SIM Hospital Missing Evidence

## Current Results That Are Not Fully Confirmed

| Claim | Status | Why it is not fully confirmed |
|---|---|---|
| Memory ON/OFF ablation improves or worsens handoff quality | Missing Evidence / Need Verification | Repo shows memory enable/disable support, but not a complete quantitative ablation study |
| Repeated-question rate is reduced by memory | Missing Evidence / Need Verification | No explicit metric file or benchmark in current evidence set |
| The triage policy matches a formal hospital guideline | Missing Evidence / Need Verification | The repo contains deterministic rules, but not clinician-reviewed guideline alignment |
| Arrival profiles are calibrated from real ED data | Missing Evidence / Need Verification | Profiles exist, but data provenance/calibration is not shown in repo evidence |
| Lab/imaging turnaround times are clinically validated | Missing Evidence / Need Verification | Parameters exist, but not a validation study |
| The system is ready for deployment | Not supported | This is a simulator/research platform, not a production clinical system |
| LLM output is used for clinical decision-making | Not supported | Repo evidence supports fallback / generation helpers, but not clinical authority |
| Personal authorship of each module | Missing Evidence / Need Verification | Repo cannot prove which commits or lines were authored by which team member |

## Missing Tests

| Test type | Missing piece |
|---|---|
| Memory ON/OFF ablation | Need a reproducible test that toggles memory and compares outcomes |
| Repeated-question rate | Need a benchmark that counts repeated or redundant follow-up questions |
| Clinical review test | Need explicit doctor/nurse review of triage and escalation rules |
| Long-run browser smoke | Need a browser automation run that demonstrates sustained movement under real UI execution |
| Quantitative scenario benchmark | Need comparable metrics for normal/surge/burst/doctor shortage/imaging bottleneck/boarding timeout |
| Reproducibility report | Need a formal report with seeds, environment, and pass/fail across repeated runs |

## Missing Metrics

| Metric | Current repo status |
|---|---|
| Average wait time across scenarios | Partially available through queue/resource outputs, but not a final benchmark report |
| Length of stay (LOS) | Not fully aggregated in the evidence set |
| Boarding delay | Supported by helper logic, but not a complete evaluation report |
| Handoff latency | Supported in handoff payloads, but not a full comparative study |
| State consistency rate | Supported by tests and runtime sync, but not a published summary metric |
| Safety block rate | Not found as a reported metric |
| Repeated-question rate | Not found as a reported metric |
| Memory retrieval quality | Not found as a reported metric |

## Missing Medical Evidence

| Topic | Missing proof |
|---|---|
| Guideline source for triage rules | No explicit citation to an external guideline in the repo evidence set |
| Clinical review of escalation hooks | No formal doctor/nurse signoff file found |
| Validation of boarding timeout thresholds | No clinical calibration note found |
| Validation of lab/imaging capacity assumptions | No dataset provenance note found |
| Safety boundary definition | Not formally documented as a clinician-reviewed boundary |

## What Must Not Be Written as Completed

| Do not claim | Safer wording |
|---|---|
| “We proved memory improves care quality.” | “The repo supports memory ON/OFF wiring, but a full quantitative ablation is still needed.” |
| “We built a clinically validated ED system.” | “We built a simulated ED workflow platform for research and testing.” |
| “LLM drives clinical decisions.” | “LLM helpers exist, but workflow control is rule/state driven.” |
| “The project is deployment ready.” | “The project demonstrates workflow modeling, synchronization, and auditability.” |
| “The results are statistically significant.” | “The repo contains tests and scenario outputs, but not a formal statistical study.” |

## How To Add Evidence Later

1. Add a reproducible evaluation script that toggles memory ON/OFF and records outcomes.
2. Add a metrics notebook or report for wait time, LOS, boarding delay, and handoff latency.
3. Add clinician review notes or external guideline references for triage/escalation.
4. Add a browser automation smoke test that records movement continuity under auto mode.
5. Add a seed-locked benchmark runner and store the output JSON in the repo.
