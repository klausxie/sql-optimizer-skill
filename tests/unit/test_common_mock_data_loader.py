"""Tests for MockDataLoader."""

import tempfile
from pathlib import Path

from sqlopt.common.mock_data_loader import MockDataLoader
from sqlopt.common.run_paths import RunPaths


class TestMockDataLoaderBaseDir:
    """MockDataLoader should respect custom run base directories."""

    def test_uses_custom_base_dir_for_real_inputs(self):
        """Loader should resolve real stage outputs beneath the provided base_dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir) / "custom-runs"
            loader = MockDataLoader("run-123", use_mock=False, base_dir=str(base_dir))
            assert loader.get_init_sql_units_path() == base_dir / "run-123" / "init" / "sql_units.json"

    def test_prefers_parse_units_dir_when_index_exists_in_custom_base_dir(self):
        """Loader should detect per-unit parse outputs inside the configured base_dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = RunPaths("run-123", base_dir=tmpdir)
            paths.parse_units_dir.mkdir(parents=True, exist_ok=True)
            paths.parse_index_file.write_text("[]", encoding="utf-8")

            loader = MockDataLoader("run-123", use_mock=False, base_dir=tmpdir)

            assert loader.get_parse_sql_units_with_branches_path() == paths.parse_units_dir

    def test_parse_unit_path_uses_sanitized_filename(self):
        """Loader should match the same sanitized unit naming as RunPaths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = MockDataLoader("run-123", use_mock=False, base_dir=tmpdir)
            assert loader.get_parse_unit_path("foo/bar").name == "foo_bar.json"
