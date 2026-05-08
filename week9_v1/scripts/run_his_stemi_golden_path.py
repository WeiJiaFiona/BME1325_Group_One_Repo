from __future__ import annotations

import json


def build_stemi_golden_path_plan() -> dict[str, object]:
    return {
        "name": "stemi_golden_path",
        "status": "placeholder",
        "scenario": "Chest pain with STEMI-like deterioration and disposition to higher level care.",
        "phases": [
            "Patient registration / lookup",
            "Encounter open",
            "Triage normalization to CTAS + zone",
            "Vital signs persistence bridge",
            "Doctor assessment persistence bridge",
            "Handoff requested / completed persistence bridge",
            "Transfer or admission disposition",
            "Timeline export verification",
        ],
        "blocked_by": [
            "Deep user-flow integration should wait until storage/base and runtime service wiring are complete."
        ],
    }


def main() -> None:
    print(json.dumps(build_stemi_golden_path_plan(), indent=2))


if __name__ == "__main__":
    main()
