#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_INPUT_ROOT = Path("test_results/auto_capacity_large_tertiary_final")
DEFAULT_OUTPUT_ROOT = Path("test_results/auto_capacity_large_tertiary_pia_target_sensitivity")
DEFAULT_DOC_PATH = Path("docs/final/EDMAS_pia_target_sensitivity_pilot.md")

SOURCE_RUN_IDS = [
    "A_LOAD_1p00_seed42",
    "B_BURST_120_seed42",
    "C_CRIT_60_seed42",
]

RENAMED_RUN_IDS = {
    "A_LOAD_1p00_seed42": "A_LOAD_1p00_PIA_TARGET_SENS_RELAXED_V1_seed42",
    "B_BURST_120_seed42": "B_BURST_120_PIA_TARGET_SENS_RELAXED_V1_seed42",
    "C_CRIT_60_seed42": "C_CRIT_60_PIA_TARGET_SENS_RELAXED_V1_seed42",
}

PIA_TARGET_OFFICIAL_V0 = {
    "L1": 0.0,
    "L2": 15.0,
    "L3": 30.0,
    "L4": 60.0,
    "L5": 120.0,
}

PIA_TARGET_RELAXED_V1_ALL = {
    "L1": 30.0,
    "L2": 45.0,
    "L3": 60.0,
    "L4": 120.0,
    "L5": 240.0,
}

PIA_TARGET_RELAXED_V1_L1STRICT = {
    "L1": 0.0,
    "L2": 45.0,
    "L3": 60.0,
    "L4": 120.0,
    "L5": 240.0,
}


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _boolish(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def _pia_success(arrival_to_pia: float | None, ctas_level: str, targets: dict[str, float]) -> bool:
    if arrival_to_pia is None:
        return False
    target = targets.get(ctas_level)
    if target is None:
        return False
    return arrival_to_pia <= target


def _ratio(numer: int, denom: int) -> float | None:
    return None if denom == 0 else numer / float(denom)


def _collect_level_summary(rows: list[dict[str, Any]], key: str) -> dict[str, float | None]:
    levels = ["L1", "L2", "L3", "L4", "L5"]
    result: dict[str, float | None] = {}
    for level in levels:
        level_rows = [row for row in rows if row.get("ctas_level") == level]
        level_success = [row for row in level_rows if _boolish(row.get(key))]
        result[level] = _ratio(len(level_success), len(level_rows))
    return result


def _build_augmented_rows(source_rows: list[dict[str, Any]], renamed_run_id: str) -> list[dict[str, Any]]:
    augmented: list[dict[str, Any]] = []
    for row in source_rows:
        new_row = dict(row)
        new_row["source_run_id"] = row.get("run_id") or ""
        new_row["run_id"] = renamed_run_id
        ctas = str(row.get("ctas_level") or "")
        arrival_to_pia = _num(row.get("arrival_to_pia_min"))
        first_contact = _num(row.get("first_doctor_contact_minute"))
        official_target = PIA_TARGET_OFFICIAL_V0.get(ctas)
        relaxed_all_target = PIA_TARGET_RELAXED_V1_ALL.get(ctas)
        relaxed_l1strict_target = PIA_TARGET_RELAXED_V1_L1STRICT.get(ctas)
        official_success = _pia_success(arrival_to_pia, ctas, PIA_TARGET_OFFICIAL_V0)
        relaxed_all_success = _pia_success(arrival_to_pia, ctas, PIA_TARGET_RELAXED_V1_ALL)
        relaxed_l1strict_success = _pia_success(arrival_to_pia, ctas, PIA_TARGET_RELAXED_V1_L1STRICT)
        unrecoverable_no_contact = first_contact is None

        new_row["official_pia_target_min"] = official_target if official_target is not None else ""
        new_row["relaxed_all_pia_target_min"] = relaxed_all_target if relaxed_all_target is not None else ""
        new_row["relaxed_l1strict_pia_target_min"] = relaxed_l1strict_target if relaxed_l1strict_target is not None else ""
        new_row["official_pia_sdr_success"] = official_success
        new_row["relaxed_all_pia_sdr_success"] = relaxed_all_success
        new_row["relaxed_l1strict_pia_sdr_success"] = relaxed_l1strict_success
        new_row["rescued_by_relaxed_all"] = (not official_success) and relaxed_all_success
        new_row["rescued_by_relaxed_l1strict"] = (not official_success) and relaxed_l1strict_success
        new_row["unrecoverable_no_contact"] = unrecoverable_no_contact
        augmented.append(new_row)
    return augmented


def _summarize_run(source_run_id: str, renamed_run_id: str, rows: list[dict[str, Any]], source_summary: dict[str, Any]) -> dict[str, Any]:
    eligible = [row for row in rows if str(row.get("ctas_level") or "").strip()]
    official_success = [row for row in eligible if _boolish(row.get("official_pia_sdr_success"))]
    relaxed_all_success = [row for row in eligible if _boolish(row.get("relaxed_all_pia_sdr_success"))]
    relaxed_l1strict_success = [row for row in eligible if _boolish(row.get("relaxed_l1strict_pia_sdr_success"))]
    critical = [row for row in eligible if row.get("ctas_level") in {"L1", "L2"}]
    official_critical_success = [row for row in critical if _boolish(row.get("official_pia_sdr_success"))]
    relaxed_all_critical_success = [row for row in critical if _boolish(row.get("relaxed_all_pia_sdr_success"))]
    relaxed_l1strict_critical_success = [row for row in critical if _boolish(row.get("relaxed_l1strict_pia_sdr_success"))]

    official_by_level = _collect_level_summary(eligible, "official_pia_sdr_success")
    relaxed_all_by_level = _collect_level_summary(eligible, "relaxed_all_pia_sdr_success")
    relaxed_l1strict_by_level = _collect_level_summary(eligible, "relaxed_l1strict_pia_sdr_success")

    rescued_by_relaxed_all = [row for row in eligible if _boolish(row.get("rescued_by_relaxed_all"))]
    rescued_by_relaxed_l1strict = [row for row in eligible if _boolish(row.get("rescued_by_relaxed_l1strict"))]
    unrecoverable_no_contact = [row for row in eligible if _boolish(row.get("unrecoverable_no_contact"))]

    return {
        "source_run_id": source_run_id,
        "run_id": renamed_run_id,
        "scenario_module": source_summary.get("scenario_module"),
        "total_arrivals": source_summary.get("total_arrivals"),
        "eligible_patient_count": len(eligible),
        "critical_patient_count": len(critical),
        "official_target_profile": "PIA_TARGET_OFFICIAL_V0_0_15_30_60_120",
        "relaxed_target_profile_all": "PIA_TARGET_RELAXED_V1_ALL_30_45_60_120_240",
        "relaxed_target_profile_l1strict": "PIA_TARGET_RELAXED_V1_L1STRICT_0_45_60_120_240",
        "official_overall_sdr": _ratio(len(official_success), len(eligible)),
        "relaxed_all_overall_sdr": _ratio(len(relaxed_all_success), len(eligible)),
        "relaxed_l1strict_overall_sdr": _ratio(len(relaxed_l1strict_success), len(eligible)),
        "official_critical_sdr": _ratio(len(official_critical_success), len(critical)),
        "relaxed_all_critical_sdr": _ratio(len(relaxed_all_critical_success), len(critical)),
        "relaxed_l1strict_critical_sdr": _ratio(len(relaxed_l1strict_critical_success), len(critical)),
        "official_l1_sdr": official_by_level.get("L1"),
        "relaxed_all_l1_sdr": relaxed_all_by_level.get("L1"),
        "relaxed_l1strict_l1_sdr": relaxed_l1strict_by_level.get("L1"),
        "official_l2_sdr": official_by_level.get("L2"),
        "relaxed_all_l2_sdr": relaxed_all_by_level.get("L2"),
        "relaxed_l1strict_l2_sdr": relaxed_l1strict_by_level.get("L2"),
        "rescued_by_relaxed_all_count": len(rescued_by_relaxed_all),
        "rescued_by_relaxed_l1strict_count": len(rescued_by_relaxed_l1strict),
        "unrecoverable_no_contact_count": len(unrecoverable_no_contact),
        "official_to_relaxed_all_overall_delta": (_ratio(len(relaxed_all_success), len(eligible)) or 0.0) - (_ratio(len(official_success), len(eligible)) or 0.0),
        "official_to_relaxed_l1strict_overall_delta": (_ratio(len(relaxed_l1strict_success), len(eligible)) or 0.0) - (_ratio(len(official_success), len(eligible)) or 0.0),
        "official_to_relaxed_all_critical_delta": (_ratio(len(relaxed_all_critical_success), len(critical)) or 0.0) - (_ratio(len(official_critical_success), len(critical)) or 0.0),
        "official_to_relaxed_l1strict_critical_delta": (_ratio(len(relaxed_l1strict_critical_success), len(critical)) or 0.0) - (_ratio(len(official_critical_success), len(critical)) or 0.0),
    }


def _summary_row(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": summary["run_id"],
        "source_run_id": summary["source_run_id"],
        "scenario_module": summary["scenario_module"],
        "eligible_patient_count": summary["eligible_patient_count"],
        "critical_patient_count": summary["critical_patient_count"],
        "official_overall_sdr": summary["official_overall_sdr"],
        "relaxed_all_overall_sdr": summary["relaxed_all_overall_sdr"],
        "relaxed_l1strict_overall_sdr": summary["relaxed_l1strict_overall_sdr"],
        "official_critical_sdr": summary["official_critical_sdr"],
        "relaxed_all_critical_sdr": summary["relaxed_all_critical_sdr"],
        "relaxed_l1strict_critical_sdr": summary["relaxed_l1strict_critical_sdr"],
        "official_l1_sdr": summary["official_l1_sdr"],
        "relaxed_all_l1_sdr": summary["relaxed_all_l1_sdr"],
        "relaxed_l1strict_l1_sdr": summary["relaxed_l1strict_l1_sdr"],
        "official_l2_sdr": summary["official_l2_sdr"],
        "relaxed_all_l2_sdr": summary["relaxed_all_l2_sdr"],
        "relaxed_l1strict_l2_sdr": summary["relaxed_l1strict_l2_sdr"],
        "rescued_by_relaxed_all_count": summary["rescued_by_relaxed_all_count"],
        "rescued_by_relaxed_l1strict_count": summary["rescued_by_relaxed_l1strict_count"],
        "unrecoverable_no_contact_count": summary["unrecoverable_no_contact_count"],
        "official_to_relaxed_all_overall_delta": summary["official_to_relaxed_all_overall_delta"],
        "official_to_relaxed_l1strict_overall_delta": summary["official_to_relaxed_l1strict_overall_delta"],
        "official_to_relaxed_all_critical_delta": summary["official_to_relaxed_all_critical_delta"],
        "official_to_relaxed_l1strict_critical_delta": summary["official_to_relaxed_l1strict_critical_delta"],
    }


def _write_doc(path: Path, summaries: list[dict[str, Any]]) -> None:
    def fmt(value: float | None) -> str:
        return "null" if value is None else f"{value:.4f}"

    lines: list[str] = []
    lines.append("# EDMAS PIA Target Sensitivity Pilot")
    lines.append("")
    lines.append("## Scope")
    lines.append("")
    lines.append("This is an offline SDR recomputation using existing 1440-step patient-level outputs.")
    lines.append("")
    lines.append("- No simulation rerun")
    lines.append("- No agent behavior change")
    lines.append("- No modification to original `patient_level_results.csv`")
    lines.append("")
    lines.append("## Target Profiles")
    lines.append("")
    lines.append("- `PIA_TARGET_OFFICIAL_V0 = {L1:0, L2:15, L3:30, L4:60, L5:120}`")
    lines.append("- `PIA_TARGET_RELAXED_V1_ALL = {L1:30, L2:45, L3:60, L4:120, L5:240}`")
    lines.append("- `PIA_TARGET_RELAXED_V1_L1STRICT = {L1:0, L2:45, L3:60, L4:120, L5:240}`")
    lines.append("")
    lines.append("## Pilot Summary")
    lines.append("")
    lines.append("| Run | Official Overall SDR | Relaxed-All Overall SDR | Relaxed-L1Strict Overall SDR | Official Critical SDR | Relaxed-All Critical SDR | Relaxed-L1Strict Critical SDR | rescued_by_relaxed_all_count | rescued_by_relaxed_l1strict_count | unrecoverable_no_contact_count |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for summary in summaries:
        lines.append(
            f"| {summary['run_id']} | "
            f"{fmt(summary['official_overall_sdr'])} | "
            f"{fmt(summary['relaxed_all_overall_sdr'])} | "
            f"{fmt(summary['relaxed_l1strict_overall_sdr'])} | "
            f"{fmt(summary['official_critical_sdr'])} | "
            f"{fmt(summary['relaxed_all_critical_sdr'])} | "
            f"{fmt(summary['relaxed_l1strict_critical_sdr'])} | "
            f"{summary['rescued_by_relaxed_all_count']} | "
            f"{summary['rescued_by_relaxed_l1strict_count']} | "
            f"{summary['unrecoverable_no_contact_count']} |"
        )
    lines.append("")
    lines.append("## Direct Reading")
    lines.append("")
    for summary in summaries:
        lines.append(f"### {summary['run_id']}")
        lines.append("")
        overall_all = summary["official_to_relaxed_all_overall_delta"]
        critical_all = summary["official_to_relaxed_all_critical_delta"]
        l2_gain_all = (summary["relaxed_all_l2_sdr"] or 0.0) - (summary["official_l2_sdr"] or 0.0)
        l1_gain_all = (summary["relaxed_all_l1_sdr"] or 0.0) - (summary["official_l1_sdr"] or 0.0)
        lines.append(f"- Overall SDR delta under relaxed-all: `{overall_all:.4f}`")
        lines.append(f"- Critical SDR delta under relaxed-all: `{critical_all:.4f}`")
        lines.append(f"- L1 SDR delta under relaxed-all: `{l1_gain_all:.4f}`")
        lines.append(f"- L2 SDR delta under relaxed-all: `{l2_gain_all:.4f}`")
        lines.append(f"- rescued_by_relaxed_all_count = `{summary['rescued_by_relaxed_all_count']}`")
        lines.append(f"- rescued_by_relaxed_l1strict_count = `{summary['rescued_by_relaxed_l1strict_count']}`")
        lines.append(f"- unrecoverable_no_contact_count = `{summary['unrecoverable_no_contact_count']}`")
        lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append("If relaxed targets improve SDR materially while `unrecoverable_no_contact_count` remains high, the low official SDR is a mixture of:")
    lines.append("")
    lines.append("1. truly missing doctor contact")
    lines.append("2. doctor contact happening, but later than strict official CTAS PIA targets")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline PIA target sensitivity recomputation.")
    parser.add_argument("--input-root", default=str(DEFAULT_INPUT_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--doc-path", default=str(DEFAULT_DOC_PATH))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_root = Path(args.input_root)
    output_root = Path(args.output_root)
    doc_path = Path(args.doc_path)

    summaries: list[dict[str, Any]] = []

    for source_run_id in SOURCE_RUN_IDS:
        renamed_run_id = RENAMED_RUN_IDS[source_run_id]
        run_dir = input_root / source_run_id
        source_rows = _read_csv(run_dir / "patient_level_results.csv")
        source_summary = _read_json(run_dir / "run_summary.json")
        augmented_rows = _build_augmented_rows(source_rows, renamed_run_id)
        summary = _summarize_run(source_run_id, renamed_run_id, augmented_rows, source_summary)
        summaries.append(summary)

        target_dir = output_root / renamed_run_id
        fieldnames = list(augmented_rows[0].keys()) if augmented_rows else []
        _write_csv(target_dir / "target_sensitivity_patient_level.csv", augmented_rows, fieldnames)
        _write_json(target_dir / "target_sensitivity_run_summary.json", summary)

    aggregate_dir = output_root / "aggregate"
    summary_rows = [_summary_row(summary) for summary in summaries]
    summary_fields = list(summary_rows[0].keys()) if summary_rows else []
    _write_csv(aggregate_dir / "pia_target_sensitivity_summary.csv", summary_rows, summary_fields)
    _write_json(
        aggregate_dir / "pia_target_sensitivity_summary.json",
        {
            "execution_identity": "LOCAL_CODEX",
            "simulation_rerun_used": False,
            "official_target_profile": "PIA_TARGET_OFFICIAL_V0_0_15_30_60_120",
            "relaxed_target_profile_all": "PIA_TARGET_RELAXED_V1_ALL_30_45_60_120_240",
            "relaxed_target_profile_l1strict": "PIA_TARGET_RELAXED_V1_L1STRICT_0_45_60_120_240",
            "runs": summaries,
        },
    )
    _write_doc(doc_path, summaries)
    print(
        json.dumps(
            {
                "execution_identity": "LOCAL_CODEX",
                "pia_target_sensitivity_completed": True,
                "simulation_rerun_used": False,
                "output_root": str(output_root),
                "doc_path": str(doc_path),
                "run_count": len(summaries),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
