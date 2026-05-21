from __future__ import annotations

import json
from pathlib import Path
import tempfile

from app_core.his.adapters import persist_current_summary, persist_handoff_snapshot, persist_memory_item
from app_core.his.schemas import CurrentSummaryRecord, EventRegistryEntry, HandoffSnapshotRecord
from app_core.his.storage.sqlite_dev import SQLiteDevHisStorage
from app_core.memory.schema import CurrentEncounterSummary, HandoffMemorySnapshot, MemoryItem


def build_timeline_export_smoke_result() -> dict[str, object]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = SQLiteDevHisStorage(db_path=Path(tmp_dir) / "timeline.sqlite3")
        storage.bootstrap()
        patient_id = "P-1a2b3c4d"
        encounter_id = "E-20260515153045-1a2b"

        item = MemoryItem(
            memory_id="mem-1",
            run_id="run-1",
            mode="user",
            encounter_id=encounter_id,
            patient_id=patient_id,
            step=1,
            sim_time=None,
            wall_time=None,
            agent_role="triage_nurse",
            event_type="encounter_started",
            source="timeline_smoke",
            priority="medium",
            content="patient entered ED",
            structured_facts={"chief_complaint": "chest pain"},
        )
        persist_memory_item(item, storage=storage)

        summary = CurrentEncounterSummary(
            run_id="run-1",
            mode="user",
            encounter_id=encounter_id,
            patient_id=patient_id,
            current_state="UNDER_EVALUATION",
            current_zone="yellow",
            acuity="3",
            latest_vitals={"spo2": 95},
            source_memory_ids=["mem-1"],
            updated_at_step=1,
        )
        persist_current_summary(summary, storage=storage)

        snapshot = HandoffMemorySnapshot(
            snapshot_id="snap-1",
            run_id="run-1",
            mode="user",
            encounter_id=encounter_id,
            patient_id=patient_id,
            from_role="doctor",
            to_role="WARD",
            handoff_stage="requested",
            patient_brief="stable chest pain",
            current_state={"state": "UNDER_EVALUATION"},
            source_memory_ids=["mem-1"],
            created_at_step=2,
        )
        persist_handoff_snapshot(snapshot, storage=storage)

        events = storage._fetch_optional_many("event_registry", None, EventRegistryEntry)
        summaries = storage._fetch_optional_many("current_summaries", None, CurrentSummaryRecord)
        handoffs = storage._fetch_optional_many("handoff_snapshots", None, HandoffSnapshotRecord)
        documents = storage.list_documents(encounter_id)
        return {
            "name": "timeline_export",
            "status": "ok",
            "patient_id": patient_id,
            "encounter_id": encounter_id,
            "events": len(events),
            "summaries": len(summaries),
            "handoff_snapshots": len(handoffs),
            "documents": len(documents),
        }


def main() -> None:
    print(json.dumps(build_timeline_export_smoke_result(), indent=2))


if __name__ == "__main__":
    main()
