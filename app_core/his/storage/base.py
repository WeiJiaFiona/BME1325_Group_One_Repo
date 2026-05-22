from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from app_core.his.schemas import (
    AuditLogEntry,
    ClinicalAssessmentRecord,
    ClinicalDocumentRecord,
    CurrentSummaryRecord,
    DiagnosisRecord,
    DocumentRegistryEntry,
    DepartmentRecord,
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
from app_core.his.exchange.outbox import OutboxEvent


class StorageError(RuntimeError):
    pass


class HisStorage(ABC):
    @abstractmethod
    def upsert_provider(self, provider: ProviderRecord) -> ProviderRecord: ...

    @abstractmethod
    def get_provider(self, provider_id: str) -> Optional[ProviderRecord]: ...

    @abstractmethod
    def upsert_department(self, department: DepartmentRecord) -> DepartmentRecord: ...

    @abstractmethod
    def get_department(self, department_id: str) -> Optional[DepartmentRecord]: ...

    @abstractmethod
    def upsert_patient(self, patient: PatientRecord) -> PatientRecord: ...

    @abstractmethod
    def get_patient(self, patient_id: str) -> Optional[PatientRecord]: ...

    @abstractmethod
    def create_encounter(self, encounter: EncounterRecord) -> EncounterRecord: ...

    @abstractmethod
    def get_encounter(self, encounter_id: str) -> Optional[EncounterRecord]: ...

    @abstractmethod
    def update_encounter(self, encounter: EncounterRecord) -> EncounterRecord: ...

    @abstractmethod
    def write_triage(self, triage: TriageRecord) -> TriageRecord: ...

    @abstractmethod
    def get_triage(self, encounter_id: str) -> Optional[TriageRecord]: ...

    @abstractmethod
    def append_vital_signs(self, vitals: VitalSignsRecord) -> VitalSignsRecord: ...

    @abstractmethod
    def list_vital_signs(self, encounter_id: str) -> list[VitalSignsRecord]: ...

    @abstractmethod
    def append_clinical_assessment(self, assessment: ClinicalAssessmentRecord) -> ClinicalAssessmentRecord: ...

    @abstractmethod
    def list_clinical_assessments(self, encounter_id: str) -> list[ClinicalAssessmentRecord]: ...

    @abstractmethod
    def append_diagnosis(self, diagnosis: DiagnosisRecord) -> DiagnosisRecord: ...

    @abstractmethod
    def list_diagnoses(self, encounter_id: str) -> list[DiagnosisRecord]: ...

    @abstractmethod
    def create_order(self, order: OrderRecord) -> OrderRecord: ...

    @abstractmethod
    def get_order(self, order_id: str) -> Optional[OrderRecord]: ...

    @abstractmethod
    def create_lab_request(self, request: LabRequestRecord) -> LabRequestRecord: ...

    @abstractmethod
    def record_lab_result(self, result: LabResultRecord) -> LabResultRecord: ...

    @abstractmethod
    def create_imaging_request(self, request: ImagingRequestRecord) -> ImagingRequestRecord: ...

    @abstractmethod
    def record_imaging_result(self, result: ImagingResultRecord) -> ImagingResultRecord: ...

    @abstractmethod
    def write_handoff_snapshot(self, snapshot: HandoffSnapshotRecord) -> HandoffSnapshotRecord: ...

    @abstractmethod
    def get_handoff_snapshots(self, encounter_id: str) -> list[HandoffSnapshotRecord]: ...

    @abstractmethod
    def write_current_summary(self, summary: CurrentSummaryRecord) -> CurrentSummaryRecord: ...

    @abstractmethod
    def get_current_summary(self, encounter_id: str) -> Optional[CurrentSummaryRecord]: ...

    @abstractmethod
    def write_clinical_document(self, document: ClinicalDocumentRecord) -> ClinicalDocumentRecord: ...

    @abstractmethod
    def register_document(self, entry: DocumentRegistryEntry) -> DocumentRegistryEntry: ...

    @abstractmethod
    def list_documents(self, encounter_id: str) -> list[ClinicalDocumentRecord]: ...

    @abstractmethod
    def append_event(self, entry: EventRegistryEntry) -> EventRegistryEntry: ...

    @abstractmethod
    def list_events(self, encounter_id: str) -> list[EventRegistryEntry]: ...

    @abstractmethod
    def append_audit(self, entry: AuditLogEntry) -> AuditLogEntry: ...

    @abstractmethod
    def list_audits(self, encounter_id: Optional[str] = None) -> list[AuditLogEntry]: ...

    @abstractmethod
    def append_outbox_event(self, event: OutboxEvent) -> OutboxEvent: ...

    @abstractmethod
    def list_outbox_events(self, encounter_id: Optional[str] = None) -> list[OutboxEvent]: ...


@dataclass
class InMemoryHisStorage(HisStorage):
    providers: dict[str, ProviderRecord] = field(default_factory=dict)
    departments: dict[str, DepartmentRecord] = field(default_factory=dict)
    patients: dict[str, PatientRecord] = field(default_factory=dict)
    encounters: dict[str, EncounterRecord] = field(default_factory=dict)
    triage_records: dict[str, TriageRecord] = field(default_factory=dict)
    vital_signs: dict[str, list[VitalSignsRecord]] = field(default_factory=dict)
    assessments: dict[str, list[ClinicalAssessmentRecord]] = field(default_factory=dict)
    diagnoses: dict[str, list[DiagnosisRecord]] = field(default_factory=dict)
    orders: dict[str, OrderRecord] = field(default_factory=dict)
    lab_requests: dict[str, LabRequestRecord] = field(default_factory=dict)
    lab_results: dict[str, LabResultRecord] = field(default_factory=dict)
    imaging_requests: dict[str, ImagingRequestRecord] = field(default_factory=dict)
    imaging_results: dict[str, ImagingResultRecord] = field(default_factory=dict)
    handoffs: dict[str, list[HandoffSnapshotRecord]] = field(default_factory=dict)
    summaries: dict[str, CurrentSummaryRecord] = field(default_factory=dict)
    documents: dict[str, list[ClinicalDocumentRecord]] = field(default_factory=dict)
    document_registry: dict[str, list[DocumentRegistryEntry]] = field(default_factory=dict)
    events: dict[str, list[EventRegistryEntry]] = field(default_factory=dict)
    audits: list[AuditLogEntry] = field(default_factory=list)
    outbox: list[OutboxEvent] = field(default_factory=list)

    def upsert_provider(self, provider: ProviderRecord) -> ProviderRecord:
        self.providers[provider.provider_id] = provider
        return provider

    def get_provider(self, provider_id: str) -> Optional[ProviderRecord]:
        return self.providers.get(provider_id)

    def upsert_department(self, department: DepartmentRecord) -> DepartmentRecord:
        self.departments[department.department_id] = department
        return department

    def get_department(self, department_id: str) -> Optional[DepartmentRecord]:
        return self.departments.get(department_id)

    def upsert_patient(self, patient: PatientRecord) -> PatientRecord:
        self.patients[patient.patient_id] = patient
        return patient

    def get_patient(self, patient_id: str) -> Optional[PatientRecord]:
        return self.patients.get(patient_id)

    def create_encounter(self, encounter: EncounterRecord) -> EncounterRecord:
        self.encounters[encounter.encounter_id] = encounter
        return encounter

    def get_encounter(self, encounter_id: str) -> Optional[EncounterRecord]:
        return self.encounters.get(encounter_id)

    def update_encounter(self, encounter: EncounterRecord) -> EncounterRecord:
        self.encounters[encounter.encounter_id] = encounter
        return encounter

    def write_triage(self, triage: TriageRecord) -> TriageRecord:
        self.triage_records[triage.encounter_id] = triage
        return triage

    def get_triage(self, encounter_id: str) -> Optional[TriageRecord]:
        return self.triage_records.get(encounter_id)

    def append_vital_signs(self, vitals: VitalSignsRecord) -> VitalSignsRecord:
        self.vital_signs.setdefault(vitals.encounter_id, []).append(vitals)
        return vitals

    def list_vital_signs(self, encounter_id: str) -> list[VitalSignsRecord]:
        return list(self.vital_signs.get(encounter_id, []))

    def append_clinical_assessment(self, assessment: ClinicalAssessmentRecord) -> ClinicalAssessmentRecord:
        self.assessments.setdefault(assessment.encounter_id, []).append(assessment)
        return assessment

    def list_clinical_assessments(self, encounter_id: str) -> list[ClinicalAssessmentRecord]:
        return list(self.assessments.get(encounter_id, []))

    def append_diagnosis(self, diagnosis: DiagnosisRecord) -> DiagnosisRecord:
        self.diagnoses.setdefault(diagnosis.encounter_id, []).append(diagnosis)
        return diagnosis

    def list_diagnoses(self, encounter_id: str) -> list[DiagnosisRecord]:
        return list(self.diagnoses.get(encounter_id, []))

    def create_order(self, order: OrderRecord) -> OrderRecord:
        self.orders[order.order_id] = order
        return order

    def get_order(self, order_id: str) -> Optional[OrderRecord]:
        return self.orders.get(order_id)

    def create_lab_request(self, request: LabRequestRecord) -> LabRequestRecord:
        self.lab_requests[request.request_id] = request
        return request

    def record_lab_result(self, result: LabResultRecord) -> LabResultRecord:
        self.lab_results[result.result_id] = result
        return result

    def create_imaging_request(self, request: ImagingRequestRecord) -> ImagingRequestRecord:
        self.imaging_requests[request.request_id] = request
        return request

    def record_imaging_result(self, result: ImagingResultRecord) -> ImagingResultRecord:
        self.imaging_results[result.result_id] = result
        return result

    def write_handoff_snapshot(self, snapshot: HandoffSnapshotRecord) -> HandoffSnapshotRecord:
        self.handoffs.setdefault(snapshot.encounter_id, []).append(snapshot)
        return snapshot

    def get_handoff_snapshots(self, encounter_id: str) -> list[HandoffSnapshotRecord]:
        return list(self.handoffs.get(encounter_id, []))

    def write_current_summary(self, summary: CurrentSummaryRecord) -> CurrentSummaryRecord:
        self.summaries[summary.encounter_id] = summary
        return summary

    def get_current_summary(self, encounter_id: str) -> Optional[CurrentSummaryRecord]:
        return self.summaries.get(encounter_id)

    def write_clinical_document(self, document: ClinicalDocumentRecord) -> ClinicalDocumentRecord:
        self.documents.setdefault(document.encounter_id, []).append(document)
        return document

    def register_document(self, entry: DocumentRegistryEntry) -> DocumentRegistryEntry:
        self.document_registry.setdefault(entry.encounter_id, []).append(entry)
        return entry

    def list_documents(self, encounter_id: str) -> list[ClinicalDocumentRecord]:
        return list(self.documents.get(encounter_id, []))

    def append_event(self, entry: EventRegistryEntry) -> EventRegistryEntry:
        self.events.setdefault(entry.encounter_id, []).append(entry)
        return entry

    def list_events(self, encounter_id: str) -> list[EventRegistryEntry]:
        return list(self.events.get(encounter_id, []))

    def append_audit(self, entry: AuditLogEntry) -> AuditLogEntry:
        self.audits.append(entry)
        return entry

    def list_audits(self, encounter_id: Optional[str] = None) -> list[AuditLogEntry]:
        if encounter_id is None:
            return list(self.audits)
        return [item for item in self.audits if item.encounter_id == encounter_id]

    def append_outbox_event(self, event: OutboxEvent) -> OutboxEvent:
        self.outbox.append(event)
        return event

    def list_outbox_events(self, encounter_id: Optional[str] = None) -> list[OutboxEvent]:
        if encounter_id is None:
            return list(self.outbox)
        return [item for item in self.outbox if item.encounter_id == encounter_id]
