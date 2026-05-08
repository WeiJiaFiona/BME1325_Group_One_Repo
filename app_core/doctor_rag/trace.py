from __future__ import annotations

from typing import Any, Dict, List


def append_doctor_kb_trace(assess: Dict[str, Any], refs: List[Dict[str, Any]]) -> None:
    trace = list((assess.get("planner_trace", []) or []))
    if not trace:
        assess["planner_trace"] = trace
        return
    # Attach to the latest trace entry for observability.
    last = dict(trace[-1])
    existing = list(last.get("evidence_refs", []) or [])
    existing.extend(refs)
    last["evidence_refs"] = existing
    trace[-1] = last
    assess["planner_trace"] = trace

