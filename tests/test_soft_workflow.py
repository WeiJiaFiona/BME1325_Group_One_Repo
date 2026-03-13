from app.schemas import IntakeInput
from app.services.feature_extractor import extract_features_from_message
from app.services.triage_service import process_session_message, single_shot_triage, start_session


def test_soft_temperature_expressions_are_understood():
    bundle = extract_features_from_message('刚才测过体温了，36.6℃，没发烧，就是喉咙痛，咽口水疼')

    assert bundle.merged_updates['temperature'] == 36.6
    assert bundle.merged_updates['fever_present'] is False
    assert '咽痛' in bundle.merged_updates['symptoms']
    assert '吞咽疼痛' in bundle.merged_updates['associated_symptoms']


def test_normal_temperature_reply_does_not_block_next_turn():
    start_response = start_session(
        IntakeInput(
            chief_complaint='喉咙痛',
            age=24,
            sex='女',
            temperature=None,
            pain_score=3,
            vital_signs={},
        )
    )

    message_response = process_session_message(
        start_response.session_id,
        '刚才测过体温了，36.6℃，没发烧，昨天开始，咽口水疼',
    )

    assert message_response is not None
    assert message_response.session_context.temperature == 36.6
    assert message_response.session_context.fever_present is False
    assert '体温' not in message_response.assistant_message


def test_sore_throat_defaults_to_ent_not_emergency():
    response = single_shot_triage(
        IntakeInput(
            chief_complaint='喉咙痛',
            age=25,
            sex='男',
            temperature=36.6,
            pain_score=3,
            vital_signs={},
        )
    )

    assert response.triage_level == '绿区'
    assert response.need_emergency_transfer is False
    assert response.recommended_outpatient_entry == '耳鼻喉科门诊'
