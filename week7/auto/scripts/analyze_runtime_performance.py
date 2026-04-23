import argparse
import json
import re
import statistics
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_ROOT = REPO_ROOT / "analysis" / "scenario_regressions"

WALL_CLOCK_RE = re.compile(r"Wall-clock duration:\s*([0-9.]+)s")
RUNTIME_ELAPSED_RE = re.compile(r"elapsed=([0-9.]+)s")


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def percentile(values: list[float], q: float):
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * q
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def summarise_values(values: list[float]) -> dict:
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "p90": None,
            "p95": None,
            "p99": None,
            "max": None,
            "steps_over_1s": 0,
            "steps_over_5s": 0,
            "steps_over_10s": 0,
            "steps_over_30s": 0,
        }
    return {
        "count": len(values),
        "mean": round(statistics.fmean(values), 3),
        "median": round(statistics.median(values), 3),
        "p90": round(percentile(values, 0.90), 3),
        "p95": round(percentile(values, 0.95), 3),
        "p99": round(percentile(values, 0.99), 3),
        "max": round(max(values), 3),
        "steps_over_1s": sum(value > 1 for value in values),
        "steps_over_5s": sum(value > 5 for value in values),
        "steps_over_10s": sum(value > 10 for value in values),
        "steps_over_30s": sum(value > 30 for value in values),
    }


def collect_step_wall_clock(scenario_dir: Path) -> list[float]:
    values = []
    for sim_output_path in scenario_dir.glob("**/_temp/*/sim_output.json"):
        payload = read_json(sim_output_path, default={}) or {}
        outputs = payload.get("outputs", [])
        for entry in outputs:
            text = entry.get("output", "") if isinstance(entry, dict) else str(entry)
            values.extend(float(match.group(1)) for match in WALL_CLOCK_RE.finditer(text))
    if values:
        return values
    for log_path in scenario_dir.glob("**/runtime.log"):
        for line in read_text(log_path).splitlines():
            if "step cycle done" not in line:
                continue
            match = RUNTIME_ELAPSED_RE.search(line)
            if match:
                values.append(float(match.group(1)))
    return values


def collect_runtime_log_counts(scenario_dir: Path) -> dict:
    text_parts = []
    for log_path in scenario_dir.glob("**/runtime.log"):
        text_parts.append(read_text(log_path))
    text = "\n".join(text_parts)
    embedding_elapsed = []
    for line in text.splitlines():
        if (
            "embedding request done" in line
            or "embedding request fallback-local" in line
            or "embedding preflight fallback-local" in line
            or "embedding request failed" in line
        ):
            match = RUNTIME_ELAPSED_RE.search(line)
            if match:
                embedding_elapsed.append(float(match.group(1)))
    structured_retries = text.count("embedding request retry")
    legacy_retries = text.count("get_embedding retry")
    structured_fallbacks = text.count("embedding request fallback-local") + text.count("embedding preflight fallback-local")
    legacy_fallbacks = text.count("get_embedding failed after retries, switching to local embeddings")
    return {
        "runtime_log_files": len(list(scenario_dir.glob("**/runtime.log"))),
        "embedding_request_begin": text.count("embedding request begin"),
        "embedding_request_done": text.count("embedding request done"),
        "embedding_request_retry": structured_retries if structured_retries else legacy_retries,
        "embedding_fallback_local": structured_fallbacks if structured_fallbacks else legacy_fallbacks,
        "embedding_preflight_fallback_local": text.count("embedding preflight fallback-local"),
        "embedding_cache_hit": text.count("embedding cache hit"),
        "embedding_cooldown_short_circuit": text.count("embedding hybrid cooldown short-circuit"),
        "llm_chat_request_done": text.count("llm chat request done"),
        "llm_structured_request_done": text.count("llm structured request done"),
        "curl_error_seen": text.count("curl.exe failed"),
        "embedding_elapsed_seconds": summarise_values(embedding_elapsed),
    }


def analyze_report_dir(report_dir: Path) -> dict:
    wall_values = collect_step_wall_clock(report_dir)
    return {
        "report_dir": str(report_dir),
        "step_wall_clock_seconds": summarise_values(wall_values),
        "runtime_events": collect_runtime_log_counts(report_dir),
    }


def compare_reports(before: dict, after: dict) -> dict:
    before_wall = before["step_wall_clock_seconds"]
    after_wall = after["step_wall_clock_seconds"]
    before_events = before["runtime_events"]
    after_events = after["runtime_events"]
    return {
        "median_delta_seconds": (
            None
            if before_wall["median"] is None or after_wall["median"] is None
            else round(after_wall["median"] - before_wall["median"], 3)
        ),
        "p95_delta_seconds": (
            None
            if before_wall["p95"] is None or after_wall["p95"] is None
            else round(after_wall["p95"] - before_wall["p95"], 3)
        ),
        "max_delta_seconds": (
            None
            if before_wall["max"] is None or after_wall["max"] is None
            else round(after_wall["max"] - before_wall["max"], 3)
        ),
        "slow_steps_over_5s_delta": after_wall["steps_over_5s"] - before_wall["steps_over_5s"],
        "embedding_retry_delta": after_events["embedding_request_retry"] - before_events["embedding_request_retry"],
        "embedding_fallback_local_delta": after_events["embedding_fallback_local"] - before_events["embedding_fallback_local"],
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Analyze real Week7 step latency and embedding runtime events.")
    parser.add_argument("--report-dir", type=Path, help="Single scenario_regressions report dir to analyze.")
    parser.add_argument("--before", type=Path, help="Before-change report dir for comparison.")
    parser.add_argument("--after", type=Path, help="After-change report dir for comparison.")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.before and args.after:
        before = analyze_report_dir(args.before)
        after = analyze_report_dir(args.after)
        payload = {
            "before": before,
            "after": after,
            "comparison": compare_reports(before, after),
        }
    else:
        report_dir = args.report_dir or max(DEFAULT_REPORT_ROOT.iterdir(), key=lambda path: path.stat().st_mtime)
        payload = analyze_report_dir(report_dir)

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
