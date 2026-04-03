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


if __name__ == "__main__":
    unittest.main()
