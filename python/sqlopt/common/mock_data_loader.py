"""Mock data loader for stage input override during debugging.

This module provides the MockDataLoader class that checks for mock data
before reading real stage outputs, enabling isolated stage debugging.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from sqlopt.common.run_paths import RunPaths

logger = logging.getLogger(__name__)


class MockDataLoader:
    """Loads mock data to override stage inputs during debugging.

    When mock data exists in runs/<run_id>/mock/<stage>/, it will be used
    instead of the real stage output, allowing isolated debugging of any stage.

    Example:
        >>> loader = MockDataLoader("test-run", use_mock=True)
        >>> path = loader.get_init_sql_units_path()
        >>> # Returns mock path if use_mock=True and mock exists
        >>> # Otherwise returns real path
    """

    def __init__(self, run_id: str, use_mock: bool = True) -> None:
        """Initialize mock data loader.

        Args:
            run_id: The run identifier
            use_mock: If True, prefer mock data over real data
        """
        self.run_id = run_id
        self.use_mock = use_mock
        self.paths = RunPaths(run_id)

    def _mock_first(self, mock_path: Path, real_path: Path) -> Path:
        """Return mock path if available and use_mock is True, else real path."""
        if self.use_mock and mock_path.exists():
            return mock_path
        return real_path

    def get_init_sql_units_path(self) -> Path:
        """Get path for init stage SQL units input."""
        return self._mock_first(self.paths.mock_init_sql_units, self.paths.init_sql_units)

    def get_parse_sql_units_with_branches_path(self) -> Path:
        """Get path for parse stage SQL units with branches input.

        Checks for new per-unit format first (parse/units/_index.json),
        falls back to legacy single-file format if not found.

        Returns:
            Path to units directory (new format) or single JSON file (legacy format)
        """
        if self.use_mock and self.paths.mock_parse_sql_units_with_branches.exists():
            return self.paths.mock_parse_sql_units_with_branches

        units_index_path = self.paths.parse_dir / "units" / "_index.json"
        if units_index_path.exists():
            return self.paths.parse_dir / "units"

        logger.warning("Using legacy single-file format")
        return self.paths.parse_sql_units_with_branches

    def get_init_sql_fragments_path(self) -> Path:
        """Get path for init stage SQL fragments input."""
        return self._mock_first(
            self.paths.mock_init_sql_fragments,
            self.paths.init_sql_fragments,
        )

    def get_init_table_schemas_path(self) -> Path:
        """Get path for init stage table schemas input."""
        return self._mock_first(
            self.paths.mock_init_table_schemas,
            self.paths.init_table_schemas,
        )

    def get_init_xml_mappings_path(self) -> Path:
        """Get path for init stage XML mappings input."""
        return self._mock_first(
            self.paths.mock_init_xml_mappings,
            self.paths.init_xml_mappings,
        )

    def get_recognition_baselines_path(self) -> Path:
        """Get path for recognition stage baselines input."""
        return self._mock_first(
            self.paths.mock_recognition_baselines,
            self.paths.recognition_baselines,
        )

    def get_optimize_proposals_path(self) -> Path:
        """Get path for optimize stage proposals input."""
        return self._mock_first(
            self.paths.mock_optimize_proposals,
            self.paths.optimize_proposals,
        )

    def get_result_report_path(self) -> Path:
        """Get path for result stage report input."""
        return self._mock_first(
            self.paths.mock_result_report,
            self.paths.result_report,
        )

    def is_mock_available(self, stage: Literal["init", "parse", "recognition", "optimize", "result"]) -> bool:
        """Check if mock data is available for a given stage."""
        mock_paths = {
            "init": self.paths.mock_init_sql_units,
            "parse": self.paths.mock_parse_sql_units_with_branches,
            "recognition": self.paths.mock_recognition_baselines,
            "optimize": self.paths.mock_optimize_proposals,
            "result": self.paths.mock_result_report,
        }
        return mock_paths[stage].exists()

    def get_parse_units_dir(self) -> Path:
        """Get directory for parse stage per-unit output files.

        Returns:
            Path to runs/{run_id}/parse/units directory
        """
        return self.paths.parse_dir / "units"

    def get_parse_unit_path(self, sql_unit_id: str) -> Path:
        """Get path for a specific parse unit output file.

        Args:
            sql_unit_id: The SQL unit identifier

        Returns:
            Path to the unit JSON file (mock if available, else real path)
        """
        mock_path = self.paths.mock_dir / "parse" / "units" / f"{sql_unit_id}.json"
        real_path = self.paths.parse_dir / "units" / f"{sql_unit_id}.json"
        return self._mock_first(mock_path, real_path)
