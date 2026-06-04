#!/usr/bin/env python
import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple


_WEEK13_FAILURE_RESOURCE_FIELDS = (
    "failure_rate",
    "failed_patients_count",
    "failure_reason_counts",
    "system_failed",
)


def _check_week13_failure_metrics_schema(status_payload: dict, strict: bool = False) -> Tuple[List[str], List[str]]:
    warnings: List[str] = []
    failures: List[str] = []
    resources = status_payload.get("resources")
    system_health = status_payload.get("system_health")

    missing_fields: List[str] = []
    if not isinstance(resources, dict):
        missing_fields.extend([f"resources.{field}" for field in _WEEK13_FAILURE_RESOURCE_FIELDS])
    else:
        for field in _WEEK13_FAILURE_RESOURCE_FIELDS:
            if field not in resources:
                missing_fields.append(f"resources.{field}")

    if not isinstance(system_health, dict) or "failed" not in system_health:
        missing_fields.append("system_health.failed")

    if missing_fields:
        message = "week13 failure metrics missing from sim_status.json: " + ", ".join(missing_fields)
        if strict:
            failures.append(message)
        else:
            warnings.append(f"WARNING: {message}")
    return warnings, failures


def _list_steps(directory: Path) -> List[int]:
    if not directory.exists():
        return []
    steps: List[int] = []
    for file_path in directory.glob("*.json"):
        try:
            steps.append(int(file_path.stem))
        except (TypeError, ValueError):
            continue
    return sorted(steps)


def _load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    rows: List[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _infer_role(name: str, scratch_payload: Optional[dict]) -> str:
    role = (scratch_payload or {}).get("role")
    if isinstance(role, str) and role.strip():
        return role.strip()
    lowered = name.lower()
    if lowered.startswith("doctor"):
        return "Doctor"
    if lowered.startswith("bedside nurse"):
        return "BedsideNurse"
    if lowered.startswith("patient"):
        return "Patient"
    return "Unknown"


def _read_scratch(curr_sim_dir: Path, persona_name: str) -> dict:
    scratch_path = curr_sim_dir / "personas" / persona_name / "bootstrap_memory" / "scratch.json"
    if not scratch_path.exists():
        return {}
    try:
        return _load_json(scratch_path)
    except Exception:
        return {}


def _xy(payload) -> Optional[Tuple[int, int]]:
    if isinstance(payload, dict):
        try:
            return (int(payload.get("x")), int(payload.get("y")))
        except (TypeError, ValueError):
            return None
    if isinstance(payload, (list, tuple)) and len(payload) >= 2:
        try:
            return (int(payload[0]), int(payload[1]))
        except (TypeError, ValueError):
            return None
    return None


def _manhattan(a: Optional[Tuple[int, int]], b: Optional[Tuple[int, int]]) -> Optional[int]:
    if a is None or b is None:
        return None
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _safe_text(value) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").strip()


def _export_dialogue_report(curr_sim_dir: Path, output_path: Path) -> int:
    trace_path = curr_sim_dir / "dialogue_trace.jsonl"
    rows = _load_jsonl(trace_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append("# Dialogue Provenance Report")
    lines.append("")
    lines.append(f"- sim_dir: `{curr_sim_dir}`")
    lines.append(f"- trace_file: `{trace_path}`")
    lines.append(f"- records: `{len(rows)}`")
    lines.append("")
    if not rows:
        lines.append("No dialogue trace records found.")
    else:
        lines.append("| step | persona | participants | source_type | llm_mode | generator | fallback | prompt_template | summary_template | movement_file |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for row in rows:
            participants = row.get("participants")
            if isinstance(participants, list):
                participants_text = ", ".join(str(item) for item in participants)
            else:
                participants_text = ""
            lines.append(
                "| "
                + f"{_safe_text(row.get('step'))} | "
                + f"{_safe_text(row.get('persona'))} | "
                + f"{_safe_text(participants_text)} | "
                + f"{_safe_text(row.get('source_type'))} | "
                + f"{_safe_text(row.get('llm_mode'))} | "
                + f"{_safe_text(row.get('generator'))} | "
                + f"{_safe_text(row.get('fallback_used'))} | "
                + f"{_safe_text(row.get('prompt_template_path'))} | "
                + f"{_safe_text(row.get('summary_template_path'))} | "
                + f"{_safe_text(row.get('linked_movement_file'))} |"
            )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="Verify movement/environment step contract for curr_sim.")
    parser.add_argument(
        "--storage-root",
        default=str(Path(__file__).resolve().parents[1] / "environment" / "frontend_server" / "storage"),
        help="Path to frontend storage root.",
    )
    parser.add_argument("--sim-code", default="curr_sim", help="Simulation code folder under storage root.")
    parser.add_argument("--start-step", type=int, default=None)
    parser.add_argument("--end-step", type=int, default=None)
    parser.add_argument(
        "--export-dialogue-report",
        action="store_true",
        help="Export dialogue provenance markdown report from dialogue_trace.jsonl.",
    )
    parser.add_argument(
        "--dialogue-report-path",
        default=str(Path(__file__).resolve().parents[1] / "artifacts" / "dialogue_provenance_report.md"),
        help="Path to markdown report generated by --export-dialogue-report.",
    )
    parser.add_argument(
        "--strict-week13-failure-metrics",
        action="store_true",
        help="Hard fail when week13 failure metrics are missing from sim_status.json.",
    )
    parser.add_argument(
        "--week13-failure-metrics-only",
        action="store_true",
        help="Only validate sim_status.json week13 failure metrics schema; skip movement/environment contract checks.",
    )
    args = parser.parse_args()

    sim_dir = Path(args.storage_root) / args.sim_code
    movement_dir = sim_dir / "movement"
    environment_dir = sim_dir / "environment"
    runtime_trace_path = sim_dir / "runtime_trace.json"
    sim_status_path = sim_dir / "sim_status.json"

    if args.week13_failure_metrics_only:
        failures: List[str] = []
        warnings: List[str] = []
        if sim_status_path.exists():
            try:
                status_payload = _load_json(sim_status_path)
            except Exception:
                status_payload = {}
            schema_warnings, schema_failures = _check_week13_failure_metrics_schema(
                status_payload,
                strict=args.strict_week13_failure_metrics,
            )
            warnings.extend(schema_warnings)
            failures.extend(schema_failures)
        else:
            message = "week13 failure metrics missing from sim_status.json: sim_status.json not found"
            if args.strict_week13_failure_metrics:
                failures.append(message)
            else:
                warnings.append(f"WARNING: {message}")

        print("=== Week13 Failure Metrics Summary ===")
        print(f"sim_code={args.sim_code}")
        for warning in warnings:
            print(warning)
        if failures:
            print("=== FAILURES ===")
            for failure in failures:
                print(f"- {failure}")
            raise SystemExit(1)
        print("PASS: week13 failure metrics schema present.")
        raise SystemExit(0)

    movement_steps = _list_steps(movement_dir)
    environment_steps = _list_steps(environment_dir)
    if not movement_steps:
        raise SystemExit("FAIL: no movement/*.json steps found.")
    if not environment_steps:
        raise SystemExit("FAIL: no environment/*.json steps found.")

    start_step = args.start_step if args.start_step is not None else movement_steps[0]
    end_step = args.end_step if args.end_step is not None else movement_steps[-1]
    if end_step < start_step:
        raise SystemExit("FAIL: end-step must be >= start-step.")

    failures: List[str] = []
    checked_steps = 0
    role_examples: Dict[str, dict] = {}
    role_schema_hits = {"Doctor": False, "BedsideNurse": False, "Patient": False}
    prev_environment_by_persona: Dict[str, Tuple[int, int]] = {}
    idle_explanations: List[str] = []
    provenance_samples: List[str] = []
    warnings: List[str] = []
    bootstrap_tolerated_count = 0

    expected_movement_steps = list(range(start_step, end_step + 1))
    missing_movement = [step for step in expected_movement_steps if step not in movement_steps]
    if missing_movement:
        failures.append(f"Missing movement steps: {missing_movement[:10]}")

    trace_payload = {}
    if runtime_trace_path.exists():
        try:
            trace_payload = _load_json(runtime_trace_path)
        except Exception:
            trace_payload = {}
    if not trace_payload.get("run_id"):
        failures.append("runtime_trace.run_id is empty/null")

    if sim_status_path.exists():
        try:
            status_payload = _load_json(sim_status_path)
        except Exception:
            status_payload = {}
        schema_warnings, schema_failures = _check_week13_failure_metrics_schema(
            status_payload,
            strict=args.strict_week13_failure_metrics,
        )
        warnings.extend(schema_warnings)
        failures.extend(schema_failures)
    else:
        message = "week13 failure metrics missing from sim_status.json: sim_status.json not found"
        if args.strict_week13_failure_metrics:
            failures.append(message)
        else:
            warnings.append(f"WARNING: {message}")

    for step in expected_movement_steps:
        is_bootstrap_step = step == start_step
        movement_path = movement_dir / f"{step}.json"
        primary_environment_path = environment_dir / f"{step + 1}.json"
        fallback_environment_path = environment_dir / f"{step}.json"
        if not movement_path.exists():
            continue
        if primary_environment_path.exists():
            environment_path = primary_environment_path
            environment_step = step + 1
            aligned_window = "step+1"
        elif fallback_environment_path.exists():
            environment_path = fallback_environment_path
            environment_step = step
            aligned_window = "same_step_fallback"
            warnings.append(f"Step {step}: missing environment/{step + 1}.json, used environment/{step}.json fallback")
        else:
            failures.append(f"Step {step}: missing environment/{step + 1}.json and environment/{step}.json")
            continue

        movement_payload = _load_json(movement_path)
        environment_payload = _load_json(environment_path)
        persona_movement = movement_payload.get("persona", {}) if isinstance(movement_payload, dict) else {}
        if not isinstance(persona_movement, dict):
            failures.append(f"Step {step}: movement persona payload is not an object")
            continue
        if not isinstance(environment_payload, dict):
            failures.append(f"Step {step}: environment payload is not an object")
            continue

        movement_personas = set(persona_movement.keys())
        environment_personas = set(environment_payload.keys())
        missing_in_environment = sorted(movement_personas - environment_personas)
        missing_in_movement = sorted(environment_personas - movement_personas)
        if missing_in_environment:
            missing_ratio = len(missing_in_environment) / max(1, len(movement_personas))
            if missing_ratio >= 0.4 and len(missing_in_environment) >= 3:
                failures.append(
                    f"Step {step}: bulk personas missing in environment/{environment_step}: {missing_in_environment[:8]}"
                )
            else:
                warnings.append(
                    f"Step {step}: lifecycle-style missing personas in environment/{environment_step}: {missing_in_environment[:5]}"
                )
        if missing_in_movement:
            warnings.append(
                f"Step {step}: personas present in environment/{environment_step} but absent in movement/{step}: {missing_in_movement[:5]}"
            )

        for persona_name, movement_info in persona_movement.items():
            env_info = environment_payload.get(persona_name)
            target_xy = _xy((movement_info or {}).get("movement"))
            env_xy = _xy(env_info)
            distance = _manhattan(target_xy, env_xy)
            if target_xy is not None and env_xy is not None and target_xy != env_xy:
                if aligned_window == "step+1":
                    if is_bootstrap_step and distance is not None and distance <= 1:
                        bootstrap_tolerated_count += 1
                        warnings.append(
                            f"Step {step}: bootstrap tolerance {persona_name} target {target_xy} vs environment/{environment_step} {env_xy} (distance={distance})"
                        )
                    else:
                        failures.append(
                            f"Step {step}: {persona_name} target {target_xy} != environment/{environment_step} {env_xy}"
                        )
                else:
                    warnings.append(
                        f"Step {step}: fallback compare {persona_name} target {target_xy} != environment/{environment_step} {env_xy} (distance={distance})"
                    )

            movement_path_tiles = (movement_info or {}).get("movement_path")
            if not isinstance(movement_path_tiles, list):
                movement_path_tiles = []
            path_len = len(movement_path_tiles)

            source_xy = prev_environment_by_persona.get(persona_name)
            if source_xy is None:
                prior_env_path = environment_dir / f"{step}.json"
                if prior_env_path.exists():
                    prior_env_payload = _load_json(prior_env_path)
                    source_xy = _xy(prior_env_payload.get(persona_name))

            if source_xy is not None and target_xy is not None and target_xy != source_xy and path_len < 2:
                failures.append(
                    f"Step {step}: {persona_name} moved from {source_xy} to {target_xy} but movement_path length={path_len}"
                )

            if path_len <= 1:
                scratch_payload = _read_scratch(sim_dir, persona_name)
                description = str((movement_info or {}).get("description") or "").strip() or "<empty>"
                scratch_state = str(scratch_payload.get("state") or "<missing>")
                idle_explanations.append(
                    f"Step {step} {persona_name}: path_len={path_len}, description={description}, scratch_state={scratch_state}"
                )

            if env_xy is not None:
                prev_environment_by_persona[persona_name] = env_xy

            scratch_payload = _read_scratch(sim_dir, persona_name)
            role = _infer_role(persona_name, scratch_payload)
            role_key = str((movement_info or {}).get("role_key") or "").strip()
            badge = str((movement_info or {}).get("badge") or "").strip()
            if role in role_schema_hits and role_key and badge:
                role_schema_hits[role] = True

            chat_payload = (movement_info or {}).get("chat")
            chat_exists = isinstance(chat_payload, list) and len(chat_payload) > 0
            dialogue_provenance = (movement_info or {}).get("dialogue_provenance")
            if chat_exists:
                if not isinstance(dialogue_provenance, dict):
                    failures.append(f"Step {step}: {persona_name} has chat but missing dialogue_provenance")
                else:
                    source_type = str(dialogue_provenance.get("source_type") or "").strip()
                    llm_mode = str(dialogue_provenance.get("llm_mode") or "").strip()
                    prompt_template_path = str(dialogue_provenance.get("prompt_template_path") or "").strip()
                    if not source_type:
                        failures.append(f"Step {step}: {persona_name} chat provenance missing source_type")
                    if source_type == "none":
                        failures.append(f"Step {step}: {persona_name} has chat but provenance source_type=none")
                    if not llm_mode:
                        failures.append(f"Step {step}: {persona_name} chat provenance missing llm_mode")
                    if not prompt_template_path:
                        failures.append(f"Step {step}: {persona_name} chat provenance missing prompt_template_path")
                    provenance_samples.append(
                        f"Step {step} {persona_name}: source_type={source_type or '<missing>'}, "
                        f"llm_mode={llm_mode or '<missing>'}, template={prompt_template_path or '<missing>'}"
                    )

            if role not in role_examples:
                role_examples[role] = {
                    "persona": persona_name,
                    "step": step,
                    "target": target_xy,
                    "environment": env_xy,
                    "path_len": path_len,
                    "description": str((movement_info or {}).get("description") or "").strip(),
                    "chat_exists": chat_exists,
                }
        checked_steps += 1

    print("=== Step Contract Summary ===")
    print(f"sim_code={args.sim_code}")
    print(f"checked_steps={checked_steps} range=[{start_step}, {end_step}]")
    print(f"movement_max_step={movement_steps[-1]} environment_max_step={environment_steps[-1]}")
    if runtime_trace_path.exists():
        try:
            trace = _load_json(runtime_trace_path)
            print(
                "runtime_trace: "
                f"run_id={trace.get('run_id')} "
                f"backend_movement_max_step={trace.get('backend_movement_max_step')} "
                f"frontend_environment_max_step={trace.get('frontend_environment_max_step')} "
                f"curr_step={trace.get('curr_step')} "
                f"lag={trace.get('lag')} "
                f"blocked_reason={trace.get('blocked_reason')}"
            )
        except Exception:
            print("runtime_trace: unreadable")
    else:
        print("runtime_trace: missing")

    for role_name in ("Doctor", "BedsideNurse", "Patient"):
        example = role_examples.get(role_name)
        if not example:
            print(f"{role_name}: not found")
            continue
        print(
            f"{role_name}: {example['persona']} step={example['step']} "
            f"target={example['target']} environment={example['environment']} "
            f"path_len={example['path_len']} chat_exists={example['chat_exists']}"
        )
        if role_schema_hits.get(role_name):
            print(f"{role_name} schema: role_key/badge present")
        else:
            print(f"{role_name} schema: role_key/badge missing")

    if idle_explanations:
        print("idle_or_waiting_samples:")
        for row in idle_explanations[:5]:
            print(f"  - {row}")
    if bootstrap_tolerated_count:
        print(f"bootstrap_tolerance_applied={bootstrap_tolerated_count}")
    if warnings:
        print("warnings:")
        for row in warnings[:10]:
            print(f"  - {row}")
    if provenance_samples:
        print("dialogue_provenance_samples:")
        for row in provenance_samples[:5]:
            print(f"  - {row}")

    for role_name, hit in role_schema_hits.items():
        if not hit:
            failures.append(f"{role_name}: missing explicit role schema fields (role_key/badge) in checked range")

    if args.export_dialogue_report:
        report_path = Path(args.dialogue_report_path).resolve()
        exported_count = _export_dialogue_report(sim_dir, report_path)
        print(f"dialogue_report_exported: path={report_path} records={exported_count}")

    if failures:
        print("=== FAILURES ===")
        for row in failures[:50]:
            print(f"- {row}")
        raise SystemExit(1)

    print("PASS: movement/environment contract checks passed.")


if __name__ == "__main__":
    main()
