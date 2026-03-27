def collect_snapshot(waiting: int, occupied_beds: int, doctor_queue: int, total_beds: int = 10):
    return {
        'avg_waiting_minutes': waiting * 2,
        'bed_utilization': occupied_beds / total_beds,
        'doctor_queue': doctor_queue,
    }
