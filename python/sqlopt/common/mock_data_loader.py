"""Mock data loader for stage input override during debugging.

This module provides the MockDataLoader class that checks for mock data
before reading real stage outputs, enabling isolated stage debugging.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from sqlopt.common.run_paths import RunPaths


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
        """Get path for parse stage SQL units with branches input."""
        return self._mock_first(
            self.paths.mock_parse_sql_units_with_branches,
            self.paths.parse_sql_units_with_branches,
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
