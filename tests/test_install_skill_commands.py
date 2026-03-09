from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def _load_install_skill_module():
    path = ROOT / "install" / "install_skill.py"
    spec = importlib.util.spec_from_file_location("install_skill_test_module", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InstallSkillCommandsTest(unittest.TestCase):
    def test_parse_args_supports_verify_flag(self) -> None:
        module = _load_install_skill_module()
        with patch.object(module.sys, "argv", ["install_skill.py", "--verify"]):
            args = module._parse_args()
        self.assertTrue(args.verify)
        self.assertEqual(args.project, ".")

    def test_parse_args_supports_no_auto_path_flag(self) -> None:
        module = _load_install_skill_module()
        with patch.object(module.sys, "argv", ["install_skill.py", "--no-auto-path"]):
            args = module._parse_args()
        self.assertTrue(args.no_auto_path)

    def test_is_dir_on_path_windows_case_insensitive(self) -> None:
        module = _load_install_skill_module()
        target = Path(r"C:\Users\A\.opencode\skills\sql-optimizer\bin")
        path_env = r'"C:\Tools\bin";C:\USERS\a\.opencode\skills\sql-optimizer\bin'
        with patch.object(module, "is_windows", return_value=True):
            self.assertTrue(module._is_dir_on_path(target, path_env))

    def test_is_dir_on_path_unix(self) -> None:
        module = _load_install_skill_module()
        target = Path("/tmp/sqlopt/bin")
        path_env = "/usr/local/bin:/tmp/sqlopt/bin:/usr/bin"
        with patch.object(module, "is_windows", return_value=False):
            self.assertTrue(module._is_dir_on_path(target, path_env))

    def test_prepend_path_entry_deduplicates_windows_paths(self) -> None:
        module = _load_install_skill_module()
        entry = Path(r"C:\Users\A\.opencode\skills\sql-optimizer\bin")
        merged = module._prepend_path_entry(
            r"C:\TOOLS\BIN;C:\Users\a\.opencode\skills\sql-optimizer\bin",
            entry,
            windows=True,
        )
        self.assertEqual(
            merged,
            r"C:\TOOLS\BIN;C:\Users\a\.opencode\skills\sql-optimizer\bin",
        )

    def test_choose_shell_rc_file_prefers_shell_type(self) -> None:
        module = _load_install_skill_module()
        home = Path("/tmp/home")
        zsh_rc = module._choose_shell_rc_file(home, "/bin/zsh")
        bash_rc = module._choose_shell_rc_file(home, "/bin/bash")
        self.assertEqual(zsh_rc, home / ".zshrc")
        self.assertEqual(bash_rc, home / ".bashrc")

    def test_run_cli_self_check_success(self) -> None:
        module = _load_install_skill_module()
        with tempfile.TemporaryDirectory(prefix="sqlopt_wrapper_") as td:
            wrapper = Path(td) / "sqlopt-cli"
            wrapper.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            completed = subprocess.CompletedProcess(
                args=["sqlopt-cli", "--help"],
                returncode=0,
                stdout="usage: sqlopt-cli\n",
                stderr="",
            )
            with patch.object(module, "cli_run_command", return_value=["sqlopt-cli", "--help"]):
                with patch.object(module.subprocess, "run", return_value=completed):
                    ok, detail = module._run_cli_self_check(wrapper)
        self.assertTrue(ok)
        self.assertIn("usage: sqlopt-cli", detail)

    def test_write_commands_runs_script_via_template_shell_execution(self) -> None:
        module = _load_install_skill_module()
        with tempfile.TemporaryDirectory(prefix="sqlopt_cmd_docs_") as td:
            command_dir = Path(td) / "commands"
            target_skill = Path(td) / "skill"

            with patch.object(module, "commands_dir", return_value=command_dir):
                with patch.object(module, "_get_python_command", return_value="python"):
                    module._write_commands(target_skill)

            run_doc = (command_dir / "sql-optimizer-run.md").read_text(encoding="utf-8")
            status_doc = (command_dir / "sql-optimizer-status.md").read_text(encoding="utf-8")

        self.assertIn("你必须立刻调用一次 bash 工具，且只调用这一次。", run_doc)
        self.assertIn("当 `$ARGUMENTS` 为空时，执行：", run_doc)
        self.assertIn("`python", run_doc)
        self.assertIn("run_until_budget.py $ARGUMENTS`", run_doc)
        self.assertNotIn("<config>", run_doc)
        self.assertNotIn("<to_stage>", run_doc)
        self.assertNotIn("<run_id>", run_doc)
        self.assertNotIn("argument-hint:", run_doc)
        self.assertIn("不要调用 skill 工具，不要读取/修改文件，不要先提问", run_doc)
        self.assertIn("当使用 `$ARGUMENTS` 时，必须按原样直接拼接，不要整体加引号。", run_doc)
        self.assertIn("命令结束后，仅返回 bash 的原始输出。", run_doc)

        self.assertIn("run_with_resolved_id.py status $ARGUMENTS`", status_doc)

    def test_command_doc_uses_template_shell_not_code_block(self) -> None:
        module = _load_install_skill_module()
        with tempfile.TemporaryDirectory(prefix="sqlopt_cmd_docs_empty_") as td:
            command_dir = Path(td) / "commands"
            target_skill = Path(td) / "skill"

            with patch.object(module, "commands_dir", return_value=command_dir):
                with patch.object(module, "_get_python_command", return_value="python"):
                    module._write_commands(target_skill)

            run_doc = (command_dir / "sql-optimizer-run.md").read_text(encoding="utf-8")

        self.assertNotIn("```", run_doc)
        self.assertNotIn("!`", run_doc)
        self.assertIn("`python", run_doc)

    def test_retire_legacy_skill_backups_disables_skill_markers(self) -> None:
        module = _load_install_skill_module()
        with tempfile.TemporaryDirectory(prefix="sqlopt_skill_backups_") as td:
            skills_root = Path(td) / "skills"
            first_backup = skills_root / "sql-optimizer.bak.1"
            second_backup = skills_root / "sql-optimizer.bak.2"
            first_backup.mkdir(parents=True)
            second_backup.mkdir(parents=True)
            (first_backup / "SKILL.md").write_text("name: sql-optimizer", encoding="utf-8")
            (second_backup / "SKILL.md").write_text("name: sql-optimizer", encoding="utf-8")

            retired = module._retire_legacy_skill_backups(skills_root)
            self.assertEqual(retired, 2)
            self.assertFalse((first_backup / "SKILL.md").exists())
            self.assertFalse((second_backup / "SKILL.md").exists())
            self.assertTrue((first_backup / "SKILL.md.disabled").exists())
            self.assertTrue((second_backup / "SKILL.md.disabled").exists())


if __name__ == "__main__":
    unittest.main()
