#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from tempfile import TemporaryDirectory
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = REPO_ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from sqlopt.config import load_config
from sqlopt.devtools.sample_project_family_scopes import (
    BOOLEAN_SAMPLE_SQL_KEYS,
    CASE_SAMPLE_SQL_KEYS,
    COALESCE_SAMPLE_SQL_KEYS,
    DISTINCT_ALIAS_SAMPLE_SQL_KEYS,
    DISTINCT_ON_SAMPLE_SQL_KEYS,
    DISTINCT_WRAPPER_SAMPLE_SQL_KEYS,
    EXISTS_SAMPLE_SQL_KEYS,
    EXPRESSION_SAMPLE_SQL_KEYS,
    GENERALIZATION_BATCH1_SQL_KEYS,
    GENERALIZATION_BATCH2_SQL_KEYS,
    GENERALIZATION_BATCH3_SQL_KEYS,
    GENERALIZATION_BATCH4_SQL_KEYS,
    GENERALIZATION_BATCH5_SQL_KEYS,
    GENERALIZATION_BATCH6_SQL_KEYS,
    FAMILY_SCOPE_SQL_KEYS,
    GROUP_BY_ALIAS_SAMPLE_SQL_KEYS,
    GROUP_BY_WRAPPER_SAMPLE_SQL_KEYS,
    HAVING_ALIAS_SAMPLE_SQL_KEYS,
    HAVING_WRAPPER_SAMPLE_SQL_KEYS,
    IF_GUARDED_COUNT_SAMPLE_SQL_KEYS,
    IF_GUARDED_SAMPLE_SQL_KEYS,
    IN_LIST_SAMPLE_SQL_KEYS,
    LIMIT_SAMPLE_SQL_KEYS,
    NULL_SAMPLE_SQL_KEYS,
    OR_SAMPLE_SQL_KEYS,
    ORDER_BY_SAMPLE_SQL_KEYS,
    STATIC_ALIAS_PROJECTION_SAMPLE_SQL_KEYS,
    STATIC_CTE_SAMPLE_SQL_KEYS,
    STATIC_DISTINCT_SAMPLE_SQL_KEYS,
    STATIC_INCLUDE_SAMPLE_SQL_KEYS,
    STATIC_STATEMENT_SAMPLE_SQL_KEYS,
    STATIC_UNION_SAMPLE_SQL_KEYS,
    STATIC_WINDOW_SAMPLE_SQL_KEYS,
    STATIC_WRAPPER_SAMPLE_SQL_KEYS,
    UNION_COLLAPSE_SAMPLE_SQL_KEYS,
)

DEFAULT_CONFIG_PATH = REPO_ROOT / "tests" / "fixtures" / "projects" / "sample_project" / "sqlopt.yml"
DEFAULT_LLM_CASSETTE_ROOT = REPO_ROOT / "tests" / "fixtures" / "llm_cassettes"
SQL_OPT_CLI_PATH = REPO_ROOT / "scripts" / "sqlopt_cli.py"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the repository sample_project with project, family, mapper, or sql scope.")
    parser.add_argument(
        "--scope",
        default="project",
        choices=("project", *FAMILY_SCOPE_SQL_KEYS.keys(), "mapper", "sql"),
        help="Run scope (default: project).",
    )
    parser.add_argument(
        "--config",
        help=f"Override config path (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--llm-mode",
        default="replay",
        choices=("live", "record", "replay"),
        help="Override llm.mode in the resolved config (default: replay).",
    )
    parser.add_argument(
        "--llm-cassette-root",
        default=str(DEFAULT_LLM_CASSETTE_ROOT),
        help="Override llm.cassette_root in the resolved config (default: tests/fixtures/llm_cassettes).",
    )
    llm_replay_group = parser.add_mutually_exclusive_group()
    llm_replay_group.add_argument(
        "--llm-replay-strict",
        dest="llm_replay_strict",
        action="store_true",
        help="Fail on replay misses instead of falling back.",
    )
    llm_replay_group.add_argument(
        "--no-llm-replay-strict",
        dest="llm_replay_strict",
        action="store_false",
        help="Allow replay misses to be handled by the caller.",
    )
    parser.set_defaults(llm_replay_strict=True)
    parser.add_argument(
        "--llm-provider",
        help="Optional llm.provider override in the resolved config.",
    )
    parser.add_argument(
        "--llm-model",
        help="Optional llm.model override in the resolved config.",
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
        default=[],
        help="SQL key(s); required for --scope sql.",
    )
    parser.add_argument("--to-stage", default="patch_generate")
    parser.add_argument("--run-id")
    parser.add_argument("--max-steps", type=int, default=0)
    parser.add_argument("--max-seconds", type=int, default=120)
    return parser


def _write_resolved_config_overlay(
    base_config_path: Path,
    *,
    workspace: Path,
    llm_mode: str,
    llm_cassette_root: Path,
    llm_replay_strict: bool,
    llm_provider: str | None = None,
    llm_model: str | None = None,
) -> Path:
    resolved_config = load_config(base_config_path)
    llm_cfg = dict(resolved_config.get("llm") or {})
    llm_cfg["mode"] = llm_mode
    llm_cfg["cassette_root"] = str(Path(llm_cassette_root).resolve())
    llm_cfg["replay_strict"] = bool(llm_replay_strict)
    if llm_provider is not None:
        llm_cfg["provider"] = llm_provider
    if llm_model is not None:
        llm_cfg["model"] = llm_model
        provider = str(llm_cfg.get("provider") or "").strip()
        if provider == "opencode_run":
            llm_cfg["opencode_model"] = llm_model
        elif provider == "direct_openai_compatible":
            llm_cfg["api_model"] = llm_model
    resolved_config["llm"] = llm_cfg
    overlay_path = workspace / "config.resolved.json"
    overlay_path.write_text(json.dumps(resolved_config, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return overlay_path


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
    elif scope in FAMILY_SCOPE_SQL_KEYS:
        if mapper_paths:
            raise ValueError(f"{scope} scope does not accept mapper-path filters")
        sql_keys = list(FAMILY_SCOPE_SQL_KEYS[scope])
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
    with TemporaryDirectory(prefix="sqlopt_sample_project_config_") as td:
        resolved_config_path = _write_resolved_config_overlay(
            Path(args.config).resolve() if args.config else DEFAULT_CONFIG_PATH,
            workspace=Path(td),
            llm_mode=args.llm_mode,
            llm_cassette_root=Path(args.llm_cassette_root),
            llm_replay_strict=bool(args.llm_replay_strict),
            llm_provider=args.llm_provider,
            llm_model=args.llm_model,
        )
        cmd = _build_sqlopt_cli_args(
            scope=args.scope,
            config=str(resolved_config_path),
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
