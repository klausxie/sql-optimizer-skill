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
from pathlib import Path

# Add python/ to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from sqlopt.application.run_service import RunService
from sqlopt.application.config_service import ConfigService


def main():
    parser = argparse.ArgumentParser(
        description="SQL Optimizer - MyBatis SQL Optimization Tool"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run command
    run_parser = subparsers.add_parser("run", help="Run optimization workflow")
    run_parser.add_argument("--config", "-c", required=True, help="Config file path")
    run_parser.add_argument("--mapper-path", help="Specific mapper path to optimize")
    run_parser.add_argument("--sql-key", help="Specific SQL key to optimize")

    # status command
    status_parser = subparsers.add_parser("status", help="Check run status")
    status_parser.add_argument("--run-id", help="Run ID")
    status_parser.add_argument("--project", help="Project directory")

    # resume command
    resume_parser = subparsers.add_parser("resume", help="Resume interrupted run")
    resume_parser.add_argument("--run-id", required=True, help="Run ID to resume")

    # apply command
    apply_parser = subparsers.add_parser("apply", help="Apply generated patches")
    apply_parser.add_argument("--run-id", required=True, help="Run ID")
    apply_parser.add_argument("--sql-key", help="Specific SQL key")

    # verify command
    verify_parser = subparsers.add_parser("verify", help="Verify optimization")
    verify_parser.add_argument("--run-id", required=True, help="Run ID")
    verify_parser.add_argument("--sql-key", required=True, help="SQL key")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Execute command
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
    config = ConfigService.load_config(args.config)
    service = RunService(config)
    run_id = service.run(mapper_path=args.mapper_path, sql_key=args.sql_key)
    print(f"Run started: {run_id}")
    return 0


def status_cmd(args):
    """Check run status"""
    from sqlopt.application.run_repository import RunRepository

    project_dir = args.project or "."
    repo = RunRepository(project_dir)

    if args.run_id:
        state = repo.load_state(args.run_id)
        print(f"Run: {args.run_id}")
        print(f"Phase: {state.get('phase', 'unknown')}")
        print(f"Current SQL: {state.get('current_sql_key', 'none')}")
    else:
        runs = repo.list_runs()
        print("Recent runs:")
        for run in runs[:10]:
            print(f"  {run['run_id']} - {run.get('phase', 'unknown')}")

    return 0


def resume_cmd(args):
    """Resume interrupted run"""
    config = {}  # Would load from saved config
    service = RunService(config)
    service.resume(args.run_id)
    print(f"Resumed run: {args.run_id}")
    return 0


def apply_cmd(args):
    """Apply patches"""
    print(f"Applying patches for run: {args.run_id}")
    # Implementation would go here
    return 0


def verify_cmd(args):
    """Verify optimization"""
    print(f"Verifying SQL: {args.sql_key}")
    # Implementation would go here
    return 0


if __name__ == "__main__":
    sys.exit(main())
