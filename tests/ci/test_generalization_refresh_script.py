from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from sqlopt.devtools.sample_project_family_scopes import GENERALIZATION_BATCH_SCOPE_SQL_KEYS


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci" / "generalization_refresh.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("generalization_refresh_script", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class GeneralizationRefreshScriptTest(unittest.TestCase):
    def test_help_runs_without_pythonpath_bootstrap(self) -> None:
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("--batch", proc.stdout)
        self.assertNotIn("--scope", proc.stdout)

    def test_known_batch_names_are_accepted(self) -> None:
        mod = _load_module()

        with mock.patch.object(sys, "argv", [str(SCRIPT), "--batch", "generalization-batch1"]):
            args = mod._parse_args()
            self.assertEqual(args.batch, ["generalization-batch1"])

        for batch_name in GENERALIZATION_BATCH_SCOPE_SQL_KEYS:
            with self.subTest(batch_name=batch_name):
                with mock.patch.object(sys, "argv", [str(SCRIPT), "--batch", batch_name]):
                    args = mod._parse_args()
                    self.assertEqual(args.batch, [batch_name])

    def test_default_batches_cover_all_generalization_batches(self) -> None:
        mod = _load_module()

        with mock.patch.object(sys, "argv", [str(SCRIPT)]):
            args = mod._parse_args()

        self.assertEqual(args.batch, [])
        self.assertEqual(args.llm_mode, "replay")
        self.assertTrue(args.llm_replay_strict)
        self.assertTrue(str(args.llm_cassette_root).endswith("tests/fixtures/llm_cassettes"))
        self.assertEqual(mod._selected_batches(args.batch), list(GENERALIZATION_BATCH_SCOPE_SQL_KEYS))
        self.assertEqual(mod.GENERALIZATION_BATCH_NAMES, tuple(GENERALIZATION_BATCH_SCOPE_SQL_KEYS))

    def test_llm_flags_can_be_overridden(self) -> None:
        mod = _load_module()

        with mock.patch.object(
            sys,
            "argv",
            [
                str(SCRIPT),
                "--llm-mode",
                "record",
                "--llm-cassette-root",
                "/tmp/custom-cassettes",
                "--no-llm-replay-strict",
                "--llm-provider",
                "heuristic",
                "--llm-model",
                "fixture-model",
            ],
        ):
            args = mod._parse_args()

        self.assertEqual(args.llm_mode, "record")
        self.assertEqual(args.llm_cassette_root, "/tmp/custom-cassettes")
        self.assertFalse(args.llm_replay_strict)
        self.assertEqual(args.llm_provider, "heuristic")
        self.assertEqual(args.llm_model, "fixture-model")

    def test_selected_batches_preserve_batch6_when_requested_explicitly(self) -> None:
        mod = _load_module()

        selected = mod._selected_batches(["generalization-batch6"])

        self.assertEqual(selected, ["generalization-batch6"])

    def test_main_emits_requested_batch_run_ids(self) -> None:
        mod = _load_module()
        calls: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            calls.append(list(cmd))
            batch_name = cmd[cmd.index("--scope") + 1]
            return SimpleNamespace(returncode=0, stdout=str({"run_id": f"run_{batch_name.replace('-', '_')}"}) + "\n")

        buf = io.StringIO()
        with (
            mock.patch.object(
                sys,
                "argv",
                [
                    str(SCRIPT),
                    "--batch",
                    "generalization-batch2",
                    "--batch",
                    "generalization-batch4",
                    "--batch",
                    "generalization-batch5",
                    "--batch",
                    "generalization-batch6",
                ],
            ),
            mock.patch.object(mod.subprocess, "run", side_effect=fake_run),
            redirect_stdout(buf),
        ):
            mod.main()

        payload = json.loads(buf.getvalue())
        self.assertEqual(
            payload,
            {
                "batches": {
                    "generalization-batch2": "run_generalization_batch2",
                    "generalization-batch4": "run_generalization_batch4",
                    "generalization-batch5": "run_generalization_batch5",
                    "generalization-batch6": "run_generalization_batch6",
                }
            },
        )
        self.assertEqual(len(calls), 4)
        self.assertTrue(all("--max-seconds" in cmd for cmd in calls))
        self.assertTrue(all(cmd[cmd.index("--max-seconds") + 1] == "480" for cmd in calls))
        self.assertEqual(
            [cmd[cmd.index("--scope") + 1] for cmd in calls],
            ["generalization-batch2", "generalization-batch4", "generalization-batch5", "generalization-batch6"],
        )
        self.assertTrue(all(cmd[cmd.index("--llm-mode") + 1] == "replay" for cmd in calls))
        self.assertTrue(
            all(
                cmd[cmd.index("--llm-cassette-root") + 1].endswith("tests/fixtures/llm_cassettes")
                for cmd in calls
            )
        )
        self.assertTrue(all("--llm-replay-strict" in cmd for cmd in calls))

    def test_failed_batch_surfaces_stdout_and_stderr(self) -> None:
        mod = _load_module()

        def fake_run(*_args, **_kwargs):
            return SimpleNamespace(returncode=2, stdout="partial output\n", stderr="db unreachable\n")

        with mock.patch.object(mod.subprocess, "run", side_effect=fake_run):
            with self.assertRaises(RuntimeError) as ctx:
                mod._run_batch("generalization-batch1", max_seconds=480)

        message = str(ctx.exception)
        self.assertIn("generalization-batch1", message)
        self.assertIn("exit=2", message)
        self.assertIn("partial output", message)
        self.assertIn("db unreachable", message)


if __name__ == "__main__":
    unittest.main()
