import json
import os
import shutil
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = PROJECT_ROOT / 'environment' / 'frontend_server'
MAZE_ASSETS_ROOT = FRONTEND_ROOT / 'static_dirs' / 'assets'
TEMP_ROOT = Path(os.environ.get("EDSIM_TEMP_DIR", str(FRONTEND_ROOT / 'temp_storage')))
STORAGE_ROOT = Path(os.environ.get("EDSIM_STORAGE_DIR", str(FRONTEND_ROOT / 'storage')))

maze_assets_loc = str(MAZE_ASSETS_ROOT)
env_matrix = str(MAZE_ASSETS_ROOT / 'the_ed' / 'matrix')
env_visuals = str(MAZE_ASSETS_ROOT / 'the_ed' / 'visuals')

fs_storage = str(STORAGE_ROOT)
fs_temp_storage = str(TEMP_ROOT)

collision_block_id = "1233"

static_sim_code = ""

# Verbose
debug = True

runtime_trace_enabled = os.environ.get("EDSIM_RUNTIME_TRACE", "1").strip().lower() not in {"0", "false", "no"}


def candidate_seed_sim_dirs(sim_code: str):
    """Return likely locations for a seed sim across nearby repo snapshots."""
    return [
        STORAGE_ROOT / sim_code,
        PROJECT_ROOT.parent / "week7" / "environment" / "frontend_server" / "storage" / sim_code,
        PROJECT_ROOT.parent / "week6" / "week6_interface" / "frontend_server" / "storage" / sim_code,
    ]


def ensure_seed_sim_storage(sim_code: str) -> Path:
    """
    Ensure the requested seed simulation exists in week8 storage.

    Week8 auto mode assumes `storage/ed_sim_n5` is present, but some local
    snapshots only include it under week7/week6. In that case, bootstrap a local
    copy so both frontend and backend can start consistently.
    """
    target = STORAGE_ROOT / sim_code
    if target.exists():
        return target

    for candidate in candidate_seed_sim_dirs(sim_code)[1:]:
        if candidate.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(candidate, target)
            return target

    raise FileNotFoundError(
        f"Seed simulation '{sim_code}' was not found in week8/week7/week6 storage."
    )


def runtime_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _format_runtime_fields(*, sim_code=None, step=None, command=None, elapsed_seconds=None, extra=None):
    fields = [f"[runtime {runtime_timestamp()}]"]
    if sim_code:
        fields.append(f"sim={sim_code}")
    if step is not None:
        fields.append(f"step={step}")
    if command:
        fields.append(f"command={command}")
    if elapsed_seconds is not None:
        fields.append(f"elapsed={elapsed_seconds:.3f}s")
    if extra:
        if isinstance(extra, dict):
            compact = json.dumps(extra, ensure_ascii=False, sort_keys=True)
        else:
            compact = str(extra)
        fields.append(f"extra={compact}")
    return " ".join(fields)


def log_runtime_event(message: str, *, sim_code=None, step=None, command=None, elapsed_seconds=None, extra=None):
    if not runtime_trace_enabled:
        return
    prefix = _format_runtime_fields(
        sim_code=sim_code,
        step=step,
        command=command,
        elapsed_seconds=elapsed_seconds,
        extra=extra,
    )
    try:
        print(f"{prefix} {message}")
    except (OSError, ValueError):
        # Non-interactive Windows runs can transiently reject stdout writes.
        # Logging should never terminate the simulation loop.
        return


@contextmanager
def runtime_timed(label: str, *, sim_code=None, step=None, command=None, extra=None):
    start = perf_counter()
    log_runtime_event(
        f"{label} start",
        sim_code=sim_code,
        step=step,
        command=command,
        extra=extra,
    )
    try:
        yield start
    except Exception as exc:
        log_runtime_event(
            f"{label} failed",
            sim_code=sim_code,
            step=step,
            command=command,
            elapsed_seconds=perf_counter() - start,
            extra={"error": str(exc)},
        )
        raise
    else:
        log_runtime_event(
            f"{label} done",
            sim_code=sim_code,
            step=step,
            command=command,
            elapsed_seconds=perf_counter() - start,
            extra=extra,
        )
