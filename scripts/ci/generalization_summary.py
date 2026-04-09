#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from sqlopt.devtools.run_progress_summary import (  # noqa: E402
    BLOCKER_BUCKETS,
    blocker_bucket_counts,
    summarize_progress_metrics,
    summarize_run_progress,
)
from sqlopt.devtools.generalization_blocker_inventory import (  # noqa: E402
    BLOCKED_BOUNDARY_SQL_KEYS,
    READY_SENTINEL_SQL_KEYS,
    POST_BATCH7_SENTINELS,
)
from sqlopt.devtools.sample_project_family_scopes import GENERALIZATION_BATCH_SCOPE_SQL_KEYS  # noqa: E402


def _parse_batch_run(value: str) -> tuple[str, Path]:
    batch_name, sep, run_dir = str(value or "").partition("=")
    batch_name = batch_name.strip()
    run_dir = run_dir.strip()
    if not sep or not batch_name or not run_dir:
        raise argparse.ArgumentTypeError("expected <batch-name>=<run-dir>")
    if batch_name not in GENERALIZATION_BATCH_SCOPE_SQL_KEYS:
        raise argparse.ArgumentTypeError(f"unknown generalization batch: {batch_name}")
    return batch_name, Path(run_dir).resolve()


def _validate_batch_run_dir(batch_name: str, run_dir: Path) -> None:
    if not run_dir.exists() or not run_dir.is_dir():
        raise SystemExit(f"generalization batch run directory does not exist: {batch_name}={run_dir}")
    convergence_path = run_dir / "artifacts" / "statement_convergence.jsonl"
    if not convergence_path.exists():
        raise SystemExit(
            "generalization batch run is missing statement_convergence.jsonl: "
            f"{batch_name}={convergence_path}"
        )


def _validate_expected_statement_coverage(batch_name: str, summary) -> None:
    expected_statement_keys = {
        str(statement_key).strip()
        for statement_key in GENERALIZATION_BATCH_SCOPE_SQL_KEYS[batch_name]
        if str(statement_key).strip()
    }
    observed_statement_keys = {row.statement_key for row in summary.rows}
    missing_statement_keys = sorted(expected_statement_keys - observed_statement_keys)
    if missing_statement_keys:
        raise SystemExit(
            "generalization batch run is missing expected statements: "
            f"{batch_name} -> {', '.join(missing_statement_keys)}"
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize one or more generalization batch runs.")
    parser.add_argument(
        "--batch-run",
        action="append",
        default=[],
        type=_parse_batch_run,
        help="Batch/run pair in the form generalization-batchN=/abs/path/to/run_dir",
    )
    parser.add_argument("--format", choices=("json", "text"), default="json")
    parser.add_argument("--top", type=int, default=3, help="top-N blocked reasons in text output")
    return parser.parse_args()


def _statement_payload(summary) -> list[dict[str, object]]:
    return [
        {
            "statement_key": row.statement_key,
            "shape_family": row.shape_family,
            "convergence_decision": row.convergence_decision,
            "conflict_reason": row.conflict_reason,
            "patch_reason_code": row.patch_reason_code,
            "patch_files": list(row.patch_files),
        }
        for row in summary.rows
    ]


def _decision_focus(blocker_bucket_counts: dict[str, int]) -> str:
    ordered = list(BLOCKER_BUCKETS)
    ranked = [(bucket, int(blocker_bucket_counts.get(bucket, 0) or 0)) for bucket in ordered]
    ranked = [item for item in ranked if item[1] > 0]
    if not ranked:
        return "READY"
    return max(ranked, key=lambda item: (item[1], -ordered.index(item[0])))[0]


def _recommended_next_step(decision_focus: str) -> str:
    mapping = {
        "NO_PATCHABLE_CANDIDATE_SELECTED": "fix_shared_candidate_selection_gaps",
        "SEMANTIC_GATE_NOT_PASS": "fix_semantic_comparison_weaknesses",
        "VALIDATE_STATUS_NOT_PASS": "fix_validation_status_propagation",
        "SHAPE_FAMILY_NOT_TARGET": "curate_family_boundary_candidates",
        "OTHER": "inspect_misc_blockers",
        "READY": "expand_generalization_coverage",
    }
    return mapping.get(decision_focus, "inspect_misc_blockers")


def _conclusion_payload(blocker_bucket_counts: dict[str, int]) -> dict[str, object]:
    focus = _decision_focus(blocker_bucket_counts)
    return {
        "decision_focus": focus,
        "recommended_next_step": _recommended_next_step(focus),
    }


def _comparison_payload(rows) -> dict[str, int]:
    ready_regressions = sum(
        1
        for row in rows
        if row.statement_key in READY_SENTINEL_SQL_KEYS and row.convergence_decision != "AUTO_PATCHABLE"
    )
    blocked_boundary_regressions = sum(
        1
        for row in rows
        if row.statement_key in BLOCKED_BOUNDARY_SQL_KEYS and row.convergence_decision == "AUTO_PATCHABLE"
    )
    return {
        "ready_regressions": ready_regressions,
        "blocked_boundary_regressions": blocked_boundary_regressions,
    }


def _batch_observability_payload(batch_name: str, rows, blocker_bucket_counts: dict[str, int]) -> dict[str, object]:
    payload = {
        **_conclusion_payload(blocker_bucket_counts),
        **_comparison_payload(rows),
    }
    if batch_name == "generalization-batch7":
        payload["post_batch7_sentinels"] = {
            group_name: list(sql_keys)
            for group_name, sql_keys in POST_BATCH7_SENTINELS.items()
        }
    return payload


def main() -> None:
    args = _parse_args()
    if not args.batch_run:
        raise SystemExit("--batch-run is required at least once")

    batches: list[dict[str, object]] = []
    overall_decisions = {"AUTO_PATCHABLE": 0, "MANUAL_REVIEW": 0, "NOT_PATCHABLE": 0}
    overall_conflicts: dict[str, int] = {}
    overall_blocker_buckets = {bucket: 0 for bucket in BLOCKER_BUCKETS}
    overall_total = 0
    overall_blocked = 0
    overall_rows = []

    for batch_name, run_dir in args.batch_run:
        _validate_batch_run_dir(batch_name, run_dir)
        summary = summarize_run_progress(run_dir, statement_keys=GENERALIZATION_BATCH_SCOPE_SQL_KEYS[batch_name])
        _validate_expected_statement_coverage(batch_name, summary)
        metrics = summarize_progress_metrics(summary)
        blocker_bucket_counts_value = blocker_bucket_counts(summary.conflict_reason_counts)
        batch_payload = {
            "batch": batch_name,
            "run_dir": str(run_dir),
            "total_statements": summary.total_statements,
            "decision_counts": summary.decision_counts,
            "auto_patchable_rate": metrics["auto_patchable_rate"],
            "blocked_statement_count": metrics["blocked_statement_count"],
            "conflict_reason_counts": summary.conflict_reason_counts,
            "blocker_bucket_counts": blocker_bucket_counts_value,
            "patch_convergence_blocked_count": summary.patch_convergence_blocked_count,
            "statements": _statement_payload(summary),
            **_batch_observability_payload(batch_name, summary.rows, blocker_bucket_counts_value),
        }
        batches.append(batch_payload)
        overall_rows.extend(summary.rows)
        overall_total += summary.total_statements
        overall_blocked += summary.patch_convergence_blocked_count
        for key, value in summary.decision_counts.items():
            overall_decisions[key] = overall_decisions.get(key, 0) + value
        for key, value in summary.conflict_reason_counts.items():
            overall_conflicts[key] = overall_conflicts.get(key, 0) + value
        for key, value in blocker_bucket_counts_value.items():
            overall_blocker_buckets[key] = overall_blocker_buckets.get(key, 0) + value

    overall_metrics = {
        "auto_patchable_rate": (overall_decisions["AUTO_PATCHABLE"] / overall_total) if overall_total else 0.0,
        "blocked_statement_count": max(overall_total - overall_decisions["AUTO_PATCHABLE"], 0),
        "blocker_bucket_counts": overall_blocker_buckets,
    }
    comparison_payload = _comparison_payload(overall_rows)
    payload = {
        "batches": batches,
        "overall": {
            "total_statements": overall_total,
            "decision_counts": overall_decisions,
            **overall_metrics,
            "conflict_reason_counts": dict(sorted(overall_conflicts.items(), key=lambda item: (-item[1], item[0]))),
            "patch_convergence_blocked_count": overall_blocked,
            **_conclusion_payload(overall_blocker_buckets),
            **comparison_payload,
        },
    }

    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False))
        return

    for batch in batches:
        print(f"batch={batch['batch']}")
        print(f"run_dir={batch['run_dir']}")
        print(f"total_statements={batch['total_statements']}")
        print(f"decision_counts={batch['decision_counts']}")
        print(f"patch_convergence_blocked_count={batch['patch_convergence_blocked_count']}")
        print(f"ready_regressions={batch['ready_regressions']}")
        print(f"blocked_boundary_regressions={batch['blocked_boundary_regressions']}")
        print(f"decision_focus={batch['decision_focus']}")
        print(f"recommended_next_step={batch['recommended_next_step']}")
        if "post_batch7_sentinels" in batch:
            print(f"post_batch7_sentinels={batch['post_batch7_sentinels']}")
        top_conflicts = ",".join(
            f"{reason}:{count}"
            for reason, count in list(batch["conflict_reason_counts"].items())[: max(int(args.top), 0)]
        )
        print(f"top_conflict_reasons={top_conflicts}")
        for row in batch["statements"]:
            print(
                "statement="
                f"{row['statement_key']} decision={row['convergence_decision']} "
                f"reason={row['conflict_reason'] or '-'} patch_reason={row['patch_reason_code'] or '-'} "
                f"patch_files={len(row['patch_files'])}"
            )
        print("")

    print("overall:")
    print(f"total_statements={payload['overall']['total_statements']}")
    print(f"decision_counts={payload['overall']['decision_counts']}")
    print(f"auto_patchable_rate={payload['overall']['auto_patchable_rate']:.4f}")
    print(f"blocked_statement_count={payload['overall']['blocked_statement_count']}")
    print(f"blocker_bucket_counts={payload['overall']['blocker_bucket_counts']}")
    print(f"patch_convergence_blocked_count={payload['overall']['patch_convergence_blocked_count']}")
    top_overall_conflicts = ",".join(
        f"{reason}:{count}"
        for reason, count in list(payload["overall"]["conflict_reason_counts"].items())[: max(int(args.top), 0)]
    )
    print(f"top_conflict_reasons={top_overall_conflicts}")
    print(f"ready_regressions={payload['overall']['ready_regressions']}")
    print(f"blocked_boundary_regressions={payload['overall']['blocked_boundary_regressions']}")
    print(f"decision_focus={payload['overall']['decision_focus']}")
    print(f"recommended_next_step={payload['overall']['recommended_next_step']}")


if __name__ == "__main__":
    main()
