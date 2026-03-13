from app.services.feature_extractor import extract_features_from_message


def test_lay_language_is_normalized_to_features():
    bundle = extract_features_from_message('昨天开始肚子绞着疼，还一直想吐，体温38.5度')

    assert bundle.merged_updates['temperature'] == 38.5
    assert '腹痛' in bundle.merged_updates['symptoms']
    assert '恶心' in bundle.merged_updates['associated_symptoms']
    assert bundle.merged_updates['severity'] == '重度'
    assert bundle.trace['lay_phrase_hits']
