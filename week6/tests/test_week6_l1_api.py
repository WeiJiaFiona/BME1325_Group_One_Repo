from week5_system.app.api_v1 import (
    ApiError,
    complete_handoff,
    queue_snapshot,
    request_handoff,
    reset_runtime_state,
    start_encounter,
)


def setup_function():
    reset_runtime_state()


def _new_encounter(chief_complaint="Chest pain with cold sweat", symptoms=None, vitals=None):
    return start_encounter(
        {
            "patient_id": "week6-p1",
            "chief_complaint": chief_complaint,
            "symptoms": symptoms or ["diaphoresis", "shortness of breath"],
            "vitals": vitals or {"spo2": 95, "sbp": 120},
        }
    )


def test_start_contract_shape():
    data = _new_encounter()
    assert data["status"] == "STARTED"
    assert data["encounter_id"].startswith("enc-")
    assert data["triage"]["acuity_ad"] in {"A", "B", "C", "D"}
    assert isinstance(data["state_trace"], list)
    assert "recommended_handoff_target" in data


def test_start_malformed_payload_rejected():
    try:
        start_encounter({"patient_id": "x", "symptoms": [], "vitals": {}})
    except ApiError as exc:
        assert "chief_complaint" in str(exc)
    else:
        raise AssertionError("expected schema validation error")


def test_handoff_request_complete_icu_flow():
    start_data = _new_encounter()
    req = request_handoff(
        {
            "encounter_id": start_data["encounter_id"],
            "target_system": "ICU",
            "reason": "FAST positive stroke and high deterioration risk",
        }
    )
    assert req["status"] == "REQUESTED"
    assert req["event_type"] == "ED_PATIENT_READY_FOR_ICU"

    done = complete_handoff(
        {
            "handoff_ticket_id": req["handoff_ticket_id"],
            "receiver_system": "ICU",
            "accepted": True,
            "accepted_at": "2026-04-08T13:30:00+00:00",
            "receiver_bed": "ICU-12",
        }
    )
    assert done["status"] == "COMPLETED"
    assert done["final_disposition_state"] == "ICU"
    assert done["transfer_latency_seconds"] >= 0


def test_handoff_rejects_invalid_receiver():
    start_data = _new_encounter(
        chief_complaint="mild ankle sprain",
        symptoms=["mild sprain"],
        vitals={"spo2": 99, "sbp": 125},
    )
    req = request_handoff(
        {
            "encounter_id": start_data["encounter_id"],
            "target_system": "OUTPATIENT",
            "reason": "outpatient follow-up",
        }
    )
    try:
        complete_handoff(
            {
                "handoff_ticket_id": req["handoff_ticket_id"],
                "receiver_system": "ICU",
                "accepted": True,
            }
        )
    except ApiError as exc:
        assert "mismatch" in str(exc)
    else:
        raise AssertionError("expected receiver mismatch error")


def test_queue_snapshot_tracks_handoff_lifecycle():
    e1 = _new_encounter(chief_complaint="FAST positive with slurred speech", symptoms=["stroke signs"])
    e2 = _new_encounter(chief_complaint="mild ankle sprain", symptoms=["mild sprain"], vitals={"spo2": 99, "sbp": 125})

    t1 = request_handoff(
        {"encounter_id": e1["encounter_id"], "target_system": "ICU", "reason": "critical stroke"}
    )
    t2 = request_handoff(
        {"encounter_id": e2["encounter_id"], "target_system": "OUTPATIENT", "reason": "stable outpatient route"}
    )
    complete_handoff(
        {"handoff_ticket_id": t2["handoff_ticket_id"], "receiver_system": "OUTPATIENT", "accepted": True}
    )

    snap = queue_snapshot()
    assert snap["total_encounters"] == 2
    assert snap["awaiting_handoff"] == 1
    assert snap["handoff"]["requested"] == 1
    assert snap["handoff"]["completed"] == 1
    assert t1["handoff_ticket_id"] != t2["handoff_ticket_id"]


def test_all_receiver_systems_supported():
    for system in ("OUTPATIENT", "ICU", "WARD"):
        reset_runtime_state()
        start_data = _new_encounter()
        req = request_handoff(
            {
                "encounter_id": start_data["encounter_id"],
                "target_system": system,
                "reason": f"route to {system}",
            }
        )
        done = complete_handoff(
            {
                "handoff_ticket_id": req["handoff_ticket_id"],
                "receiver_system": system,
                "accepted": True,
            }
        )
        assert done["final_disposition_state"] == system
