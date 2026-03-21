"""Report stage execute_one function.

Generates optimization reports for SQL statements by collecting data from all stages.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...contracts import ContractValidator
from ...manifest import log_event
from ...run_paths import canonical_paths
from .report_generator import ReportGenerator, ReportResult


@dataclass
class ReportStageResult:
    """Result of report generation for a single SQL unit."""

    sql_key: str
    summary: dict[str, Any]
    recommendations: list[dict[str, Any]]
    risks: list[dict[str, Any]]
    baseline: dict[str, Any] | None
    validation: dict[str, Any] | None
    execution_time_ms: float
    trace: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def execute_one(
    sql_unit: dict[str, Any],
    run_dir: Path,
    validator: ContractValidator,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate a report for a single SQL unit.

    Args:
        sql_unit: SQL unit dictionary
        run_dir: Run directory
        validator: Contract validator
        config: Optional configuration

    Returns:
        Report result dictionary
    """
    config = config or {}
    paths = canonical_paths(run_dir)

    sql_key = sql_unit.get(
        "sqlKey",
        sql_unit.get("namespace", "unknown")
        + "."
        + sql_unit.get("statementId", "unknown"),
    )

    # Generate report using ReportGenerator
    generator = ReportGenerator(run_dir, config)
    result = generator.generate(sql_key)

    # Convert to dict format
    report_dict = result.to_dict()

    # Build trace info
    trace = {
        "stage": "report",
        "sql_key": sql_key,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "execution_time_ms": result.execution_time_ms,
    }

    # Build result
    report_result = {
        "sqlKey": sql_key,
        "summary": report_dict["summary"],
        "recommendations": report_dict["recommendations"],
        "risks": report_dict["risks"],
        "baseline": report_dict["baseline"],
        "validation": report_dict["validation"],
        "executionTimeMs": result.execution_time_ms,
        "generatedAt": result.generated_at,
        "trace": trace,
    }

    # Log event
    log_event(
        paths.manifest_path,
        "report",
        "done",
        {
            "statement_key": sql_key,
            "total_risks": result.summary.total_risks,
            "recommendation_count": len(result.recommendations),
        },
    )

    return report_result


class ReportStage:
    """Report stage wrapper for V8 architecture."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the report stage.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}

    def execute_one(
        self,
        sql_unit: dict[str, Any],
        run_dir: Path,
        validator: ContractValidator,
    ) -> dict[str, Any]:
        """Generate a report for a single SQL unit.

        Args:
            sql_unit: SQL unit dictionary
            run_dir: Run directory
            validator: Contract validator

        Returns:
            Report result dictionary
        """
        return execute_one(sql_unit, run_dir, validator, self.config)

    def generate_summary(self, run_dir: Path) -> str:
        """Generate a summary report for all SQL units.

        Args:
            run_dir: Run directory

        Returns:
            Markdown string containing the summary report
        """
        from .report_builder import ReportBuilder

        generator = ReportGenerator(run_dir, self.config)
        builder = ReportBuilder()

        results = generator.generate_all()
        return builder.build_summary(results)

    def save_summary_report(
        self, run_dir: Path, output_path: Path | None = None
    ) -> Path:
        """Generate and save a summary report.

        Args:
            run_dir: Run directory
            output_path: Optional custom output path

        Returns:
            Path to the saved summary report
        """
        if output_path is None:
            output_path = run_dir / "report.summary.md"

        summary = self.generate_summary(run_dir)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(summary)

        return output_path

    def save_reports(self, run_dir: Path) -> list[Path]:
        """Generate and save individual reports for each SQL unit.

        Args:
            run_dir: Run directory

        Returns:
            List of paths to saved report files
        """
        generator = ReportGenerator(run_dir, self.config)
        results = generator.generate_all()

        saved_paths = []
        for result in results:
            path = generator.save_report(result)
            saved_paths.append(path)

        return saved_paths
