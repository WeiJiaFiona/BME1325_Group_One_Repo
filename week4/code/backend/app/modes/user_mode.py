from app.domain.triage_rules import triage_level, route_zone


def start_user_encounter(payload: dict) -> dict:
    level = triage_level(payload)
    zone = route_zone(level)
    return {
        'triage_level': level,
        'zone': zone,
        'next_action': 'doctor_assessment' if zone != 'green' else 'fast_track_assessment',
    }
