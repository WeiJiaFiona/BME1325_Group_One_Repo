import os
from datetime import datetime, timedelta

from app_core.app.handoff import HANDOFF_TIMEOUT_SECONDS, complete, request, reset_store
from app_core.app.mock_server import start_mock_server, stop_mock_server


def _base_request():
    return {
        "patient_id": "p1",
        "acuity_ad": "A",
        "zone": "red",
        "stability": "critical",
        "required_unit": "ICU",
        "clinical_summary": "needs ICU",
        "pending_tasks": ["ct"],
    }


def test_handoff_request_complete():
    server, _ = start_mock_server()
    host, port = server.server_address
    os.environ["HANDOFF_MOCK_URL"] = f"http://{host}:{port}/handoff/request"
    reset_store()
    try:
        resp = request(_base_request())
        assert resp["status"] in {"REQUESTED", "REJECTED"}
        ticket = resp["handoff_ticket_id"]
        accepted_at = datetime.utcnow().isoformat() + "Z"
        resp2 = complete(
            {
                "handoff_ticket_id": ticket,
                "receiver_system": "ICU",
                "accepted_at": accepted_at,
                "receiver_bed": "ICU-1",
            }
        )
        assert resp2["final_disposition_state"] in {"COMPLETED", "TIMEOUT", "REJECTED"}
        assert "event_trace" in resp2
    finally:
        stop_mock_server(server)
        os.environ.pop("HANDOFF_MOCK_URL", None)


def test_handoff_timeout():
    reset_store()
    resp = request(_base_request())
    ticket = resp["handoff_ticket_id"]
    future = datetime.utcnow() + timedelta(seconds=HANDOFF_TIMEOUT_SECONDS + 5)
    resp2 = complete(
        {
            "handoff_ticket_id": ticket,
            "receiver_system": "ICU",
            "accepted_at": future.isoformat() + "Z",
            "receiver_bed": "ICU-1",
        }
    )
    assert resp2["final_disposition_state"] == "TIMEOUT"


def test_handoff_invalid_state():
    reset_store()
    resp = request(_base_request())
    ticket = resp["handoff_ticket_id"]
    accepted_at = datetime.utcnow().isoformat() + "Z"
    complete(
        {
            "handoff_ticket_id": ticket,
            "receiver_system": "ICU",
            "accepted_at": accepted_at,
            "receiver_bed": "ICU-1",
        }
    )
    resp2 = complete(
        {
            "handoff_ticket_id": ticket,
            "receiver_system": "ICU",
            "accepted_at": accepted_at,
            "receiver_bed": "ICU-1",
        }
    )
    assert resp2["error_code"] == "INVALID_STATE"


def test_handoff_not_found():
    resp = complete(
        {
            "handoff_ticket_id": "missing",
            "receiver_system": "ICU",
            "accepted_at": datetime.utcnow().isoformat() + "Z",
            "receiver_bed": "ICU-1",
        }
    )
    assert resp["error_code"] == "NOT_FOUND"
