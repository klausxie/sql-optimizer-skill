"""
V9 Init Stage Overview Generation Integration Test

Tests that the Init stage generates an overview markdown report
with correct metrics when run with real MyBatis XML files.
"""

import json
from pathlib import Path

from sqlopt.application.v9_stages import run_stage

# Imports from conftest
from conftest import load_sql_units


class TestInitOverview:
    """Integration tests for Init stage overview generation."""

    def test_init_generates_overview_md(
        self, temp_run_dir: Path, real_mapper_config: dict, validator
    ) -> None:
        """
        Test that INIT stage generates init.overview.md with expected metrics.

        Validates:
        - init.overview.md is created
        - Contains "# Init Stage Overview" header
        - Contains "## 执行摘要" section
        - Contains "## 关键指标" section with SQL total count
        - Contains statement type distribution table
        """
        # Run init stage
        result = run_stage(
            "init",
            temp_run_dir,
            config=real_mapper_config,
            validator=validator,
        )

        # Verify stage succeeded
        assert result.get("success", False), f"Init stage failed: {result}"

        # Verify init.overview.md exists
        overview_path = temp_run_dir / "init" / "init.overview.md"
        assert overview_path.exists(), f"init.overview.md not found at {overview_path}"

        # Read and verify content
        content = overview_path.read_text()

        # Verify required sections
        assert "# Init Stage Overview" in content, (
            "Missing '# Init Stage Overview' header"
        )
        assert "## 执行摘要" in content, "Missing '## 执行摘要' section"
        assert "## 关键指标" in content, "Missing '## 关键指标' section"

        # Verify SQL total count is present
        assert "SQL 总数" in content, "Missing 'SQL 总数' metric"

        # Verify statement type distribution is present
        assert "SELECT" in content, "Missing SELECT count in metrics"

        # Verify data source reference
        assert "init/sql_units.json" in content, "Missing data source reference"

        # Load sql_units to verify metrics match
        sql_units = load_sql_units(temp_run_dir)
        total_count = len(sql_units)

        # Statement type counts
        type_counts = {}
        for unit in sql_units:
            stype = unit.get("statementType", "UNKNOWN")
            type_counts[stype] = type_counts.get(stype, 0) + 1

        # Verify metrics match actual data
        assert str(total_count) in content, (
            f"SQL total count {total_count} not found in overview"
        )

        if "SELECT" in type_counts:
            assert str(type_counts["SELECT"]) in content, (
                f"SELECT count {type_counts['SELECT']} not found in overview"
            )
