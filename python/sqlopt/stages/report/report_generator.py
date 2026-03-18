"""
Report Generator - Generate optimization reports from stage results.

Collects data from all stages (discovery, branching, pruning, baseline, optimize, validate)
and produces a comprehensive report for each SQL statement.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import json
from datetime import datetime, timezone


@dataclass
class ReportSummary:
    """Summary statistics for the report."""

    total_risks: int = 0
    high_risk: int = 0
    medium_risk: int = 0
    low_risk: int = 0
    optimization_candidates: int = 0
    baseline_collected: bool = False
    validation_passed: bool = False
    patch_applied: bool = False


@dataclass
class Recommendation:
    """Single optimization recommendation."""

    type: str  # "index", "rewrite", "wildcard", "structuring"
    priority: str  # "high", "medium", "low"
    description: str
    original_sql: Optional[str] = None
    suggested_sql: Optional[str] = None
    reason: str = ""


@dataclass
class ReportResult:
    """Complete report result for a SQL statement."""

    run_id: str
    sql_key: str
    summary: ReportSummary
    recommendations: list[Recommendation]
    risks: list[dict[str, Any]] = field(default_factory=list)
    baseline: Optional[dict[str, Any]] = None
    validation: Optional[dict[str, Any]] = None
    execution_time_ms: float = 0.0
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "sql_key": self.sql_key,
            "summary": {
                "total_risks": self.summary.total_risks,
                "high_risk": self.summary.high_risk,
                "medium_risk": self.summary.medium_risk,
                "low_risk": self.summary.low_risk,
                "optimization_candidates": self.summary.optimization_candidates,
                "baseline_collected": self.summary.baseline_collected,
                "validation_passed": self.summary.validation_passed,
                "patch_applied": self.summary.patch_applied,
            },
            "recommendations": [
                {
                    "type": r.type,
                    "priority": r.priority,
                    "description": r.description,
                    "original_sql": r.original_sql,
                    "suggested_sql": r.suggested_sql,
                    "reason": r.reason,
                }
                for r in self.recommendations
            ],
            "risks": self.risks,
            "baseline": self.baseline,
            "validation": self.validation,
            "execution_time_ms": self.execution_time_ms,
            "generated_at": self.generated_at,
        }


class ReportGenerator:
    """
    Main report generation class.

    Collects data from stage outputs in the run directory and produces
    comprehensive optimization reports.
    """

    def __init__(self, run_dir: Path, config: dict[str, Any] | None = None):
        """
        Initialize the report generator.

        Args:
            run_dir: Path to the run directory (runs/<run_id>/)
            config: Optional configuration dictionary
        """
        self.run_dir = Path(run_dir)
        self.config = config or {}
        self.run_id = self.run_dir.name

    def generate(self, sql_key: str) -> ReportResult:
        """
        Generate a report for a specific SQL statement.

        Args:
            sql_key: The SQL key to generate report for

        Returns:
            ReportResult containing the complete report
        """
        import time

        start_time = time.perf_counter()

        # Collect data from all stages
        risks = self._load_risks(sql_key)
        baseline = self._load_baseline(sql_key)
        proposals = self._load_proposals(sql_key)
        validation = self._load_validation(sql_key)
        patch = self._load_patch(sql_key)

        # Build summary
        summary = self._build_summary(risks, proposals, baseline, validation, patch)

        # Build recommendations
        recommendations = self._build_recommendations(risks, proposals)

        execution_time_ms = (time.perf_counter() - start_time) * 1000

        return ReportResult(
            run_id=self.run_id,
            sql_key=sql_key,
            summary=summary,
            recommendations=recommendations,
            risks=risks,
            baseline=baseline,
            validation=validation,
            execution_time_ms=execution_time_ms,
        )

    def generate_all(self) -> list[ReportResult]:
        """
        Generate reports for all SQL statements in the run.

        Returns:
            List of ReportResult for all SQL statements
        """
        sql_units = self._load_sql_units()
        results = []
        for unit in sql_units:
            sql_key = unit.get("sqlKey", "unknown")
            result = self.generate(sql_key)
            results.append(result)
        return results

    def _load_sql_units(self) -> list[dict[str, Any]]:
        """Load SQL units from scan output."""
        scan_file = self.run_dir / "scan.sqlunits.jsonl"
        if not scan_file.exists():
            return []

        units = []
        with open(scan_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        units.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return units

    def _load_risks(self, sql_key: str) -> list[dict[str, Any]]:
        """Load risk data from pruning stage."""
        risks_file = self.run_dir / "acceptance" / f"{sql_key}.jsonl"
        if not risks_file.exists():
            return []

        risks = []
        with open(risks_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        if data.get("sqlKey") == sql_key and "risks" in data:
                            risks.extend(data["risks"])
                    except json.JSONDecodeError:
                        continue
        return risks

    def _load_baseline(self, sql_key: str) -> dict[str, Any] | None:
        """Load baseline data from baseline stage."""
        baseline_dir = self.run_dir / "baseline"
        if not baseline_dir.exists():
            return None

        baseline_file = baseline_dir / f"{sql_key}.json"
        if baseline_file.exists():
            with open(baseline_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def _load_proposals(self, sql_key: str) -> list[dict[str, Any]]:
        """Load optimization proposals."""
        proposals_dir = self.run_dir / "proposals"
        if not proposals_dir.exists():
            return []

        proposals = []
        for proposal_file in proposals_dir.glob(f"{sql_key}*.json"):
            with open(proposal_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    proposals.extend(data)
                else:
                    proposals.append(data)
        return proposals

    def _load_validation(self, sql_key: str) -> dict[str, Any] | None:
        """Load validation results."""
        validation_dir = self.run_dir / "validation"
        if not validation_dir.exists():
            return None

        validation_file = validation_dir / f"{sql_key}.json"
        if validation_file.exists():
            with open(validation_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def _load_patch(self, sql_key: str) -> dict[str, Any] | None:
        """Load patch information."""
        patch_dir = self.run_dir / "patches"
        if not patch_dir.exists():
            return None

        patch_file = patch_dir / f"{sql_key}.json"
        if patch_file.exists():
            with open(patch_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def _build_summary(
        self,
        risks: list[dict[str, Any]],
        proposals: list[dict[str, Any]],
        baseline: dict[str, Any] | None,
        validation: dict[str, Any] | None,
        patch: dict[str, Any] | None,
    ) -> ReportSummary:
        """Build summary statistics from collected data."""
        summary = ReportSummary()

        # Count risks by severity
        for risk in risks:
            risk_level = risk.get("risk_level", "low")
            summary.total_risks += 1
            if risk_level == "high":
                summary.high_risk += 1
            elif risk_level == "medium":
                summary.medium_risk += 1
            else:
                summary.low_risk += 1

        # Count optimization candidates
        summary.optimization_candidates = len(proposals)

        # Check baseline
        summary.baseline_collected = baseline is not None

        # Check validation
        if validation:
            summary.validation_passed = validation.get("passed", False)

        # Check patch
        summary.patch_applied = patch is not None and patch.get("applied", False)

        return summary

    def _build_recommendations(
        self,
        risks: list[dict[str, Any]],
        proposals: list[dict[str, Any]],
    ) -> list[Recommendation]:
        """Build optimization recommendations from risks and proposals."""
        recommendations = []

        # Convert risks to recommendations
        for risk in risks:
            risk_type = risk.get("risk_type", "unknown")
            risk_level = risk.get("risk_level", "low")

            if risk_type == "prefix_wildcard":
                recommendations.append(
                    Recommendation(
                        type="wildcard",
                        priority=risk_level,
                        description="Prefix wildcard detected - prevents index usage",
                        original_sql=risk.get("sql_fragment"),
                        suggested_sql=None,
                        reason="Using LIKE '%%' prefix pattern forces full table scan",
                    )
                )
            elif risk_type == "concat_wildcard":
                recommendations.append(
                    Recommendation(
                        type="wildcard",
                        priority=risk_level,
                        description="CONCAT with wildcard - prevents index usage",
                        original_sql=risk.get("sql_fragment"),
                        suggested_sql=None,
                        reason="CONCAT in LIKE pattern prevents index optimization",
                    )
                )
            elif risk_type == "function_wrap":
                recommendations.append(
                    Recommendation(
                        type="structuring",
                        priority=risk_level,
                        description="Function wrapper on column - prevents index usage",
                        original_sql=risk.get("sql_fragment"),
                        suggested_sql=None,
                        reason="Function on indexed column prevents index usage",
                    )
                )
            elif risk_type == "suffix_wildcard_only":
                recommendations.append(
                    Recommendation(
                        type="wildcard",
                        priority="low",
                        description="Suffix-only wildcard - consider adding prefix index",
                        original_sql=risk.get("sql_fragment"),
                        suggested_sql=None,
                        reason="Suffix wildcard can still use index but may be suboptimal",
                    )
                )

        # Convert proposals to recommendations
        for proposal in proposals:
            proposal_type = proposal.get("type", "general")
            priority = proposal.get("priority", "medium")

            recommendations.append(
                Recommendation(
                    type=proposal_type,
                    priority=priority,
                    description=proposal.get("description", "Optimization suggestion"),
                    original_sql=proposal.get("original_sql"),
                    suggested_sql=proposal.get("suggested_sql"),
                    reason=proposal.get("reason", ""),
                )
            )

        return recommendations

    def save_report(
        self, result: ReportResult, output_path: Path | None = None
    ) -> Path:
        """
        Save report to JSON file.

        Args:
            result: The report result to save
            output_path: Optional custom output path

        Returns:
            Path to the saved report file
        """
        if output_path is None:
            output_path = self.run_dir / "reports" / f"{result.sql_key}.json"

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

        return output_path
