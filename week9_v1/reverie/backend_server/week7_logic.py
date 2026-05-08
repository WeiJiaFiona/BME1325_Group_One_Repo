import datetime


def arrival_profile_multiplier(mode: str, hour: int) -> float:
    mode = (mode or "normal").strip().lower()
    hour = int(hour) % 24

    if mode == "surge":
        return 1.75

    if mode == "burst":
        if 7 <= hour <= 9:
            return 2.2
        if 16 <= hour <= 19:
            return 2.6
        if 11 <= hour <= 13:
            return 1.15
        return 0.65

    return 1.0


def effective_arrival_rate(base_rate: float, mode: str, hour: int) -> float:
    return max(0.0, float(base_rate) * arrival_profile_multiplier(mode, hour))


def testing_kind_for_ctas(ctas_score) -> str:
    try:
        score = int(ctas_score)
    except (TypeError, ValueError):
        score = 3
    return "imaging" if score <= 2 else "lab"


def boarding_timeout_reached(start_time, current_time, timeout_minutes) -> bool:
    if not start_time or not current_time:
        return False
    try:
        timeout_minutes = float(timeout_minutes or 0)
    except (TypeError, ValueError):
        return False
    if timeout_minutes <= 0:
        return False
    return current_time >= start_time + datetime.timedelta(minutes=timeout_minutes)
