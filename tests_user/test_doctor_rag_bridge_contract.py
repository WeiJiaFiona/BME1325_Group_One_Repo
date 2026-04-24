from app_core.doctor_rag.bridge import run_bridge
from app_core.clinical_kb.compiler import build_lex_indices, compile_chunks, normalize_all
from app_core.clinical_kb.validators import validate_or_raise


def test_bridge_contract_never_changes_next_slot_or_emits_disposition():
    validate_or_raise()
    normalize_all()
    compile_chunks()
    build_lex_indices()

    out = run_bridge(
        complaint_id="headache",
        patient_text="我头很疼，我应该做什么影像？",
        language="zh",
        next_slot="duration",
        filled_slots={},
        asked_question_ids=[],
    )
    assert out.next_slot_echo == "duration"
    assert out.disposition_proposed is None
    assert out.urgency_proposed is None
    assert "ICU" not in (out.patient_explanation or "")
    assert "WARD" not in (out.patient_explanation or "")

