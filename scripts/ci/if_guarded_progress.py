#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from sqlopt.devtools.run_progress_summary import summarize_run_progress  # noqa: E402


def _compute_if_guarded_progress(run_dir: Path, *, shape_family: str) -> dict[str, Any]:
    summary = summarize_run_progress(run_dir, shape_family=shape_family)
    total = summary.total_statements
    auto = summary.decision_counts["AUTO_PATCHABLE"]
    auto_rate = (auto / total) if total else 0.0
    return {
        "shape_family": shape_family.strip().upper(),
        "total_statements": total,
        "decision_counts": summary.decision_counts,
        "auto_patchable_rate": auto_rate,
        "conflict_reason_counts": summary.conflict_reason_counts,
        "patch_convergence_blocked_count": summary.patch_convergence_blocked_count,
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
