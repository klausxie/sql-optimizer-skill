"""
Report Stage - Generate optimization reports from stage results.

Exports:
    ReportGenerator: Main report generation class
    ReportBuilder: Report content builder
    ReportStage: V8 stage wrapper with execute_one
    ReportResult: Report result dataclass
    execute_one: Per-SQL report generation entry point
"""

from sqlopt.stages.report.report_generator import (
    ReportGenerator,
    ReportResult,
)
from sqlopt.stages.report.report_builder import (
    ReportBuilder,
)
from sqlopt.stages.report.execute_one import (
    ReportStage,
    execute_one,
)

__all__ = [
    # Core classes
    "ReportGenerator",
    "ReportBuilder",
    "ReportStage",
    # Data class
    "ReportResult",
    # Entry point
    "execute_one",
]
