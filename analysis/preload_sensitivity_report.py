from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def dominant_failure_reason(failure_reason_counts: dict | None) -> str | None:
    if not isinstance(failure_reason_counts, dict) or not failure_reason_counts:
        return None
    non_zero = {k: int(v or 0) for k, v in failure_reason_counts.items() if int(v or 0) > 0}
    if not non_zero:
        return None
    return max(sorted(non_zero), key=lambda key: non_zero[key])


def build_preload_sensitivity_report(
    results: list[dict],
    *,
    mode: str,
    source_matrix: str,
    known_limitations: list[str] | None = None,
) -> dict:
    success_count = sum(1 for row in results if row.get("run_status") == "success")
    blocked_count = sum(1 for row in results if row.get("run_status") == "blocked")
    failed_count = sum(1 for row in results if row.get("run_status") == "failed")
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "mode": mode,
        "source_matrix": source_matrix,
        "scenario_count": len(results),
        "success_count": success_count,
        "blocked_count": blocked_count,
        "failed_count": failed_count,
        "known_limitations": list(known_limitations or []),
        "results": results,
    }


def write_preload_sensitivity_report(
    results: list[dict],
    *,
    mode: str,
    source_matrix: str,
    output_path: str | Path,
    known_limitations: list[str] | None = None,
) -> dict:
    report = build_preload_sensitivity_report(
        results,
        mode=mode,
        source_matrix=source_matrix,
        known_limitations=known_limitations,
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report
