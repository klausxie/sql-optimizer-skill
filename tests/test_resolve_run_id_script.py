from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "resolve_run_id.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("resolve_run_id_script", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class ResolveRunIdScriptTest(unittest.TestCase):
    def test_resolve_latest_from_index(self) -> None:
        mod = _load_module()
        with tempfile.TemporaryDirectory(prefix="sqlopt_resolve_idx_") as td:
            repo = Path(td)
            project = repo / "project"
            run_old = project / "runs" / "run_old"
            run_new = project / "runs" / "run_new"
            (run_old / "pipeline" / "supervisor").mkdir(parents=True, exist_ok=True)
            (run_new / "pipeline" / "supervisor").mkdir(parents=True, exist_ok=True)
            (project / "runs" / "index.json").write_text(json.dumps({
                "run_old": {"run_dir": str(run_old), "updated_at": "2026-02-01T00:00:00+00:00"},
                "run_new": {"run_dir": str(run_new), "updated_at": "2026-02-02T00:00:00+00:00"},
            }), encoding="utf-8")
            with patch.object(mod, "_repo_root", return_value=repo):
                rid, run_dir = mod.resolve_run_id(None, str(project))
            self.assertEqual(rid, "run_new")
            self.assertEqual(run_dir.resolve(), run_new.resolve())

    def test_resolve_by_scan_when_index_missing(self) -> None:
        mod = _load_module()
        with tempfile.TemporaryDirectory(prefix="sqlopt_resolve_scan_") as td:
            repo = Path(td)
            run_id = "run_scan_1"
            run_dir = repo / "any" / "runs" / run_id
            (run_dir / "pipeline" / "supervisor").mkdir(parents=True, exist_ok=True)
            (run_dir / "pipeline" / "supervisor" / "meta.json").write_text('{"run_id": "run_scan_1"}', encoding="utf-8")
            with patch.object(mod, "_repo_root", return_value=repo):
                rid, resolved = mod.resolve_run_id(run_id, str(repo))
            self.assertEqual(rid, run_id)
            self.assertEqual(resolved.resolve(), run_dir.resolve())


if __name__ == "__main__":
    unittest.main()
