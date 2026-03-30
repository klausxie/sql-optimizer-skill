from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from sqlopt.cli import build_parser


class CliHelpTextTest(unittest.TestCase):
    def _capture_help(self, argv: list[str]) -> str:
        parser = build_parser()
        buf = io.StringIO()
        with redirect_stdout(buf):
            with self.assertRaises(SystemExit) as ctx:
                parser.parse_args(argv)
        self.assertEqual(ctx.exception.code, 0)
        return buf.getvalue()

    def test_top_level_help_contains_workflow_and_defaults(self) -> None:
        text = self._capture_help(["--help"])
        self.assertIn("快速工作流", text)
        self.assertIn("sqlopt-cli run --config sqlopt.yml", text)
        self.assertIn("省略 --run-id 时自动选择最新 run", text)
        self.assertNotIn("verify", text)

    def test_run_help_contains_examples_and_continuous_default(self) -> None:
        text = self._capture_help(["run", "--help"])
        self.assertIn("默认会自动持续推进", text)
        self.assertIn("sqlopt-cli run --to-stage report --run-id <run-id>", text)
        self.assertIn("sqlopt-cli run --max-steps 3 --max-seconds 60", text)

    def test_resume_help_contains_latest_and_budget_examples(self) -> None:
        text = self._capture_help(["resume", "--help"])
        self.assertIn("默认会持续推进", text)
        self.assertIn("sqlopt-cli resume --project /path/to/project --max-steps 1", text)
        self.assertIn("自动选择最新运行", text)

if __name__ == "__main__":
    unittest.main()
