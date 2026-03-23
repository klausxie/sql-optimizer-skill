"""Tests for RunPaths."""

import tempfile
from pathlib import Path

import pytest

from sqlopt.common.run_paths import RunPaths


class TestRunPathsInit:
    """Test RunPaths initialization."""

    def test_init_stores_run_id(self):
        """Test RunPaths stores run_id correctly."""
        paths = RunPaths(run_id="run-123")
        assert paths.run_id == "run-123"

    def test_init_stores_base_dir_as_path(self):
        """Test RunPaths stores base_dir as Path."""
        paths = RunPaths(run_id="run-123", base_dir="/custom/base")
        assert paths.base_dir == Path("/custom/base")

    def test_default_base_dir_is_runs(self):
        """Test default base_dir is ./runs."""
        paths = RunPaths(run_id="run-123")
        assert paths.base_dir == Path("./runs")

    def test_run_dir_is_base_dir_run_id(self):
        """Test run_dir is base_dir / run_id."""
        paths = RunPaths(run_id="run-456", base_dir="/tmp/runs")
        assert paths.run_dir == Path("/tmp/runs/run-456")


class TestRunPathsStageDirs:
    """Test RunPaths stage directory properties."""

    def test_init_dir(self):
        """Test init_dir property returns correct path."""
        paths = RunPaths(run_id="run-123")
        assert paths.init_dir == paths.run_dir / "init"

    def test_parse_dir(self):
        """Test parse_dir property returns correct path."""
        paths = RunPaths(run_id="run-123")
        assert paths.parse_dir == paths.run_dir / "parse"

    def test_recognition_dir(self):
        """Test recognition_dir property returns correct path."""
        paths = RunPaths(run_id="run-123")
        assert paths.recognition_dir == paths.run_dir / "recognition"

    def test_optimize_dir(self):
        """Test optimize_dir property returns correct path."""
        paths = RunPaths(run_id="run-123")
        assert paths.optimize_dir == paths.run_dir / "optimize"

    def test_result_dir(self):
        """Test result_dir property returns correct path."""
        paths = RunPaths(run_id="run-123")
        assert paths.result_dir == paths.run_dir / "result"


class TestRunPathsFilePaths:
    """Test RunPaths file path properties."""

    def test_init_sql_units(self):
        """Test init_sql_units returns init_dir / sql_units.json."""
        paths = RunPaths(run_id="run-123")
        assert paths.init_sql_units == paths.init_dir / "sql_units.json"

    def test_parse_sql_units_with_branches(self):
        """Test parse_sql_units_with_branches returns correct path."""
        paths = RunPaths(run_id="run-123")
        assert (
            paths.parse_sql_units_with_branches == paths.parse_dir / "sql_units_with_branches.json"
        )

    def test_parse_risks(self):
        """Test parse_risks returns parse_dir / risks.json."""
        paths = RunPaths(run_id="run-123")
        assert paths.parse_risks == paths.parse_dir / "risks.json"

    def test_recognition_baselines(self):
        """Test recognition_baselines returns recognition_dir / baselines.json."""
        paths = RunPaths(run_id="run-123")
        assert paths.recognition_baselines == paths.recognition_dir / "baselines.json"

    def test_optimize_proposals(self):
        """Test optimize_proposals returns optimize_dir / proposals.json."""
        paths = RunPaths(run_id="run-123")
        assert paths.optimize_proposals == paths.optimize_dir / "proposals.json"

    def test_result_report(self):
        """Test result_report returns result_dir / report.json."""
        paths = RunPaths(run_id="run-123")
        assert paths.result_report == paths.result_dir / "report.json"


class TestRunPathsEnsureDirs:
    """Test RunPaths.ensure_dirs method."""

    def test_ensure_dirs_creates_run_dir(self):
        """Test ensure_dirs creates the run directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "runs"
            paths = RunPaths(run_id="test-run", base_dir=str(base))
            paths.ensure_dirs()
            assert paths.run_dir.exists()
            assert paths.run_dir.is_dir()

    def test_ensure_dirs_creates_all_stage_dirs(self):
        """Test ensure_dirs creates all stage subdirectories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "runs"
            paths = RunPaths(run_id="test-run", base_dir=str(base))
            paths.ensure_dirs()

            assert paths.init_dir.exists()
            assert paths.init_dir.is_dir()
            assert paths.parse_dir.exists()
            assert paths.recognition_dir.exists()
            assert paths.optimize_dir.exists()
            assert paths.result_dir.exists()

    def test_ensure_dirs_is_idempotent(self):
        """Test ensure_dirs can be called multiple times safely."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "runs"
            paths = RunPaths(run_id="test-run", base_dir=str(base))
            paths.ensure_dirs()
            paths.ensure_dirs()  # Should not raise
            assert paths.run_dir.exists()

    def test_ensure_dirs_creates_nested_paths(self):
        """Test ensure_dirs creates nested directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "nested" / "runs"
            paths = RunPaths(run_id="deep-run", base_dir=str(base))
            paths.ensure_dirs()
            assert paths.run_dir.exists()
            assert (base / "deep-run").exists()


class TestRunPathsPathTypes:
    """Test that RunPaths returns Path objects."""

    def test_all_dir_properties_return_path(self):
        """Test all directory properties return Path instances."""
        paths = RunPaths(run_id="test-run")
        for prop_name in ["init_dir", "parse_dir", "recognition_dir", "optimize_dir", "result_dir"]:
            prop_value = getattr(paths, prop_name)
            assert isinstance(prop_value, Path), f"{prop_name} should return Path"

    def test_all_file_properties_return_path(self):
        """Test all file properties return Path instances."""
        paths = RunPaths(run_id="test-run")
        for prop_name in [
            "init_sql_units",
            "parse_sql_units_with_branches",
            "parse_risks",
            "recognition_baselines",
            "optimize_proposals",
            "result_report",
        ]:
            prop_value = getattr(paths, prop_name)
            assert isinstance(prop_value, Path), f"{prop_name} should return Path"
