from __future__ import annotations

import argparse
from pathlib import Path

from app_core.clinical_kb.compiler import build_lex_indices, compile_chunks, normalize_all
from app_core.clinical_kb.validators import DEFAULT_KB_ROOT, validate_all_sources


def main() -> int:
    parser = argparse.ArgumentParser(prog="app_core.clinical_kb.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate")
    sub.add_parser("normalize")
    sub.add_parser("compile")
    sub.add_parser("build-index")
    args = parser.parse_args()

    kb_root = DEFAULT_KB_ROOT
    if args.cmd == "validate":
        issues = validate_all_sources(kb_root=kb_root)
        errors = [i for i in issues if i.level == "error"]
        for it in issues:
            print(f"{it.level.upper()}: {it.message} {it.path}".strip())
        return 1 if errors else 0
    if args.cmd == "normalize":
        normalize_all(kb_root=kb_root)
        print("normalized_ok")
        return 0
    if args.cmd == "compile":
        normalize_all(kb_root=kb_root)
        compile_chunks(kb_root=kb_root)
        print("compile_ok")
        return 0
    if args.cmd == "build-index":
        normalize_all(kb_root=kb_root)
        compile_chunks(kb_root=kb_root)
        build_lex_indices(kb_root=kb_root)
        print("build_index_ok")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

