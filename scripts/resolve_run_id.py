#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import sys

sys.path.insert(0, str((Path(__file__).resolve().parents[1] / "python").resolve()))

from sqlopt.application.run_resolution import resolve_run_id as _resolve_run_id


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_run_id(run_id: str | None, project: str | None = None) -> tuple[str, Path]:
    return _resolve_run_id(run_id, project=project, repo_root=_repo_root())


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--run-id")
    p.add_argument("--project", default=".")
    p.add_argument("--print-run-dir", action="store_true")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    try:
        rid, run_dir = resolve_run_id(args.run_id, args.project)
    except FileNotFoundError:
        missing = args.run_id or "latest"
        print({"error": {"reason_code": "RUN_NOT_FOUND", "message": f"run_id not found: {missing}"}})
        raise SystemExit(2)
    if args.print_run_dir:
        print({"run_id": rid, "run_dir": str(run_dir)})
    else:
        print(rid)


if __name__ == "__main__":
    main()
