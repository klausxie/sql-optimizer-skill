from __future__ import annotations

import importlib.util
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
