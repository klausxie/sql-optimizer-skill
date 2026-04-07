from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "run_sample_project.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("run_sample_project_script", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class RunSampleProjectScriptTest(unittest.TestCase):
    def test_family_scope_registry_contains_stable_sample_project_groups(self) -> None:
        mod = _load_module()
        self.assertEqual(
            mod.FAMILY_SCOPE_SQL_KEYS["having-alias-family"],
            (
                "demo.order.harness.listOrderUserCountsHavingAliased",
            ),
        )
        self.assertIn("groupby-family", mod.FAMILY_SCOPE_SQL_KEYS)
        self.assertIn("having-family", mod.FAMILY_SCOPE_SQL_KEYS)
        self.assertIn("in-list-family", mod.FAMILY_SCOPE_SQL_KEYS)
        self.assertIn("or-family", mod.FAMILY_SCOPE_SQL_KEYS)
        self.assertIn("case-family", mod.FAMILY_SCOPE_SQL_KEYS)
        self.assertIn("coalesce-family", mod.FAMILY_SCOPE_SQL_KEYS)
        self.assertIn("expression-family", mod.FAMILY_SCOPE_SQL_KEYS)
        self.assertIn("limit-family", mod.FAMILY_SCOPE_SQL_KEYS)
        self.assertIn("null-family", mod.FAMILY_SCOPE_SQL_KEYS)
        self.assertIn("distinct-on-family", mod.FAMILY_SCOPE_SQL_KEYS)
        self.assertIn("exists-family", mod.FAMILY_SCOPE_SQL_KEYS)
        self.assertIn("union-collapse-family", mod.FAMILY_SCOPE_SQL_KEYS)

    def test_project_scope_uses_default_sample_project_config(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="project",
            config=None,
            to_stage="patch_generate",
            run_id=None,
            max_steps=0,
            max_seconds=120,
            mapper_paths=[],
            sql_keys=[],
        )
        self.assertEqual(args[0:5], ["run", "--config", str(mod.DEFAULT_CONFIG_PATH), "--to-stage", "patch_generate"])
        self.assertNotIn("--mapper-path", args)
        self.assertNotIn("--sql-key", args)
        self.assertEqual(args[-4:], ["--max-steps", "0", "--max-seconds", "120"])

    def test_mapper_scope_requires_mapper_path(self) -> None:
        mod = _load_module()
        with self.assertRaises(ValueError):
            mod._build_sqlopt_cli_args(
                scope="mapper",
                config=None,
                to_stage="patch_generate",
                run_id=None,
                max_steps=0,
                max_seconds=120,
                mapper_paths=[],
                sql_keys=[],
            )

    def test_mapper_scope_passes_mapper_paths(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="mapper",
            config=None,
            to_stage="patch_generate",
            run_id=None,
            max_steps=0,
            max_seconds=120,
            mapper_paths=["src/main/resources/com/example/mapper/user/advanced_user_mapper.xml"],
            sql_keys=[],
        )
        self.assertIn("--mapper-path", args)
        self.assertNotIn("--sql-key", args)

    def test_sql_scope_requires_sql_key(self) -> None:
        mod = _load_module()
        with self.assertRaises(ValueError):
            mod._build_sqlopt_cli_args(
                scope="sql",
                config=None,
                to_stage="patch_generate",
                run_id=None,
                max_steps=0,
                max_seconds=120,
                mapper_paths=[],
                sql_keys=[],
            )

    def test_sql_scope_passes_sql_keys(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="sql",
            config=None,
            to_stage="patch_generate",
            run_id="run_demo",
            max_steps=5,
            max_seconds=30,
            mapper_paths=[],
            sql_keys=["demo.user.advanced.listUsersFilteredAliased"],
        )
        self.assertIn("--sql-key", args)
        self.assertIn("demo.user.advanced.listUsersFilteredAliased", args)
        self.assertIn("--run-id", args)
        self.assertIn("run_demo", args)

    def test_project_scope_arguments_start_with_run_command(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="project",
            config=None,
            to_stage="report",
            run_id="run_demo",
            max_steps=5,
            max_seconds=30,
            mapper_paths=[],
            sql_keys=[],
        )
        self.assertEqual(args[:3], ["run", "--config", str(mod.DEFAULT_CONFIG_PATH)])
        self.assertIn("--to-stage", args)
        self.assertIn("report", args)

    def test_family_scope_expands_if_guarded_sql_keys(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="family",
            config=None,
            to_stage="patch_generate",
            run_id="run_if_guarded",
            max_steps=0,
            max_seconds=120,
            mapper_paths=[],
            sql_keys=[],
        )
        sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
        self.assertEqual(sql_key_values, list(mod.IF_GUARDED_SAMPLE_SQL_KEYS))
        self.assertIn("--run-id", args)
        self.assertIn("run_if_guarded", args)
        self.assertIn("demo.user.advanced.listUsersFilteredAliasedChoose", sql_key_values)
        self.assertIn("demo.user.advanced.listUsersFilteredAliasedChooseContractBlocked", sql_key_values)
        self.assertIn("demo.user.advanced.listUsersFilteredPredicateAliasedContractBlocked", sql_key_values)
        self.assertEqual(len(sql_key_values), 8)

    def test_count_family_scope_expands_if_guarded_count_wrapper_sql_keys(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="count-family",
            config=None,
            to_stage="patch_generate",
            run_id="run_if_guarded_count",
            max_steps=0,
            max_seconds=120,
            mapper_paths=[],
            sql_keys=[],
        )
        sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
        self.assertEqual(sql_key_values, list(mod.IF_GUARDED_COUNT_SAMPLE_SQL_KEYS))
        self.assertEqual(
            sql_key_values,
            [
                "demo.user.advanced.countUsersWrapped",
                "demo.user.advanced.countUsersDirectFiltered",
                "demo.user.advanced.countUsersFilteredWrapped",
            ],
        )
        self.assertIn("--run-id", args)
        self.assertIn("run_if_guarded_count", args)

    def test_in_list_family_scope_expands_single_value_in_list_sql_keys(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="in-list-family",
            config=None,
            to_stage="patch_generate",
            run_id="run_static_in_list",
            max_steps=0,
            max_seconds=120,
            mapper_paths=[],
            sql_keys=[],
        )
        sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
        self.assertEqual(sql_key_values, ["demo.user.advanced.listUsersStatusInSingle"])
        self.assertIn("--run-id", args)
        self.assertIn("run_static_in_list", args)

    def test_second_batch_static_family_scopes_expand_expected_sql_keys(self) -> None:
        mod = _load_module()
        cases = {
            "orderby-family": ["demo.user.advanced.listUsersOrderByConstant"],
            "or-family": ["demo.user.advanced.listUsersStatusOrPair"],
            "case-family": ["demo.user.advanced.listUsersCaseWhenTrue"],
            "coalesce-family": ["demo.user.advanced.listUsersCoalesceIdentity"],
            "expression-family": ["demo.user.advanced.listUsersFoldedExpression"],
        }

        for scope, expected_sql_keys in cases.items():
            with self.subTest(scope=scope):
                args = mod._build_sqlopt_cli_args(
                    scope=scope,
                    config=None,
                    to_stage="patch_generate",
                    run_id=f"run_{scope}",
                    max_steps=0,
                    max_seconds=120,
                    mapper_paths=[],
                    sql_keys=[],
                )
                sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
                self.assertEqual(sql_key_values, expected_sql_keys)

    def test_include_family_scope_expands_static_include_sql_keys(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="include-family",
            config=None,
            to_stage="patch_generate",
            run_id="run_static_include",
            max_steps=0,
            max_seconds=120,
            mapper_paths=[],
            sql_keys=[],
        )
        sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
        self.assertEqual(sql_key_values, list(mod.STATIC_INCLUDE_SAMPLE_SQL_KEYS))
        self.assertEqual(
            sql_key_values,
            [
                "demo.user.listUsers",
                "demo.user.advanced.listUsersRecentPaged",
                "demo.user.advanced.listUsersViaStaticIncludeWrapped",
                "demo.user.advanced.listUsersRecentPagedWrapped",
            ],
        )
        self.assertIn("--run-id", args)
        self.assertIn("run_static_include", args)

    def test_static_family_scope_expands_static_statement_sql_keys(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="static-family",
            config=None,
            to_stage="patch_generate",
            run_id="run_static_statement",
            max_steps=0,
            max_seconds=120,
            mapper_paths=[],
            sql_keys=[],
        )
        sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
        self.assertEqual(sql_key_values, list(mod.STATIC_STATEMENT_SAMPLE_SQL_KEYS))
        self.assertEqual(
            sql_key_values,
            [
                "demo.user.advanced.listUsersProjected",
                "demo.user.advanced.listUsersProjectedAliases",
                "demo.user.advanced.listUsersProjectedQualifiedAliases",
            ],
        )
        self.assertIn("--run-id", args)
        self.assertIn("run_static_statement", args)

    def test_alias_family_scope_expands_static_alias_projection_sql_keys(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="alias-family",
            config=None,
            to_stage="patch_generate",
            run_id="run_static_alias",
            max_steps=0,
            max_seconds=120,
            mapper_paths=[],
            sql_keys=[],
        )
        sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
        self.assertEqual(sql_key_values, list(mod.STATIC_ALIAS_PROJECTION_SAMPLE_SQL_KEYS))
        self.assertEqual(
            sql_key_values,
            [
                "demo.user.advanced.listUsersProjectedAliases",
                "demo.user.advanced.listUsersProjectedQualifiedAliases",
            ],
        )
        self.assertIn("--run-id", args)
        self.assertIn("run_static_alias", args)

    def test_groupby_family_scope_expands_groupby_wrapper_sql_keys(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="groupby-family",
            config=None,
            to_stage="patch_generate",
            run_id="run_groupby",
            max_steps=0,
            max_seconds=120,
            mapper_paths=[],
            sql_keys=[],
        )
        sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
        self.assertEqual(
            sql_key_values,
            [
                "demo.order.harness.aggregateOrdersByStatus",
                "demo.order.harness.aggregateOrdersByStatusWrapped",
            ],
        )
        self.assertIn("--run-id", args)
        self.assertIn("run_groupby", args)

    def test_having_family_scope_expands_having_wrapper_sql_keys(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="having-family",
            config=None,
            to_stage="patch_generate",
            run_id="run_having",
            max_steps=0,
            max_seconds=120,
            mapper_paths=[],
            sql_keys=[],
        )
        sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
        self.assertEqual(
            sql_key_values,
            [
                "demo.order.harness.listOrderUserCountsHaving",
                "demo.order.harness.listOrderUserCountsHavingWrapped",
            ],
        )
        self.assertIn("--run-id", args)
        self.assertIn("run_having", args)

    def test_having_alias_family_scope_expands_groupby_having_alias_sql_key(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="having-alias-family",
            config=None,
            to_stage="patch_generate",
            run_id="run_having_alias",
            max_steps=0,
            max_seconds=120,
            mapper_paths=[],
            sql_keys=[],
        )
        sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
        self.assertEqual(
            sql_key_values,
            [
                "demo.order.harness.listOrderUserCountsHavingAliased",
            ],
        )
        self.assertIn("--run-id", args)
        self.assertIn("run_having_alias", args)

    def test_groupby_alias_family_scope_expands_groupby_alias_sql_key(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="groupby-alias-family",
            config=None,
            to_stage="patch_generate",
            run_id="run_groupby_alias",
            max_steps=0,
            max_seconds=120,
            mapper_paths=[],
            sql_keys=[],
        )
        sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
        self.assertEqual(
            sql_key_values,
            [
                "demo.order.harness.aggregateOrdersByStatusAliased",
            ],
        )
        self.assertIn("--run-id", args)
        self.assertIn("run_groupby_alias", args)

    def test_distinct_family_scope_expands_static_distinct_sql_keys(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="distinct-family",
            config=None,
            to_stage="patch_generate",
            run_id="run_static_distinct",
            max_steps=0,
            max_seconds=120,
            mapper_paths=[],
            sql_keys=[],
        )
        sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
        self.assertEqual(sql_key_values, list(mod.STATIC_DISTINCT_SAMPLE_SQL_KEYS))
        self.assertEqual(
            sql_key_values,
            [
                "demo.user.advanced.listDistinctUserStatuses",
                "demo.user.advanced.listDistinctUserStatusesWrapped",
                "demo.user.advanced.listDistinctUserStatusesAliased",
            ],
        )
        self.assertIn("--run-id", args)
        self.assertIn("run_static_distinct", args)

    def test_distinct_alias_family_scope_expands_distinct_alias_sql_key(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="distinct-alias-family",
            config=None,
            to_stage="patch_generate",
            run_id="run_distinct_alias",
            max_steps=0,
            max_seconds=120,
            mapper_paths=[],
            sql_keys=[],
        )
        sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
        self.assertEqual(
            sql_key_values,
            [
                "demo.user.advanced.listDistinctUserStatusesAliased",
            ],
        )
        self.assertIn("--run-id", args)
        self.assertIn("run_distinct_alias", args)

    def test_distinct_wrapper_family_scope_expands_distinct_wrapper_sql_key(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="distinct-wrapper-family",
            config=None,
            to_stage="patch_generate",
            run_id="run_distinct_wrapper",
            max_steps=0,
            max_seconds=120,
            mapper_paths=[],
            sql_keys=[],
        )
        sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
        self.assertEqual(
            sql_key_values,
            [
                "demo.user.advanced.listDistinctUserStatusesWrapped",
            ],
        )
        self.assertIn("--run-id", args)
        self.assertIn("run_distinct_wrapper", args)

    def test_orderby_family_scope_expands_orderby_sql_key(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="orderby-family",
            config=None,
            to_stage="patch_generate",
            run_id="run_orderby",
            max_steps=0,
            max_seconds=120,
            mapper_paths=[],
            sql_keys=[],
        )
        sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
        self.assertEqual(
            sql_key_values,
            [
                "demo.user.advanced.listUsersOrderByConstant",
            ],
        )
        self.assertIn("--run-id", args)
        self.assertIn("run_orderby", args)

    def test_boolean_family_scope_expands_boolean_sql_key(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="boolean-family",
            config=None,
            to_stage="patch_generate",
            run_id="run_boolean",
            max_steps=0,
            max_seconds=120,
            mapper_paths=[],
            sql_keys=[],
        )
        sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
        self.assertEqual(
            sql_key_values,
            [
                "demo.user.advanced.listUsersBooleanTautology",
            ],
        )
        self.assertIn("--run-id", args)
        self.assertIn("run_boolean", args)

    def test_wrapper_family_scope_expands_static_wrapper_sql_keys(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="wrapper-family",
            config=None,
            to_stage="patch_generate",
            run_id="run_static_wrapper",
            max_steps=0,
            max_seconds=120,
            mapper_paths=[],
            sql_keys=[],
        )
        sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
        self.assertEqual(sql_key_values, list(mod.STATIC_WRAPPER_SAMPLE_SQL_KEYS))
        self.assertEqual(
            sql_key_values,
            [
                "demo.shipment.harness.listRecentShipmentsPaged",
            ],
        )
        self.assertIn("--run-id", args)
        self.assertIn("run_static_wrapper", args)

    def test_union_family_scope_expands_static_union_sql_keys(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="union-family",
            config=None,
            to_stage="patch_generate",
            run_id="run_static_union",
            max_steps=0,
            max_seconds=120,
            mapper_paths=[],
            sql_keys=[],
        )
        sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
        self.assertEqual(sql_key_values, list(mod.STATIC_UNION_SAMPLE_SQL_KEYS))
        self.assertEqual(
            sql_key_values,
            [
                "demo.shipment.harness.listShipmentStatusUnion",
            ],
        )
        self.assertIn("--run-id", args)
        self.assertIn("run_static_union", args)

    def test_window_family_scope_expands_static_window_sql_keys(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="window-family",
            config=None,
            to_stage="patch_generate",
            run_id="run_static_window",
            max_steps=0,
            max_seconds=120,
            mapper_paths=[],
            sql_keys=[],
        )
        sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
        self.assertEqual(sql_key_values, list(mod.STATIC_WINDOW_SAMPLE_SQL_KEYS))
        self.assertEqual(
            sql_key_values,
            [
                "demo.order.harness.listOrderAmountWindowRanks",
            ],
        )
        self.assertIn("--run-id", args)
        self.assertIn("run_static_window", args)

    def test_cte_family_scope_expands_static_cte_sql_keys(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="cte-family",
            config=None,
            to_stage="patch_generate",
            run_id="run_static_cte",
            max_steps=0,
            max_seconds=120,
            mapper_paths=[],
            sql_keys=[],
        )
        sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
        self.assertEqual(sql_key_values, list(mod.STATIC_CTE_SAMPLE_SQL_KEYS))
        self.assertEqual(
            sql_key_values,
            [
                "demo.user.advanced.listRecentUsersViaCte",
            ],
        )
        self.assertIn("--run-id", args)
        self.assertIn("run_static_cte", args)

    def test_third_batch_family_scopes_expand_expected_sql_keys(self) -> None:
        mod = _load_module()
        cases = {
            "limit-family": ["demo.user.advanced.listUsersLargeLimit"],
            "null-family": ["demo.user.advanced.listUsersEmailNullComparison"],
            "distinct-on-family": ["demo.user.advanced.listUsersDistinctOnStatus"],
            "exists-family": ["demo.user.advanced.listUsersExistsSelfIdentity"],
            "union-collapse-family": ["demo.shipment.harness.listShipmentStatusUnionWrapped"],
        }

        for scope, expected_sql_keys in cases.items():
            with self.subTest(scope=scope):
                args = mod._build_sqlopt_cli_args(
                    scope=scope,
                    config=None,
                    to_stage="patch_generate",
                    run_id=f"run_{scope}",
                    max_steps=0,
                    max_seconds=120,
                    mapper_paths=[],
                    sql_keys=[],
                )
                sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
                self.assertEqual(sql_key_values, expected_sql_keys)

    def test_sql_parser_defaults_to_no_sql_keys(self) -> None:
        mod = _load_module()
        parser = mod._build_parser()
        args = parser.parse_args([])
        self.assertEqual(args.sql_key, [])

    def test_project_scope_rejects_explicit_sql_filters(self) -> None:
        mod = _load_module()
        with self.assertRaises(ValueError):
            mod._build_sqlopt_cli_args(
                scope="project",
                config=None,
                to_stage="patch_generate",
                run_id=None,
                max_steps=0,
                max_seconds=120,
                mapper_paths=[],
                sql_keys=["demo.user.findUsers"],
            )


if __name__ == "__main__":
    unittest.main()
