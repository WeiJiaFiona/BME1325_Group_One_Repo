# Week 6 L1 API Contract (Frozen)

This contract is the Week 6 stable interface for ED -> OUTPATIENT/ICU/WARD integration.

## 1) `POST /mode/user/encounter/start`
Start one patient-facing ED encounter from User Mode input.

### Request
```json
{
  "patient_id": "P-001",
  "chief_complaint": "chest pain with cold sweat",
  "symptoms": ["diaphoresis", "shortness of breath"],
  "vitals": {"spo2": 95, "sbp": 120},
  "arrival_mode": "walk-in"
}
```

### Response
```json
{
  "ok": true,
  "data": {
    "encounter_id": "enc-xxxx",
    "patient_id": "P-001",
    "triage": {"acuity_ad": "B", "ctas_compat": 2},
    "state_trace": ["ARRIVAL", "WAITING_FOR_TRIAGE", "TRIAGE_COMPLETE"],
    "final_state": "UNDER_EVALUATION",
    "recommended_handoff_target": "ICU",
    "status": "STARTED"
  }
}
```

## 2) `POST /ed/handoff/request`
Create a handoff ticket from ED to external subsystem.

### Request
```json
{
  "encounter_id": "enc-xxxx",
  "target_system": "ICU",
  "reason": "high risk stroke"
}
```

`target_system` enum: `OUTPATIENT | ICU | WARD`

### Response
```json
{
  "ok": true,
  "data": {
    "handoff_ticket_id": "hdt-xxxx",
    "status": "REQUESTED",
    "event_type": "ED_PATIENT_READY_FOR_ICU",
    "reason": "high risk stroke"
  }
}
```

## 3) `POST /ed/handoff/complete`
Synchronously confirm handoff acceptance/rejection.

### Request
```json
{
  "handoff_ticket_id": "hdt-xxxx",
  "receiver_system": "ICU",
  "accepted": true,
  "accepted_at": "2026-04-08T13:30:00+00:00",
  "receiver_bed": "ICU-12"
}
```

### Response
```json
{
  "ok": true,
  "data": {
    "handoff_ticket_id": "hdt-xxxx",
    "status": "COMPLETED",
    "final_disposition_state": "ICU",
    "transfer_latency_seconds": 120,
    "receiver_system": "ICU"
  }
}
```

## 4) `GET /ed/queue/snapshot`
Read current ED queue and handoff pressure.

### Response
```json
{
  "ok": true,
  "data": {
    "total_encounters": 12,
    "active_encounters": 9,
    "waiting_for_physician": 3,
    "under_evaluation": 2,
    "high_acuity_waiting": 1,
    "awaiting_handoff": 2,
    "handoff": {"requested": 2, "completed": 5, "rejected": 1, "total_tickets": 8}
  }
}
```

## Error Model
- Validation / malformed payload: `400`
- Unknown encounter or handoff ticket: `404`
- Method mismatch: `405`
