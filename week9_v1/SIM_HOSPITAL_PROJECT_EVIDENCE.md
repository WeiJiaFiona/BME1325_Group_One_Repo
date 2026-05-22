# SIM Hospital Project Evidence

## Evidence Legend
- `Confirmed` means the claim is directly supported by code, tests, or docs in this repo.
- `Partial` means the repo supports the module, but some performance or ownership claims still need more proof.
- `Missing Evidence / Need Verification` means the repo does not yet give enough proof for a strong CV/PS claim.

## Project File Map

| Path | Role | Key functions / classes / variables | Narrative link | CV/PS ready? |
|---|---|---|---|---|
| `app_core/rule_core/state_machine.py` | Core ED finite-state machine | `EncounterStateMachine`, `ALLOWED_TRANSITIONS`, `HOOK_ESCALATIONS`, `transition()`, `apply_hook()` | Shows the project is more than a chat UI: it is a rule-based workflow engine | Confirmed |
| `app_core/rule_core/encounter.py` | Rule-based encounter driver | `start_user_encounter()`, `EncounterResult`, triage-to-routing transitions | User mode clinical path and state continuity | Confirmed |
| `app_core/rule_core/triage_policy.py` | Deterministic triage policy | `TriageInput`, `TriageDecision`, `triage_cn_ad()`, resource-demand estimation | Rule-based triage, acuity assignment, and resource realism proxy | Confirmed |
| `app_core/app/api_v1.py` | L1 API and user-mode orchestration | `start_encounter()`, `request_handoff()`, `complete_handoff()`, `queue_snapshot()`, `export_encounter_timeline()`, `export_auto_timeline()`, `user_mode_chat_turn()` | Formal API surface for user mode, handoff, queue snapshot, and timeline export | Confirmed |
| `app_core/app/mode_user.py` | User-mode encounter entrypoint | `start()`, `_build_event_trace()` | Minimal user-mode engine with traceable state transitions | Confirmed |
| `app_core/app/handoff.py` | Handoff request/complete wrapper | `request()`, `complete()`, `HANDOFF_TIMEOUT_SECONDS` | Mock or formal receiver handoff path | Confirmed |
| `app_core/app/schema.py` | Payload validation | `validate_encounter_start_payload()`, `validate_handoff_request_payload()`, `validate_handoff_complete_payload()`, `PayloadError` | Payload safety and malformed-input handling | Confirmed |
| `app_core/queue_state_primitives/snapshot.py` | Queue snapshot model | `queue_snapshot()` | Queue state visibility for API / evaluation | Confirmed |
| `app_core/queue_state_primitives/wait_time_utils.py` | Wait-time realism | `_load_ctas_wait_config()`, `_sample_wait_minutes()`, `_assign_wait_targets()` | Resource realism, turnaround sampling, surge modifier | Confirmed |
| `reverie/backend_server/week7_logic.py` | Week7 realism helpers | `arrival_profile_multiplier()`, `effective_arrival_rate()`, `testing_kind_for_ctas()`, `boarding_timeout_reached()` | Scenario realism: normal/surge/burst, imaging/lab routing, timeout logic | Confirmed |
| `reverie/backend_server/reverie.py` | Auto-mode backend runner | `ReverieServer`, `_atomic_write_json()`, `_build_safe_movement_path()`, crash logging, bootstrap, runtime loop | Backend simulation loop, movement generation, crash resilience, sync backbone | Confirmed |
| `app_core/simulation_loop/reverie.py` | Simulation loop runtime | `run_simulation`-style step progression, movement/environment/status writing | Lower-level runtime loop used in simulation/debug workflows | Partial |
| `environment/frontend_server/translator/views.py` | Django bridge | `home()`, `process_environment()`, `update_environment()`, `start_backend()`, `send_sim_command()`, `live_dashboard_api()`, `save_simulation_settings()` | Frontend-backend synchronization, bootstrap, runtime health, fixed-seed config | Confirmed |
| `environment/frontend_server/frontend_server/urls.py` | Routing table | `/update_environment/`, `/process_environment/`, `/start_backend/.../`, `/api/live_dashboard/`, user-mode and handoff routes | Public API surface of the simulator | Confirmed |
| `environment/frontend_server/templates/home/scripts/auto_main_script.html` | Auto-mode Phaser/JS loop | `render_step`, `playback_step`, `runtime_sync`, `backend_health`, `movementWaitReason`, `ROLE_STYLE`, `ROLE_SPRITE_KEY`, `ROLE_AVATAR_PATH`, `sanitizeMovementPath`, `updateRuntimeStatusBanner()` | Continuous movement playback, sync debugging, backend-health gating | Confirmed |
| `environment/frontend_server/templates/home/scripts/user_main_script.html` | User-mode Phaser/JS loop | `sanitizeMovementPath`, role/avatar/sprite helpers, `window.__EDSIM_DEBUG__` | User-mode visual rendering and movement replay | Confirmed |
| `environment/frontend_server/templates/home/home.html` | Landing/debug page | Mode switch info, runtime notes, dashboard entry | User-facing explanation of auto/user runtime chain | Confirmed |
| `environment/frontend_server/templates/home/start_simulation.html` | Start page | Seed defaults, bootstrap controls | Reproducible auto-mode launch | Confirmed |
| `environment/frontend_server/frontend_server/settings/base.py` | Django settings | `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | Host/origin compatibility for local and EasyConnect-like environments | Confirmed |
| `environment/frontend_server/frontend_server/settings/local.py` | Local overrides | Local development toggles | Stable local startup | Confirmed |
| `app_core/memory/schema.py` | Memory data model | `MemoryItem`, `CurrentEncounterSummary`, `HandoffMemorySnapshot`, `AuditRecord`, `MemoryQuery` | Structured memory, handoff memory, auditability | Confirmed |
| `app_core/memory/storage.py` | Memory persistence abstraction | `JsonFileMemoryStorage`, `NullMemoryStorage`, `events.jsonl`, `audit.jsonl`, `current/`, `snapshots/` | Memory ON/OFF substrate and replay storage | Confirmed |
| `app_core/memory/service.py` | Memory service façade | `MemoryService`, `append_event()`, `update_current_summary()`, `write_handoff_snapshot()`, `retrieve()`, `export_replay()` | Structured memory pipeline | Confirmed |
| `app_core/memory/hooks.py` | Memory helper constructors | `generate_auto_run_id()`, `generate_user_run_id()`, `build_memory_event()`, `build_handoff_snapshot_id()`, `build_audit_record()` | Deterministic memory identifiers and event assembly | Confirmed |
| `app_core/memory/config.py` | Memory feature flags | `memory_v1_enabled()`, `get_runtime_root()` | Memory ON/OFF and storage root configuration | Confirmed |
| `reverie/backend_server/auto_memory_hooks.py` | Auto-mode memory hooks | `record_encounter_started()`, `record_handoff_requested()`, `record_handoff_completed()`, `record_boarding_timeout()`, `record_resource_bottlenecks()` | Auto-mode event capture and memory replay support | Confirmed |
| `app_core/his/adapters/memory_adapter.py` | Memory -> HIS mapping layer | `get_memory_upgrade_plan()`, `persist_memory_item_to_his()`, `persist_current_summary_to_his()`, `map_handoff_snapshot_to_his_writes()` | Formal bridge from runtime memory to HIS tables/documents | Confirmed |
| `app_core/his/adapters/runtime_bridge.py` | Runtime HIS integration | `reset_runtime_bridge_state()`, `register_runtime_patient()`, `_append_memory_event()`, `_persist_summary()`, `_maybe_seed_stemi_workup()` | Runtime memory/HIS sync, outbox/audit, STEMI bootstrap | Confirmed |
| `app_core/his/services/*.py` | HIS repositories/services | patient registry, encounter service, handoff service, audit log, document registry | HIS persistence and query surface | Confirmed |
| `tests_user/*.py` | User-mode and API tests | user encounter, malformed payloads, handoff integration, queue snapshot, L1 API | Endpoint freeze, schema validation, workflow evidence | Confirmed |
| `tests_backend/*.py` | Backend realism and runtime tests | week7 features, wait times, auto memory hooks, long regression, local LLM fallback | Resource realism, reproducibility, runtime correctness | Confirmed |
| `tests_his/*.py` | HIS / memory / timeline tests | memory upgrade path, timeline export, contract alignment, STEMI smoke | Memory/HIS bridge, formal export and audit trail | Confirmed |
| `tests_frontend/*.py` | Frontend sync and debug-contract tests | `test_views.py`, `test_frontend_debug_contracts.py` | Frontend/backend sync, step alignment, debug state contract | Confirmed |
| `docs/operations/week7_long_run_regression.md` | Long-run regression note | runtime chain, scenario runner, seed reproducibility | Evidence for fixed-seed, long-run validation | Confirmed |
| `docs/architecture/week7_auto_baseline_analysis.md` | Baseline vs week7 analysis | arrival profile, lab/imaging, boarding timeout, baseline comparison | Useful for “why week7 is more realistic” narrative | Confirmed |
| `docs/architecture/week9_memory_to_his_field_mapping.md` | Memory/HIS contract mapping | frozen route names, contract fields, upgrade plan | Useful for week9 HIS bridge narrative | Confirmed |

## Key Functions, Classes, and Variables

| Item | Where | Why it matters |
|---|---|---|
| `EncounterStateMachine` | `app_core/rule_core/state_machine.py` | Encodes allowed ED transitions and escalation hooks |
| `triage_cn_ad()` | `app_core/rule_core/triage_policy.py` | Deterministic triage and acuity/risk routing |
| `start_user_encounter()` | `app_core/rule_core/encounter.py` | Converts triage into a state trace and final state |
| `start_encounter()` | `app_core/app/api_v1.py` | Formal user-mode API entrypoint |
| `request_handoff()` / `complete_handoff()` | `app_core/app/api_v1.py`, `app_core/app/handoff.py` | Handoff request/accept/timeout flow |
| `queue_snapshot()` | `app_core/queue_state_primitives/snapshot.py`, `app_core/app/api_v1.py` | Visible queue/occupancy state for runtime evaluation |
| `arrival_profile_multiplier()` | `reverie/backend_server/week7_logic.py` | Scenario-specific arrival intensity |
| `boarding_timeout_reached()` | `reverie/backend_server/week7_logic.py` | Boarding timeout realism and event triggering |
| `MemoryItem` | `app_core/memory/schema.py` | Structured event record for replay, audit, and retrieval |
| `CurrentEncounterSummary` | `app_core/memory/schema.py` | Compact current-state memory for handoff continuity |
| `HandoffMemorySnapshot` | `app_core/memory/schema.py` | Pre-handoff structured snapshot of active state |
| `JsonFileMemoryStorage` | `app_core/memory/storage.py` | File-backed memory, audit, and replay persistence |
| `AutoMemoryHookManager` | `reverie/backend_server/auto_memory_hooks.py` | Runtime event capture for auto mode |
| `runtime_sync` | `views.py`, `auto_main_script.html` | Frontend/backend step alignment and health |
| `backend_health` | `views.py`, `auto_main_script.html` | Command queue, stalled runtime, and liveness tracking |
| `movementWaitReason` | `auto_main_script.html` | Debugging why movement is not advancing |
| `ROLE_SPRITE_KEY` / `ROLE_AVATAR_PATH` | `auto_main_script.html`, `user_main_script.html` | Role-to-visual mapping evidence |
| `curr_step.json` / `sim_status.json` | `reverie.py`, `views.py` | Runtime pointer and simulation progress source |
| `events.jsonl` / `audit.jsonl` | `memory/storage.py` | Memory history and audit trail persistence |

## Test Evidence

| Test / script | What it verifies | Result evidence in repo |
|---|---|---|
| `tests_user/test_week6_user_mode_chat.py` | user encounter path, chat/session flow, memory version, timeline export | `pytest` coverage and assertions around calling nurse / triage / doctor flow |
| `tests_user/test_week6_l1_api.py` | payload validation, malformed inputs, handoff API | Structured errors for missing fields / invalid vitals / invalid arrival mode |
| `tests_user/test_malformed_payloads.py` | malformed handoff and encounter payload handling | Error code contract |
| `tests_user/test_queue_snapshot.py` | queue snapshot structure and defaults | Snapshot schema and empty case |
| `tests_user/test_handoff_integration.py` | handoff request/complete, timeout, invalid state | Handoff lifecycle evidence |
| `tests_his/test_his_user_flow_integration.py` | user-mode HIS writes | Encounter/triage/summary/handoff persisted |
| `tests_his/test_memory_upgrade_path.py` | memory-to-HIS mapping plan | `MemoryItem`, `CurrentEncounterSummary`, `HandoffMemorySnapshot` all map to HIS writes |
| `tests_his/test_timeline_export.py` | timeline bundle structure | `document_type == timeline_export` and replay exports |
| `tests_his/test_stemi_golden_path_smoke.py` | STEMI workflow smoke | Golden-path clinical workflow evidence |
| `tests_backend/test_week7_features.py` | arrival profile, lab/imaging capacity, boarding timeout | Resource realism and scenario helpers |
| `tests_backend/test_wait_time_utils.py` | CTAS wait config, stage sampling, surge multiplier | Wait-time realism configuration and sampling |
| `tests_backend/test_auto_memory_hooks.py` | auto memory hooks, dedupe, fail-open | Memory capture and resilience |
| `tests_backend/test_local_llm_fallbacks.py` | local-only fallback | LLM gateway failure fallback evidence |
| `tests_frontend/test_views.py` | process/update environment, runtime sync, bridge logs | Frontend/backend sync and health checks |
| `tests_frontend/test_frontend_debug_contracts.py` | debug contract fields on auto/user pages | Frontend observability evidence |
| `scripts/verify_frontend_backend_chain.py` | bridge sync and runtime recovery smoke | Useful for operations, but not a substitute for manual verification |
| `scripts/debug_bridge_sync.py` | bridge-only local sync simulator | Proves process/update path can be exercised without a real browser |

## Missing Evidence / Need Verification

| Topic | Missing proof |
|---|---|
| Memory ON/OFF ablation quality claims | Repo shows `memory_v1_enabled()` and `NullMemoryStorage`, but not a full quantified ON/OFF ablation study |
| Repeated-question rate | No direct metric file found in current evidence set |
| Clinical expert review | No clinician signoff or external validation file found |
| Real emergency department data | Arrival/turnaround profiles exist, but the repo does not prove they are calibrated from real hospital logs |
| Strong baseline comparison | There is a baseline-vs-week7 analysis doc, but not a fully reproducible benchmark suite with final numbers |
| Personal authorship | Repo evidence cannot prove which lines were authored by the user versus teammates |
| Production deployment readiness | This is a simulator and teaching/research codebase, not a deployable clinical system |
