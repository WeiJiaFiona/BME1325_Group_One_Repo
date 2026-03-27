def summarize_snapshots(rows: list[dict]) -> dict:
    if not rows:
        return {'avg_waiting_minutes': 0, 'avg_bed_utilization': 0, 'avg_doctor_queue': 0}
    n = len(rows)
    return {
        'avg_waiting_minutes': sum(r['avg_waiting_minutes'] for r in rows) / n,
        'avg_bed_utilization': sum(r['bed_utilization'] for r in rows) / n,
        'avg_doctor_queue': sum(r['doctor_queue'] for r in rows) / n,
    }
