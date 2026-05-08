# Week8 Init Context

Use `week8/` as the only active project root for Week 8 work.

## Working Rule

- Run, test, and edit only inside `week8/`.
- Treat `week8/` as the merged system root for both `auto` and `user` mode.
- Do not point runtime paths back to old source trees such as `week7/`, `week7_auto/`, `week8_auto/`, or external merge snapshots.
- If a missing runtime file is required, copy or create it under `week8/`; do not make the system depend on another directory.

## Canonical Runtime Paths

- merged root:
  `week8/`
- frontend root:
  `week8/environment/frontend_server/`
- backend root:
  `week8/reverie/backend_server/`
- app core root:
  `week8/app_core/`
- memory substrate root:
  `week8/app_core/memory/`
- runtime memory root:
  `week8/runtime_data/memory/`
- frontend storage root:
  `week8/environment/frontend_server/storage/`
- frontend temp root:
  `week8/environment/frontend_server/temp_storage/`

## Mode Boundary

- `EDSIM_MODE` is the only authoritative runtime mode switch.
- `ui_mode` only changes frontend presentation and must not switch backend runtime behavior.
- `EDSIM_MODE=auto` means the simulation loop under `reverie/backend_server/` is active.
- `EDSIM_MODE=user` means the user-mode runtime under `app_core/` is active.

## Current Week 8 Status

- The merged system preserves both `auto` and `user` mode.
- User mode already includes LLM-facing doctor flow, doctor-only local RAG, and Week 8 Memory v1 user-side integration support.
- Developer A has completed the Memory v1 substrate under `app_core/memory/`.
- Auto mode still needs further optimization around runtime sync, queue stability, and minimal Memory v1 hook integration.

## Memory v1 Boundary

- Memory v1 is a parallel ED event substrate.
- It does not replace old persona `scratch`.
- It does not write back to old `associative_memory`.
- It does not read old `spatial_memory`.
- Use `app_core/memory/service.py` as the only supported entrypoint.

## Current Backlog Focus

- Auto mode bug fixing:
  - runtime sync lag between frontend and backend
  - repeated patient re-insert queue churn
  - minimal auto memory hooks such as `encounter_spawned`, `boarding_timeout`, `resource_bottleneck`, `encounter_closed`
- Week 9 focus:
  - safety / ethics / recovery
  - high-risk advice blocking
  - PHI-redacted logs
  - fallback-to-rule on timeout

## Recommended Startup Defaults

- Conda env:
  `edmas`
- Auto mode frontend:
  `EDSIM_MODE=auto`
- Auto mode backend:
  `LLM_MODE=local_only`
  `EMBEDDING_MODE=local_only`
- User mode memory:
  `MEMORY_V1_ENABLED=1`
  `MEMORY_V1_ROOT=week8/runtime_data/memory`

## Reference Files

- `week8/MERGE_HANDOFF.md`
- `week8/week8_proposal.md`
- `week8/Developer_A.md`
- `week8/DeveloperA_memory_contract_freeze.md`
- `week8/week8_conclass.md`

## Init Prompt Template

When starting a new interaction, first read `week8/init.md` and treat it as the project bootstrap note. Confirm the active root is `week8/`, respect the `EDSIM_MODE` runtime boundary, and use only canonical paths under this directory. Before proposing edits, summarize the current state of `auto mode`, `user mode`, and `Memory v1`, then state which files you will inspect next. If a task touches memory, use `app_core/memory/service.py` as the only supported entrypoint. If a task touches runtime behavior, distinguish clearly between `auto` and `user` mode and avoid mixing their logic.
