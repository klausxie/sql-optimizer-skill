"""
Report Builder - Build report content from report data.

Provides methods to build summary and detail sections for reports
in various formats (Markdown, JSON).
"""

from pathlib import Path
from typing import Any, Optional
import json

from sqlopt.stages.report.report_generator import (
    ReportResult,
    ReportSummary,
    Recommendation,
)


class ReportBuilder:
    """
    Report content builder.

    Builds report sections in different formats from ReportResult data.
    """

    def __init__(self, template_dir: Path | None = None):
        """
        Initialize the report builder.

        Args:
            template_dir: Path to templates directory. If None, uses embedded templates.
        """
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"
        self.template_dir = Path(template_dir)

    def build_summary(self, results: list[ReportResult]) -> str:
        """
        Build a summary report in Markdown format.

        Args:
            results: List of ReportResult to summarize

        Returns:
            Markdown string containing the summary report
        """
        if not results:
            return self._build_empty_summary()

        # Aggregate statistics
        total_sql = len(results)
        total_risks = sum(r.summary.total_risks for r in results)
        high_risk = sum(r.summary.high_risk for r in results)
        medium_risk = sum(r.summary.medium_risk for r in results)
        low_risk = sum(r.summary.low_risk for r in results)
        optimization_candidates = sum(
            r.summary.optimization_candidates for r in results
        )
        baseline_collected = sum(1 for r in results if r.summary.baseline_collected)
        validation_passed = sum(1 for r in results if r.summary.validation_passed)
        patch_applied = sum(1 for r in results if r.summary.patch_applied)

        # Load template
        template = self._load_template("summary.md")

        # Build risk breakdown table
        risk_items = []
        for r in results:
            if r.summary.high_risk > 0 or r.summary.medium_risk > 0:
                risk_items.append(
                    f"| {r.sql_key} | {r.summary.high_risk} | {r.summary.medium_risk} | {r.summary.low_risk} |"
                )

        risk_table = (
            "| SQL Key | High Risk | Medium Risk | Low Risk |\n"
            "|---------|-----------|-------------|----------|\n" + "\n".join(risk_items)
            if risk_items
            else "| *No risks detected* | - | - | - |"
        )

        # Build recommendations table
        rec_items = []
        for r in results:
            for rec in r.recommendations:
                rec_items.append(
                    f"| {r.sql_key} | {rec.type} | {rec.priority} | {rec.description[:60]}... |"
                    if len(rec.description) > 60
                    else f"| {r.sql_key} | {rec.type} | {rec.priority} | {rec.description} |"
                )

        rec_table = (
            "| SQL Key | Type | Priority | Description |\n"
            "|---------|------|----------|-------------|\n"
            + "\n".join(rec_items[:20])  # Limit to 20 entries
            + (
                f"\n*... and {len(rec_items) - 20} more recommendations*"
                if len(rec_items) > 20
                else ""
            )
            if rec_items
            else "| *No recommendations* | - | - | - |"
        )

        # Fill template
        substitutions = {
            "{{total_sql}}": str(total_sql),
            "{{total_risks}}": str(total_risks),
            "{{high_risk}}": str(high_risk),
            "{{medium_risk}}": str(medium_risk),
            "{{low_risk}}": str(low_risk),
            "{{optimization_candidates}}": str(optimization_candidates),
            "{{baseline_collected}}": str(baseline_collected),
            "{{validation_passed}}": str(validation_passed),
            "{{patch_applied}}": str(patch_applied),
            "{{risk_table}}": risk_table,
            "{{recommendations_table}}": rec_table,
        }

        for key, value in substitutions.items():
            template = template.replace(key, value)

        return template

    def build_detail(self, result: ReportResult) -> dict[str, Any]:
        """
        Build a detailed report for a single SQL statement.

        Args:
            result: The ReportResult to detail

        Returns:
            Dictionary containing the detailed report
        """
        # Load JSON template
        template = self._load_json_template("detail.json")

        # Build recommendations list
        recommendations = []
        for rec in result.recommendations:
            recommendations.append(
                {
                    "type": rec.type,
                    "priority": rec.priority,
                    "description": rec.description,
                    "original_sql": rec.original_sql,
                    "suggested_sql": rec.suggested_sql,
                    "reason": rec.reason,
                }
            )

        # Build detail structure
        detail = {
            "run_id": result.run_id,
            "sql_key": result.sql_key,
            "summary": {
                "total_risks": result.summary.total_risks,
                "high_risk": result.summary.high_risk,
                "medium_risk": result.summary.medium_risk,
                "low_risk": result.summary.low_risk,
                "optimization_candidates": result.summary.optimization_candidates,
                "baseline_collected": result.summary.baseline_collected,
                "validation_passed": result.summary.validation_passed,
                "patch_applied": result.summary.patch_applied,
            },
            "risks": result.risks,
            "baseline": result.baseline,
            "validation": result.validation,
            "recommendations": recommendations,
            "execution_time_ms": result.execution_time_ms,
            "generated_at": result.generated_at,
        }

        # Apply template fields if present
        if "properties" in template:
            for key in template["properties"]:
                if key in detail:
                    # Type is already correct
                    pass

        return detail

    def build_markdown_detail(self, result: ReportResult) -> str:
        """
        Build a detailed report for a single SQL statement in Markdown format.

        Args:
            result: The ReportResult to detail

        Returns:
            Markdown string containing the detailed report
        """
        lines = [
            f"# SQL Optimization Report: {result.sql_key}",
            "",
            f"**Run ID**: {result.run_id}",
            f"**Generated**: {result.generated_at}",
            "",
            "## Summary",
            "",
            f"- **Total Risks**: {result.summary.total_risks}",
            f"  - High: {result.summary.high_risk}",
            f"  - Medium: {result.summary.medium_risk}",
            f"  - Low: {result.summary.low_risk}",
            f"- **Optimization Candidates**: {result.summary.optimization_candidates}",
            f"- **Baseline Collected**: {'Yes' if result.summary.baseline_collected else 'No'}",
            f"- **Validation Passed**: {'Yes' if result.summary.validation_passed else 'No'}",
            f"- **Patch Applied**: {'Yes' if result.summary.patch_applied else 'No'}",
            "",
        ]

        # Add risks section
        if result.risks:
            lines.append("## Risks Detected")
            lines.append("")
            for risk in result.risks:
                risk_type = risk.get("risk_type", "unknown")
                risk_level = risk.get("risk_level", "low")
                description = risk.get("description", "")
                sql_fragment = risk.get("sql_fragment", "")

                lines.append(f"### [{risk_level.upper()}] {risk_type}")
                lines.append("")
                lines.append(f"**Description**: {description}")
                if sql_fragment:
                    lines.append(f"**SQL Fragment**: ```sql\n{sql_fragment}\n```")
                lines.append("")
        else:
            lines.append("## Risks Detected")
            lines.append("")
            lines.append("*No risks detected.*")
            lines.append("")

        # Add recommendations section
        if result.recommendations:
            lines.append("## Recommendations")
            lines.append("")
            for i, rec in enumerate(result.recommendations, 1):
                lines.append(f"### {i}. [{rec.priority.upper()}] {rec.type}")
                lines.append("")
                lines.append(rec.description)
                lines.append("")
                if rec.original_sql:
                    lines.append("**Original SQL**:")
                    lines.append(f"```sql\n{rec.original_sql}\n```")
                    lines.append("")
                if rec.suggested_sql:
                    lines.append("**Suggested SQL**:")
                    lines.append(f"```sql\n{rec.suggested_sql}\n```")
                    lines.append("")
                if rec.reason:
                    lines.append(f"**Reason**: {rec.reason}")
                    lines.append("")
        else:
            lines.append("## Recommendations")
            lines.append("")
            lines.append("*No recommendations.*")
            lines.append("")

        # Add baseline section if available
        if result.baseline:
            lines.append("## Baseline Performance")
            lines.append("")
            plan = result.baseline.get("explain_plan", {})
            lines.append(f"- **Scan Type**: {plan.get('scan_type', 'UNKNOWN')}")
            lines.append(f"- **Estimated Cost**: {plan.get('estimated_cost', 'N/A')}")
            lines.append(f"- **Estimated Rows**: {plan.get('estimated_rows', 'N/A')}")
            if result.baseline.get("execution_time_ms"):
                lines.append(
                    f"- **Execution Time**: {result.baseline.get('execution_time_ms')} ms"
                )
            lines.append("")

        return "\n".join(lines)

    def _build_empty_summary(self) -> str:
        """Build an empty summary when no results are available."""
        return """# SQL Optimization Summary

*No SQL statements found in this run.*

## Statistics

| Metric | Value |
|--------|-------|
| Total SQL Statements | 0 |
| Total Risks | 0 |
| High Risk | 0 |
| Medium Risk | 0 |
| Low Risk | 0 |
| Optimization Candidates | 0 |
| Baseline Collected | 0 |
| Validation Passed | 0 |
| Patches Applied | 0 |

## Risks Detected

*No risks detected.*

## Recommendations

*No recommendations available.*
"""

    def _load_template(self, name: str) -> str:
        """Load a text template from the template directory."""
        template_path = self.template_dir / name
        if template_path.exists():
            with open(template_path, "r", encoding="utf-8") as f:
                return f.read()
        # Return embedded template if file doesn't exist
        return self._get_embedded_template(name)

    def _load_json_template(self, name: str) -> dict[str, Any]:
        """Load a JSON template from the template directory."""
        template_path = self.template_dir / name
        if template_path.exists():
            with open(template_path, "r", encoding="utf-8") as f:
                return json.load(f)
        # Return embedded template if file doesn't exist
        return self._get_embedded_json_template(name)

    def _get_embedded_template(self, name: str) -> str:
        """Get embedded template string."""
        templates = {
            "summary.md": """# SQL Optimization Summary

## Statistics

| Metric | Value |
|--------|-------|
| Total SQL Statements | {{total_sql}} |
| Total Risks | {{total_risks}} |
| High Risk | {{high_risk}} |
| Medium Risk | {{medium_risk}} |
| Low Risk | {{low_risk}} |
| Optimization Candidates | {{optimization_candidates}} |
| Baseline Collected | {{baseline_collected}} |
| Validation Passed | {{validation_passed}} |
| Patches Applied | {{patch_applied}} |

## Risks Breakdown

{{risk_table}}

## Recommendations

{{recommendations_table}}
""",
        }
        return templates.get(name, "")

    def _get_embedded_json_template(self, name: str) -> dict[str, Any]:
        """Get embedded JSON template."""
        templates = {
            "detail.json": {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "title": "ReportDetail",
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "sql_key": {"type": "string"},
                    "summary": {
                        "type": "object",
                        "properties": {
                            "total_risks": {"type": "integer"},
                            "high_risk": {"type": "integer"},
                            "medium_risk": {"type": "integer"},
                            "low_risk": {"type": "integer"},
                            "optimization_candidates": {"type": "integer"},
                            "baseline_collected": {"type": "boolean"},
                            "validation_passed": {"type": "boolean"},
                            "patch_applied": {"type": "boolean"},
                        },
                    },
                    "risks": {"type": "array"},
                    "baseline": {"type": "object"},
                    "validation": {"type": "object"},
                    "recommendations": {"type": "array"},
                    "execution_time_ms": {"type": "number"},
                    "generated_at": {"type": "string"},
                },
            },
        }
        return templates.get(name, {})
