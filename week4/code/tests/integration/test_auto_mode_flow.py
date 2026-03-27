from app.modes.auto_mode import run_auto_tick


def test_auto_tick_produces_patient_events():
    result = run_auto_tick(seed=42)
    assert result['generated_patients'] >= 1
    assert result['events_emitted'] >= 1
