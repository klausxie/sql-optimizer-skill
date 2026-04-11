#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from sqlopt.contracts import ContractValidator
from sqlopt.io_utils import read_json, read_jsonl


def _latest_dir(path: Path) -> Path | None:
    if not path.exists():
        return None
    candidates = [child for child in path.iterdir() if child.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda child: child.stat().st_mtime)


def _default_run_dir() -> Path | None:
    sample_runs_dir = ROOT / "tests" / "fixtures" / "projects" / "sample_project" / "runs"
    index_path = sample_runs_dir / "index.json"
    if index_path.exists():
        try:
            payload = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        latest: tuple[str, Path] | None = None
        for row in payload.values():
            if not isinstance(row, dict):
                continue
            run_dir_text = str(row.get("run_dir") or "").strip()
            updated_at = str(row.get("updated_at") or "").strip()
            if not run_dir_text or not updated_at:
                continue
            run_dir = Path(run_dir_text)
            if not run_dir.exists():
                continue
            if latest is None or updated_at > latest[0]:
                latest = (updated_at, run_dir)
        if latest is not None:
            return latest[1]
    return _latest_dir(sample_runs_dir)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate schema contracts for a completed run directory.",
    )
    parser.add_argument(
        "run_dir",
        nargs="?",
        help="Run directory to validate. Defaults to the latest sample_project fixture run.",
    )
    return parser.parse_args()


def validate_jsonl(validator: ContractValidator, path: Path, schema_name: str) -> None:
    if not path.exists():
        return
    for row in read_jsonl(path):
        validator.validate(schema_name, row)


def main() -> None:
    args = _parse_args()
    run_dir = Path(args.run_dir) if args.run_dir else _default_run_dir()
    if run_dir is None:
        raise SystemExit("usage: schema_validate_all.py [run_dir] (no default run directory found)")
    if not run_dir.exists():
        raise SystemExit(f"run directory not found: {run_dir}")

    validator = ContractValidator(ROOT)
    validate_jsonl(validator, run_dir / "artifacts" / "scan.jsonl", "sqlunit")
    validate_jsonl(validator, run_dir / "artifacts" / "fragments.jsonl", "fragment_record")
    validate_jsonl(validator, run_dir / "artifacts" / "proposals.jsonl", "optimization_proposal")
    validate_jsonl(validator, run_dir / "artifacts" / "acceptance.jsonl", "acceptance_result")
    validate_jsonl(validator, run_dir / "artifacts" / "statement_convergence.jsonl", "statement_convergence")
    validate_jsonl(validator, run_dir / "artifacts" / "patches.jsonl", "patch_result")

    report_path = run_dir / "report.json"
    if report_path.exists():
        validator.validate("run_report", read_json(report_path))

    catalog_path = run_dir / "sql" / "catalog.jsonl"
    if catalog_path.exists():
        validate_jsonl(validator, catalog_path, "sql_artifact_index_row")

    print("ok")


if __name__ == "__main__":
    main()
