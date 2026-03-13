from app.schemas import IntakeInput, SessionContext, TriageResponse
from app.services.llm_service import generate_followup_question
from app.services.triage_service import start_session


def test_start_session_prioritizes_required_template_question(monkeypatch):
    def should_not_be_called(*args, **kwargs):
        raise AssertionError('LLM should not be called before required fields are collected.')

    monkeypatch.setattr('app.services.triage_service.generate_followup_question', should_not_be_called)

    response = start_session(
        IntakeInput(
            chief_complaint='腹痛',
            age=8,
            sex='女',
            temperature=None,
            pain_score=6,
            vital_signs={'heart_rate': 110},
        )
    )

    assert '体温' in response.assistant_message


def test_generate_followup_question_degrades_on_timeout(monkeypatch):
    monkeypatch.setenv('DASHSCOPE_API_KEY', 'dummy-key')

    def timeout_query(*args, **kwargs):
        raise TimeoutError('read timed out')

    monkeypatch.setattr('app.services.llm_service.query_model', timeout_query)

    context = SessionContext(
        session_id='test-session',
        chief_complaint='腹痛',
        age=20,
        sex='女',
        temperature=37.2,
        temperature_status='已知',
        pain_score=4,
        vital_signs={},
        symptoms=['腹痛'],
        onset_time='昨天',
        duration='1 天',
        severity='中度',
        associated_symptoms=['恶心'],
        trauma_history=False,
        suspected_risk_signals=[],
        risk_flags=[],
        rule_engine_hits=[],
        triage_level='黄区',
        need_emergency_transfer=False,
        recommended_outpatient_entry='普通内科',
        missing_required_fields=[],
        next_question=None,
        last_extraction_trace={},
        conversation_history=[],
    )
    triage_result = TriageResponse(
        triage_level='黄区',
        risk_flags=[],
        need_emergency_transfer=False,
        recommended_outpatient_entry='普通内科',
        rule_engine_hits=[],
    )

    assert generate_followup_question(context, triage_result) is None
