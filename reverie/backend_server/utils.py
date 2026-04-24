import json
import os
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
    print(f"{prefix} {message}")


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
