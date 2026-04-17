# user_mode README

This directory is the standalone Week6 `user_mode` package.
It includes frontend + backend + RAG + LLM integration in one runnable tree.

## 1. What Has Been Done

### 1.1 Directory Refactor (Standalone Structure)
- Merged into one EDSim-style structure:
  - `environment/frontend_server` (Django frontend)
  - `reverie/backend_server` (simulation backend)
  - `app_core` (core logic, triage, APIs, RAG, planning)
  - `tests` (week6 test suite)
- Removed runtime dependency on sibling week folders.
- Renamed internal imports from `week5_system.*` to `app_core.*`.

### 1.2 User Mode Flow Upgrades
- Calling nurse + triage + doctor + bedside flow integrated.
- Queue auto-progression enabled (no extra "hello" required to advance turn).
- Shared memory is persisted in session and reused by agents.
- Doctor supports one-question-per-turn behavior with anti-repeat guard.

### 1.3 RAG + LLM Integration
- RAG pipeline wired into doctor loop:
  - `retrieve_protocols -> build_evidence_package -> build_doctor_plan -> validate_plan`
- Evidence is logged in `shared_memory.doctor_assessment.planner_trace`.
- Local case bank retrieval included (`case_bank` evidence refs).
- Protocol coverage expanded:
  - `chest_pain`, `dyspnea`, `stroke`, `sepsis`, `trauma`
  - `labor`, `abdominal_pain`, `anaphylaxis`, `headache`
- LLM adapter hardened:
  - retries without environment proxies when proxy TLS path fails.

### 1.4 Clinical Behavior Improvements
- Doctor can answer patient imaging-intent questions (CT/MRI/X-ray/US guidance) before continuing triage questioning.
- Doctor disposition message now includes preliminary clinical impression + key findings + target destination.
- Bedside nurse now reports explicit bed number.

### 1.5 Triage Improvements
- Chinese/English high-risk keywords added in triage policy.
- CTAS can now realistically trigger A/B/C/D, including CTAS 1 in critical cases.

### 1.6 Test Status
- Current regression set:
  - `tests/test_week6_stage2_rag.py`
  - `tests/test_week6_user_mode_chat.py`
  - `tests/test_week6_user_mode_natural.py`
  - `tests/test_week6_l1_api.py`
- Last verified result: **31 passed**.

## 2. What Still Needs To Be Done

### 2.1 State-Machine Hook Compatibility Bug
- Known issue in direct `start_encounter(...)` path for extreme acuity:
  - `Hook deterioration cannot be applied from UNDER_EVALUATION`
- Needs rule-core state machine transition fix for hook ordering / allowed states.

### 2.2 Doctor Clinical Realism (Next Level)
- Current doctor is hybrid (rules + RAG + LLM), but still constrained by slot-plan.
- Next steps:
  - stronger intent handling (`patient asks advice`, `patient asks plan`, `patient asks why`)
  - richer dynamic reasoning across longitudinal context
  - better multilingual response consistency

### 2.3 Disposition Granularity
- Add richer targets and pathways:
  - e.g., `OBS`, specialty consult routing, discharge instructions quality.
- Improve explicit diagnosis confidence statement and uncertainty handling.

### 2.4 Data/Knowledge Expansion
- Expand local case bank coverage and quality.
- Add protocol versioning and validation checks.
- Add curated ED knowledge chunks for more robust RAG retrieval quality.

### 2.5 Frontend/UX Completion
- Improve patient-facing explanation panels:
  - current risk level, rationale, next step transparency.
- Better visualization of multi-patient concurrent movement in user mode view.

## 3. How To Run

### 3.1 Backend + Frontend (Django)
```bash
cd /home/jiawei2022/BME1325/week6/week6/user_mode/environment/frontend_server
python manage.py runserver 0.0.0.0:8010
```

Open:
- `http://127.0.0.1:8010/`

### 3.2 Run Tests
```bash
cd /home/jiawei2022/BME1325/week6/week6/user_mode
pytest -q tests/test_week6_stage2_rag.py tests/test_week6_user_mode_chat.py tests/test_week6_user_mode_natural.py tests/test_week6_l1_api.py
```

## 4. Key Files

- Core API orchestration:
  - `app_core/app/api_v1.py`
- LLM adapter:
  - `app_core/app/llm_adapter.py`
- RAG retriever + evidence:
  - `app_core/app/rag/protocol_retriever.py`
  - `app_core/app/rag/case_retriever.py`
  - `app_core/app/rag/evidence_builder.py`
- Doctor planner/validator:
  - `app_core/app/planning/doctor_planner.py`
  - `app_core/app/planning/plan_validator.py`
- Triage rules:
  - `app_core/rule_core/triage_policy.py`

