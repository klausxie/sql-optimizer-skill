#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = REPO_ROOT / "tests" / "fixtures" / "projects" / "sample_project" / "sqlopt.yml"
SQL_OPT_CLI_PATH = REPO_ROOT / "scripts" / "sqlopt_cli.py"
IF_GUARDED_SAMPLE_SQL_KEYS = (
    "demo.user.advanced.listUsersFilteredWrapped",
    "demo.user.advanced.listUsersFilteredAliased",
    "demo.user.advanced.listUsersFilteredQualifiedAliases",
    "demo.user.advanced.listUsersFilteredTableAliased",
    "demo.user.advanced.listUsersFilteredPredicateAliased",
    "demo.user.advanced.listUsersFilteredAliasedChoose",
    "demo.user.advanced.listUsersFilteredAliasedChooseContractBlocked",
    "demo.user.advanced.listUsersFilteredPredicateAliasedContractBlocked",
)
IF_GUARDED_COUNT_SAMPLE_SQL_KEYS = (
    "demo.user.advanced.countUsersWrapped",
    "demo.user.advanced.countUsersDirectFiltered",
    "demo.user.advanced.countUsersFilteredWrapped",
)
STATIC_INCLUDE_SAMPLE_SQL_KEYS = (
    "demo.user.listUsers",
    "demo.user.advanced.listUsersRecentPaged",
    "demo.user.advanced.listUsersViaStaticIncludeWrapped",
    "demo.user.advanced.listUsersRecentPagedWrapped",
)
STATIC_STATEMENT_SAMPLE_SQL_KEYS = (
    "demo.user.advanced.listUsersProjected",
    "demo.user.advanced.listUsersProjectedAliases",
    "demo.user.advanced.listUsersProjectedQualifiedAliases",
)
STATIC_ALIAS_PROJECTION_SAMPLE_SQL_KEYS = (
    "demo.user.advanced.listUsersProjectedAliases",
    "demo.user.advanced.listUsersProjectedQualifiedAliases",
)
GROUP_BY_WRAPPER_SAMPLE_SQL_KEYS = (
    "demo.order.harness.aggregateOrdersByStatus",
    "demo.order.harness.aggregateOrdersByStatusWrapped",
)
GROUP_BY_ALIAS_SAMPLE_SQL_KEYS = (
    "demo.order.harness.aggregateOrdersByStatusAliased",
)
HAVING_WRAPPER_SAMPLE_SQL_KEYS = (
    "demo.order.harness.listOrderUserCountsHaving",
    "demo.order.harness.listOrderUserCountsHavingWrapped",
)
HAVING_ALIAS_SAMPLE_SQL_KEYS = (
    "demo.order.harness.listOrderUserCountsHavingAliased",
)
STATIC_DISTINCT_SAMPLE_SQL_KEYS = (
    "demo.user.advanced.listDistinctUserStatuses",
    "demo.user.advanced.listDistinctUserStatusesWrapped",
    "demo.user.advanced.listDistinctUserStatusesAliased",
)
DISTINCT_ALIAS_SAMPLE_SQL_KEYS = (
    "demo.user.advanced.listDistinctUserStatusesAliased",
)
DISTINCT_WRAPPER_SAMPLE_SQL_KEYS = (
    "demo.user.advanced.listDistinctUserStatusesWrapped",
)
ORDER_BY_SAMPLE_SQL_KEYS = (
    "demo.user.advanced.listUsersOrderByConstant",
)
OR_SAMPLE_SQL_KEYS = (
    "demo.user.advanced.listUsersStatusOrPair",
)
CASE_SAMPLE_SQL_KEYS = (
    "demo.user.advanced.listUsersCaseWhenTrue",
)
COALESCE_SAMPLE_SQL_KEYS = (
    "demo.user.advanced.listUsersCoalesceIdentity",
)
EXPRESSION_SAMPLE_SQL_KEYS = (
    "demo.user.advanced.listUsersFoldedExpression",
)
LIMIT_SAMPLE_SQL_KEYS = (
    "demo.user.advanced.listUsersLargeLimit",
)
NULL_SAMPLE_SQL_KEYS = (
    "demo.user.advanced.listUsersEmailNullComparison",
)
DISTINCT_ON_SAMPLE_SQL_KEYS = (
    "demo.user.advanced.listUsersDistinctOnStatus",
)
EXISTS_SAMPLE_SQL_KEYS = (
    "demo.user.advanced.listUsersExistsSelfIdentity",
)
UNION_COLLAPSE_SAMPLE_SQL_KEYS = (
    "demo.shipment.harness.listShipmentStatusUnionWrapped",
)
BOOLEAN_SAMPLE_SQL_KEYS = (
    "demo.user.advanced.listUsersBooleanTautology",
)
IN_LIST_SAMPLE_SQL_KEYS = (
    "demo.user.advanced.listUsersStatusInSingle",
)
STATIC_WRAPPER_SAMPLE_SQL_KEYS = (
    "demo.shipment.harness.listRecentShipmentsPaged",
)
STATIC_UNION_SAMPLE_SQL_KEYS = (
    "demo.shipment.harness.listShipmentStatusUnion",
)
STATIC_WINDOW_SAMPLE_SQL_KEYS = (
    "demo.order.harness.listOrderAmountWindowRanks",
)
STATIC_CTE_SAMPLE_SQL_KEYS = (
    "demo.user.advanced.listRecentUsersViaCte",
)
FAMILY_SCOPE_SQL_KEYS = {
    "family": IF_GUARDED_SAMPLE_SQL_KEYS,
    "count-family": IF_GUARDED_COUNT_SAMPLE_SQL_KEYS,
    "include-family": STATIC_INCLUDE_SAMPLE_SQL_KEYS,
    "static-family": STATIC_STATEMENT_SAMPLE_SQL_KEYS,
    "alias-family": STATIC_ALIAS_PROJECTION_SAMPLE_SQL_KEYS,
    "groupby-family": GROUP_BY_WRAPPER_SAMPLE_SQL_KEYS,
    "groupby-alias-family": GROUP_BY_ALIAS_SAMPLE_SQL_KEYS,
    "having-family": HAVING_WRAPPER_SAMPLE_SQL_KEYS,
    "having-alias-family": HAVING_ALIAS_SAMPLE_SQL_KEYS,
    "distinct-family": STATIC_DISTINCT_SAMPLE_SQL_KEYS,
    "distinct-alias-family": DISTINCT_ALIAS_SAMPLE_SQL_KEYS,
    "distinct-wrapper-family": DISTINCT_WRAPPER_SAMPLE_SQL_KEYS,
    "orderby-family": ORDER_BY_SAMPLE_SQL_KEYS,
    "or-family": OR_SAMPLE_SQL_KEYS,
    "case-family": CASE_SAMPLE_SQL_KEYS,
    "coalesce-family": COALESCE_SAMPLE_SQL_KEYS,
    "expression-family": EXPRESSION_SAMPLE_SQL_KEYS,
    "limit-family": LIMIT_SAMPLE_SQL_KEYS,
    "null-family": NULL_SAMPLE_SQL_KEYS,
    "distinct-on-family": DISTINCT_ON_SAMPLE_SQL_KEYS,
    "exists-family": EXISTS_SAMPLE_SQL_KEYS,
    "union-collapse-family": UNION_COLLAPSE_SAMPLE_SQL_KEYS,
    "boolean-family": BOOLEAN_SAMPLE_SQL_KEYS,
    "in-list-family": IN_LIST_SAMPLE_SQL_KEYS,
    "wrapper-family": STATIC_WRAPPER_SAMPLE_SQL_KEYS,
    "union-family": STATIC_UNION_SAMPLE_SQL_KEYS,
    "window-family": STATIC_WINDOW_SAMPLE_SQL_KEYS,
    "cte-family": STATIC_CTE_SAMPLE_SQL_KEYS,
}


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
