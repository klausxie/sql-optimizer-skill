#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from sqlopt.devtools.generalization_blocker_inventory import (  # noqa: E402
    READY_SENTINEL_SQL_KEYS,
    TEMPLATE_PRESERVING_DYNAMIC_PRIMARY_SENTINELS,
)
from sqlopt.devtools.sample_project_family_scopes import GENERALIZATION_BATCH_SCOPE_SQL_KEYS  # noqa: E402
from sqlopt.application.boundary_mapping import present_boundary  # noqa: E402
from sqlopt.devtools.run_progress_summary import summarize_run_progress  # noqa: E402


def _parse_batch_run(value: str) -> tuple[str, Path]:
    batch_name, sep, run_dir = str(value or "").partition("=")
    batch_name = batch_name.strip()
    run_dir = run_dir.strip()
    if not sep or not batch_name or not run_dir:
        raise argparse.ArgumentTypeError("expected <batch-name>=<run-dir>")
    if batch_name not in GENERALIZATION_BATCH_SCOPE_SQL_KEYS:
        raise argparse.ArgumentTypeError(f"unknown generalization batch: {batch_name}")
    return batch_name, Path(run_dir).resolve()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Boundary protection gate for generalization batch runs.")
    parser.add_argument(
        "--batch-run",
        action="append",
        default=[],
        type=_parse_batch_run,
        help="Batch/run pair in the form generalization-batchN=/abs/path/to/run_dir",
    )
    parser.add_argument("--mode", choices=("observe", "hard"), default="observe")
    parser.add_argument("--format", choices=("json", "text"), default="json")
    return parser.parse_args()


def _expected_boundary_categories() -> dict[str, str]:
    expected: dict[str, str] = {}
    for statement_key in TEMPLATE_PRESERVING_DYNAMIC_PRIMARY_SENTINELS:
        expected[statement_key] = "PROVIDER_LIMITED"
    return expected


def _summarize_batch(batch_name: str, run_dir: Path) -> dict[str, object]:
    summary = summarize_run_progress(run_dir, statement_keys=GENERALIZATION_BATCH_SCOPE_SQL_KEYS[batch_name])
    rows = list(summary.rows)
    ready_regressions = [
        row.statement_key
        for row in rows
        if row.statement_key in READY_SENTINEL_SQL_KEYS and row.convergence_decision != "AUTO_PATCHABLE"
    ]
    blocked_boundary_regressions = [
        row.statement_key
        for row in rows
        if row.statement_key in _expected_boundary_categories() and row.convergence_decision == "AUTO_PATCHABLE"
    ]
    category_mismatches: dict[str, dict[str, str]] = {}
    checked_categories: dict[str, str] = {}
    expected_categories = _expected_boundary_categories()
    for row in rows:
        boundary = present_boundary(
            statement_key=row.statement_key,
            blocker_code=row.conflict_reason,
            delivery_decision=row.convergence_decision,
        )
        if row.statement_key in expected_categories:
            checked_categories[row.statement_key] = boundary.category
            expected = expected_categories[row.statement_key]
            if boundary.category != expected:
                category_mismatches[row.statement_key] = {
                    "expected": expected,
                    "actual": boundary.category,
                }
    gate_passed = not ready_regressions and not blocked_boundary_regressions and not category_mismatches
    return {
        "batch": batch_name,
        "run_dir": str(run_dir),
        "ready_regressions": ready_regressions,
        "blocked_boundary_regressions": blocked_boundary_regressions,
        "checked_boundary_categories": checked_categories,
        "boundary_category_mismatches": category_mismatches,
        "gate_passed": gate_passed,
    }


def main() -> None:
    args = _parse_args()
    if not args.batch_run:
        raise SystemExit("--batch-run is required at least once")

    batch_payloads = [_summarize_batch(batch_name, run_dir) for batch_name, run_dir in args.batch_run]
    overall_ready_regressions: list[str] = []
    overall_blocked_regressions: list[str] = []
    checked_categories: dict[str, str] = {}
    mismatches: dict[str, dict[str, str]] = {}
    for payload in batch_payloads:
        overall_ready_regressions.extend(payload["ready_regressions"])
        overall_blocked_regressions.extend(payload["blocked_boundary_regressions"])
        checked_categories.update(payload["checked_boundary_categories"])
        mismatches.update(payload["boundary_category_mismatches"])

    gate_passed = not overall_ready_regressions and not overall_blocked_regressions and not mismatches
    payload = {
        "batches": batch_payloads,
        "overall": {
            "ready_regressions": len(overall_ready_regressions),
            "blocked_boundary_regressions": len(overall_blocked_regressions),
        },
        "checked_boundary_categories": checked_categories,
        "boundary_category_mismatches": mismatches,
        "gate_passed": gate_passed,
    }

    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"gate_passed={payload['gate_passed']}")
        print(f"ready_regressions={payload['overall']['ready_regressions']}")
        print(f"blocked_boundary_regressions={payload['overall']['blocked_boundary_regressions']}")
        print(f"checked_boundary_categories={payload['checked_boundary_categories']}")
        print(f"boundary_category_mismatches={payload['boundary_category_mismatches']}")

    if args.mode == "hard" and not gate_passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
