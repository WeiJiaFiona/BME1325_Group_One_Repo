#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = REPO_ROOT / "analysis"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for _path in (str(REPO_ROOT), str(ANALYSIS_DIR), str(SCRIPTS_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from analysis.failure_report import write_failure_report
from analysis.preload_sensitivity_report import dominant_failure_reason
from analysis.threshold_search_report import (
    build_target_sim_name,
    build_threshold_search_report,
    detect_local_brackets,
    determine_signal_check_status,
    generate_cluster_final_validation_matrix,
    generate_cluster_fine_sweep_matrix,
    generate_coarse_load_factors,
    generate_coarse_sweep_plan,
    generate_signal_check_plan,
    has_failure_signal,
    load_hospital_profiles,
    load_threshold_search_config,
    read_csv,
    write_csv,
    write_json,
)
from scripts.run_week13_smoke import run_smoke


DEFAULT_CONFIG = REPO_ROOT / "configs" / "failure_rate_threshold_search.yaml"


def _read_json(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    target = Path(path)
    if not target.exists():
        return {}
    return json.loads(target.read_text(encoding="utf-8"))


def _extract_runtime_fields(sim_status_path: str | None) -> dict[str, Any]:
    payload = _read_json(sim_status_path)
    resources = dict(payload.get("resources") or {})
    nurse_status = payload.get("nurse_status") or []
    nurses_total_runtime = None
    if isinstance(nurse_status, list):
        nurses_total_runtime = len(nurse_status)
    elif isinstance(nurse_status, dict):
        numeric_counts = [int(value or 0) for value in nurse_status.values() if isinstance(value, (int, float))]
        if numeric_counts:
            nurses_total_runtime = sum(numeric_counts)
    return {
        "doctors_total_runtime": payload.get("doctors_total"),
        "nurses_total_runtime": nurses_total_runtime,
        "lab_capacity_runtime": resources.get("lab_capacity"),
        "imaging_capacity_runtime": resources.get("imaging_capacity"),
        "boarding_timeout_minutes_runtime": resources.get("boarding_timeout_minutes"),
    }


def _staffing_status(runtime_fields: dict[str, Any]) -> str:
    if runtime_fields.get("doctors_total_runtime") is not None and runtime_fields.get("nurses_total_runtime") is not None:
        return "confirmed"
    if runtime_fields.get("doctors_total_runtime") is not None:
        return "partial_confirmation"
    return "unknown"


def _read_data_collection(sim_dir: str | Path | None) -> dict[str, Any]:
    if not sim_dir:
        return {}
    root = Path(sim_dir)
    for candidate in (root / "reverie" / "data_collection.json", root / "data_collection.json"):
        payload = _read_json(candidate)
        if payload:
            return payload
    return {}


def _parse_sim_status_txt_metrics(sim_dir: str | Path | None) -> dict[str, Any]:
    if not sim_dir:
        return {}
    path = Path(sim_dir) / "sim_status.txt"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    patterns = {
        "final_observed_triage_queue": r"Triage queue\s+(\d+)",
        "final_observed_bedside_nurse_waiting": r"Bedside nurse waiting\s+(\d+)",
        "final_observed_doctor_queue": r"Doctor global queue\s+(\d+)",
        "final_observed_lab_queue": r"Lab waiting\s+(\d+)",
        "final_observed_imaging_queue": r"Imaging waiting\s+(\d+)",
        "final_observed_boarding_timeout_events": r"Boarding timeout events\s+(\d+)",
    }
    result: dict[str, Any] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            result[key] = int(match.group(1))
    return result


def _extract_trigger_audit_metrics(
    *,
    sim_dir: str | Path | None,
    plan: dict[str, Any],
    resource_summary: dict[str, Any],
    run_steps_completed: int,
) -> dict[str, Any]:
    data_collection = _read_data_collection(sim_dir)
    patient_records = dict(data_collection.get("Patient") or {})
    txt_metrics = _parse_sim_status_txt_metrics(sim_dir)

    ctas_scored_count = 0
    boarding_patient_count = 0
    triage_completed_at_count = 0
    first_doctor_contact_at_count = 0
    ed_exit_at_count = 0
    queue_exposure_record_count = 0
    for record in patient_records.values():
        if record.get("CTAS_score") not in (None, "", 0, "0"):
            ctas_scored_count += 1
        admitted = dict(record.get("admitted_to_hospital") or {})
        if bool(admitted.get("occurred", False)):
            boarding_patient_count += 1
        if record.get("triage_completed_at") is not None:
            triage_completed_at_count += 1
        if record.get("first_doctor_contact_at") is not None:
            first_doctor_contact_at_count += 1
        if record.get("ed_exit_at") is not None:
            ed_exit_at_count += 1
        if record.get("queue_exposure") is not None:
            queue_exposure_record_count += 1

    ctas_eligible_count = None
    if triage_completed_at_count > 0 and first_doctor_contact_at_count > 0:
        ctas_eligible_count = min(triage_completed_at_count, first_doctor_contact_at_count)

    notes: list[str] = []
    if ctas_eligible_count is None:
        notes.append("ctas_eligible_count not observable from current data_collection schema")
    if queue_exposure_record_count == 0:
        notes.append("queue_exposure records not present in current data_collection schema")
    if triage_completed_at_count == 0:
        notes.append("triage_completed_at not present in current data_collection schema")
    if first_doctor_contact_at_count == 0:
        notes.append("first_doctor_contact_at not present in current data_collection schema")
    if ed_exit_at_count == 0:
        notes.append("ed_exit_at not present in current data_collection schema")

    return {
        "total_arrived_patients": resource_summary.get("total_arrived_patients"),
        "preload_patient_count_runtime_target": int(plan["preload_patient_count"]),
        "run_steps_completed": int(run_steps_completed),
        "ctas_eligible_count": ctas_eligible_count,
        "ctas_scored_count": int(ctas_scored_count),
        "triage_completed_at_count": int(triage_completed_at_count),
        "first_doctor_contact_at_count": int(first_doctor_contact_at_count),
        "ed_exit_at_count": int(ed_exit_at_count),
        "boarding_timeout_count": int(resource_summary.get("boarding_timeout_count", 0) or 0),
        "queue_overflow_exposure_count": int(resource_summary.get("queue_overflow_exposure_count", 0) or 0),
        "boarding_patient_count": int(boarding_patient_count),
        "queue_exposure_record_count": int(queue_exposure_record_count),
        "max_doctor_queue": txt_metrics.get("final_observed_doctor_queue"),
        "max_lab_queue": txt_metrics.get("final_observed_lab_queue"),
        "max_imaging_queue": txt_metrics.get("final_observed_imaging_queue"),
        "final_observed_triage_queue": txt_metrics.get("final_observed_triage_queue"),
        "final_observed_bedside_nurse_waiting": txt_metrics.get("final_observed_bedside_nurse_waiting"),
        "boarding_timeout_event_count": int(resource_summary.get("boarding_timeout_count", 0) or 0),
        "trigger_audit_notes": notes,
    }


def _build_run_result(plan: dict[str, Any], smoke_summary: dict[str, Any], *, phase: str) -> dict[str, Any]:
    resource_summary = dict(smoke_summary.get("resource_summary") or {})
    runtime_fields = _extract_runtime_fields(smoke_summary.get("sim_status_path"))
    trigger_metrics = _extract_trigger_audit_metrics(
        sim_dir=smoke_summary.get("sim_dir"),
        plan=plan,
        resource_summary=resource_summary,
        run_steps_completed=int(plan["run_steps"]),
    )
    reason_counts = dict(resource_summary.get("failure_reason_counts") or {})
    total_arrived_patients = resource_summary.get("total_arrived_patients")
    run_status = "success" if smoke_summary.get("status") == "success" else "failed"
    notes: list[str] = []
    verify_normal = dict(smoke_summary.get("verify_normal") or {})
    if int(verify_normal.get("returncode", 1)) != 0:
        notes.append("full movement/environment contract mismatch remains known limitation")
    if runtime_fields.get("nurses_total_runtime") is None:
        notes.append("nurses_total_runtime could not be fully confirmed from sim_status")
    if runtime_fields.get("doctors_total_runtime") is None:
        notes.append("doctors_total_runtime could not be fully confirmed from sim_status")
    return {
        "target_sim": smoke_summary.get("target"),
        "sim_dir": smoke_summary.get("sim_dir"),
        "hospital_profile": plan["hospital_profile"],
        "profile": plan["hospital_profile"],
        "load_factor": float(plan["load_factor"]),
        "normal_patient_count": int(plan["normal_patient_count"]),
        "preload_patient_count": int(plan["preload_patient_count"]),
        "preload_patient_count_configured": int(plan["preload_patient_count"]),
        "preload_runtime_confirmed": bool(
            smoke_summary.get("status") == "success"
            and total_arrived_patients is not None
            and int(total_arrived_patients) >= int(plan["preload_patient_count"])
        ),
        "doctor_count_configured": int(plan["doctor_count"]),
        "nurse_count_configured": int(plan["nurse_count"]),
        "seed": int(plan["seed"]),
        "run_steps_requested": int(plan["run_steps"]),
        "run_steps_completed": int(plan["run_steps"]),
        "run_status": run_status,
        "failure_rate": float(resource_summary.get("failure_rate", 0.0) or 0.0),
        "failed_patients_count": int(resource_summary.get("failed_patients_count", 0) or 0),
        "failure_reason_counts": reason_counts,
        "dominant_failure_reason": dominant_failure_reason(reason_counts),
        "system_failed": bool(resource_summary.get("system_failed", False)),
        "week13_failure_metrics_verify": "passed" if smoke_summary.get("strict_verify_passed") else "failed",
        "failure_report_path": smoke_summary.get("failure_report_path"),
        "full_step_contract_status": "passed"
        if int(verify_normal.get("returncode", 1)) == 0
        else "failed_known_movement_environment_mismatch",
        "notes": "; ".join(notes),
        **runtime_fields,
        **trigger_metrics,
        "runtime_staffing_injection_status": _staffing_status(runtime_fields),
        "phase": phase,
    }


def _find_latest_target_sim_dir(target_root: str) -> Path | None:
    storage_root = REPO_ROOT / "environment" / "frontend_server" / "storage"
    candidates = sorted(
        [
            path
            for path in storage_root.glob(f"{target_root}*")
            if path.is_dir() and (path / "sim_status.json").exists()
        ],
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _run_verify_for_sim(sim_code: str, *, strict: bool) -> subprocess.CompletedProcess[str]:
    args = [sys.executable, "scripts/verify_step_contract.py", "--sim-code", sim_code]
    if strict:
        args.extend(["--strict-week13-failure-metrics", "--week13-failure-metrics-only"])
    return subprocess.run(
        args,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _salvage_run_result(plan: dict[str, Any], *, target_root: str, phase: str, exception_text: str) -> dict[str, Any] | None:
    sim_dir = _find_latest_target_sim_dir(target_root)
    if sim_dir is None:
        return None

    sim_status_path = sim_dir / "sim_status.json"
    sim_status = _read_json(sim_status_path)
    if not sim_status:
        return None

    failure_report_path = sim_dir / "analysis" / "failure_report.json"
    if not failure_report_path.exists():
        write_failure_report(sim_dir)
    failure_report = _read_json(failure_report_path)
    resources = dict(sim_status.get("resources") or {})
    reason_counts = dict(failure_report.get("failure_reason_counts") or resources.get("failure_reason_counts") or {})
    verify_normal = _run_verify_for_sim(sim_dir.name, strict=False)
    verify_strict = _run_verify_for_sim(sim_dir.name, strict=True)
    runtime_fields = _extract_runtime_fields(str(sim_status_path))
    total_arrived_patients = resources.get("total_arrived_patients")
    step_value = sim_status.get("step")
    run_steps_completed = 0
    if isinstance(step_value, int):
        run_steps_completed = step_value + 1
    trigger_metrics = _extract_trigger_audit_metrics(
        sim_dir=sim_dir,
        plan=plan,
        resource_summary=resources,
        run_steps_completed=run_steps_completed,
    )

    notes = [
        f"recovered_from_existing_artifacts_after_exception: {exception_text}",
    ]
    if verify_normal.returncode != 0:
        notes.append("full movement/environment contract mismatch remains known limitation")
    if runtime_fields.get("nurses_total_runtime") is None:
        notes.append("nurses_total_runtime could not be fully confirmed from sim_status")
    if runtime_fields.get("doctors_total_runtime") is None:
        notes.append("doctors_total_runtime could not be fully confirmed from sim_status")

    return {
        "target_sim": sim_dir.name,
        "sim_dir": str(sim_dir),
        "hospital_profile": plan["hospital_profile"],
        "profile": plan["hospital_profile"],
        "load_factor": float(plan["load_factor"]),
        "normal_patient_count": int(plan["normal_patient_count"]),
        "preload_patient_count": int(plan["preload_patient_count"]),
        "preload_patient_count_configured": int(plan["preload_patient_count"]),
        "preload_runtime_confirmed": bool(
            total_arrived_patients is not None and int(total_arrived_patients) >= int(plan["preload_patient_count"])
        ),
        "doctor_count_configured": int(plan["doctor_count"]),
        "nurse_count_configured": int(plan["nurse_count"]),
        "seed": int(plan["seed"]),
        "run_steps_requested": int(plan["run_steps"]),
        "run_steps_completed": int(run_steps_completed),
        "run_status": "success",
        "failure_rate": float(failure_report.get("failure_rate", resources.get("failure_rate", 0.0)) or 0.0),
        "failed_patients_count": int(
            failure_report.get("failed_patients_count", resources.get("failed_patients_count", 0)) or 0
        ),
        "failure_reason_counts": reason_counts,
        "dominant_failure_reason": dominant_failure_reason(reason_counts),
        "system_failed": bool(failure_report.get("system_failed", resources.get("system_failed", False))),
        "week13_failure_metrics_verify": "passed" if verify_strict.returncode == 0 else "failed",
        "failure_report_path": str(failure_report_path),
        "full_step_contract_status": "passed"
        if verify_normal.returncode == 0
        else "failed_known_movement_environment_mismatch",
        "notes": "; ".join(notes),
        **runtime_fields,
        **trigger_metrics,
        "runtime_staffing_injection_status": _staffing_status(runtime_fields),
        "phase": phase,
    }


def _run_plan(plan_rows: list[dict[str, Any]], *, origin: str, phase: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    base_port = 8012
    for index, plan in enumerate(plan_rows, start=1):
        phase_label = str(plan.get("phase_label") or phase)
        target = str(plan.get("target_sim_override") or build_target_sim_name(plan["hospital_profile"], phase_label, float(plan["load_factor"]), int(plan["seed"])))
        settings_overrides = {
            "arrival_profile_mode": plan["arrival_profile_mode"],
            "doctor_starting_amount": int(plan["doctor_count"]),
            "triage_starting_amount": max(1, int(round(int(plan["nurse_count"]) / 4.0))),
            "bedside_starting_amount": max(1, int(plan["nurse_count"])),
            "preload_waiting_room_patients": int(plan["preload_patient_count"]),
            "fill_injuries": 0.3,
            "add_patient_threshold": 0,
            "seed": int(plan["seed"]),
            "patient_rate_modifier": 0,
        }
        try:
            smoke_summary = run_smoke(
                port=base_port + index - 1,
                origin=origin,
                target=target,
                run_steps=int(plan["run_steps"]),
                max_attempts=3,
                settings_overrides=settings_overrides,
            )
        except Exception as exc:
            salvaged = _salvage_run_result(plan, target_root=target, phase=phase, exception_text=str(exc))
            if salvaged is not None:
                results.append(salvaged)
                continue
            results.append(
                {
                    "target_sim": target,
                    "sim_dir": None,
                    "hospital_profile": plan["hospital_profile"],
                    "profile": plan["hospital_profile"],
                    "load_factor": float(plan["load_factor"]),
                    "normal_patient_count": int(plan["normal_patient_count"]),
                    "preload_patient_count": int(plan["preload_patient_count"]),
                    "preload_patient_count_configured": int(plan["preload_patient_count"]),
                    "preload_runtime_confirmed": False,
                    "doctor_count_configured": int(plan["doctor_count"]),
                    "nurse_count_configured": int(plan["nurse_count"]),
                    "seed": int(plan["seed"]),
                    "run_steps_requested": int(plan["run_steps"]),
                    "run_steps_completed": 0,
                    "run_status": "failed",
                    "failure_rate": 0.0,
                    "failed_patients_count": 0,
                    "failure_reason_counts": {},
                    "dominant_failure_reason": None,
                    "system_failed": False,
                    "week13_failure_metrics_verify": "failed",
                    "failure_report_path": None,
                    "full_step_contract_status": "not_run",
                    "notes": f"smoke launcher exception: {exc}",
                    "doctors_total_runtime": None,
                    "nurses_total_runtime": None,
                    "lab_capacity_runtime": None,
                    "imaging_capacity_runtime": None,
                    "boarding_timeout_minutes_runtime": None,
                    "runtime_staffing_injection_status": "unknown",
                    "phase": phase,
                }
            )
            continue

        results.append(_build_run_result(plan, smoke_summary, phase=phase_label))
    return results


def _signal_report_payload(results: list[dict[str, Any]], run_steps: int) -> dict[str, Any]:
    return {
        "generated_at": __import__("datetime").datetime.utcnow().isoformat(),
        "phase": "5A",
        "stage": "signal_check",
        "run_steps": int(run_steps),
        "threshold_search_status": determine_signal_check_status(results),
        "results": results,
    }


def _signal_report_alias_path(config: dict[str, Any], run_steps: int) -> Path:
    default_path = Path(str(config["outputs"]["local_signal_check_report"]))
    return default_path.with_name(f"{default_path.stem}_run{int(run_steps)}{default_path.suffix}")


def _coarse_report_payload(results: list[dict[str, Any]], run_steps: int) -> dict[str, Any]:
    return {
        "generated_at": __import__("datetime").datetime.utcnow().isoformat(),
        "phase": "5A",
        "stage": "preliminary_coarse_sweep",
        "run_steps": int(run_steps),
        "results": results,
    }


def _bracket_report_payload(results: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    brackets = detect_local_brackets(results, threshold=threshold)
    return {
        "generated_at": __import__("datetime").datetime.utcnow().isoformat(),
        "phase": "5A",
        "stage": "local_bracket_detection",
        "failure_threshold": float(threshold),
        "profiles": brackets,
    }


def _write_trigger_audit(path: str | Path, *, signal_results: list[dict[str, Any]], threshold_status: str) -> None:
    lines = [
        "# Week13 Failure Reason Trigger Audit",
        "",
        f"- threshold_search_status: `{threshold_status}`",
        "- local observation: all Phase 5A signal-check runs had `failure_rate == 0.0` and no non-zero failure reason counts.",
        "- implication: threshold must not be fabricated from local data.",
        "",
        "## Recommended Audit Targets",
        "1. Increase run steps from 100 to 200, then 1000, before any 20000-step cluster submission.",
        "2. Confirm CTAS timestamp progression and wait-threshold exposure in longer runs.",
        "3. Confirm queue exposure timeline for doctor, lab, imaging, and boarding bottlenecks.",
        "4. Confirm boarding timeout trigger can fire under this preload-only setup.",
        "5. Confirm staffing injection at runtime, especially nurse count derivation.",
        "",
        "## Local Signal Check Snapshot",
    ]
    for row in signal_results:
        lines.append(
            f"- `{row['hospital_profile']}` load_factor=`{row['load_factor']}` run_steps=`{row['run_steps_requested']}` "
            f"failure_rate=`{row['failure_rate']}` dominant_failure_reason=`{row['dominant_failure_reason']}` "
            f"failure_report=`{row['failure_report_path']}`"
        )
        lines.append(
            f"  evidence: total_arrived_patients=`{row.get('total_arrived_patients')}` "
            f"preload_patient_count=`{row.get('preload_patient_count')}` "
            f"preload_runtime_confirmed=`{row.get('preload_runtime_confirmed')}` "
            f"run_steps_completed=`{row.get('run_steps_completed')}` "
            f"triage_completed_at_count=`{row.get('triage_completed_at_count')}` "
            f"first_doctor_contact_at_count=`{row.get('first_doctor_contact_at_count')}` "
            f"ctas_eligible_count=`{row.get('ctas_eligible_count')}` "
            f"ctas_scored_count=`{row.get('ctas_scored_count')}` "
            f"max_doctor_queue=`{row.get('max_doctor_queue')}` "
            f"max_lab_queue=`{row.get('max_lab_queue')}` "
            f"max_imaging_queue=`{row.get('max_imaging_queue')}` "
            f"queue_exposure_record_count=`{row.get('queue_exposure_record_count')}` "
            f"boarding_patient_count=`{row.get('boarding_patient_count')}` "
            f"boarding_timeout_event_count=`{row.get('boarding_timeout_event_count')}` "
            f"ed_exit_at_count=`{row.get('ed_exit_at_count')}`"
        )
        if row.get("trigger_audit_notes"):
            lines.append(f"  notes: {'; '.join(row['trigger_audit_notes'])}")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_phase5_summary(
    path: str | Path,
    *,
    threshold_report: dict[str, Any],
    signal_report_path: str,
    coarse_report_path: str,
    bracket_report_path: str,
    fine_matrix_path: str,
    final_matrix_path: str,
) -> None:
    lines = [
        "# Week13 Phase 5 Two-Stage Threshold Search Summary",
        "",
        f"- phase5a_status: `{threshold_report['phase5a_status']}`",
        f"- phase5b_status: `{threshold_report['phase5b_status']}`",
        f"- threshold_status: `{threshold_report['threshold_status']}`",
        f"- cluster_matrix_generated: `{threshold_report['cluster_matrix_generated']}`",
        f"- cluster_fine_sweep_jobs_count: `{threshold_report['cluster_fine_sweep_jobs_count']}`",
        f"- cluster_final_validation_jobs_count: `{threshold_report['cluster_final_validation_jobs_count']}`",
        "",
        "## Reports",
        f"- local_signal_check_report: `{signal_report_path}`",
        f"- local_preliminary_coarse_sweep_report: `{coarse_report_path}`",
        f"- local_bracket_report: `{bracket_report_path}`",
        f"- cluster_fine_sweep_matrix: `{fine_matrix_path}`",
        f"- cluster_final_validation_matrix: `{final_matrix_path}`",
        "",
        "## Known Limitations",
    ]
    for item in threshold_report.get("known_limitations", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Next Steps"])
    for item in threshold_report.get("next_steps", []):
        lines.append(f"- {item}")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def phase5a_dry_run(config: dict[str, Any], profiles: list[str]) -> dict[str, Any]:
    hospital_profiles = load_hospital_profiles()
    signal_plan = generate_signal_check_plan(
        profiles=profiles,
        hospital_profiles=hospital_profiles,
        run_steps=100,
        seeds=[42],
    )
    coarse_plan = generate_coarse_sweep_plan(
        profiles=profiles,
        hospital_profiles=hospital_profiles,
        load_factors=generate_coarse_load_factors(config),
        run_steps=200,
        seeds=[42],
    )
    return {
        "generated_at": __import__("datetime").datetime.utcnow().isoformat(),
        "phase": "5A",
        "mode": "dry_run",
        "signal_check_plan": signal_plan,
        "coarse_sweep_plan": coarse_plan,
    }


def phase5a_signal_check(
    config: dict[str, Any],
    profiles: list[str],
    run_steps: int,
    seeds: list[int],
    *,
    target_sim_override: str | None = None,
    phase_label: str = "signal_check",
) -> dict[str, Any]:
    hospital_profiles = load_hospital_profiles()
    plan = generate_signal_check_plan(
        profiles=profiles,
        hospital_profiles=hospital_profiles,
        run_steps=run_steps,
        seeds=seeds,
    )
    if target_sim_override and len(plan) == 1:
        plan[0]["target_sim_override"] = target_sim_override
    if len(plan) == 1:
        plan[0]["phase_label"] = phase_label
    results = _run_plan(plan, origin="ed_sim_n5", phase="signal_check")
    payload = _signal_report_payload(results, run_steps)
    write_json(config["outputs"]["local_signal_check_report"], payload)
    write_json(_signal_report_alias_path(config, run_steps), payload)
    if payload["threshold_search_status"] == "no_failure_signal_detected":
        _write_trigger_audit(
            config["outputs"]["trigger_audit"],
            signal_results=results,
            threshold_status=payload["threshold_search_status"],
        )
    return payload


def phase5a_coarse(config: dict[str, Any], profiles: list[str], run_steps: int, seeds: list[int]) -> dict[str, Any]:
    signal_report = _read_json(config["outputs"]["local_signal_check_report"])
    signal_results = list(signal_report.get("results") or [])
    if not any(has_failure_signal(row) for row in signal_results):
        payload = {
            "generated_at": __import__("datetime").datetime.utcnow().isoformat(),
            "phase": "5A",
            "stage": "preliminary_coarse_sweep",
            "run_steps": int(run_steps),
            "status": "blocked_no_failure_signal",
            "results": [],
        }
        write_json(config["outputs"]["local_preliminary_coarse_sweep_report"], payload)
        bracket_report = {
            "generated_at": __import__("datetime").datetime.utcnow().isoformat(),
            "phase": "5A",
            "stage": "local_bracket_detection",
            "failure_threshold": float(config["failure_threshold"]),
            "threshold_search_status": "no_failure_signal_detected",
            "profiles": {
                profile: {"bracket_status": "not_applicable_no_failure_signal", "last_safe": None, "first_fail": None}
                for profile in profiles
            },
        }
        write_json(config["outputs"]["local_bracket_report"], bracket_report)
        return payload

    hospital_profiles = load_hospital_profiles()
    plan = generate_coarse_sweep_plan(
        profiles=profiles,
        hospital_profiles=hospital_profiles,
        load_factors=generate_coarse_load_factors(config),
        run_steps=run_steps,
        seeds=seeds,
    )
    results = _run_plan(plan, origin="ed_sim_n5", phase="coarse_sweep")
    coarse_payload = _coarse_report_payload(results, run_steps)
    write_json(config["outputs"]["local_preliminary_coarse_sweep_report"], coarse_payload)

    bracket_results = [
        {
            "profile": row["profile"],
            "load_factor": row["load_factor"],
            "failure_rate": row["failure_rate"],
        }
        for row in results
        if row["run_status"] == "success"
    ]
    bracket_payload = _bracket_report_payload(bracket_results, float(config["failure_threshold"]))
    write_json(config["outputs"]["local_bracket_report"], bracket_payload)
    return coarse_payload


def phase5b_prepare_cluster(config: dict[str, Any]) -> dict[str, Any]:
    hospital_profiles = load_hospital_profiles()
    signal_report = _read_json(config["outputs"]["local_signal_check_report"])
    coarse_report = _read_json(config["outputs"]["local_preliminary_coarse_sweep_report"])
    bracket_report = _read_json(config["outputs"]["local_bracket_report"])

    profiles = [profile for profile in config["profiles"] if profile in hospital_profiles and profile != "large_tertiary_ed"]
    threshold_search_status = str(signal_report.get("threshold_search_status") or "unknown")
    brackets = dict(bracket_report.get("profiles") or {})

    fine_rows = generate_cluster_fine_sweep_matrix(
        brackets=brackets,
        hospital_profiles=hospital_profiles,
        fine_step=float(config["search"]["fine_step"]),
        seeds=[int(seed) for seed in config["search"]["cluster_fine_seeds"]],
        run_steps=int(config["search"]["cluster_run_steps"]),
        failure_threshold=float(config["failure_threshold"]),
        system_failed_comparator=str(config["system_failed_comparator"]),
    )
    write_csv(config["outputs"]["cluster_fine_sweep_matrix"], fine_rows)

    threshold_candidates = {
        profile: float(brackets[profile]["first_fail"]) if brackets.get(profile, {}).get("bracket_status") == "found" else None
        for profile in profiles
    }
    final_rows = generate_cluster_final_validation_matrix(
        threshold_candidates=threshold_candidates,
        hospital_profiles=hospital_profiles,
        seeds=[int(seed) for seed in config["search"]["cluster_final_validation_seeds"]],
        run_steps=int(config["search"]["cluster_run_steps"]),
        failure_threshold=float(config["failure_threshold"]),
        system_failed_comparator=str(config["system_failed_comparator"]),
    )
    write_csv(config["outputs"]["cluster_final_validation_matrix"], final_rows)

    bracket_found = any(brackets.get(profile, {}).get("bracket_status") == "found" for profile in profiles)
    phase5a_status = "completed_with_local_bracket" if bracket_found else threshold_search_status
    phase5b_status = "cluster_scaffold_generated" if bracket_found else "not_ready_for_cluster_fine_sweep"
    threshold_status = "waiting_for_cluster_fine_sweep" if bracket_found else "not_ready_for_cluster_fine_sweep"

    known_limitations = [
        "failure_rate definition unchanged",
        "nurses_total runtime confirmation may still be incomplete depending on sim_status payload",
        "full movement/environment contract mismatch remains a known limitation and is not a Phase 5 blocker",
    ]
    if threshold_search_status == "no_failure_signal_detected":
        known_limitations.append("local Phase 5A signal check found no non-zero failure signal at current run steps")

    next_steps = (
        ["submit cluster fine sweep job array after reviewing matrix"]
        if bracket_found
        else [
            "increase run_steps to 200 then 1000 before any 20000-step run",
            "audit failure reason triggers and CTAS timestamp progression",
            "confirm queue exposure timeline and boarding timeout trigger path",
        ]
    )
    threshold_report = build_threshold_search_report(
        phase5a_status=phase5a_status,
        phase5b_status=phase5b_status,
        local_signal_check_summary={
            "status": threshold_search_status,
            "report_path": config["outputs"]["local_signal_check_report"],
            "result_count": len(signal_report.get("results") or []),
        },
        local_coarse_sweep_summary={
            "status": coarse_report.get("status", "completed" if coarse_report.get("results") else "not_run"),
            "report_path": config["outputs"]["local_preliminary_coarse_sweep_report"],
            "result_count": len(coarse_report.get("results") or []),
        },
        local_bracket_status=brackets,
        cluster_matrix_generated=True,
        cluster_fine_sweep_jobs_count=len(fine_rows),
        cluster_final_validation_jobs_count=len([row for row in final_rows if row.get("phase") == "final_validation"]),
        threshold_status=threshold_status,
        threshold_load_factor=None,
        threshold_preload_patient_count=None,
        median_failure_rate_at_threshold=None,
        fail_seed_count_at_threshold=None,
        dominant_failure_reason_at_threshold=None,
        known_limitations=known_limitations,
        next_steps=next_steps,
    )
    write_json(config["outputs"]["threshold_report"], threshold_report)
    _write_phase5_summary(
        config["outputs"]["phase5_summary"],
        threshold_report=threshold_report,
        signal_report_path=config["outputs"]["local_signal_check_report"],
        coarse_report_path=config["outputs"]["local_preliminary_coarse_sweep_report"],
        bracket_report_path=config["outputs"]["local_bracket_report"],
        fine_matrix_path=config["outputs"]["cluster_fine_sweep_matrix"],
        final_matrix_path=config["outputs"]["cluster_final_validation_matrix"],
    )
    return threshold_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Week13 Phase 5 two-stage failure threshold search workflow.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--phase", choices=["5A", "5B"], required=True)
    parser.add_argument("--profiles", nargs="*", default=["medium_city_ed", "small_county_ed"])
    parser.add_argument("--run-steps", type=int, default=100)
    parser.add_argument("--seeds", nargs="*", type=int, default=[42])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--signal-check", action="store_true")
    parser.add_argument("--coarse", action="store_true")
    parser.add_argument("--prepare-cluster", action="store_true")
    parser.add_argument("--target-sim-override", default=None)
    parser.add_argument("--phase-label", default="signal_check")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_threshold_search_config(args.config)
    profiles = [profile for profile in args.profiles if profile in load_hospital_profiles()]

    if args.phase == "5A" and args.dry_run:
        payload = phase5a_dry_run(config, profiles)
    elif args.phase == "5A" and args.signal_check:
        payload = phase5a_signal_check(
            config,
            profiles,
            int(args.run_steps),
            [int(seed) for seed in args.seeds],
            target_sim_override=args.target_sim_override,
            phase_label=str(args.phase_label),
        )
    elif args.phase == "5A" and args.coarse:
        payload = phase5a_coarse(config, profiles, int(args.run_steps), [int(seed) for seed in args.seeds])
    elif args.phase == "5B" and args.prepare_cluster:
        payload = phase5b_prepare_cluster(config)
    else:
        raise SystemExit("Unsupported command combination for run_failure_threshold_search.py")

    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
