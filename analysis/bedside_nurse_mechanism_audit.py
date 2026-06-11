from __future__ import annotations

import argparse
import json
import re
from itertools import combinations
from pathlib import Path
from typing import Any


REINSERT_RE = re.compile(r"Re-inserted\s+(Patient\s+\d+)\s+into bedside_nurse_waiting")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _data_collection_path(sim_dir: Path) -> Path:
    nested = sim_dir / "reverie" / "data_collection.json"
    if nested.exists():
        return nested
    return sim_dir / "data_collection.json"


def _patient_records(data_collection: Any) -> dict[str, dict[str, Any]]:
    if isinstance(data_collection, list):
        return {str(row.get("name") or row.get("patient_id") or idx): row for idx, row in enumerate(data_collection, start=1) if isinstance(row, dict)}
    if not isinstance(data_collection, dict):
        return {}
    patients = data_collection.get("Patient", data_collection)
    if isinstance(patients, dict):
        return {str(k): v for k, v in patients.items() if isinstance(v, dict)}
    if isinstance(patients, list):
        return {str(row.get("name") or row.get("patient_id") or idx): row for idx, row in enumerate(patients, start=1) if isinstance(row, dict)}
    return {}


def parse_reinsert_counts_from_text(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for match in REINSERT_RE.finditer(text or ""):
        patient = match.group(1)
        counts[patient] = counts.get(patient, 0) + 1
    return counts


def _merge_counts(*maps: dict[str, int]) -> dict[str, int]:
    merged: dict[str, int] = {}
    for item in maps:
        for key, value in item.items():
            merged[key] = merged.get(key, 0) + int(value)
    return merged


def _bedside_exposed_patients(records: dict[str, dict[str, Any]]) -> set[str]:
    exposed = set()
    for patient_id, record in records.items():
        exposure = record.get("queue_exposure")
        payload = exposure.get("bedside_nurse") if isinstance(exposure, dict) else None
        if not isinstance(payload, dict):
            continue
        try:
            minutes = float(payload.get("exposure_minutes", 0) or 0)
        except (TypeError, ValueError):
            minutes = 0.0
        if minutes > 0:
            exposed.add(patient_id)
    return exposed


def _nurse_assignments(data_collection: Any) -> tuple[dict[str, list[str]], dict[str, int]]:
    nurse_sets: dict[str, list[str]] = {}
    unique_counts: dict[str, int] = {}
    if not isinstance(data_collection, dict):
        return nurse_sets, unique_counts
    for role_name, role_payload in data_collection.items():
        if "bedside" not in str(role_name).lower() or not isinstance(role_payload, dict):
            continue
        for nurse_name, nurse_payload in role_payload.items():
            if not isinstance(nurse_payload, dict):
                continue
            patients = []
            for entry in nurse_payload.get("Patients_Attended", []) or []:
                if isinstance(entry, (list, tuple)) and entry:
                    patients.append(str(entry[0]))
                elif isinstance(entry, dict) and entry.get("patient"):
                    patients.append(str(entry["patient"]))
            nurse_sets[str(nurse_name)] = patients
            unique_counts[str(nurse_name)] = len(set(patients))
    return nurse_sets, unique_counts


def _read_log_counts(status: dict[str, Any]) -> dict[str, int]:
    counts = parse_reinsert_counts_from_text(str(status.get("backend_stdout_tail") or ""))
    log_path = status.get("backend_log_path")
    if log_path:
        path = Path(str(log_path))
        if path.exists():
            counts = _merge_counts(counts, parse_reinsert_counts_from_text(path.read_text(encoding="utf-8", errors="replace")))
    return counts


def _audit_one(status_path: Path) -> dict[str, Any]:
    status = _load_json(status_path)
    scenario = status.get("scenario") if isinstance(status.get("scenario"), dict) else {}
    report_path = status_path.parent / "success_failure_report.json"
    report = _load_json(report_path) if report_path.exists() else {}
    sim_dir_raw = status.get("sim_dir") or status.get("resolved_sim_dir")
    data_collection = {}
    if sim_dir_raw:
        data_path = _data_collection_path(Path(str(sim_dir_raw)))
        if data_path.exists():
            data_collection = _load_json(data_path)
    records = _patient_records(data_collection)
    exposed = _bedside_exposed_patients(records)
    valid_arrival = {pid for pid, row in records.items() if row.get("ed_arrival_minute") not in (None, "") or row.get("ed_arrival_at") not in (None, "")}
    valid_ctas = {pid for pid, row in records.items() if row.get("CTAS_score") not in (None, "", 0, "0") or row.get("ctas_level") not in (None, "", 0, "0")}
    nurse_sets, nurse_unique_counts = _nurse_assignments(data_collection)
    served = {patient for patients in nurse_sets.values() for patient in patients}
    reinsert_from_records = {
        pid: int(row.get("bedside_reinsert_count", 0) or 0)
        for pid, row in records.items()
        if int(row.get("bedside_reinsert_count", 0) or 0) > 0
    }
    reinsert_counts = _merge_counts(reinsert_from_records, _read_log_counts(status))
    total = len(records)
    return {
        "scenario_id": scenario.get("scenario_id") or status.get("scenario_id") or status_path.parent.name,
        "bedside_nurse_count": int(scenario.get("bedside_nurse_count") or 0),
        "exposed_patient_set": sorted(exposed),
        "missing_arrival_count": max(0, total - len(valid_arrival)),
        "missing_ctas_count": max(0, total - len(valid_ctas)),
        "exposed_all": len(exposed),
        "exposed_valid_arrival": len(exposed & valid_arrival),
        "exposed_valid_ctas": len(exposed & valid_ctas),
        "queue_success_all": None if total <= 0 else 1.0 - (len(exposed) / float(total)),
        "queue_success_valid_arrival": None if not valid_arrival else 1.0 - (len(exposed & valid_arrival) / float(len(valid_arrival))),
        "queue_success_valid_ctas": None if not valid_ctas else 1.0 - (len(exposed & valid_ctas) / float(len(valid_ctas))),
        "report_queue_success_rate": report.get("queue_success_rate"),
        "reinsert_count_by_patient": reinsert_counts,
        "nurse_assignment_unique_patient_count": nurse_unique_counts,
        "nurse_assignment_patient_sets": {key: sorted(set(value)) for key, value in nurse_sets.items()},
        "patients_never_served_but_exposed": sorted(exposed - served),
        "patients_served_but_still_exposed": sorted(exposed & served),
    }


def build_audit(output_root: str | Path, analysis_dir: str | Path) -> dict[str, Any]:
    output_root = Path(output_root)
    analysis_dir = Path(analysis_dir)
    scenarios = [_audit_one(path) for path in sorted(output_root.glob("*/*/scenario_status.json"))]
    exposed_by_count: dict[str, list[str]] = {}
    for item in scenarios:
        if item["bedside_nurse_count"]:
            exposed_by_count[str(item["bedside_nurse_count"])] = item["exposed_patient_set"]

    pairwise = {}
    for left, right in combinations(sorted(exposed_by_count), 2):
        pairwise[f"{left}_vs_{right}"] = set(exposed_by_count[left]) == set(exposed_by_count[right])

    audit = {
        "scenario_count": len(scenarios),
        "exposed_patient_sets_by_bedside_count": exposed_by_count,
        "pairwise_exposed_set_same": pairwise,
        "scenarios": scenarios,
    }
    analysis_dir.mkdir(parents=True, exist_ok=True)
    json_path = analysis_dir / "bedside_nurse_mechanism_audit.json"
    md_path = analysis_dir / "bedside_nurse_mechanism_audit.md"
    json_path.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [
        "# Bedside Nurse Mechanism Audit",
        "",
        f"- scenario_count: {len(scenarios)}",
        f"- bedside_count_groups: {', '.join(sorted(exposed_by_count))}",
        "",
        "## Pairwise Exposed Set Same",
        "",
        "```json",
        json.dumps(pairwise, indent=2, ensure_ascii=False),
        "```",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit bedside nurse queue mechanism from ED bottleneck V1 outputs.")
    parser.add_argument("--output-root", default="cluster_outputs/ed_bottleneck_v1")
    parser.add_argument("--analysis-dir", default="analysis")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(json.dumps(build_audit(args.output_root, args.analysis_dir), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
