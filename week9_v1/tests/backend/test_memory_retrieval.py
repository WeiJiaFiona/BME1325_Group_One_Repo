from __future__ import annotations

from app_core.memory.schema import MemoryItem, MemoryQuery
from app_core.memory.storage import JsonFileMemoryStorage


def _event(*, memory_id: str, run_id: str, encounter_id: str, step: int, event_type: str, tags: list[str] | None = None):
    return MemoryItem(
        memory_id=memory_id,
        run_id=run_id,
        mode="auto",
        encounter_id=encounter_id,
        patient_id="Patient_3",
        step=step,
        sim_time=step * 60,
        wall_time="2026-04-24T14:07:53+00:00",
        agent_role="doctor",
        event_type=event_type,
        source="auto",
        priority="medium",
        content=f"{event_type} at step {step}",
        structured_facts={},
        tags=tags or [],
        salience=step,
    )


def test_retrieval_is_bounded_to_same_run_and_encounter(tmp_path):
    storage = JsonFileMemoryStorage(root=tmp_path / "runtime_data" / "memory")
    run_id = "auto_curr_sim_20260424_140753"
    encounter_id = "auto_auto_curr_sim_20260424_140753_Patient_3"
    storage.append_event(_event(memory_id="mem-1", run_id=run_id, encounter_id=encounter_id, step=1, event_type="triage_started"))
    storage.append_event(_event(memory_id="mem-2", run_id=run_id, encounter_id=encounter_id, step=2, event_type="triage_completed", tags=["triage"]))
    storage.append_event(_event(memory_id="mem-3", run_id=run_id, encounter_id="other", step=3, event_type="triage_completed"))
    storage.append_event(_event(memory_id="mem-4", run_id="auto_other_20260424_140753", encounter_id=encounter_id, step=4, event_type="triage_completed"))

    results = storage.retrieve(
        MemoryQuery(
            run_id=run_id,
            mode="auto",
            encounter_id=encounter_id,
            checkpoint="post_triage",
            event_types=["triage_completed"],
            top_k=5,
            max_age_steps=20,
        )
    )

    assert [item.memory_id for item in results] == ["mem-2"]


def test_retrieval_respects_top_k_and_age_window(tmp_path):
    storage = JsonFileMemoryStorage(root=tmp_path / "runtime_data" / "memory")
    run_id = "auto_curr_sim_20260424_140753"
    encounter_id = "auto_auto_curr_sim_20260424_140753_Patient_3"

    for step in range(1, 8):
        storage.append_event(
            _event(
                memory_id=f"mem-{step}",
                run_id=run_id,
                encounter_id=encounter_id,
                step=step,
                event_type="doctor_assessment_checkpoint",
            )
        )

    results = storage.retrieve(
        MemoryQuery(
            run_id=run_id,
            mode="auto",
            encounter_id=encounter_id,
            checkpoint="doctor_assessment_checkpoint",
            top_k=3,
            max_age_steps=2,
        )
    )

    assert [item.memory_id for item in results] == ["mem-7", "mem-6", "mem-5"]
