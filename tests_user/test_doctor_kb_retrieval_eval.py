import yaml

from app_core.clinical_kb.loader import load_kb
from app_core.doctor_rag.retriever import retrieve_explanations, retrieve_questions, retrieve_redflags


def _load_eval():
    p = "RAG/doctor_kb/manifests/retrieval_eval_set.yaml"
    data = yaml.safe_load(open(p, "r", encoding="utf-8")) or {}
    return data


def test_retrieval_eval_topk_hits():
    data = _load_eval()
    defaults = data.get("defaults", {}) or {}
    k_default = int(defaults.get("k", 5) or 5)
    cases = data.get("cases", []) or []
    assert cases

    kb = load_kb()
    for c in cases:
        complaint_id = c["complaint_id"]
        intent = c["intent"]
        next_slot = c["next_slot"]
        query_text = c["query_text"]
        k = int(c.get("k", k_default) or k_default)

        if intent in {"ask_imaging", "ask_labs", "ask_next_steps"}:
            topic = {
                "ask_imaging": "ct_vs_mri",
                "ask_labs": "labs_common",
                "ask_next_steps": "next_steps",
            }.get(intent, "next_steps")
            items = retrieve_explanations(kb, complaint_id=complaint_id, topic=topic, query_text=query_text, k=k)
        elif intent == "ask_why_question":
            items = retrieve_redflags(kb, complaint_id=complaint_id, query_text=query_text, k=k)
        else:
            items = retrieve_questions(kb, complaint_id=complaint_id, next_slot=next_slot, query_text=query_text, k=k)

        # Evaluate expected_hits: semantic must_contain check.
        expected = c.get("expected_hits", []) or []
        assert expected
        joined = " ".join([it.row.get("text", "") for it in items if it.row])
        for e in expected:
            must = e.get("must_contain", []) or []
            for kw in must:
                assert kw in joined

