# AGENTS.md (RAG Subtree Rules)

## Scope
These rules apply to everything under:
- `/home/jiawei2022/BME1325/week6/week6/week6_interface/RAG`

## Purpose
This subtree is for Stage 2 RAG planning, references, and implementation support for the Week 6 ED user mode.

## Hard Constraints
1. `refs/` is read-only reference material.
- Do not modify files under `RAG/refs/*` unless explicitly requested.
- Do not commit upstream reference code changes by default.

2. Never import runtime code from `refs/`.
- Do not add Python imports pointing to `RAG/refs/*`.
- Any needed logic from reference repos must be copied/adapted into this project’s own RAG implementation modules.
- Treat `RAG/refs` as disposable; it may be deleted at any time.

3. Implement changes in project code, not in reference repos.
- Main implementation target is under `week5_system/app/*`.
- Primary integration point is `week5_system/app/api_v1.py` (`DOCTOR_CALLED` branch).

4. Keep external behavior stable.
- Do not change public API response shape unless explicitly requested.
- Keep Stage 1 state machine flow intact.

5. Stage 2 scope is doctor-only by default.
- RAG/planner/validator upgrades should apply to `doctor` agent first.
- Triage/calling flow should remain deterministic unless explicitly expanded.

## Recommended Structure
When implementing Stage 2, prefer these modules:
- `week5_system/app/protocols/*` (versioned local protocol files)
- `week5_system/app/rag/*` (retrieval/evidence)
- `week5_system/app/planning/*` (planner/validator/fallback)

## Testing Requirements
Before claiming completion, run at least:
- `cd /home/jiawei2022/BME1325/week6/week6 && pytest -q tests/test_week6_user_mode_chat.py tests/test_week6_user_mode_natural.py`
- `cd /home/jiawei2022/BME1325/week6/week6 && pytest -q tests/test_week6_l1_api.py`

## Commit Hygiene
- Keep commits focused and small.
- Avoid committing runtime artifacts (`__pycache__`, logs, temp outputs) unless explicitly requested.
- Do not include secrets or API keys in commits.
