# Week 9 Memory-to-HIS Field Mapping

This note records the B-side placeholder mapping for the fetched Week 9 HIS substrate.
It follows:

- `docs/architecture/week9_his_contract_freeze_v1.md`
- `week9_his_dev_readme_v2.md`
- `week9_his_developer_B_spec_v2.md`
- `week9_his_merge_protocol_v2.md`

## Guardrails

- Use A's frozen service boundary only.
- Do not write SQL from `api_v1.py` or ED workflow code.
- Do not invent alternate table names or service names.
- Keep Memory v1 as the upstream timeline substrate and HIS as the formal persistence layer.

## Frozen Contract Fields

| Contract field | Source today | Frozen rule |
| --- | --- | --- |
| `patient_id` | Memory v1 records, user-mode responses, HIS patient rows | `P-{8 hex}` |
| `encounter_id` | Memory v1 records, user-mode responses, HIS encounter rows | `E-{14 timestamp}-{4 hex}` |
| `ctas_level` | ED triage normalization | `L1` to `L5` |
| `zone` | ED triage normalization | `red`, `orange`, `yellow`, `green`, `blue` |
| event envelope | Normalized HIS event writes | `event_id`, `event_type`, `occurred_at`, `patient_id`, `encounter_id`, `source`, `payload` |

## MemoryItem -> HIS

| Memory v1 artifact | HIS target table | Frozen service boundary | Notes |
| --- | --- | --- | --- |
| `MemoryItem.memory_id` | `memory_events` | `event_registry_service.append_event_registry_entry` plus future event write path | Use as the raw ED-memory event anchor; no direct SQL from adapters. |
| `MemoryItem.patient_id` | `memory_events.patient_id` | same boundary | Must already satisfy the frozen patient ID format. |
| `MemoryItem.encounter_id` | `memory_events.encounter_id` | same boundary | Must already satisfy the frozen encounter ID format. |
| `MemoryItem.event_type` | `memory_events` and `event_registry.event_type` | same boundary | Also feeds the external HIS event envelope. |
| `MemoryItem.source` | `memory_events.source`, `event_registry.source` | same boundary | Preserve source provenance from Memory v1. |
| `MemoryItem.content` | `memory_events.payload/content` | same boundary | Keep free-text continuity payload in the raw event stream. |
| `MemoryItem.structured_facts` | `memory_events.payload`, `event_registry.payload` | same boundary | Primary structured facts bag for downstream HIS projections. |
| `MemoryItem.created_at` / `wall_time` | `event_registry.occurred_at` | same boundary | Final timestamp rule stays pending until the write path is implemented. |

## CurrentEncounterSummary -> HIS

| Memory v1 artifact | HIS target table | Frozen service boundary | Notes |
| --- | --- | --- | --- |
| `CurrentEncounterSummary.encounter_id` | `current_encounter_summaries.encounter_id` | `encounter_service.write_current_summary` | No parallel summary store should be created. |
| `CurrentEncounterSummary.patient_id` | `current_encounter_summaries.patient_id` | same boundary | Contract field preserved as-is. |
| `CurrentEncounterSummary.current_state` | `current_encounter_summaries.current_state` | same boundary | Summary stays a derived view, not source of truth. |
| `CurrentEncounterSummary.current_zone` | `current_encounter_summaries.payload.zone` | same boundary | Keep normalized zone values only. |
| `CurrentEncounterSummary.acuity` | `current_encounter_summaries.payload.ctas_level` | same boundary | Convert to contract-facing CTAS before HIS writes. |
| `CurrentEncounterSummary.latest_vitals` | `current_encounter_summaries.payload.latest_vitals` | same boundary | Do not split into direct SQL writes from the adapter. |
| `CurrentEncounterSummary.active_risks` | `current_encounter_summaries.payload.active_risks` | same boundary | Supports handoff and timeline export later. |
| `CurrentEncounterSummary.pending_tasks` | `current_encounter_summaries.payload.pending_tasks` | same boundary | Supports downstream handoff continuity. |
| `CurrentEncounterSummary.completed_actions` | `current_encounter_summaries.payload.completed_actions` | same boundary | Use for replay/timeline context only after service wiring. |
| `CurrentEncounterSummary.source_memory_ids` | `current_encounter_summaries.source_memory_ids` | same boundary | Traceability back to raw Memory v1 events. |

## HandoffMemorySnapshot -> HIS

| Memory v1 artifact | HIS target table | Frozen service boundary | Notes |
| --- | --- | --- | --- |
| `HandoffMemorySnapshot.snapshot_id` | `handoff_snapshots.snapshot_id` | `handoff_service.write_handoff_snapshot` | Primary HIS handoff record key. |
| `HandoffMemorySnapshot.encounter_id` | `handoff_snapshots.encounter_id` | same boundary | Shared with document-facing mirror record. |
| `HandoffMemorySnapshot.patient_id` | `handoff_snapshots.patient_id` | same boundary | Frozen patient key. |
| `HandoffMemorySnapshot.from_role` / `to_role` | `handoff_snapshots.from_role`, `handoff_snapshots.to_role` | same boundary | Preserve role-to-role continuity. |
| `HandoffMemorySnapshot.handoff_stage` | `handoff_snapshots.handoff_stage` | same boundary | Requested/completed semantics stay aligned with Memory v1. |
| `HandoffMemorySnapshot.patient_brief` | `handoff_snapshots.patient_brief`, `clinical_documents` mirror payload | same boundary plus future document path | Clinical brief should remain queryable from the HIS layer. |
| `HandoffMemorySnapshot.current_state` | `handoff_snapshots.current_state` | same boundary | No direct workflow SQL writes. |
| action/risk/task lists | `handoff_snapshots` and `clinical_documents` payloads | same boundary plus future document path | Used by handoff connectivity and timeline export. |

## Replay and Timeline Export Placeholder

| Source bundle | HIS target table | Status |
| --- | --- | --- |
| replay export payload with events, summaries, snapshots, audits | `replay_exports` | Placeholder only until A exposes the storage/service path for replay export writes. |

## Current Observations from the fetched A upload

- Frozen route names are `transfer`, `admissions`, `summary`, and `timeline`.
- Frozen event envelope fields are present in `app_core/his/config.py`.
- Service stubs now exist for event registry, encounter summary, and handoff snapshot writes.
- `app_core/his/storage/base.py` is not present in the fetched upload yet, so this document intentionally stops at contract/mapping scaffolding.
