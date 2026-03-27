# EDSim ED MAS Week4-12 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-grade course-deliverable ED multi-agent simulator (user-participation mode + fully autonomous mode) on an EDSim-first architecture with measurable outcomes and final defense artifacts.

**Architecture:** Use a rules-first simulation core (triage/zone/SLA constraints) with LLM-assisted agents for interaction and coordination. Keep one shared state machine for both modes; only the patient-entry source differs (human input vs auto generator). Implement as modular backend services + web UI/dashboard + reproducible evaluation pipeline.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic, pytest, SQLite/PostgreSQL (local SQLite first), React + TypeScript + Phaser, Vite, Vitest, Playwright (smoke UI), Mermaid, pandas/seaborn for reports.

---

## Planning Format Output

## Background
- Course requires multi-agent hospital simulation with staged delivery and final defense.
- Domain references define ED triage, red/yellow/green zoning, green channel, and resource constraints.
- Existing EDSim provides a strong base for environment + workflow simulation.

## Challenges
- Keep medical safety constraints deterministic while still using LLM-driven role interaction.
- Deliver two operation modes without duplicating core workflow logic.
- Ensure observability and reproducible metrics for weekly demos and final defense.

## Innovation
- Unified dual-mode architecture: one state machine, two entry channels.
- Rule-hardening layer in front of all high-risk agent actions.
- Event-sourced ED timeline enabling replay, evaluation, and ablation-friendly experiments.

## Method
- Build modular services in sequence: domain rules -> world state -> agent runtime -> UI -> metrics.
- Use TDD for each core module (failing test -> minimal code -> passing test).
- Weekly DoD-driven increments with stable demo scripts.

## Result (expected)
- By Week 12, deliver a runnable ED simulator with both modes, metrics dashboard, what-if experiments, final report, and defense demo package.

---

## Scope Check
This request spans multiple independent subsystems (simulation kernel, agents, UI, analytics, governance). To keep delivery realistic, this plan decomposes work into 10 tasks mapped to weekly milestones. Each task yields a testable, demo-ready artifact.

---

## File Structure (Target)

- `week_4_progress/ed_mas/README.md`: project entry, runbook, milestone map.
- `week_4_progress/ed_mas/backend/app/main.py`: API bootstrap.
- `week_4_progress/ed_mas/backend/app/config.py`: runtime settings.
- `week_4_progress/ed_mas/backend/app/domain/triage_rules.py`: deterministic triage and zone routing rules.
- `week_4_progress/ed_mas/backend/app/domain/state_machine.py`: patient encounter state machine.
- `week_4_progress/ed_mas/backend/app/domain/sla_policy.py`: timeout/escalation policies.
- `week_4_progress/ed_mas/backend/app/world/models.py`: world state entities.
- `week_4_progress/ed_mas/backend/app/world/repository.py`: persistence adapter.
- `week_4_progress/ed_mas/backend/app/world/event_bus.py`: event emission and subscriptions.
- `week_4_progress/ed_mas/backend/app/agents/base.py`: agent contract.
- `week_4_progress/ed_mas/backend/app/agents/triage_agent.py`: triage workflow agent.
- `week_4_progress/ed_mas/backend/app/agents/doctor_agent.py`: physician workflow agent.
- `week_4_progress/ed_mas/backend/app/agents/nurse_agent.py`: bedside nurse workflow agent.
- `week_4_progress/ed_mas/backend/app/agents/coordinator_agent.py`: ED coordinator agent.
- `week_4_progress/ed_mas/backend/app/modes/user_mode.py`: human patient entry orchestration.
- `week_4_progress/ed_mas/backend/app/modes/auto_mode.py`: autonomous patient generation and run loop.
- `week_4_progress/ed_mas/backend/app/tools/actions.py`: structured tool interface.
- `week_4_progress/ed_mas/backend/app/safety/guardrails.py`: action/output risk constraints.
- `week_4_progress/ed_mas/backend/app/metrics/collector.py`: metric ingestion.
- `week_4_progress/ed_mas/backend/app/metrics/reporting.py`: metric aggregation/report output.
- `week_4_progress/ed_mas/frontend/src/App.tsx`: UI shell and mode switch.
- `week_4_progress/ed_mas/frontend/src/components/MapView.tsx`: Phaser map wrapper.
- `week_4_progress/ed_mas/frontend/src/components/QueuePanel.tsx`: queue/zone panel.
- `week_4_progress/ed_mas/frontend/src/components/UserPatientChat.tsx`: user patient dialog UI.
- `week_4_progress/ed_mas/frontend/src/components/Dashboard.tsx`: KPI dashboards.
- `week_4_progress/ed_mas/tests/unit/test_triage_rules.py`: triage rule tests.
- `week_4_progress/ed_mas/tests/unit/test_state_machine.py`: encounter transitions tests.
- `week_4_progress/ed_mas/tests/unit/test_tools.py`: tool contract tests.
- `week_4_progress/ed_mas/tests/integration/test_user_mode_flow.py`: user-mode end-to-end flow tests.
- `week_4_progress/ed_mas/tests/integration/test_auto_mode_flow.py`: auto-mode end-to-end flow tests.
- `week_4_progress/ed_mas/tests/integration/test_safety_constraints.py`: guardrail tests.
- `week_4_progress/ed_mas/tests/e2e/test_dashboard.spec.ts`: UI smoke tests.
- `week_4_progress/ed_mas/docs/milestones/week4-12.md`: weekly deliverables and DoD.
- `week_4_progress/ed_mas/docs/defense/final_report.md`: final technical report draft.

---

### Task 1: Project Bootstrap and Baseline Test Harness (Week 4)

**Files:**
- Create: `week_4_progress/ed_mas/backend/app/main.py`
- Create: `week_4_progress/ed_mas/backend/app/config.py`
- Create: `week_4_progress/ed_mas/tests/unit/test_bootstrap.py`
- Create: `week_4_progress/ed_mas/pyproject.toml`
- Create: `week_4_progress/ed_mas/README.md`

- [ ] **Step 1: Write the failing test**

```python
# week_4_progress/ed_mas/tests/unit/test_bootstrap.py
from fastapi.testclient import TestClient
from app.main import app


def test_healthcheck_endpoint():
    client = TestClient(app)
    resp = client.get('/health')
    assert resp.status_code == 200
    assert resp.json()['status'] == 'ok'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd week_4_progress/ed_mas && pytest tests/unit/test_bootstrap.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: Write minimal implementation**

```python
# week_4_progress/ed_mas/backend/app/main.py
from fastapi import FastAPI

app = FastAPI(title='ED MAS')


@app.get('/health')
def health():
    return {'status': 'ok'}
```

```toml
# week_4_progress/ed_mas/pyproject.toml
[project]
name = "ed-mas"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["fastapi", "uvicorn", "pydantic", "pytest"]

[tool.pytest.ini_options]
pythonpath = ["backend"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd week_4_progress/ed_mas && pytest tests/unit/test_bootstrap.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add week_4_progress/ed_mas
git commit -m "feat: bootstrap ed_mas service with healthcheck and test harness"
```

---

### Task 2: Deterministic Triage and Zone Routing (Week 4-5)

**Files:**
- Create: `week_4_progress/ed_mas/backend/app/domain/triage_rules.py`
- Test: `week_4_progress/ed_mas/tests/unit/test_triage_rules.py`

- [ ] **Step 1: Write the failing test**

```python
# week_4_progress/ed_mas/tests/unit/test_triage_rules.py
from app.domain.triage_rules import triage_level, route_zone


def test_level_1_route_red():
    patient = {"vitals": {"spo2": 82}, "chief_complaint": "呼吸困难"}
    level = triage_level(patient)
    zone = route_zone(level)
    assert level == 1
    assert zone == "red"


def test_level_4_route_green():
    patient = {"vitals": {"spo2": 98}, "chief_complaint": "轻微擦伤", "resource_need": 1}
    level = triage_level(patient)
    zone = route_zone(level)
    assert level == 4
    assert zone == "green"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd week_4_progress/ed_mas && pytest tests/unit/test_triage_rules.py -v`
Expected: FAIL with `ModuleNotFoundError: app.domain.triage_rules`

- [ ] **Step 3: Write minimal implementation**

```python
# week_4_progress/ed_mas/backend/app/domain/triage_rules.py

def triage_level(patient: dict) -> int:
    spo2 = patient.get('vitals', {}).get('spo2', 100)
    resource_need = patient.get('resource_need', 1)
    complaint = patient.get('chief_complaint', '')

    if spo2 < 90 or '意识障碍' in complaint:
        return 1
    if spo2 < 94 or '胸痛' in complaint or '卒中' in complaint:
        return 2
    if resource_need >= 2:
        return 3
    return 4


def route_zone(level: int) -> str:
    if level in (1, 2):
        return 'red'
    if level == 3:
        return 'yellow'
    return 'green'
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd week_4_progress/ed_mas && pytest tests/unit/test_triage_rules.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add week_4_progress/ed_mas/backend/app/domain/triage_rules.py week_4_progress/ed_mas/tests/unit/test_triage_rules.py
git commit -m "feat: add deterministic triage levels and zone routing"
```

---

### Task 3: Unified Encounter State Machine (Week 5)

**Files:**
- Create: `week_4_progress/ed_mas/backend/app/domain/state_machine.py`
- Test: `week_4_progress/ed_mas/tests/unit/test_state_machine.py`

- [ ] **Step 1: Write the failing test**

```python
# week_4_progress/ed_mas/tests/unit/test_state_machine.py
from app.domain.state_machine import EncounterStateMachine


def test_user_and_auto_share_same_state_machine_path():
    machine = EncounterStateMachine()
    s = machine.start()
    s = machine.transition(s, 'triaged')
    s = machine.transition(s, 'doctor_assessed')
    s = machine.transition(s, 'test_ordered')
    s = machine.transition(s, 'result_received')
    s = machine.transition(s, 'disposition_discharge')
    assert s == 'discharged'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd week_4_progress/ed_mas && pytest tests/unit/test_state_machine.py -v`
Expected: FAIL with import error

- [ ] **Step 3: Write minimal implementation**

```python
# week_4_progress/ed_mas/backend/app/domain/state_machine.py
class EncounterStateMachine:
    _graph = {
        'arrival': {'triaged': 'zone_routed'},
        'zone_routed': {'doctor_assessed': 'assessment_done'},
        'assessment_done': {'test_ordered': 'waiting_result', 'disposition_discharge': 'discharged'},
        'waiting_result': {'result_received': 'assessment_done'},
    }

    def start(self) -> str:
        return 'arrival'

    def transition(self, state: str, event: str) -> str:
        if state not in self._graph or event not in self._graph[state]:
            raise ValueError(f'invalid transition: {state} + {event}')
        return self._graph[state][event]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd week_4_progress/ed_mas && pytest tests/unit/test_state_machine.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add week_4_progress/ed_mas/backend/app/domain/state_machine.py week_4_progress/ed_mas/tests/unit/test_state_machine.py
git commit -m "feat: add unified encounter state machine for both modes"
```

---

### Task 4: Tool Layer Contracts and Event Bus (Week 5-6)

**Files:**
- Create: `week_4_progress/ed_mas/backend/app/tools/actions.py`
- Create: `week_4_progress/ed_mas/backend/app/world/event_bus.py`
- Test: `week_4_progress/ed_mas/tests/unit/test_tools.py`

- [ ] **Step 1: Write the failing test**

```python
# week_4_progress/ed_mas/tests/unit/test_tools.py
from app.world.event_bus import EventBus
from app.tools.actions import order_test


def test_order_test_emits_event():
    bus = EventBus()
    order_test(bus, patient_id='p1', test_type='ct')
    events = bus.read_all()
    assert events[-1]['type'] == 'test_ordered'
    assert events[-1]['payload']['test_type'] == 'ct'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd week_4_progress/ed_mas && pytest tests/unit/test_tools.py -v`
Expected: FAIL with import error

- [ ] **Step 3: Write minimal implementation**

```python
# week_4_progress/ed_mas/backend/app/world/event_bus.py
class EventBus:
    def __init__(self):
        self._events = []

    def emit(self, event_type: str, payload: dict):
        self._events.append({'type': event_type, 'payload': payload})

    def read_all(self):
        return self._events
```

```python
# week_4_progress/ed_mas/backend/app/tools/actions.py
from app.world.event_bus import EventBus


def order_test(bus: EventBus, patient_id: str, test_type: str):
    bus.emit('test_ordered', {'patient_id': patient_id, 'test_type': test_type})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd week_4_progress/ed_mas && pytest tests/unit/test_tools.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add week_4_progress/ed_mas/backend/app/world/event_bus.py week_4_progress/ed_mas/backend/app/tools/actions.py week_4_progress/ed_mas/tests/unit/test_tools.py
git commit -m "feat: add tool contract and event bus primitives"
```

---

### Task 5: Mode-U (User Participation) End-to-End API (Week 6)

**Files:**
- Create: `week_4_progress/ed_mas/backend/app/modes/user_mode.py`
- Modify: `week_4_progress/ed_mas/backend/app/main.py`
- Test: `week_4_progress/ed_mas/tests/integration/test_user_mode_flow.py`

- [ ] **Step 1: Write the failing test**

```python
# week_4_progress/ed_mas/tests/integration/test_user_mode_flow.py
from fastapi.testclient import TestClient
from app.main import app


def test_user_patient_flow_returns_zone_and_next_action():
    client = TestClient(app)
    payload = {"chief_complaint": "胸痛", "vitals": {"spo2": 95}, "resource_need": 2}
    resp = client.post('/mode/user/encounter/start', json=payload)
    data = resp.json()
    assert resp.status_code == 200
    assert data['zone'] in ['red', 'yellow', 'green']
    assert 'next_action' in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd week_4_progress/ed_mas && pytest tests/integration/test_user_mode_flow.py -v`
Expected: FAIL with missing endpoint

- [ ] **Step 3: Write minimal implementation**

```python
# week_4_progress/ed_mas/backend/app/modes/user_mode.py
from app.domain.triage_rules import triage_level, route_zone


def start_user_encounter(payload: dict) -> dict:
    level = triage_level(payload)
    zone = route_zone(level)
    return {
        'triage_level': level,
        'zone': zone,
        'next_action': 'doctor_assessment' if zone != 'green' else 'fast_track_assessment'
    }
```

```python
# week_4_progress/ed_mas/backend/app/main.py (append)
from fastapi import FastAPI
from app.modes.user_mode import start_user_encounter

app = FastAPI(title='ED MAS')

@app.post('/mode/user/encounter/start')
def mode_user_start(payload: dict):
    return start_user_encounter(payload)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd week_4_progress/ed_mas && pytest tests/integration/test_user_mode_flow.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add week_4_progress/ed_mas/backend/app/modes/user_mode.py week_4_progress/ed_mas/backend/app/main.py week_4_progress/ed_mas/tests/integration/test_user_mode_flow.py
git commit -m "feat: implement user participation mode encounter start flow"
```

---

### Task 6: Mode-A (Autonomous MAS) Simulation Loop (Week 7)

**Files:**
- Create: `week_4_progress/ed_mas/backend/app/modes/auto_mode.py`
- Test: `week_4_progress/ed_mas/tests/integration/test_auto_mode_flow.py`

- [ ] **Step 1: Write the failing test**

```python
# week_4_progress/ed_mas/tests/integration/test_auto_mode_flow.py
from app.modes.auto_mode import run_auto_tick


def test_auto_tick_produces_patient_events():
    result = run_auto_tick(seed=42)
    assert result['generated_patients'] >= 1
    assert result['events_emitted'] >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd week_4_progress/ed_mas && pytest tests/integration/test_auto_mode_flow.py -v`
Expected: FAIL with import error

- [ ] **Step 3: Write minimal implementation**

```python
# week_4_progress/ed_mas/backend/app/modes/auto_mode.py
import random
from app.world.event_bus import EventBus


def run_auto_tick(seed: int = 0) -> dict:
    random.seed(seed)
    bus = EventBus()
    generated = random.randint(1, 3)
    for i in range(generated):
        bus.emit('patient_arrival', {'patient_id': f'auto_{i}'})
    return {'generated_patients': generated, 'events_emitted': len(bus.read_all())}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd week_4_progress/ed_mas && pytest tests/integration/test_auto_mode_flow.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add week_4_progress/ed_mas/backend/app/modes/auto_mode.py week_4_progress/ed_mas/tests/integration/test_auto_mode_flow.py
git commit -m "feat: implement autonomous mode simulation tick"
```

---

### Task 7: Safety Guardrails and Risk Blocking (Week 9)

**Files:**
- Create: `week_4_progress/ed_mas/backend/app/safety/guardrails.py`
- Test: `week_4_progress/ed_mas/tests/integration/test_safety_constraints.py`

- [ ] **Step 1: Write the failing test**

```python
# week_4_progress/ed_mas/tests/integration/test_safety_constraints.py
from app.safety.guardrails import guard_action


def test_block_direct_medication_dose_from_llm_output():
    action = {'type': 'llm_recommendation', 'content': '建议立即静推某药 20mg'}
    guarded = guard_action(action)
    assert guarded['allowed'] is False
    assert guarded['reason'] == 'clinical_high_risk'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd week_4_progress/ed_mas && pytest tests/integration/test_safety_constraints.py -v`
Expected: FAIL with import error

- [ ] **Step 3: Write minimal implementation**

```python
# week_4_progress/ed_mas/backend/app/safety/guardrails.py

def guard_action(action: dict) -> dict:
    content = action.get('content', '')
    high_risk_keywords = ['静推', '剂量', '立即用药', '处方']
    if any(k in content for k in high_risk_keywords):
        return {'allowed': False, 'reason': 'clinical_high_risk'}
    return {'allowed': True, 'reason': 'ok'}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd week_4_progress/ed_mas && pytest tests/integration/test_safety_constraints.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add week_4_progress/ed_mas/backend/app/safety/guardrails.py week_4_progress/ed_mas/tests/integration/test_safety_constraints.py
git commit -m "feat: add safety guardrails for high-risk LLM actions"
```

---

### Task 8: Metrics, Dashboard Data API, and Weekly DoD Matrix (Week 8-12)

**Files:**
- Create: `week_4_progress/ed_mas/backend/app/metrics/collector.py`
- Create: `week_4_progress/ed_mas/backend/app/metrics/reporting.py`
- Create: `week_4_progress/ed_mas/docs/milestones/week4-12.md`
- Create: `week_4_progress/ed_mas/docs/defense/final_report.md`

- [ ] **Step 1: Write the failing test**

```python
# week_4_progress/ed_mas/tests/unit/test_metrics.py
from app.metrics.collector import collect_snapshot


def test_collect_snapshot_has_required_kpis():
    data = collect_snapshot(waiting=12, occupied_beds=8, doctor_queue=5)
    assert 'avg_waiting_minutes' in data
    assert 'bed_utilization' in data
    assert 'doctor_queue' in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd week_4_progress/ed_mas && pytest tests/unit/test_metrics.py -v`
Expected: FAIL with import error

- [ ] **Step 3: Write minimal implementation**

```python
# week_4_progress/ed_mas/backend/app/metrics/collector.py

def collect_snapshot(waiting: int, occupied_beds: int, doctor_queue: int, total_beds: int = 10):
    return {
        'avg_waiting_minutes': waiting * 2,
        'bed_utilization': occupied_beds / total_beds,
        'doctor_queue': doctor_queue,
    }
```

```markdown
# week_4_progress/ed_mas/docs/milestones/week4-12.md
# Week4-12 DoD Matrix

| Week | Deliverable | DoD |
|---|---|---|
| 4 | Architecture + PRD | Reviewed and frozen |
| 5 | Rule + State core | Unit tests pass |
| 6 | Mode-U | User path demo successful |
| 7 | Mode-A | Auto-run with logs |
| 8 | KPI v1 | Dashboard shows core KPIs |
| 9 | Safety | High-risk output blocked |
| 10 | Stability | 30-minute run without crash |
| 11 | What-if experiments | Comparative charts ready |
| 12 | Final package | Demo + report + defense slides |
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd week_4_progress/ed_mas && pytest tests/unit/test_metrics.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add week_4_progress/ed_mas/backend/app/metrics/collector.py week_4_progress/ed_mas/docs/milestones/week4-12.md
git commit -m "feat: add KPI collection and milestone DoD matrix"
```

---

### Task 9: Frontend Mode Switch and Core Panels (Week 6-8)

**Files:**
- Create: `week_4_progress/ed_mas/frontend/src/App.tsx`
- Create: `week_4_progress/ed_mas/frontend/src/components/UserPatientChat.tsx`
- Create: `week_4_progress/ed_mas/frontend/src/components/QueuePanel.tsx`
- Create: `week_4_progress/ed_mas/frontend/src/components/MapView.tsx`
- Test: `week_4_progress/ed_mas/tests/e2e/test_dashboard.spec.ts`

- [ ] **Step 1: Write the failing UI smoke test**

```ts
// week_4_progress/ed_mas/tests/e2e/test_dashboard.spec.ts
import { test, expect } from '@playwright/test';

test('mode switch visible', async ({ page }) => {
  await page.goto('http://127.0.0.1:5174');
  await expect(page.getByText('Mode-U')).toBeVisible();
  await expect(page.getByText('Mode-A')).toBeVisible();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd week_4_progress/ed_mas && npx playwright test tests/e2e/test_dashboard.spec.ts`
Expected: FAIL (frontend not implemented)

- [ ] **Step 3: Write minimal UI implementation**

```tsx
// week_4_progress/ed_mas/frontend/src/App.tsx
import { useState } from 'react';

export default function App() {
  const [mode, setMode] = useState<'U' | 'A'>('U');
  return (
    <main>
      <h1>ED MAS</h1>
      <button onClick={() => setMode('U')}>Mode-U</button>
      <button onClick={() => setMode('A')}>Mode-A</button>
      <p>Current: {mode}</p>
    </main>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd week_4_progress/ed_mas && npx playwright test tests/e2e/test_dashboard.spec.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add week_4_progress/ed_mas/frontend/src/App.tsx week_4_progress/ed_mas/tests/e2e/test_dashboard.spec.ts
git commit -m "feat: add frontend mode switch and ui smoke test"
```

---

### Task 10: Final Packaging for Defense (Week 11-12)

**Files:**
- Modify: `week_4_progress/ed_mas/README.md`
- Modify: `week_4_progress/ed_mas/docs/defense/final_report.md`
- Create: `week_4_progress/ed_mas/scripts/demo_run.sh`

- [ ] **Step 1: Write failing acceptance checklist**

```markdown
# Acceptance Checklist
- [ ] Mode-U full encounter demo recorded
- [ ] Mode-A 30-min stable run log available
- [ ] KPI dashboard screenshots and CSV exported
- [ ] Safety block demo included
- [ ] Final report includes background/challenges/innovation/method/result
```

- [ ] **Step 2: Run checklist and verify fails initially**

Run: manually check artifacts under `week_4_progress/ed_mas/artifacts/`
Expected: several unchecked items

- [ ] **Step 3: Add deterministic demo script and report skeleton**

```bash
# week_4_progress/ed_mas/scripts/demo_run.sh
#!/usr/bin/env bash
set -euo pipefail
uvicorn backend.app.main:app --host 0.0.0.0 --port 18180
```

```markdown
# week_4_progress/ed_mas/docs/defense/final_report.md
# Final Report
## Background
## Challenges
## Innovation
## Method
## Result
```

- [ ] **Step 4: Run final smoke checks**

Run: `bash week_4_progress/ed_mas/scripts/demo_run.sh`
Expected: service starts and `/health` returns `{"status":"ok"}`

- [ ] **Step 5: Commit**

```bash
git add week_4_progress/ed_mas/README.md week_4_progress/ed_mas/docs/defense/final_report.md week_4_progress/ed_mas/scripts/demo_run.sh
git commit -m "chore: add final defense packaging scripts and report skeleton"
```

---

## Weekly推进计划（汇总视图）

| Week | Core Build | Test Gate | Demo Gate |
|---|---|---|---|
| 4 | bootstrap + rules | unit: bootstrap/triage | architecture walkthrough |
| 5 | state machine + event bus | unit: transitions/tools | deterministic flow replay |
| 6 | mode-U API + UI entry | integration: user mode | user as patient live demo |
| 7 | mode-A loop | integration: auto mode | autonomous multi-agent run |
| 8 | metrics v1 | unit: metrics | KPI dashboard |
| 9 | safety guardrails | integration: safety | blocked-risk output demo |
| 10 | reliability hardening | long-run smoke | 30-min stable run |
| 11 | what-if experiments | reproducibility scripts | comparison charts |
| 12 | final report + defense package | acceptance checklist | end-to-end final demo |

---

## Spec Coverage Check (Self-Review)
- Covers dual-mode requirement (Task 5 + Task 6 + shared state machine).
- Covers ED process constraints (Task 2 + Task 3 + Task 7).
- Covers engineering-first weekly delivery (weekly table + DoD matrix in Task 8).
- Covers final proposal narrative structure (Background/Challenges/Innovation/Method/Result in Task 10 docs).

## Placeholder Scan (Self-Review)
- No `TODO`/`TBD` placeholders left in task instructions.
- Each task contains concrete files, tests, commands, and expected results.

## Type/Name Consistency (Self-Review)
- Shared naming: `Mode-U`, `Mode-A`, `EncounterStateMachine`, `EventBus`, `guard_action`, `collect_snapshot`.
- Transition/event names aligned across Task 3-6.

