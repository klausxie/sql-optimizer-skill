from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlopt import cli
from sqlopt.application import run_index
from sqlopt.io_utils import write_json


class RunIndexResolutionTest(unittest.TestCase):
    def test_resolve_run_dir_falls_back_to_runs_scan(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_run_index_") as td:
            repo = Path(td)
            run_id = "run_fallback_1"
            run_dir = repo / "tests" / "fixtures" / "project" / "runs" / run_id
            (run_dir / "pipeline" / "supervisor").mkdir(parents=True, exist_ok=True)
            write_json(run_dir / "pipeline" / "supervisor" / "meta.json", {"run_id": run_id})
            with patch("sqlopt.cli._repo_root", return_value=repo):
                resolved = cli._resolve_run_dir(run_id)
                self.assertEqual(resolved.resolve(), run_dir.resolve())

    def test_resolve_run_dir_ignores_legacy_index_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_run_index_legacy_") as td:
            repo = Path(td)
            legacy_index = repo / ".sqlopt-run-index.json"
            legacy_run = repo / "legacy_project" / "runs" / "run_legacy_1"
            legacy_run.mkdir(parents=True, exist_ok=True)
            write_json(legacy_index, {"run_legacy_1": {"run_dir": str(legacy_run)}})
            with self.assertRaises(FileNotFoundError):
                run_index.resolve_run_dir("run_legacy_1", repo_root_fn=lambda: repo)


if __name__ == "__main__":
    unittest.main()
