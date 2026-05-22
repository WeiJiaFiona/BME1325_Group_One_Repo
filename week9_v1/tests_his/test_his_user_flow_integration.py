from __future__ import annotations

from app_core.his.schemas import (
    CurrentSummaryRecord,
    EncounterRecord,
    HandoffSnapshotRecord,
    PatientRecord,
    TriageRecord,
    VitalSignsRecord,
)
from app_core.his.services.encounter_service import (
    get_current_summary,
    open_encounter,
    record_vital_signs,
    update_encounter_state,
    write_current_summary,
)
from app_core.his.services.handoff_service import get_handoff_snapshots, write_handoff_snapshot
from app_core.his.services.patient_registry_service import get_patient, register_patient
from app_core.his.services.triage_service import get_triage, record_triage
from app_core.his.storage.sqlite_dev import SQLiteDevHisStorage


def test_user_flow_integration_persists_minimal_his_path(tmp_path) -> None:
    storage = SQLiteDevHisStorage(db_path=tmp_path / "user_flow.sqlite3")
    storage.bootstrap()

    patient = register_patient(PatientRecord(full_name="Week9 User Flow"), storage=storage)
    encounter = open_encounter(
        EncounterRecord(
            patient_id=patient.patient_id,
            arrival_mode="walk-in",
            metadata={"source": "tests_his"},
        ),
        storage=storage,
    )
    triage = record_triage(
        TriageRecord(
            encounter_id=encounter.encounter_id,
            patient_id=patient.patient_id,
            triage_id="triage-user-flow",
            ctas_level="L2",
            zone="orange",
            summary="Chest pain arrival",
            structured_data={"chief_complaint": "chest pain"},
        ),
        storage=storage,
    )
    vitals = record_vital_signs(
        VitalSignsRecord(
            encounter_id=encounter.encounter_id,
            patient_id=patient.patient_id,
            vital_id="vitals-user-flow",
            readings={"spo2": 94, "sbp": 102},
        ),
        storage=storage,
    )
    updated_encounter = update_encounter_state(
        encounter.encounter_id,
        status="TRIAGED",
        current_zone=triage.zone,
        ctas_level=triage.ctas_level,
        storage=storage,
    )
    summary = write_current_summary(
        CurrentSummaryRecord(
            encounter_id=encounter.encounter_id,
            patient_id=patient.patient_id,
            summary_id="summary-user-flow",
            current_state="awaiting_doctor",
            payload={
                "ctas_level": triage.ctas_level,
                "zone": triage.zone,
                "latest_vitals": vitals.readings,
            },
            source_memory_ids=[],
        ),
        storage=storage,
    )
    handoff = write_handoff_snapshot(
        HandoffSnapshotRecord(
            snapshot_id="handoff-user-flow",
            encounter_id=encounter.encounter_id,
            patient_id=patient.patient_id,
            from_role="triage_nurse",
            to_role="doctor",
            handoff_stage="requested",
            patient_brief="High-acuity chest pain pending doctor review.",
            current_state={"zone": triage.zone, "ctas_level": triage.ctas_level},
            pending_tasks=[{"task": "doctor_assessment"}],
        ),
        storage=storage,
    )

    assert get_patient(patient.patient_id, storage=storage) == patient
    assert get_triage(encounter.encounter_id, storage=storage) == triage
    assert updated_encounter.current_zone == "orange"
    assert updated_encounter.ctas_level == "L2"
    assert get_current_summary(encounter.encounter_id, storage=storage) == summary
    assert get_handoff_snapshots(encounter.encounter_id, storage=storage) == [handoff]
