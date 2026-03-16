from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlopt.stages import apply as apply_stage


class ApplyModeTest(unittest.TestCase):
    def test_default_mode_is_patch_only(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_apply_default_") as td:
            run_dir = Path(td)
            state = apply_stage.apply_from_config(run_dir)
        self.assertEqual(state.get("mode"), "PATCH_ONLY")
        self.assertFalse(state.get("applied"))
        self.assertIn("patch_results", state)

    def test_apply_in_place_runs_git_apply(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_apply_inplace_") as td:
            run_dir = Path(td)
            project_root = run_dir / "project"
            patch_dir = run_dir / "pipeline" / "patch_generate"
            project_root.mkdir(parents=True, exist_ok=True)
            patch_dir.mkdir(parents=True, exist_ok=True)
            patch_file = patch_dir / "a.patch"
            patch_file.write_text("dummy", encoding="utf-8")
            (run_dir / "overview").mkdir(parents=True, exist_ok=True)
            (run_dir / "overview" / "config.resolved.json").write_text(
                json.dumps(
                    {
                        "project": {"root_path": str(project_root)},
                        "apply": {"mode": "APPLY_IN_PLACE"},
                    }
                ),
                encoding="utf-8",
            )
            (patch_dir / "patch.results.jsonl").write_text(
                json.dumps({"patchFiles": [str(patch_file)]}) + "\n",
                encoding="utf-8",
            )

            with patch("sqlopt.stages.apply.subprocess.run") as run_mock:
                run_mock.return_value.returncode = 0
                run_mock.return_value.stdout = ""
                run_mock.return_value.stderr = ""
                state = apply_stage.apply_from_config(run_dir)

        self.assertTrue(state.get("applied"))
        self.assertEqual(state.get("mode"), "APPLY_IN_PLACE")
        self.assertEqual(state.get("applied_files"), [str(patch_file.resolve())])
        run_mock.assert_called_once()
        args, kwargs = run_mock.call_args
        self.assertEqual(args[0][:2], ["git", "apply"])
        self.assertEqual(Path(kwargs["cwd"]).resolve(), project_root.resolve())

    def test_apply_in_place_reports_skipped_patch_results_when_no_patch_files_exist(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_apply_skip_") as td:
            run_dir = Path(td)
            patch_dir = run_dir / "pipeline" / "patch_generate"
            overview_dir = run_dir / "overview"
            project_root = run_dir / "project"
            patch_dir.mkdir(parents=True, exist_ok=True)
            overview_dir.mkdir(parents=True, exist_ok=True)
            project_root.mkdir(parents=True, exist_ok=True)
            (overview_dir / "config.resolved.json").write_text(
                json.dumps(
                    {
                        "project": {"root_path": str(project_root)},
                        "apply": {"mode": "APPLY_IN_PLACE"},
                    }
                ),
                encoding="utf-8",
            )
            (patch_dir / "patch.results.jsonl").write_text(
                json.dumps({"patchFiles": [], "selectionReason": {"code": "PATCH_NOT_APPLICABLE"}}) + "\n",
                encoding="utf-8",
            )

            state = apply_stage.apply_from_config(run_dir)

        self.assertFalse(state["applied"])
        self.assertEqual(state["patch_results"]["result_count"], 1)
        self.assertEqual(state["patch_results"]["selected_count"], 0)
        self.assertEqual(state["patch_results"]["skipped_count"], 1)
        self.assertEqual(state["patch_results"]["skipped_reason_codes"], ["PATCH_NOT_APPLICABLE"])
        self.assertIn("skipped reasons", state["message"])


if __name__ == "__main__":
    unittest.main()
