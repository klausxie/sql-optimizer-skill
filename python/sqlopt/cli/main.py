#!/usr/bin/env python3
"""
SQL Optimizer CLI - Main Entry Point

Usage:
    sqlopt-cli run --config sqlopt.yml
    sqlopt-cli status --run-id <run_id>
    sqlopt-cli resume --run-id <run_id>
    sqlopt-cli apply --run-id <run_id>
    sqlopt-cli verify --run-id <run_id> --sql-key <sqlKey>
"""

import argparse
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from sqlopt.application import run_service
from sqlopt.run_paths import canonical_paths
from sqlopt.verification import read_verification_ledger, summarize_records


def main():
    parser = argparse.ArgumentParser(
        description="SQL Optimizer - MyBatis SQL Optimization Tool"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    run_parser = subparsers.add_parser("run", help="Run optimization workflow")
    run_parser.add_argument("--config", "-c", required=True, help="Config file path")
    run_parser.add_argument("--mapper-path", help="Specific mapper path to optimize")
    run_parser.add_argument("--sql-key", help="Specific SQL key to optimize")

    status_parser = subparsers.add_parser("status", help="Check run status")
    status_parser.add_argument("--run-id", help="Run ID")
    status_parser.add_argument("--project", help="Project directory")

    resume_parser = subparsers.add_parser("resume", help="Resume interrupted run")
    resume_parser.add_argument("--run-id", required=True, help="Run ID to resume")

    apply_parser = subparsers.add_parser("apply", help="Apply generated patches")
    apply_parser.add_argument("--run-id", required=True, help="Run ID")
    apply_parser.add_argument("--sql-key", help="Specific SQL key")

    verify_parser = subparsers.add_parser("verify", help="Verify optimization")
    verify_parser.add_argument("--run-id", help="Run ID")
    verify_parser.add_argument("--project", default=".", help="Project directory")
    verify_parser.add_argument("--sql-key", help="Specific SQL key to verify")
    verify_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed records"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        if args.command == "run":
            return run_cmd(args)
        elif args.command == "status":
            return status_cmd(args)
        elif args.command == "resume":
            return resume_cmd(args)
        elif args.command == "apply":
            return apply_cmd(args)
        elif args.command == "verify":
            return verify_cmd(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


def run_cmd(args):
    """Run optimization workflow"""
    config_path = Path(args.config)
    run_id, _ = run_service.start_run(
        config_path=config_path,
        to_stage="apply",
        run_id=None,
        repo_root=config_path.parent,
    )
    print(f"Run started: {run_id}")
    return 0


def status_cmd(args):
    """Check run status"""
    runs_dir = Path(args.project or ".") / "runs"
    if args.run_id:
        run_dir = runs_dir / args.run_id / "supervisor"
        state_file = run_dir / "state.json"
        if state_file.exists():
            with open(state_file) as f:
                state = json.load(f)
            print(f"Run: {args.run_id}")
            print(f"Phase: {state.get('phase', 'unknown')}")
        else:
            print(f"Run not found: {args.run_id}")
    else:
        if runs_dir.exists():
            runs = sorted(
                runs_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True
            )
            print("Recent runs:")
            for run in runs[:10]:
                print(f"  {run.name}")
        else:
            print("No runs found")
    return 0


def resume_cmd(args):
    """Resume interrupted run"""
    print(f"Resuming run: {args.run_id}")
    return 0


def apply_cmd(args):
    """Apply patches"""
    print(f"Applying patches for run: {args.run_id}")
    return 0


def verify_cmd(args):
    """Verify optimization evidence chain"""
    # Resolve run directory
    project_dir = Path(args.project or ".").resolve()
    runs_dir = project_dir / "runs"

    # Find run_id
    run_id = args.run_id
    if not run_id:
        # Find latest run
        if runs_dir.exists():
            runs = sorted(
                runs_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True
            )
            if runs:
                run_id = runs[0].name

    if not run_id:
        print(
            {
                "error": "No run found",
                "hint": "Specify --run-id or run from project directory",
            },
            file=sys.stderr,
        )
        return 1

    run_dir = runs_dir / run_id
    if not run_dir.exists():
        print({"error": f"Run not found: {run_id}"}, file=sys.stderr)
        return 1

    # Check verification ledger
    paths = canonical_paths(run_dir)
    ledger_path = paths.verification_ledger_path

    if not ledger_path.exists():
        print(
            {
                "run_id": run_id,
                "error": "Verification ledger not found",
                "hint": "Run sqlopt-cli run first to generate verification records",
            }
        )
        return 1

    try:
        records = read_verification_ledger(run_dir)
    except Exception as e:
        print({"run_id": run_id, "error": f"Failed to read verification ledger: {e}"})
        return 1

    # Filter by sql_key if specified
    if args.sql_key:
        records = [r for r in records if r.get("sql_key") == args.sql_key]
        if not records:
            print(
                {
                    "run_id": run_id,
                    "sql_key": args.sql_key,
                    "error": f"No verification records found for sql_key={args.sql_key}",
                }
            )
            return 1

    if args.verbose:
        # Detailed output
        result = {"run_id": run_id, "record_count": len(records), "records": records}
    else:
        # Summary output
        # Get total_sql from plan.json
        total_sql = 0
        plan_path = paths.plan_path
        if plan_path.exists():
            try:
                with open(plan_path, "r", encoding="utf-8") as f:
                    plan_data = json.load(f)
                    total_sql = len(plan_data.get("statements", []))
            except Exception:
                pass

        summary = summarize_records(run_id, records, total_sql=total_sql)
        result = summary.to_contract()

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
