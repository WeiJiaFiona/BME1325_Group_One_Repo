from app_core.clinical_kb.registry import registry_map, load_registry
from app_core.clinical_kb.validators import validate_or_raise
from app_core.clinical_kb.compiler import normalize_all, compile_chunks, build_lex_indices


def test_kb_registry_has_eight_families():
    items = load_registry()
    assert len(items) >= 8
    ids = {it.complaint_id for it in items}
    for cid in [
        "headache",
        "abdominal_pain",
        "dizziness",
        "fever",
        "dysuria",
        "nausea_vomiting",
        "back_pain",
        "palpitations",
    ]:
        assert cid in ids


def test_kb_validate_normalize_compile_build_index():
    validate_or_raise()
    normalize_all()
    compile_chunks()
    idx = build_lex_indices()
    assert idx

