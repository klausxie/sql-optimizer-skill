"""Run paths management for SQL optimizer pipeline stages.

This module provides the RunPaths class for managing directory and file paths
across different stages of a SQL optimization run.
"""

from __future__ import annotations

from pathlib import Path

VALID_STAGES = ("init", "parse", "recognition", "optimize", "result")


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

    @staticmethod
    def sanitize_unit_id(unit_id: str) -> str:
        """Sanitize a unit identifier for filesystem-safe file names."""
        return unit_id.replace("/", "_").replace("\\", "_").replace("..", "_")

    def stage_dir(self, stage_name: str) -> Path:
        """Return the directory for a named stage."""
        if stage_name not in VALID_STAGES:
            raise ValueError(f"Invalid stage '{stage_name}'. Must be one of: {VALID_STAGES}")
        return self.run_dir / stage_name

    def stage_file(self, stage_name: str, filename: str) -> Path:
        """Return a file path under a named stage directory."""
        return self.stage_dir(stage_name) / filename

    def mock_stage_dir(self, stage_name: str) -> Path:
        """Return the mock directory for a named stage."""
        if stage_name not in VALID_STAGES:
            raise ValueError(f"Invalid stage '{stage_name}'. Must be one of: {VALID_STAGES}")
        return self.mock_dir / stage_name

    def mock_stage_file(self, stage_name: str, filename: str) -> Path:
        """Return a mock file path for a named stage."""
        return self.mock_stage_dir(stage_name) / filename

    def stage_units_dir(self, stage_name: str) -> Path:
        """Return the per-unit directory for a stage."""
        return self.stage_dir(stage_name) / "units"

    def stage_index_file(self, stage_name: str) -> Path:
        """Return the per-unit index file for a stage."""
        return self.stage_units_dir(stage_name) / "_index.json"

    def stage_unit_file(self, stage_name: str, unit_id: str) -> Path:
        """Return the per-unit JSON file path for a stage."""
        return self.stage_units_dir(stage_name) / f"{self.sanitize_unit_id(unit_id)}.json"

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
        return self.mock_stage_file("init", "sql_units.json")

    @property
    def mock_init_sql_fragments(self) -> Path:
        """Mock path for init stage SQL fragments."""
        return self.mock_stage_file("init", "sql_fragments.json")

    @property
    def mock_init_table_schemas(self) -> Path:
        """Mock path for init stage table schemas."""
        return self.mock_stage_file("init", "table_schemas.json")

    @property
    def mock_init_field_distributions(self) -> Path:
        """Mock path for init stage field distributions."""
        return self.mock_stage_file("init", "field_distributions.json")

    @property
    def mock_init_xml_mappings(self) -> Path:
        """Mock path for init stage XML mappings."""
        return self.mock_stage_file("init", "xml_mappings.json")

    @property
    def mock_parse_sql_units_with_branches(self) -> Path:
        """Mock path for parse stage output."""
        return self.mock_stage_file("parse", "sql_units_with_branches.json")

    @property
    def mock_recognition_baselines(self) -> Path:
        """Mock path for recognition stage output."""
        return self.mock_stage_file("recognition", "baselines.json")

    @property
    def mock_optimize_proposals(self) -> Path:
        """Mock path for optimize stage output."""
        return self.mock_stage_file("optimize", "proposals.json")

    @property
    def mock_result_report(self) -> Path:
        """Mock path for result stage output."""
        return self.mock_stage_file("result", "report.json")

    @property
    def init_sql_units(self) -> Path:
        """Path to SQL units JSON file from init stage."""
        return self.stage_file("init", "sql_units.json")

    @property
    def init_sql_fragments(self) -> Path:
        """Path to SQL fragments JSON file from init stage."""
        return self.stage_file("init", "sql_fragments.json")

    @property
    def init_table_schemas(self) -> Path:
        """Path to table schemas JSON file from init stage."""
        return self.stage_file("init", "table_schemas.json")

    @property
    def init_field_distributions(self) -> Path:
        """Path to field distributions JSON file from init stage."""
        return self.stage_file("init", "field_distributions.json")

    @property
    def init_xml_mappings(self) -> Path:
        """Path to XML mappings JSON file from init stage."""
        return self.stage_file("init", "xml_mappings.json")

    @property
    def parse_sql_units_with_branches(self) -> Path:
        """Path to SQL units with branches JSON file."""
        return self.stage_file("parse", "sql_units_with_branches.json")

    @property
    def parse_risks(self) -> Path:
        """Path to risks JSON file from parse stage."""
        return self.stage_file("parse", "risks.json")

    @property
    def parse_units_dir(self) -> Path:
        """Directory for per-unit parse files."""
        return self.stage_units_dir("parse")

    def parse_unit_file(self, unit_id: str) -> Path:
        """Path to a specific unit's parse JSON file.

        Args:
            unit_id: Unique identifier for the SQL unit.

        Returns:
            Path to the unit's JSON file with sanitized filename.
        """
        # Sanitize unit_id for filesystem safety
        return self.stage_unit_file("parse", unit_id)

    @property
    def parse_index_file(self) -> Path:
        """Path to the parse units index file."""
        return self.stage_index_file("parse")

    @property
    def recognition_baselines(self) -> Path:
        """Path to baselines JSON file from recognition stage."""
        return self.stage_file("recognition", "baselines.json")

    @property
    def optimize_proposals(self) -> Path:
        """Path to proposals JSON file from optimize stage."""
        return self.stage_file("optimize", "proposals.json")

    @property
    def result_report(self) -> Path:
        """Path to final report JSON file."""
        return self.stage_file("result", "report.json")

    def ensure_dirs(self) -> None:
        """Create all stage directories if they don't exist.

        This method creates the run directory and all stage subdirectories.
        It's safe to call multiple times.
        """
        for stage_dir in [*(self.stage_dir(stage) for stage in VALID_STAGES), self.mock_dir]:
            stage_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def find_latest_run_id(base_dir: str = "./runs") -> str | None:
        """Find the most recent run directory by modification time.

        Args:
            base_dir: Base directory for all runs.

        Returns:
            The run_id of the most recently modified run, or None if no runs exist.
        """
        base = Path(base_dir)
        if not base.exists():
            return None

        runs = [d for d in base.iterdir() if d.is_dir() and not d.name.startswith(".")]
        if not runs:
            return None

        latest = max(runs, key=lambda d: d.stat().st_mtime)
        return latest.name
