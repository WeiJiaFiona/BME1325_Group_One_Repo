from app.safety.guardrails import guard_action


def test_block_direct_medication_dose_from_llm_output():
    action = {'type': 'llm_recommendation', 'content': '建议立即静推某药 20mg'}
    guarded = guard_action(action)
    assert guarded['allowed'] is False
    assert guarded['reason'] == 'clinical_high_risk'
