from app.rule_engine import evaluate_triage_context
from app.schemas import SessionContext


def test_red_zone_for_chest_pain_and_dyspnea():
    context = SessionContext(
        session_id='case-1',
        chief_complaint='胸痛伴呼吸困难',
        age=56,
        sex='男',
        temperature=36.8,
        temperature_status='已知',
        pain_score=9,
        symptoms=['胸痛', '呼吸困难'],
    )

    result = evaluate_triage_context(context)

    assert result.triage_level == '红区'
    assert result.need_emergency_transfer is True
    assert result.recommended_outpatient_entry == '急诊'


def test_pediatric_abdominal_pain_prefers_pediatrics():
    context = SessionContext(
        session_id='case-2',
        chief_complaint='腹痛',
        age=8,
        sex='女',
        temperature=37.8,
        temperature_status='已知',
        pain_score=6,
        symptoms=['腹痛'],
    )

    result = evaluate_triage_context(context)

    assert result.triage_level == '黄区'
    assert result.recommended_outpatient_entry == '儿科'
    assert '儿童腹痛分科保护' in result.risk_flags
