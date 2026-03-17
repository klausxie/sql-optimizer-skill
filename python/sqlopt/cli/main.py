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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from sqlopt.application import run_service


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
    verify_parser.add_argument("--run-id", required=True, help="Run ID")
    verify_parser.add_argument("--sql-key", required=True, help="SQL key")
    
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
            runs = sorted(runs_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
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
    """Verify optimization"""
    print(f"Verifying SQL: {args.sql_key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
