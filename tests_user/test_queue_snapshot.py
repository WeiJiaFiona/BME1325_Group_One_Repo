from app_core.queue_state_primitives.snapshot import queue_snapshot


class DummyMaze:
    def __init__(self):
        self.triage_queue = [1, 2]
        self.patients_waiting_for_doctor = ["p1"]
        self.injuries_zones = {
            "trauma": {"capacity": 2, "available_beds": [[1, 1]]},
            "diagnostic": {"capacity": 1, "available_beds": []},
        }


def test_queue_snapshot_structure():
    maze = DummyMaze()
    resp = queue_snapshot(maze)
    assert "queues" in resp
    assert "occupancy" in resp
    assert "snapshot_time" in resp
    assert "trace_id" in resp
    assert resp["queues"]["triage"]["size"] == 2
    assert resp["queues"]["doctor"]["size"] == 1
    assert resp["occupancy"]["beds_total"] == 3
    assert resp["occupancy"]["beds_available"] == 1


def test_queue_snapshot_empty():
    resp = queue_snapshot(None)
    assert resp["queues"]["triage"]["size"] == 0
    assert resp["occupancy"]["beds_total"] == 0
    assert "trace_id" in resp
