from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from sqlopt.application import run_service

ROOT = Path(__file__).resolve().parents[3]


def run_cli(*args: str) -> dict:
    cmd = args[0]
    if cmd == "run":
        config = Path(args[args.index("--config") + 1]).resolve()
        to_stage = args[args.index("--to-stage") + 1]
        run_id = args[args.index("--run-id") + 1]
        with patch("sqlopt.stages.preflight.check_db_connectivity", return_value={"name": "db", "enabled": True, "ok": True}):
            resolved_run_id, result = run_service.start_run(config, to_stage, run_id, repo_root=ROOT)
        return {"run_id": resolved_run_id, "result": result}
    if cmd == "resume":
        run_id = args[args.index("--run-id") + 1]
        with patch("sqlopt.stages.preflight.check_db_connectivity", return_value={"name": "db", "enabled": True, "ok": True}):
            result = run_service.resume_run(run_id, repo_root=ROOT)
        return {"run_id": run_id, "result": result}
    if cmd == "status":
        run_id = args[args.index("--run-id") + 1]
        return run_service.get_status(run_id, repo_root=ROOT)
    raise ValueError(f"unsupported test command: {cmd}")


class WorkflowSupervisorTest(unittest.TestCase):
    def _write_cfg(self, td: str, *, report_enabled: bool = True, mapper_glob: str | None = None) -> Path:
        cfg = Path(td) / "sqlopt.yml"
        mapper = mapper_glob or "src/main/resources/com/example/mapper/user/user_mapper.xml"
        report_flag = "true" if report_enabled else "false"
        cfg.write_text(
            "\n".join(
                [
                    "project:",
                    f"  root_path: {str((ROOT / 'tests' / 'fixtures' / 'project').resolve())}",
                    "scan:",
                    "  mapper_globs:",
                    f"    - {mapper}",
                    "db:",
                    "  platform: postgresql",
                    "  dsn: postgresql://postgres:postgres@127.0.0.1:9/postgres?sslmode=disable",
                    "report:",
                    f"  enabled: {report_flag}",
                    "llm:",
                    "  enabled: false",
                    "  provider: heuristic",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return cfg

    def test_patch_generate_auto_finalizes_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_cfg_") as td:
            cfg = self._write_cfg(td)
            run_id = f"run_supervisor_auto_report_{uuid4().hex[:8]}"
            run_cli("run", "--config", str(cfg), "--to-stage", "patch_generate", "--run-id", run_id)
            for _ in range(80):
                status = run_cli("status", "--run-id", run_id)
                if status["complete"]:
                    break
                run_cli("resume", "--run-id", run_id)

        run_dir = ROOT / "tests" / "fixtures" / "project" / "runs" / run_id
        self.assertTrue((run_dir / "overview" / "report.json").exists())
        report = json.loads((run_dir / "overview" / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["stats"]["pipeline_coverage"]["report"], "DONE")
        meta = json.loads((run_dir / "pipeline" / "supervisor" / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta.get("status"), "COMPLETED")
        self.assertTrue((run_dir / "pipeline" / "supervisor" / "results" / "scan.jsonl").exists())
        self.assertTrue((run_dir / "pipeline" / "supervisor" / "results" / "preflight.jsonl").exists())
        self.assertTrue((run_dir / "pipeline" / "supervisor" / "results" / "optimize.jsonl").exists())
        self.assertTrue((run_dir / "pipeline" / "supervisor" / "results" / "validate.jsonl").exists())
        self.assertTrue((run_dir / "pipeline" / "supervisor" / "results" / "patch_generate.jsonl").exists())
        self.assertTrue((run_dir / "pipeline" / "supervisor" / "results" / "report.jsonl").exists())

    def test_optimize_stage_still_generates_report_by_default(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_cfg_") as td:
            cfg = self._write_cfg(td)
            run_id = f"run_supervisor_optimize_report_{uuid4().hex[:8]}"
            run_cli("run", "--config", str(cfg), "--to-stage", "optimize", "--run-id", run_id)
            for _ in range(80):
                status = run_cli("status", "--run-id", run_id)
                if status["complete"]:
                    break
                run_cli("resume", "--run-id", run_id)

        run_dir = ROOT / "tests" / "fixtures" / "project" / "runs" / run_id
        self.assertTrue((run_dir / "overview" / "report.json").exists())
        report = json.loads((run_dir / "overview" / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["stats"]["pipeline_coverage"]["report"], "DONE")
        state = json.loads((run_dir / "pipeline" / "supervisor" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["phase_status"]["optimize"], "DONE")
        self.assertEqual(state["phase_status"]["validate"], "SKIPPED")
        self.assertEqual(state["phase_status"]["patch_generate"], "SKIPPED")
        self.assertEqual(state["phase_status"]["report"], "DONE")

    def test_optimize_stage_skips_report_when_disabled(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_cfg_") as td:
            cfg = self._write_cfg(td, report_enabled=False)
            run_id = f"run_supervisor_optimize_no_report_{uuid4().hex[:8]}"
            run_cli("run", "--config", str(cfg), "--to-stage", "optimize", "--run-id", run_id)
            for _ in range(80):
                status = run_cli("status", "--run-id", run_id)
                if status["complete"]:
                    break
                run_cli("resume", "--run-id", run_id)

        run_dir = ROOT / "tests" / "fixtures" / "project" / "runs" / run_id
        self.assertFalse((run_dir / "overview" / "report.json").exists())
        state = json.loads((run_dir / "pipeline" / "supervisor" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["phase_status"]["report"], "SKIPPED")
        meta = json.loads((run_dir / "pipeline" / "supervisor" / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta.get("status"), "COMPLETED")

    def test_explicit_report_rebuild_does_not_append_duplicate_done_result(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_cfg_") as td:
            cfg = self._write_cfg(td)
            run_id = f"run_supervisor_report_rebuild_{uuid4().hex[:8]}"
            run_cli("run", "--config", str(cfg), "--to-stage", "patch_generate", "--run-id", run_id)
            for _ in range(80):
                status = run_cli("status", "--run-id", run_id)
                if status["complete"]:
                    break
                run_cli("resume", "--run-id", run_id)

            run_dir = ROOT / "tests" / "fixtures" / "project" / "runs" / run_id
            report_results = run_dir / "pipeline" / "supervisor" / "results" / "report.jsonl"
            before_lines = report_results.read_text(encoding="utf-8").strip().splitlines()

            run_cli("run", "--config", str(cfg), "--to-stage", "report", "--run-id", run_id)

        after_lines = report_results.read_text(encoding="utf-8").strip().splitlines()
        state = json.loads((run_dir / "pipeline" / "supervisor" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(len(before_lines), 1)
        self.assertEqual(len(after_lines), 1)
        self.assertFalse(state.get("report_rebuild_required", False))


if __name__ == "__main__":
    unittest.main()
