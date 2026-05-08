from __future__ import annotations

import json

from app_core.his.adapters import get_memory_upgrade_plan


def build_timeline_export_smoke_plan() -> dict[str, object]:
    return {
        "name": "timeline_export",
        "status": "placeholder",
        "blocked_by": ["Replay export service/storage boundary is not frozen yet."],
        "expected_sources": ["memory_events", "current_encounter_summaries", "handoff_snapshots", "audit_logs"],
        "reserved_targets": [plan.target_table for plan in get_memory_upgrade_plan() if plan.target_table == "replay_exports"],
        "checks": [
            "Load one encounter's Memory v1 events.",
            "Join the latest derived summary projection.",
            "Join handoff snapshot continuity artifacts.",
            "Emit one export bundle for demo/QA once replay write path exists.",
        ],
    }


def main() -> None:
    print(json.dumps(build_timeline_export_smoke_plan(), indent=2))


if __name__ == "__main__":
    main()
