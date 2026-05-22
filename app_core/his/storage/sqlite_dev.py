from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import sqlite3
from typing import Any, Optional, Type, TypeVar

from app_core.his.config import DEFAULT_SQLITE_DEV_PATH, POSTGRES_MIGRATION_SEQUENCE
from app_core.his.exchange.outbox import OutboxEvent
from app_core.his.schemas import (
    AuditLogEntry,
    ClinicalAssessmentRecord,
    ClinicalDocumentRecord,
    CurrentSummaryRecord,
    DiagnosisRecord,
    DepartmentRecord,
    DocumentRegistryEntry,
    EncounterRecord,
    EventRegistryEntry,
    HandoffSnapshotRecord,
    ImagingRequestRecord,
    ImagingResultRecord,
    LabRequestRecord,
    LabResultRecord,
    OrderRecord,
    PatientRecord,
    ProviderRecord,
    TriageRecord,
    VitalSignsRecord,
)

from .base import HisStorage

T = TypeVar("T")


@dataclass
class SQLiteDevHisStorage(HisStorage):
    db_path: Path = field(default_factory=lambda: Path(DEFAULT_SQLITE_DEV_PATH))

    def bootstrap(self) -> Path:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS patients (
                    record_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    encounter_id TEXT,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS providers (
                    record_id TEXT PRIMARY KEY,
                    patient_id TEXT,
                    encounter_id TEXT,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS departments (
                    record_id TEXT PRIMARY KEY,
                    patient_id TEXT,
                    encounter_id TEXT,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS encounters (
                    record_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    encounter_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS triage_records (
                    record_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    encounter_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS vital_signs (
                    record_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    encounter_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS clinical_assessments (
                    record_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    encounter_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS diagnosis_records (
                    record_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    encounter_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS orders (
                    record_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    encounter_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS lab_requests (
                    record_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    encounter_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS lab_results (
                    record_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    encounter_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS imaging_requests (
                    record_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    encounter_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS imaging_results (
                    record_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    encounter_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS handoff_snapshots (
                    record_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    encounter_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS current_summaries (
                    record_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    encounter_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS clinical_documents (
                    record_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    encounter_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS document_registry (
                    record_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    encounter_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS event_registry (
                    record_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    encounter_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_logs (
                    record_id TEXT PRIMARY KEY,
                    patient_id TEXT,
                    encounter_id TEXT,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS outbox_events (
                    record_id TEXT PRIMARY KEY,
                    patient_id TEXT,
                    encounter_id TEXT,
                    payload TEXT NOT NULL
                );
                """
            )
            conn.commit()
        return self.db_path

    def migration_plan(self) -> tuple[str, ...]:
        return POSTGRES_MIGRATION_SEQUENCE

    def upsert_patient(self, patient: PatientRecord) -> PatientRecord:
        self._replace("patients", patient.patient_id, patient.to_dict(), patient_id=patient.patient_id)
        return patient

    def get_patient(self, patient_id: str) -> Optional[PatientRecord]:
        return self._fetch_one("patients", "patient_id", patient_id, PatientRecord)

    def upsert_provider(self, provider: ProviderRecord) -> ProviderRecord:
        self._replace("providers", provider.provider_id, provider.to_dict())
        return provider

    def get_provider(self, provider_id: str) -> Optional[ProviderRecord]:
        return self._fetch_one("providers", "record_id", provider_id, ProviderRecord)

    def upsert_department(self, department: DepartmentRecord) -> DepartmentRecord:
        self._replace("departments", department.department_id, department.to_dict())
        return department

    def get_department(self, department_id: str) -> Optional[DepartmentRecord]:
        return self._fetch_one("departments", "record_id", department_id, DepartmentRecord)

    def create_encounter(self, encounter: EncounterRecord) -> EncounterRecord:
        self._replace(
            "encounters",
            encounter.encounter_id,
            encounter.to_dict(),
            patient_id=encounter.patient_id,
            encounter_id=encounter.encounter_id,
        )
        return encounter

    def get_encounter(self, encounter_id: str) -> Optional[EncounterRecord]:
        return self._fetch_one("encounters", "encounter_id", encounter_id, EncounterRecord)

    def update_encounter(self, encounter: EncounterRecord) -> EncounterRecord:
        return self.create_encounter(encounter)

    def write_triage(self, triage: TriageRecord) -> TriageRecord:
        self._replace(
            "triage_records",
            triage.triage_id,
            triage.to_dict(),
            patient_id=triage.patient_id,
            encounter_id=triage.encounter_id,
        )
        return triage

    def get_triage(self, encounter_id: str) -> Optional[TriageRecord]:
        return self._fetch_one("triage_records", "encounter_id", encounter_id, TriageRecord)

    def append_vital_signs(self, vitals: VitalSignsRecord) -> VitalSignsRecord:
        self._replace(
            "vital_signs",
            vitals.vital_id,
            vitals.to_dict(),
            patient_id=vitals.patient_id,
            encounter_id=vitals.encounter_id,
        )
        return vitals

    def list_vital_signs(self, encounter_id: str) -> list[VitalSignsRecord]:
        return self._fetch_many("vital_signs", encounter_id, VitalSignsRecord)

    def append_clinical_assessment(self, assessment: ClinicalAssessmentRecord) -> ClinicalAssessmentRecord:
        self._replace(
            "clinical_assessments",
            assessment.assessment_id,
            assessment.to_dict(),
            patient_id=assessment.patient_id,
            encounter_id=assessment.encounter_id,
        )
        return assessment

    def list_clinical_assessments(self, encounter_id: str) -> list[ClinicalAssessmentRecord]:
        return self._fetch_many("clinical_assessments", encounter_id, ClinicalAssessmentRecord)

    def append_diagnosis(self, diagnosis: DiagnosisRecord) -> DiagnosisRecord:
        self._replace(
            "diagnosis_records",
            diagnosis.diagnosis_id,
            diagnosis.to_dict(),
            patient_id=diagnosis.patient_id,
            encounter_id=diagnosis.encounter_id,
        )
        return diagnosis

    def list_diagnoses(self, encounter_id: str) -> list[DiagnosisRecord]:
        return self._fetch_many("diagnosis_records", encounter_id, DiagnosisRecord)

    def create_order(self, order: OrderRecord) -> OrderRecord:
        self._replace(
            "orders",
            order.order_id,
            order.to_dict(),
            patient_id=order.patient_id,
            encounter_id=order.encounter_id,
        )
        return order

    def get_order(self, order_id: str) -> Optional[OrderRecord]:
        return self._fetch_one("orders", "record_id", order_id, OrderRecord)

    def create_lab_request(self, request: LabRequestRecord) -> LabRequestRecord:
        self._replace(
            "lab_requests",
            request.request_id,
            request.to_dict(),
            patient_id=request.patient_id,
            encounter_id=request.encounter_id,
        )
        return request

    def record_lab_result(self, result: LabResultRecord) -> LabResultRecord:
        self._replace(
            "lab_results",
            result.result_id,
            result.to_dict(),
            patient_id=result.patient_id,
            encounter_id=result.encounter_id,
        )
        return result

    def create_imaging_request(self, request: ImagingRequestRecord) -> ImagingRequestRecord:
        self._replace(
            "imaging_requests",
            request.request_id,
            request.to_dict(),
            patient_id=request.patient_id,
            encounter_id=request.encounter_id,
        )
        return request

    def record_imaging_result(self, result: ImagingResultRecord) -> ImagingResultRecord:
        self._replace(
            "imaging_results",
            result.result_id,
            result.to_dict(),
            patient_id=result.patient_id,
            encounter_id=result.encounter_id,
        )
        return result

    def write_handoff_snapshot(self, snapshot: HandoffSnapshotRecord) -> HandoffSnapshotRecord:
        self._replace(
            "handoff_snapshots",
            snapshot.snapshot_id,
            snapshot.to_dict(),
            patient_id=snapshot.patient_id,
            encounter_id=snapshot.encounter_id,
        )
        return snapshot

    def get_handoff_snapshots(self, encounter_id: str) -> list[HandoffSnapshotRecord]:
        return self._fetch_many("handoff_snapshots", encounter_id, HandoffSnapshotRecord)

    def write_current_summary(self, summary: CurrentSummaryRecord) -> CurrentSummaryRecord:
        self._replace(
            "current_summaries",
            summary.summary_id,
            summary.to_dict(),
            patient_id=summary.patient_id,
            encounter_id=summary.encounter_id,
        )
        return summary

    def get_current_summary(self, encounter_id: str) -> Optional[CurrentSummaryRecord]:
        return self._fetch_one("current_summaries", "encounter_id", encounter_id, CurrentSummaryRecord)

    def write_clinical_document(self, document: ClinicalDocumentRecord) -> ClinicalDocumentRecord:
        self._replace(
            "clinical_documents",
            document.document_id,
            document.to_dict(),
            patient_id=document.patient_id,
            encounter_id=document.encounter_id,
        )
        return document

    def register_document(self, entry: DocumentRegistryEntry) -> DocumentRegistryEntry:
        self._replace(
            "document_registry",
            entry.registry_id,
            entry.to_dict(),
            patient_id=entry.patient_id,
            encounter_id=entry.encounter_id,
        )
        return entry

    def list_documents(self, encounter_id: str) -> list[ClinicalDocumentRecord]:
        return self._fetch_many("clinical_documents", encounter_id, ClinicalDocumentRecord)

    def append_event(self, entry: EventRegistryEntry) -> EventRegistryEntry:
        self._replace(
            "event_registry",
            entry.event_id,
            entry.to_dict(),
            patient_id=entry.patient_id,
            encounter_id=entry.encounter_id,
        )
        return entry

    def list_events(self, encounter_id: str) -> list[EventRegistryEntry]:
        return self._fetch_many("event_registry", encounter_id, EventRegistryEntry)

    def append_audit(self, entry: AuditLogEntry) -> AuditLogEntry:
        self._replace(
            "audit_logs",
            entry.audit_id,
            entry.to_dict(),
            patient_id=entry.patient_id,
            encounter_id=entry.encounter_id,
        )
        return entry

    def list_audits(self, encounter_id: Optional[str] = None) -> list[AuditLogEntry]:
        return self._fetch_optional_many("audit_logs", encounter_id, AuditLogEntry)

    def append_outbox_event(self, event: OutboxEvent) -> OutboxEvent:
        payload = event.to_dict()
        self._replace(
            "outbox_events",
            event.outbox_id,
            payload,
            patient_id=str(payload.get("patient_id") or ""),
            encounter_id=event.encounter_id,
        )
        return event

    def list_outbox_events(self, encounter_id: Optional[str] = None) -> list[OutboxEvent]:
        return self._fetch_optional_many("outbox_events", encounter_id, OutboxEvent)

    def as_storage(self) -> HisStorage:
        return self

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _replace(
        self,
        table: str,
        record_id: str,
        payload: dict[str, Any],
        *,
        patient_id: str = "",
        encounter_id: str = "",
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO {table} (record_id, patient_id, encounter_id, payload) VALUES (?, ?, ?, ?)",
                (record_id, patient_id, encounter_id, json.dumps(payload, ensure_ascii=False)),
            )
            conn.commit()

    def _fetch_one(self, table: str, column: str, value: str, cls: Type[T]) -> Optional[T]:
        with self._connect() as conn:
            row = conn.execute(f"SELECT payload FROM {table} WHERE {column} = ? LIMIT 1", (value,)).fetchone()
        if row is None:
            return None
        return cls(**json.loads(row["payload"]))

    def _fetch_many(self, table: str, encounter_id: str, cls: type[T]) -> list[T]:
        return self._fetch_optional_many(table, encounter_id, cls)

    def _fetch_optional_many(self, table: str, encounter_id: Optional[str], cls: Type[T]) -> list[T]:
        with self._connect() as conn:
            if encounter_id is None:
                rows = conn.execute(f"SELECT payload FROM {table} ORDER BY rowid ASC").fetchall()
            else:
                rows = conn.execute(
                    f"SELECT payload FROM {table} WHERE encounter_id = ? ORDER BY rowid ASC",
                    (encounter_id,),
                ).fetchall()
        return [cls(**json.loads(row["payload"])) for row in rows]
