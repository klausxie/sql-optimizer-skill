"""Run paths management for SQL optimizer pipeline stages.

This module provides the RunPaths class for managing directory and file paths
across different stages of a SQL optimization run.
"""

from pathlib import Path


class RunPaths:
    """Manages paths for a single SQL optimization run.

    Each run has a dedicated directory under the base directory, with
    subdirectories for each stage of the optimization pipeline.

    Stages:
        - init: Initial SQL parsing and unit extraction
        - parse: SQL analysis with branch information
        - recognition: Baseline recognition and risk assessment
        - optimize: Optimization proposal generation
        - result: Final optimization reports
    """

    def __init__(self, run_id: str, base_dir: str = "./runs"):
        """Initialize paths for a run.

        Args:
            run_id: Unique identifier for this run.
            base_dir: Base directory for all runs (default: "./runs").
        """
        self.run_id = run_id
        self.base_dir = Path(base_dir)
        self.run_dir = self.base_dir / run_id

    @property
    def init_dir(self) -> Path:
        """Directory for initialization stage."""
        return self.run_dir / "init"

    @property
    def parse_dir(self) -> Path:
        """Directory for parsing stage."""
        return self.run_dir / "parse"

    @property
    def recognition_dir(self) -> Path:
        """Directory for recognition stage."""
        return self.run_dir / "recognition"

    @property
    def optimize_dir(self) -> Path:
        """Directory for optimization stage."""
        return self.run_dir / "optimize"

    @property
    def result_dir(self) -> Path:
        """Directory for final results."""
        return self.run_dir / "result"

    @property
    def mock_dir(self) -> Path:
        """Directory for mock data (can be used to override any stage input)."""
        return self.run_dir / "mock"

    @property
    def mock_init_sql_units(self) -> Path:
        """Mock path for init stage SQL units."""
        return self.mock_dir / "init" / "sql_units.json"

    @property
    def mock_parse_sql_units_with_branches(self) -> Path:
        """Mock path for parse stage output."""
        return self.mock_dir / "parse" / "sql_units_with_branches.json"

    @property
    def mock_recognition_baselines(self) -> Path:
        """Mock path for recognition stage output."""
        return self.mock_dir / "recognition" / "baselines.json"

    @property
    def mock_optimize_proposals(self) -> Path:
        """Mock path for optimize stage output."""
        return self.mock_dir / "optimize" / "proposals.json"

    @property
    def mock_result_report(self) -> Path:
        """Mock path for result stage output."""
        return self.mock_dir / "result" / "report.json"

    @property
    def init_sql_units(self) -> Path:
        """Path to SQL units JSON file from init stage."""
        return self.init_dir / "sql_units.json"

    @property
    def parse_sql_units_with_branches(self) -> Path:
        """Path to SQL units with branches JSON file."""
        return self.parse_dir / "sql_units_with_branches.json"

    @property
    def parse_risks(self) -> Path:
        """Path to risks JSON file from parse stage."""
        return self.parse_dir / "risks.json"

    @property
    def recognition_baselines(self) -> Path:
        """Path to baselines JSON file from recognition stage."""
        return self.recognition_dir / "baselines.json"

    @property
    def optimize_proposals(self) -> Path:
        """Path to proposals JSON file from optimize stage."""
        return self.optimize_dir / "proposals.json"

    @property
    def result_report(self) -> Path:
        """Path to final report JSON file."""
        return self.result_dir / "report.json"

    def ensure_dirs(self) -> None:
        """Create all stage directories if they don't exist.

        This method creates the run directory and all stage subdirectories.
        It's safe to call multiple times.
        """
        for stage_dir in [
            self.init_dir,
            self.parse_dir,
            self.recognition_dir,
            self.optimize_dir,
            self.result_dir,
            self.mock_dir,
        ]:
            stage_dir.mkdir(parents=True, exist_ok=True)
