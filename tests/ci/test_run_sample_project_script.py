from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from sqlopt.devtools.sample_project_family_scopes import (
    FAMILY_SCOPE_SQL_KEYS as EXPORTED_FAMILY_SCOPE_SQL_KEYS,
    GENERALIZATION_BATCH_SCOPE_SQL_KEYS,
)


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "run_sample_project.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("run_sample_project_script", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class RunSampleProjectScriptTest(unittest.TestCase):
    def test_help_runs_without_pythonpath_bootstrap(self) -> None:
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        proc = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--help"],
            cwd=str(SCRIPT_PATH.parents[1]),
            env=env,
            capture_output=True,
            text=True,
        )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Run scope", proc.stdout)

    def test_family_scope_registry_is_loaded_from_shared_module(self) -> None:
        mod = _load_module()

        self.assertEqual(mod.FAMILY_SCOPE_SQL_KEYS, EXPORTED_FAMILY_SCOPE_SQL_KEYS)

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
        self.assertIn("generalization-batch1", mod.FAMILY_SCOPE_SQL_KEYS)
        self.assertIn("generalization-batch2", mod.FAMILY_SCOPE_SQL_KEYS)
        self.assertIn("generalization-batch3", mod.FAMILY_SCOPE_SQL_KEYS)
        self.assertIn("generalization-batch4", mod.FAMILY_SCOPE_SQL_KEYS)
        self.assertIn("generalization-batch5", mod.FAMILY_SCOPE_SQL_KEYS)
        self.assertIn("generalization-batch6", mod.FAMILY_SCOPE_SQL_KEYS)
        self.assertEqual(mod.FAMILY_SCOPE_SQL_KEYS["exists-family"], mod.EXISTS_SAMPLE_SQL_KEYS)
        self.assertEqual(mod.FAMILY_SCOPE_SQL_KEYS["exists-family"], ("demo.user.advanced.listUsersExistsSelfIdentity",))
        self.assertEqual(
            {name: mod.FAMILY_SCOPE_SQL_KEYS[name] for name in GENERALIZATION_BATCH_SCOPE_SQL_KEYS},
            GENERALIZATION_BATCH_SCOPE_SQL_KEYS,
        )

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

    def test_build_resolved_config_overlay_defaults_to_replay(self) -> None:
        mod = _load_module()

        with TemporaryDirectory(prefix="sqlopt_sample_project_overlay_") as td:
            workspace = Path(td)
            resolved_path = mod._write_resolved_config_overlay(
                mod.DEFAULT_CONFIG_PATH,
                workspace=workspace,
                llm_mode="replay",
                llm_cassette_root=mod.DEFAULT_LLM_CASSETTE_ROOT,
                llm_replay_strict=True,
            )
            payload = json.loads(resolved_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["llm"]["mode"], "replay")
        self.assertEqual(payload["llm"]["cassette_root"], str(mod.DEFAULT_LLM_CASSETTE_ROOT.resolve()))
        self.assertTrue(payload["llm"]["replay_strict"])
        self.assertEqual(payload["llm"]["provider"], "opencode_run")

    def test_build_resolved_config_overlay_can_override_provider_and_model(self) -> None:
        mod = _load_module()

        with TemporaryDirectory(prefix="sqlopt_sample_project_overlay_") as td:
            workspace = Path(td)
            resolved_path = mod._write_resolved_config_overlay(
                mod.DEFAULT_CONFIG_PATH,
                workspace=workspace,
                llm_mode="record",
                llm_cassette_root=workspace / "cassettes",
                llm_replay_strict=False,
                llm_provider="heuristic",
                llm_model="fixture-model",
            )
            payload = json.loads(resolved_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["llm"]["mode"], "record")
        self.assertEqual(payload["llm"]["provider"], "heuristic")
        self.assertEqual(payload["llm"]["model"], "fixture-model")
        self.assertFalse(payload["llm"]["replay_strict"])

    def test_main_defaults_developer_runs_to_replay_overlay(self) -> None:
        mod = _load_module()
        seen: dict[str, object] = {}

        def fake_run(cmd, **kwargs):
            seen["cmd"] = list(cmd)
            seen["cwd"] = kwargs.get("cwd")
            config_path = Path(cmd[cmd.index("--config") + 1])
            seen["config_payload"] = json.loads(config_path.read_text(encoding="utf-8"))
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with (
            mock.patch.object(sys, "argv", [str(SCRIPT_PATH), "--scope", "family", "--max-seconds", "1"]),
            mock.patch.object(mod.subprocess, "run", side_effect=fake_run),
        ):
            with self.assertRaises(SystemExit) as ctx:
                mod.main()

        payload = seen["config_payload"]
        self.assertEqual(payload["llm"]["mode"], "replay")
        self.assertTrue(payload["llm"]["replay_strict"])
        self.assertEqual(payload["llm"]["cassette_root"], str(mod.DEFAULT_LLM_CASSETTE_ROOT.resolve()))
        self.assertIn("cmd", seen)
        self.assertIn("--config", seen["cmd"])
        self.assertEqual(seen["cwd"], str(mod.REPO_ROOT))
        self.assertEqual(ctx.exception.code, 0)

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

    def test_generalization_batch1_scope_expands_curated_sql_keys(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="generalization-batch1",
            config=None,
            to_stage="patch_generate",
            run_id="run_generalization_batch1",
            max_steps=0,
            max_seconds=120,
            mapper_paths=[],
            sql_keys=[],
        )
        sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
        self.assertEqual(sql_key_values, list(mod.GENERALIZATION_BATCH1_SQL_KEYS))
        self.assertEqual(
            sql_key_values,
            [
                "demo.user.findUsers",
                "demo.user.countUser",
                "demo.shipment.harness.findShipments",
                "demo.order.harness.listOrdersWithUsersPaged",
                "demo.test.complex.fromClauseSubquery",
            ],
        )

    def test_generalization_batch2_scope_expands_curated_sql_keys(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="generalization-batch2",
            config=None,
            to_stage="patch_generate",
            run_id="run_generalization_batch2",
            max_steps=0,
            max_seconds=120,
            mapper_paths=[],
            sql_keys=[],
        )
        sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
        self.assertEqual(sql_key_values, list(mod.GENERALIZATION_BATCH2_SQL_KEYS))
        self.assertEqual(
            sql_key_values,
            [
                "demo.test.complex.wrapperCount",
                "demo.test.complex.multiFragmentLevel1",
                "demo.test.complex.staticSimpleSelect",
                "demo.test.complex.inSubquery",
                "demo.user.advanced.findUsersByKeyword",
            ],
        )

    def test_generalization_batch3_scope_expands_curated_sql_keys(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="generalization-batch3",
            config=None,
            to_stage="patch_generate",
            run_id="run_generalization_batch3",
            max_steps=0,
            max_seconds=120,
            mapper_paths=[],
            sql_keys=[],
        )
        sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
        self.assertEqual(sql_key_values, list(mod.GENERALIZATION_BATCH3_SQL_KEYS))
        self.assertEqual(
            sql_key_values,
            [
                "demo.test.complex.includeSimple",
                "demo.test.complex.multiFragmentLevel2",
                "demo.test.complex.staticOrderBy",
                "demo.test.complex.existsSubquery",
                "demo.test.complex.leftJoinWithNull",
            ],
        )

    def test_generalization_batch4_scope_expands_curated_sql_keys(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="generalization-batch4",
            config=None,
            to_stage="patch_generate",
            run_id="run_generalization_batch4",
            max_steps=0,
            max_seconds=120,
            mapper_paths=[],
            sql_keys=[],
        )
        sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
        self.assertEqual(
            sql_key_values,
            [
                "demo.order.harness.findOrdersByNos",
                "demo.order.harness.findOrdersByUserIdsAndStatus",
                "demo.shipment.harness.findShipmentsByOrderIds",
                "demo.test.complex.fragmentMultiplePlaces",
                "demo.test.complex.multiFragmentSeparate",
            ],
        )

    def test_generalization_batch5_scope_expands_curated_sql_keys(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="generalization-batch5",
            config=None,
            to_stage="patch_generate",
            run_id="run_generalization_batch5",
            max_steps=0,
            max_seconds=120,
            mapper_paths=[],
            sql_keys=[],
        )
        sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
        self.assertEqual(sql_key_values, list(GENERALIZATION_BATCH_SCOPE_SQL_KEYS["generalization-batch5"]))

    def test_generalization_batch6_scope_expands_candidate_pool(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="generalization-batch6",
            config=None,
            to_stage="patch_generate",
            run_id="run_generalization_batch6",
            max_steps=0,
            max_seconds=120,
            mapper_paths=[],
            sql_keys=[],
        )
        sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
        self.assertEqual(sql_key_values, list(GENERALIZATION_BATCH_SCOPE_SQL_KEYS["generalization-batch6"]))
        self.assertIn("--run-id", args)
        self.assertIn("run_generalization_batch6", args)

    def test_generalization_batch7_scope_expands_candidate_pool(self) -> None:
        mod = _load_module()
        args = mod._build_sqlopt_cli_args(
            scope="generalization-batch7",
            config=None,
            to_stage="patch_generate",
            run_id="run_generalization_batch7",
            max_steps=0,
            max_seconds=120,
            mapper_paths=[],
            sql_keys=[],
        )
        sql_key_values = [args[idx + 1] for idx, value in enumerate(args) if value == "--sql-key"]
        self.assertEqual(sql_key_values, list(GENERALIZATION_BATCH_SCOPE_SQL_KEYS["generalization-batch7"]))
        self.assertIn("--run-id", args)
        self.assertIn("run_generalization_batch7", args)

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
