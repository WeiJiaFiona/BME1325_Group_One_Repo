from __future__ import annotations

import json
from pathlib import Path
import tempfile

from app_core.his.adapters import build_event_envelope, derive_zone_from_ctas
from app_core.his.schemas import (
    ClinicalAssessmentRecord,
    DiagnosisRecord,
    EncounterRecord,
    HandoffSnapshotRecord,
    PatientRecord,
    TriageRecord,
    VitalSignsRecord,
)
from app_core.his.services.encounter_service import (
    open_encounter,
    record_clinical_assessment,
    record_diagnosis,
    record_vital_signs,
    update_encounter_state,
    write_current_summary,
)
from app_core.his.services.event_registry_service import append_event_registry_entry
from app_core.his.services.handoff_service import get_handoff_snapshots, write_handoff_snapshot
from app_core.his.services.patient_registry_service import register_patient
from app_core.his.services.triage_service import record_triage
from app_core.his.storage.sqlite_dev import SQLiteDevHisStorage
from app_core.his.schemas import CurrentSummaryRecord, EventRegistryEntry


def build_stemi_golden_path_result() -> dict[str, object]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = SQLiteDevHisStorage(db_path=Path(tmp_dir) / "stemi.sqlite3")
        storage.bootstrap()
        patient = register_patient(
            PatientRecord(patient_id="P-1a2b3c4d", full_name="STEMI Demo Patient"),
            storage=storage,
        )
        encounter = open_encounter(
            EncounterRecord(
                patient_id=patient.patient_id,
                encounter_id="E-20260515153045-1a2b",
                status="OPEN",
                arrival_mode="ambulance",
                current_zone="orange",
                ctas_level="L2",
            ),
            storage=storage,
        )
        record_triage(
            TriageRecord(
                encounter_id=encounter.encounter_id,
                patient_id=patient.patient_id,
                triage_id="triage-1",
                ctas_level="L2",
                zone=derive_zone_from_ctas("L2"),
                summary="high-risk chest pain",
                structured_data={"acuity_ad": "B", "green_channel": True},
            ),
            storage=storage,
        )
        record_vital_signs(
            VitalSignsRecord(
                encounter_id=encounter.encounter_id,
                patient_id=patient.patient_id,
                vital_id="vitals-1",
                readings={"spo2": 92, "sbp": 88, "pain_score": 9},
            ),
            storage=storage,
        )
        record_clinical_assessment(
            ClinicalAssessmentRecord(
                encounter_id=encounter.encounter_id,
                patient_id=patient.patient_id,
                assessment_id="assessment-1",
                author_role="doctor",
                findings={"impression": "possible STEMI"},
            ),
            storage=storage,
        )
        record_diagnosis(
            DiagnosisRecord(
                encounter_id=encounter.encounter_id,
                patient_id=patient.patient_id,
                diagnosis_id="dx-1",
                label="ICU",
                details={"working_impression": "possible STEMI"},
            ),
            storage=storage,
        )
        handoff = write_handoff_snapshot(
            HandoffSnapshotRecord(
                snapshot_id="handoff-1",
                encounter_id=encounter.encounter_id,
                patient_id=patient.patient_id,
                from_role="doctor",
                to_role="ICU",
                handoff_stage="completed",
                patient_brief="high-risk chest pain with hypotension",
                current_state={"state": "ICU"},
                completed_actions=[{"event": "transfer"}],
            ),
            storage=storage,
        )
        update_encounter_state(encounter.encounter_id, status="COMPLETED", current_zone="ICU", storage=storage)
        write_current_summary(
            CurrentSummaryRecord(
                encounter_id=encounter.encounter_id,
                patient_id=patient.patient_id,
                summary_id="summary-1",
                current_state="ICU",
                payload={"triage": "L2", "working_impression": "possible STEMI"},
            ),
            storage=storage,
        )
        envelope = build_event_envelope(
            event_type="handoff_completed",
            patient_id=patient.patient_id,
            encounter_id=encounter.encounter_id,
            source="stemi_smoke",
            payload={"target_system": "ICU"},
        )
        append_event_registry_entry(
            EventRegistryEntry(
                event_id=str(envelope["event_id"]),
                event_type=str(envelope["event_type"]),
                occurred_at=str(envelope["occurred_at"]),
                patient_id=str(envelope["patient_id"]),
                encounter_id=str(envelope["encounter_id"]),
                source=str(envelope["source"]),
                payload=dict(envelope["payload"]),
            ),
            storage=storage,
        )
        return {
            "name": "stemi_golden_path",
            "status": "ok",
            "encounter_id": encounter.encounter_id,
            "final_state": "ICU",
            "handoff_count": len(get_handoff_snapshots(encounter.encounter_id, storage=storage)),
            "latest_handoff_stage": handoff.handoff_stage,
        }


def main() -> None:
    print(json.dumps(build_stemi_golden_path_result(), indent=2))


if __name__ == "__main__":
    main()
