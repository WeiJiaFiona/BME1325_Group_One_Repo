from app.metrics.collector import collect_snapshot


def test_collect_snapshot_has_required_kpis():
    data = collect_snapshot(waiting=12, occupied_beds=8, doctor_queue=5)
    assert 'avg_waiting_minutes' in data
    assert 'bed_utilization' in data
    assert 'doctor_queue' in data
