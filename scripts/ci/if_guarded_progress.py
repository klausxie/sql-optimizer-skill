#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _compute_if_guarded_progress(run_dir: Path, *, shape_family: str) -> dict[str, Any]:
    convergence_rows = _read_jsonl(run_dir / "artifacts" / "statement_convergence.jsonl")
    patch_rows = _read_jsonl(run_dir / "artifacts" / "patches.jsonl")
    normalized_family = shape_family.strip().upper()

    by_statement: dict[str, dict[str, Any]] = {}
    family_rows: list[dict[str, Any]] = []
    for row in convergence_rows:
        family = str(row.get("shapeFamily") or "").strip().upper()
        if family != normalized_family:
            continue
        statement_key = str(row.get("statementKey") or "").strip()
        if not statement_key:
            continue
        by_statement[statement_key] = row
        family_rows.append(row)

    decision_counts = {
        "AUTO_PATCHABLE": 0,
        "MANUAL_REVIEW": 0,
        "NOT_PATCHABLE": 0,
    }
    conflict_reason_counts: dict[str, int] = {}
    for row in family_rows:
        decision = str(row.get("convergenceDecision") or "").strip().upper()
        if decision in decision_counts:
            decision_counts[decision] += 1
        reason = str(row.get("conflictReason") or "").strip()
        if reason:
            conflict_reason_counts[reason] = conflict_reason_counts.get(reason, 0) + 1

    patch_convergence_blocked = 0
    for row in patch_rows:
        statement_key = str(row.get("statementKey") or "").strip() or str(row.get("sqlKey") or "").split("#", 1)[0]
        if statement_key not in by_statement:
            continue
        code = str(((row.get("selectionReason") or {}).get("code") or "")).strip()
        if code.startswith("PATCH_CONVERGENCE_"):
            patch_convergence_blocked += 1

    total = len(family_rows)
    auto = decision_counts["AUTO_PATCHABLE"]
    auto_rate = (auto / total) if total else 0.0
    return {
        "shape_family": normalized_family,
        "total_statements": total,
        "decision_counts": decision_counts,
        "auto_patchable_rate": auto_rate,
        "conflict_reason_counts": dict(sorted(conflict_reason_counts.items(), key=lambda item: (-item[1], item[0]))),
        "patch_convergence_blocked_count": patch_convergence_blocked,
    }


def _gate_result(progress: dict[str, Any], *, min_auto_rate: float) -> bool:
    total = int(progress.get("total_statements") or 0)
    if total <= 0:
        return False
    auto_rate = float(progress.get("auto_patchable_rate") or 0.0)
    return auto_rate >= float(min_auto_rate)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="North-star progress snapshot for IF_GUARDED family.")
    parser.add_argument("run_dir", type=Path, help="run directory path")
    parser.add_argument("--shape-family", default="IF_GUARDED_FILTER_STATEMENT")
    parser.add_argument("--mode", choices=("observe", "soft", "hard"), default="observe")
    parser.add_argument("--min-auto-rate", type=float, default=0.0)
    parser.add_argument("--format", choices=("json", "text"), default="json")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    run_dir = Path(args.run_dir).resolve()
    progress = _compute_if_guarded_progress(run_dir, shape_family=args.shape_family)
    gate_passed = _gate_result(progress, min_auto_rate=args.min_auto_rate)
    payload = {
        "run_dir": str(run_dir),
        "mode": args.mode,
        "min_auto_rate": args.min_auto_rate,
        "gate_passed": gate_passed,
        **progress,
    }

    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False))
    else:
        top_conflicts = ",".join(
            f"{reason}:{count}"
            for reason, count in list(payload["conflict_reason_counts"].items())[:3]
        )
        print(f"shape_family={payload['shape_family']}")
        print(f"total_statements={payload['total_statements']}")
        print(f"decision_counts={payload['decision_counts']}")
        print(f"auto_patchable_rate={payload['auto_patchable_rate']:.4f}")
        print(f"patch_convergence_blocked_count={payload['patch_convergence_blocked_count']}")
        print(f"gate_passed={payload['gate_passed']}")
        print(f"top_conflict_reasons={top_conflicts}")

    if args.mode == "hard" and not gate_passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
