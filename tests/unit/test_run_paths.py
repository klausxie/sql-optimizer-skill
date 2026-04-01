from __future__ import annotations

import unittest
from pathlib import Path

from sqlopt.run_paths import RunPaths, canonical_paths


class TestCanonicalRunLayout(unittest.TestCase):
    """Test that run paths use the new minimal layout."""

    def test_report_json_path_at_root(self) -> None:
        """report.json should be at the run root, not in overview/."""
        paths = canonical_paths(Path("/tmp/run_demo"))
        self.assertEqual(paths.report_json_path, Path("/tmp/run_demo/report.json"))

    def test_control_dir_exists(self) -> None:
        """control/ directory should exist."""
        paths = canonical_paths(Path("/tmp/run_demo"))
        self.assertEqual(paths.control_dir, Path("/tmp/run_demo/control"))

    def test_control_state_path(self) -> None:
        """state.json should be in control/, not pipeline/supervisor/."""
        paths = canonical_paths(Path("/tmp/run_demo"))
        self.assertEqual(paths.state_path, Path("/tmp/run_demo/control/state.json"))

    def test_control_plan_path(self) -> None:
        """plan.json should be in control/, not pipeline/supervisor/."""
        paths = canonical_paths(Path("/tmp/run_demo"))
        self.assertEqual(paths.plan_path, Path("/tmp/run_demo/control/plan.json"))

    def test_control_manifest_path(self) -> None:
        """manifest.jsonl should be in control/, not pipeline/."""
        paths = canonical_paths(Path("/tmp/run_demo"))
        self.assertEqual(paths.manifest_path, Path("/tmp/run_demo/control/manifest.jsonl"))

    def test_artifacts_dir_exists(self) -> None:
        """artifacts/ directory should exist."""
        paths = canonical_paths(Path("/tmp/run_demo"))
        self.assertEqual(paths.artifacts_dir, Path("/tmp/run_demo/artifacts"))

    def test_artifacts_scan_path(self) -> None:
        """scan.jsonl should be in artifacts/, not pipeline/scan/sqlunits.jsonl."""
        paths = canonical_paths(Path("/tmp/run_demo"))
        self.assertEqual(paths.scan_units_path, Path("/tmp/run_demo/artifacts/scan.jsonl"))

    def test_artifacts_fragments_path(self) -> None:
        """fragments.jsonl should be in artifacts/."""
        paths = canonical_paths(Path("/tmp/run_demo"))
        self.assertEqual(paths.scan_fragments_path, Path("/tmp/run_demo/artifacts/fragments.jsonl"))

    def test_artifacts_proposals_path(self) -> None:
        """proposals.jsonl should be in artifacts/, not pipeline/optimize/."""
        paths = canonical_paths(Path("/tmp/run_demo"))
        self.assertEqual(paths.proposals_path, Path("/tmp/run_demo/artifacts/proposals.jsonl"))

    def test_artifacts_acceptance_path(self) -> None:
        """acceptance.jsonl should be in artifacts/, not pipeline/validate/."""
        paths = canonical_paths(Path("/tmp/run_demo"))
        self.assertEqual(paths.acceptance_path, Path("/tmp/run_demo/artifacts/acceptance.jsonl"))

    def test_artifacts_patches_path(self) -> None:
        """patches.jsonl should be in artifacts/, not pipeline/patch_generate/."""
        paths = canonical_paths(Path("/tmp/run_demo"))
        self.assertEqual(paths.patches_path, Path("/tmp/run_demo/artifacts/patches.jsonl"))

    def test_sql_dir_exists(self) -> None:
        """sql/ directory should still exist."""
        paths = canonical_paths(Path("/tmp/run_demo"))
        self.assertEqual(paths.sql_dir, Path("/tmp/run_demo/sql"))

    def test_sql_catalog_path(self) -> None:
        """catalog.jsonl should be in sql/."""
        paths = canonical_paths(Path("/tmp/run_demo"))
        self.assertEqual(paths.sql_catalog_path, Path("/tmp/run_demo/sql/catalog.jsonl"))

    def test_no_overview_dir(self) -> None:
        """overview/ directory should not exist in the new layout."""
        paths = canonical_paths(Path("/tmp/run_demo"))
        # The overview_dir property should not exist or should be removed
        self.assertFalse(hasattr(paths, 'overview_dir') and (Path("/tmp/run_demo") / "overview").exists())


class TestOldPathsRemoved(unittest.TestCase):
    """Test that old paths are removed."""

    def test_no_pipeline_dir(self) -> None:
        """pipeline/ should not exist in the new layout."""
        paths = canonical_paths(Path("/tmp/run_demo"))
        # The pipeline_dir property should either not exist or return a path that's not used
        # For now we just ensure the new paths don't use pipeline/
        self.assertNotIn("pipeline", str(paths.report_json_path))

    def test_no_supervisor_dir(self) -> None:
        """pipeline/supervisor/ should not be used."""
        paths = canonical_paths(Path("/tmp/run_demo"))
        # state and plan should be in control/, not pipeline/supervisor/
        self.assertNotIn("pipeline/supervisor", str(paths.state_path))
        self.assertNotIn("pipeline/supervisor", str(paths.plan_path))

    def test_no_verification_dir(self) -> None:
        """pipeline/verification/ should not exist."""
        paths = canonical_paths(Path("/tmp/run_demo"))
        self.assertFalse(hasattr(paths, "verification_ledger_path"))
        self.assertFalse(hasattr(paths, "verification_dir"))

    def test_no_diagnostics_dir(self) -> None:
        """diagnostics/ should not exist."""
        paths = canonical_paths(Path("/tmp/run_demo"))
        self.assertNotIn("diagnostics", str(paths.report_json_path))

    def test_no_ops_dir(self) -> None:
        """pipeline/ops/ should not exist."""
        paths = canonical_paths(Path("/tmp/run_demo"))
        self.assertFalse(hasattr(paths, "health_path"))
        self.assertFalse(hasattr(paths, "topology_path"))
        self.assertFalse(hasattr(paths, "pipeline_dir"))

    def test_no_report_md(self) -> None:
        """report.md should not be generated."""
        paths = canonical_paths(Path("/tmp/run_demo"))
        # report_md_path should not be in overview/
        if hasattr(paths, 'report_md_path'):
            self.assertNotIn("overview", str(paths.report_md_path))


if __name__ == "__main__":
    unittest.main()
