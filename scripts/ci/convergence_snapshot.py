#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from sqlopt.devtools.harness.benchmark import snapshot_from_artifacts  # noqa: E402
from sqlopt.devtools.harness.runtime import load_run_artifacts  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print convergence-focused benchmark snapshot for a run directory.")
    parser.add_argument("run_dir", type=Path, help="run directory path")
    parser.add_argument("--format", choices=("json", "text"), default="json")
    parser.add_argument("--top", type=int, default=5, help="top-N conflict reasons in text output")
    return parser.parse_args()


def _top_counts(counts: dict[str, int], n: int) -> list[tuple[str, int]]:
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[: max(int(n), 0)]


def main() -> None:
    args = _parse_args()
    run_dir = Path(args.run_dir).resolve()
    artifacts = load_run_artifacts(run_dir)
    snapshot = snapshot_from_artifacts(artifacts)
    payload = {
        "run_id": snapshot.run_id,
        "status": snapshot.status,
        "verdict": snapshot.verdict,
        "next_action": snapshot.next_action,
        "convergence_decision_counts": snapshot.convergence_decision_counts,
        "convergence_conflict_reason_counts": snapshot.convergence_conflict_reason_counts,
        "convergence_shape_family_counts": snapshot.convergence_shape_family_counts,
        "patch_convergence_blocked_count": snapshot.patch_convergence_blocked_count,
    }

    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False))
        return

    print(f"run_id={payload['run_id']}")
    print(f"status={payload['status']} verdict={payload['verdict']} next_action={payload['next_action']}")
    print(f"convergence_decisions={payload['convergence_decision_counts']}")
    print(f"patch_convergence_blocked_count={payload['patch_convergence_blocked_count']}")
    print("top_conflict_reasons:")
    for code, count in _top_counts(snapshot.convergence_conflict_reason_counts, args.top):
        print(f"  - {code}: {count}")


if __name__ == "__main__":
    main()
