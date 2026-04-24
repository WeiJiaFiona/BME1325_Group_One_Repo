from app_core.app.surge_sim import StaffingConfig, run_multi_agent_surge


def test_multi_agent_surge_20_patients_with_limited_staff_completes_encounters():
    result = run_multi_agent_surge(
        staffing=StaffingConfig(doctors=3, triage_nurses=2, bedside_nurses=2),
        num_patients=20,
        max_steps=500,
    )

    assert result.total_patients == 20
    assert result.completed_patients == 20
    assert result.timed_out is False
    assert result.final_step <= 500


def test_multi_agent_surge_is_deterministic_under_same_config():
    cfg = StaffingConfig(doctors=3, triage_nurses=2, bedside_nurses=2)
    r1 = run_multi_agent_surge(staffing=cfg, num_patients=20, max_steps=500)
    r2 = run_multi_agent_surge(staffing=cfg, num_patients=20, max_steps=500)

    assert r1 == r2


def test_high_acuity_flow_is_not_dropped_under_surge():
    result = run_multi_agent_surge(
        staffing=StaffingConfig(doctors=3, triage_nurses=2, bedside_nurses=2),
        num_patients=20,
        max_steps=500,
    )

    # Ensure high-acuity patients complete, not starved.
    assert result.high_acuity_completed > 0
    assert result.completed_patients >= result.high_acuity_completed
