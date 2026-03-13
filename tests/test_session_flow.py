from app.schemas import IntakeInput
from app.services.triage_service import process_session_message, start_session


def test_session_flow_collects_temperature():
    start_payload = IntakeInput(
        chief_complaint='腹痛',
        age=8,
        sex='女',
        temperature=None,
        pain_score=6,
        vital_signs={'heart_rate': 110},
    )

    start_response = start_session(start_payload)
    assert start_response.session_context.session_id
    assert '体温' in start_response.session_context.missing_required_fields

    message_response = process_session_message(
        start_response.session_id,
        '体温38.5度，昨天开始，没有外伤',
    )

    assert message_response is not None
    assert message_response.session_context.temperature == 38.5
    assert message_response.session_context.trauma_history is False
    assert message_response.triage_result.triage_level in {'黄区', '红区'}
