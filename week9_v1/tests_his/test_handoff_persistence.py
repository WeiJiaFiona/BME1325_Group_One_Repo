from app_core.his.schemas import EncounterRecord, HandoffSnapshotRecord, PatientRecord
from app_core.his.services.encounter_service import open_encounter
from app_core.his.services.handoff_service import get_handoff_snapshots, write_handoff_snapshot
from app_core.his.services.patient_registry_service import register_patient
from app_core.his.storage.base import InMemoryHisStorage


def test_handoff_snapshot_persists_and_reads_back() -> None:
    storage = InMemoryHisStorage()
    patient = register_patient(PatientRecord(full_name="Handoff Patient"), storage=storage)
    encounter = open_encounter(EncounterRecord(patient_id=patient.patient_id), storage=storage)
    snapshot = HandoffSnapshotRecord(
        snapshot_id="SNAP-001",
        encounter_id=encounter.encounter_id,
        patient_id=patient.patient_id,
        from_role="doctor",
        to_role="bed_nurse",
        handoff_stage="requested",
        patient_brief="Observation handoff",
        current_state={"state": "handoff"},
    )

    stored = write_handoff_snapshot(snapshot, storage=storage)

    assert stored == snapshot
    assert get_handoff_snapshots(encounter.encounter_id, storage=storage) == [snapshot]
