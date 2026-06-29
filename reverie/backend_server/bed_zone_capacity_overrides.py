from __future__ import annotations

import math
from typing import Any


MAJOR_ZONE = "major injuries zone"
MINOR_ZONE = "minor injuries zone"
OBSERVATION_ZONE_CANDIDATES = (
    "observation unit",
    "observation zone",
    "observation room",
    "observation",
)


def _positive_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _bed_count(maze: Any, zone: str) -> int | None:
    if not hasattr(maze, "available_beds") or not hasattr(maze, "bed_assignments"):
        return None
    if zone not in maze.available_beds and zone not in maze.bed_assignments:
        return None
    return len(maze.available_beds.get(zone, set())) + len(maze.bed_assignments.get(zone, {}))


def _physical_bed_tiles(maze: Any, zone: str) -> list[tuple[int, int]]:
    bed_key = f"ed map:emergency department:{zone}:bed"
    raw = getattr(maze, "address_tiles", {}).get(bed_key, set()) or set()
    tiles: list[tuple[int, int]] = []
    for coord in raw:
        if isinstance(coord, (list, tuple)) and len(coord) >= 2:
            tiles.append((int(coord[0]), int(coord[1])))
    return sorted(set(tiles))


def _override_bed_tracked_zone(maze: Any, zone: str, multiplier: Any) -> dict[str, Any]:
    parsed_multiplier = _positive_float(multiplier)
    baseline = _bed_count(maze, zone)
    if parsed_multiplier is None:
        return {
            "zone": zone,
            "status": "not_requested",
            "baseline_capacity": baseline,
            "effective_capacity": baseline,
            "multiplier": None,
        }
    if baseline is None:
        return {
            "zone": zone,
            "status": "not_available",
            "baseline_capacity": None,
            "effective_capacity": None,
            "multiplier": parsed_multiplier,
        }
    if baseline <= 0:
        return {
            "zone": zone,
            "status": "not_available",
            "baseline_capacity": baseline,
            "effective_capacity": baseline,
            "multiplier": parsed_multiplier,
            "reason": "baseline_bed_count_zero",
        }

    target = max(baseline, int(math.ceil(float(baseline) * parsed_multiplier)))
    zone_info = maze.injuries_zones.get(zone, {})
    if isinstance(zone_info, dict):
        zone_info["capacity"] = target

    added = 0
    if target > baseline:
        physical_tiles = _physical_bed_tiles(maze, zone)
        if not physical_tiles:
            return {
                "zone": zone,
                "status": "not_available",
                "baseline_capacity": baseline,
                "effective_capacity": baseline,
                "multiplier": parsed_multiplier,
                "reason": "no_pathable_bed_tiles",
            }
        maze.available_beds.setdefault(zone, set())
        maze.bed_assignments.setdefault(zone, {})
        for slot_index in range(baseline, target):
            x, y = physical_tiles[slot_index % len(physical_tiles)]
            maze.available_beds[zone].add((x, y, slot_index))
            added += 1
        if hasattr(maze, "_sync_bed_state"):
            maze._sync_bed_state(zone)

    return {
        "zone": zone,
        "status": "applied" if target != baseline else "baseline",
        "baseline_capacity": baseline,
        "effective_capacity": target,
        "multiplier": parsed_multiplier,
        "logical_beds_added": added,
    }


def _find_observation_zone(maze: Any) -> str | None:
    for zone in OBSERVATION_ZONE_CANDIDATES:
        if zone in getattr(maze, "injuries_zones", {}):
            return zone
    return None


def apply_bed_zone_capacity_overrides(maze: Any, overrides: dict[str, Any] | None) -> dict[str, Any]:
    overrides = dict(overrides or {})
    observation_zone = _find_observation_zone(maze)
    observation_multiplier = overrides.get("observation_bed_multiplier")

    result = {
        "major_zone_bed": _override_bed_tracked_zone(
            maze,
            MAJOR_ZONE,
            overrides.get("major_zone_bed_multiplier"),
        ),
        "minor_zone_capacity": _override_bed_tracked_zone(
            maze,
            MINOR_ZONE,
            overrides.get("minor_zone_capacity_multiplier"),
        ),
        "observation_bed": (
            _override_bed_tracked_zone(maze, observation_zone, observation_multiplier)
            if observation_zone
            else {
                "zone": None,
                "status": "not_available" if _positive_float(observation_multiplier) is not None else "not_requested",
                "baseline_capacity": None,
                "effective_capacity": None,
                "multiplier": _positive_float(observation_multiplier),
                "reason": "observation_zone_not_found",
            }
        ),
    }
    return result

