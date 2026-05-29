from app_core.app import api_v1


def test_extract_duration_cn_variants():
    assert api_v1._extract_duration("半小时前突然发生头痛") != ""
    assert api_v1._extract_duration("今天上午10点开始头痛") != ""
    assert api_v1._extract_duration("从早上开始不舒服") != ""


def test_patient_question_intent_detection():
    assert api_v1._is_risk_anxiety_question("医生我会不会脑出血？会不会有生命危险？") is True
    assert api_v1._is_imaging_question("我现在需要做CT还是MRI？") is True


def test_doctor_next_question_chinese_only():
    q = api_v1._doctor_next_question("duration", 1)
    assert "I still need the timeline" not in q
    assert "什么时候" in q or "时间线" in q

