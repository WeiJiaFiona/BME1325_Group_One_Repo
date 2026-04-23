from pathlib import Path

from persona.prompt_template import run_gpt_prompt


def test_patient_scratch_local_only_uses_patient_specific_fallback(monkeypatch):
    monkeypatch.setattr(run_gpt_prompt, "llm_local_only_mode", lambda: True)

    scratch = run_gpt_prompt.run_gpt_generate_patient_scratch(
        "Patient",
        "Name: (Patient 9) | Description: chest pain and dizziness | Innate: Calm, Cooperative",
    )

    assert scratch["name"] == "Patient 9"
    assert scratch["living_area"] == "ed map:emergency department:waiting room"
    assert "hospital patient" in scratch["role_description"]
    assert "chest pain and dizziness" in scratch["current_state"]


def test_next_patient_local_only_returns_first_valid_queue_entry(monkeypatch):
    monkeypatch.setattr(run_gpt_prompt, "llm_local_only_mode", lambda: True)

    result = run_gpt_prompt.run_gpt_generate_next_patient(
        persona=type("PersonaStub", (), {"role": "Doctor"})(),
        personas={"Patient 2": object()},
        queue=[[2, "Patient 2"]],
    )

    assert result == [2, "Patient 2"]
