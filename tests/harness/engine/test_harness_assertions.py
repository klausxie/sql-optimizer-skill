from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from sqlopt.devtools.harness.assertions import (
    assert_manifest_contains_stages,
    assert_phase_status,
    assert_report_generated,
    assert_report_rebuild_cleared,
    assert_run_completed,
)
from sqlopt.devtools.harness.runtime import HarnessHooks, load_run_artifacts, prepare_fixture_project, run_until_complete


def _write_cfg(td: str, project_root: Path, *, report_enabled: bool = True) -> Path:
    cfg = Path(td) / "sqlopt.assertions.json"
    cfg.write_text(
        json.dumps(
            {
                "project": {"root_path": str(project_root)},
                "scan": {"mapper_globs": ["src/main/resources/**/*.xml"]},
                "db": {
                    "platform": "postgresql",
                    "dsn": "postgresql://postgres:postgres@127.0.0.1:9/postgres?sslmode=disable",
                },
                "report": {"enabled": report_enabled},
                "llm": {"enabled": False, "provider": "heuristic"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return cfg


class HarnessAssertionsTest(unittest.TestCase):
    HOOKS = HarnessHooks(preflight_db_check={"name": "db", "enabled": True, "ok": True})

    def test_run_report_and_manifest_assertions_accept_completed_patch_generate_run(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_harness_assertions_") as td:
            handle = prepare_fixture_project(Path(td), mutable=True, init_git=True)
            cfg = _write_cfg(td, handle.root_path, report_enabled=True)
            run_id = f"run_assertions_{uuid4().hex[:8]}"

            result = run_until_complete(
                config_path=cfg,
                to_stage="patch_generate",
                run_id=run_id,
                repo_root=handle.root_path,
                hooks=self.HOOKS,
            )
            artifacts = load_run_artifacts(result.run_dir)

            assert_run_completed(artifacts)
            assert_phase_status(artifacts, "patch_generate", "DONE")
            assert_phase_status(artifacts, "report", "DONE")
            assert_report_generated(artifacts)
            assert_manifest_contains_stages(
                artifacts,
                ["preflight", "scan", "optimize", "validate", "patch_generate", "report"],
            )
            assert_report_rebuild_cleared(artifacts)


if __name__ == "__main__":
    unittest.main()
