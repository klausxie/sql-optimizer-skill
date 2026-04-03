#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = REPO_ROOT / "tests" / "fixtures" / "projects" / "sample_project" / "sqlopt.yml"
SQL_OPT_CLI_PATH = REPO_ROOT / "scripts" / "sqlopt_cli.py"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the repository sample_project with project, mapper, or sql scope.")
    parser.add_argument(
        "--scope",
        default="project",
        choices=("project", "mapper", "sql"),
        help="Run scope (default: project).",
    )
    parser.add_argument(
        "--config",
        help=f"Override config path (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--mapper-path",
        action="append",
        default=[],
        help="Mapper relative path(s); required for --scope mapper.",
    )
    parser.add_argument(
        "--sql-key",
        action="append",
        default=["demo.user.findUsers"],
        help="SQL key(s); required for --scope sql.",
    )
    parser.add_argument("--to-stage", default="patch_generate")
    parser.add_argument("--run-id")
    parser.add_argument("--max-steps", type=int, default=0)
    parser.add_argument("--max-seconds", type=int, default=120)
    return parser


def _build_sqlopt_cli_args(
    *,
    scope: str,
    config: str | None,
    to_stage: str,
    run_id: str | None,
    max_steps: int,
    max_seconds: int,
    mapper_paths: list[str],
    sql_keys: list[str],
) -> list[str]:
    if scope == "project":
        if mapper_paths or sql_keys:
            raise ValueError("project scope does not accept mapper-path or sql-key filters")
    elif scope == "mapper":
        if not mapper_paths:
            raise ValueError("mapper scope requires at least one --mapper-path")
    elif scope == "sql":
        if not sql_keys:
            raise ValueError("sql scope requires at least one --sql-key")
    else:
        raise ValueError(f"unsupported scope: {scope}")

    resolved_config = Path(config).resolve() if config else DEFAULT_CONFIG_PATH
    cmd = [
        "run",
        "--config",
        str(resolved_config),
        "--to-stage",
        to_stage,
        "--max-steps",
        str(max_steps),
        "--max-seconds",
        str(max_seconds),
    ]
    if run_id:
        cmd.extend(["--run-id", run_id])
    for mapper_path in mapper_paths:
        cmd.extend(["--mapper-path", mapper_path])
    for sql_key in sql_keys:
        cmd.extend(["--sql-key", sql_key])
    return cmd


def main() -> None:
    args = _build_parser().parse_args()
    cmd = _build_sqlopt_cli_args(
        scope=args.scope,
        config=args.config,
        to_stage=args.to_stage,
        run_id=args.run_id,
        max_steps=args.max_steps,
        max_seconds=args.max_seconds,
        mapper_paths=list(args.mapper_path or []),
        sql_keys=list(args.sql_key or []),
    )
    proc = subprocess.run([sys.executable, str(SQL_OPT_CLI_PATH), *cmd], cwd=str(REPO_ROOT))
    raise SystemExit(proc.returncode)


if __name__ == "__main__":
    main()
