def triage_level(patient: dict) -> int:
    spo2 = patient.get('vitals', {}).get('spo2', 100)
    resource_need = patient.get('resource_need', 1)
    complaint = patient.get('chief_complaint', '')

    if spo2 < 90 or '意识障碍' in complaint or '呼吸困难' in complaint:
        return 1
    if spo2 < 94 or '胸痛' in complaint or '卒中' in complaint:
        return 2
    if resource_need >= 2:
        return 3
    return 4


def route_zone(level: int) -> str:
    if level in (1, 2):
        return 'red'
    if level == 3:
        return 'yellow'
    return 'green'
