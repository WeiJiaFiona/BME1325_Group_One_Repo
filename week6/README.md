# week5_workdir

Minimal Week 5 scope only.

## Integrated Week5 Contribution (single folder)
- `week5_system/agents/`: copied baseline agents (`patient.py`, `triage_nurse.py`, `bedside_nurse.py`, `doctor.py`)
- `week5_system/simulation_loop/`: copied baseline loop files (`reverie.py`, `run_simulation.py`)
- `week5_system/queue_state_primitives/`: copied baseline primitives (`maze.py`, `wait_time_utils.py`)
- `week5_system/rule_core/triage_policy.py`: `CN_AD + CTAS_COMPAT`
- `week5_system/rule_core/state_machine.py`: unified patient state machine + escalation hooks
- `week5_system/rule_core/encounter.py`
- `week5_system/app/mode_user.py`

## Run tests
```bash
cd /home/jiawei2022/BME1325/week5_progress/EDMAS/edmas/week5_workdir
python -m pytest -q
```
