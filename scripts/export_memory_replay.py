"""Export Week8 Memory v1 replay to a JSON file.

This is a demo/helper tool. It does not change any planner ownership.

Example:
  MEMORY_V1_ROOT=runtime_data/memory python scripts/export_memory_replay.py \
      --run_id user_20260424_140753 --mode user --encounter_id user_user_... --out analysis/replay_user.json
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app_core.memory.service import create_memory_service


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--run_id", required=True)
    p.add_argument("--mode", required=True, choices=["auto", "user"])
    p.add_argument("--encounter_id", required=True)
    p.add_argument("--out", required=True)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    out_path = Path(args.out)
    svc = create_memory_service()
    dest = svc.export_replay_to_path(out_path, run_id=args.run_id, mode=args.mode, encounter_id=args.encounter_id)
    if dest is None:
        raise SystemExit("memory service disabled or replay backend unavailable")
    print(str(dest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
