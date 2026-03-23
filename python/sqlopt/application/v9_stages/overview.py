"""
V9 Stage Overview Generator - Base class for generating markdown overview reports.

Provides reusable rendering methods for V9 stage overview reports.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class StageOverviewGenerator:
    """Base class for generating markdown overview reports for V9 stages.

    Provides common rendering methods for stage overview reports with
    consistent formatting and structure.

    Usage:
        gen = StageOverviewGenerator("init", Path("runs/run_xxx/init"))
        report_path = gen.write(sql_units_data, "init.overview.md")
    """

    def __init__(self, stage_name: str, output_dir: Path):
        """Initialize the overview generator.

        Args:
            stage_name: Name of the stage (e.g., "init", "parse", "recognition").
            output_dir: Directory where stage output files are located.
        """
        self.stage_name = stage_name
        self.output_dir = Path(output_dir)

    def generate(self, data: dict[str, Any]) -> str:
        """Generate markdown overview report from stage data.

        Args:
            data: Stage output data dictionary.

        Returns:
            Markdown string of the overview report.
        """
        raise NotImplementedError("Subclasses must implement generate()")

    def write(self, data: dict[str, Any], filename: str) -> Path:
        """Generate and write overview report to file.

        Args:
            data: Stage output data dictionary.
            filename: Output filename (e.g., "init.overview.md").

        Returns:
            Path to the written file.
        """
        markdown = self.generate(data)
        output_path = self.output_dir / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
        return output_path

    def _render_header(self, stage_name: str, summary: str) -> str:
        """Render the report header with stage name and summary.

        Args:
            stage_name: Name of the stage.
            summary: Executive summary text.

        Returns:
            Formatted markdown header.
        """
        return f"""# {stage_name.title()} Stage Overview

## 执行摘要
{summary}
"""

    def _render_table(self, headers: list[str], rows: list[list[Any]]) -> str:
        """Render a markdown table.

        Args:
            headers: List of column header strings.
            rows: List of row data (each row is a list of values).

        Returns:
            Formatted markdown table.
        """
        if not headers:
            return ""

        # Build header row
        lines = ["## 关键指标", "", "| " + " | ".join(headers) + " |"]
        lines.append("| " + " | ".join(["------"] * len(headers)) + " |")

        # Build data rows
        for row in rows:
            cells = [str(cell) if cell is not None else "" for cell in row]
            lines.append("| " + " | ".join(cells) + " |")

        return "\n".join(lines) + "\n"

    def _render_bullet_list(self, items: list[str]) -> str:
        """Render a bullet list.

        Args:
            items: List of bullet point strings.

        Returns:
            Formatted markdown bullet list.
        """
        if not items:
            return ""
        return "\n".join(f"- {item}" for item in items) + "\n"

    def _render_risk_summary(self, risks: list[dict[str, Any]]) -> str:
        """Render a risk summary section.

        Args:
            risks: List of risk dictionaries with keys like:
                - severity: "high", "medium", "low"
                - risk_type: Type of risk (e.g., "prefix_wildcard")
                - description: Human-readable description
                - location: Where the risk was found

        Returns:
            Formatted markdown risk summary section.
        """
        if not risks:
            return ""

        lines = ["## 问题与风险", ""]

        # Group risks by severity
        high_risks = [r for r in risks if r.get("severity") == "high"]
        medium_risks = [r for r in risks if r.get("severity") == "medium"]
        low_risks = [r for r in risks if r.get("severity") == "low"]

        if high_risks:
            lines.append("### 🔴 高风险")
            for risk in high_risks:
                lines.append(
                    f"- **{risk.get('risk_type', 'unknown')}**: {risk.get('description', '')}"
                )
            lines.append("")

        if medium_risks:
            lines.append("### 🟡 中风险")
            for risk in medium_risks:
                lines.append(
                    f"- **{risk.get('risk_type', 'unknown')}**: {risk.get('description', '')}"
                )
            lines.append("")

        if low_risks:
            lines.append("### 🟢 低风险")
            for risk in low_risks:
                lines.append(
                    f"- **{risk.get('risk_type', 'unknown')}**: {risk.get('description', '')}"
                )
            lines.append("")

        return "\n".join(lines) + "\n"


class InitOverviewGenerator(StageOverviewGenerator):
    """Overview generator for the Init stage.

    Generates markdown report summarizing SQL unit extraction results.
    """

    def generate(self, data: dict[str, Any]) -> str:
        """Generate Init stage overview markdown report.

        Args:
            data: Dictionary containing sql_units list from init stage.

        Returns:
            Markdown string of the overview report.
        """
        sql_units = data.get("sql_units", [])
        total_count = len(sql_units)

        # Statement type distribution
        type_counts: dict[str, int] = {}
        for unit in sql_units:
            stype = unit.get("statementType", "UNKNOWN")
            type_counts[stype] = type_counts.get(stype, 0) + 1

        # Dynamic SQL count (has if/choose/foreach)
        dynamic_count = sum(1 for unit in sql_units if unit.get("dynamicFeatures"))

        # Cross-file reference count
        cross_file_count = sum(1 for unit in sql_units if unit.get("includeTrace"))

        # Build summary
        summary_parts = [f"扫描完成，共提取 {total_count} 个 SQL 语句"]
        if dynamic_count > 0:
            summary_parts.append(f"检测到 {dynamic_count} 个动态 SQL")
        if cross_file_count > 0:
            summary_parts.append(f"发现 {cross_file_count} 个跨文件引用")
        summary = "，".join(summary_parts) + "。"

        # Build header
        lines = [self._render_header("init", summary)]

        # Build table
        headers = ["指标", "数值"]
        rows = [
            ["SQL 总数", total_count],
            ["SELECT", type_counts.get("SELECT", 0)],
            ["INSERT", type_counts.get("INSERT", 0)],
            ["UPDATE", type_counts.get("UPDATE", 0)],
            ["DELETE", type_counts.get("DELETE", 0)],
            ["动态 SQL", dynamic_count],
            ["跨文件引用", cross_file_count],
        ]
        lines.append(self._render_table(headers, rows))

        # Build detail section
        lines.append("## 详情")
        lines.append("- 数据来源: `init/sql_units.json`")
        lines.append("- 扫描配置文件: `sqlopt.yml`")

        return "\n".join(lines) + "\n"


class ParseOverviewGenerator(StageOverviewGenerator):
    """Overview generator for the Parse stage.

    Generates markdown report summarizing branch generation and risk detection results.
    """

    def generate(self, data: dict[str, Any]) -> str:
        """Generate Parse stage overview markdown report.

        Args:
            data: Dictionary containing sql_units_with_branches and risks from parse stage.

        Returns:
            Markdown string of the overview report.
        """
        sql_units = data.get("sql_units_with_branches", [])
        risks = data.get("risks", [])

        total_units = len(sql_units)
        total_branches = sum(u.get("branchCount", 0) for u in sql_units)
        units_with_branches = sum(1 for u in sql_units if u.get("branchCount", 0) > 0)

        # Risk summary
        high_risks = [r for r in risks if r.get("severity") == "high"]
        medium_risks = [r for r in risks if r.get("severity") == "medium"]
        low_risks = [r for r in risks if r.get("severity") == "low"]

        # Build summary
        summary_parts = [f"解析完成，共生成 {total_branches} 个分支路径"]
        if len(risks) > 0:
            summary_parts.append(f"检测到 {len(risks)} 个风险")
        if len(high_risks) > 0:
            summary_parts.append(f"其中 {len(high_risks)} 个高风险")
        summary = "，".join(summary_parts) + "。"

        # Build header
        lines = [self._render_header("parse", summary)]

        # Build table
        headers = ["指标", "数值"]
        rows = [
            ["SQL 单元数", total_units],
            ["分支路径总数", total_branches],
            ["含分支的单元数", units_with_branches],
            ["风险总数", len(risks)],
            ["🔴 高风险", len(high_risks)],
            ["🟡 中风险", len(medium_risks)],
            ["🟢 低风险", len(low_risks)],
        ]
        lines.append(self._render_table(headers, rows))

        # Build risk summary
        if risks:
            lines.append(self._render_risk_summary(risks[:10]))  # Top 10 risks
            if len(risks) > 10:
                lines.append(f"- ... 还有 {len(risks) - 10} 个风险")
            lines.append("")

        # Build detail section
        lines.append("## 详情")
        lines.append("- 分支数据: `parse/sql_units_with_branches.json`")
        lines.append("- 风险数据: `parse/risks.json`")

        return "\n".join(lines) + "\n"


class RecognitionOverviewGenerator(StageOverviewGenerator):
    """Overview generator for the Recognition stage.

    Generates markdown report summarizing EXPLAIN analysis and baseline results.
    """

    def generate(self, data: dict[str, Any]) -> str:
        """Generate Recognition stage overview markdown report.

        Args:
            data: Dictionary containing baselines from recognition stage.

        Returns:
            Markdown string of the overview report.
        """
        baselines = data.get("baselines", [])

        total_baselines = len(baselines)
        successful_baselines = sum(1 for b in baselines if b.get("success", False))
        failed_baselines = total_baselines - successful_baselines

        # Performance issues
        slow_queries = sum(1 for b in baselines if b.get("is_slow", False))
        high_cost_queries = sum(
            1 for b in baselines if b.get("estimated_cost", 0) > 1000
        )

        # Build summary
        summary_parts = [f"识别完成，共分析 {total_baselines} 个 SQL 执行计划"]
        if failed_baselines > 0:
            summary_parts.append(f"{failed_baselines} 个分析失败")
        if slow_queries > 0:
            summary_parts.append(f"发现 {slow_queries} 个慢查询")
        summary = "，".join(summary_parts) + "。"

        # Build header
        lines = [self._render_header("recognition", summary)]

        # Build table
        headers = ["指标", "数值"]
        rows = [
            ["EXPLAIN 分析数", total_baselines],
            ["成功", successful_baselines],
            ["失败", failed_baselines],
            ["慢查询", slow_queries],
            ["高成本查询", high_cost_queries],
        ]
        lines.append(self._render_table(headers, rows))

        # Build detail section
        lines.append("## 详情")
        lines.append("- 基线数据: `recognition/baselines.json`")

        return "\n".join(lines) + "\n"


class OptimizeOverviewGenerator(StageOverviewGenerator):
    """Overview generator for the Optimize stage.

    Generates markdown report summarizing optimization proposals.
    """

    def generate(self, data: dict[str, Any]) -> str:
        """Generate Optimize stage overview markdown report.

        Args:
            data: Dictionary containing proposals from optimize stage.

        Returns:
            Markdown string of the overview report.
        """
        proposals = data.get("proposals", [])

        total_proposals = len(proposals)
        verified_proposals = sum(1 for p in proposals if p.get("verified", False))
        pending_proposals = total_proposals - verified_proposals

        # Proposal types
        type_counts: dict[str, int] = {}
        for p in proposals:
            ptype = p.get("type", "unknown")
            type_counts[ptype] = type_counts.get(ptype, 0) + 1

        # Build summary
        summary_parts = [f"优化完成，共生成 {total_proposals} 个优化建议"]
        if verified_proposals > 0:
            summary_parts.append(f"其中 {verified_proposals} 个已验证")
        summary = "，".join(summary_parts) + "。"

        # Build header
        lines = [self._render_header("optimize", summary)]

        # Build table
        headers = ["指标", "数值"]
        rows = [
            ["优化建议总数", total_proposals],
            ["已验证", verified_proposals],
            ["待验证", pending_proposals],
        ]
        for ptype, count in sorted(type_counts.items()):
            rows.append([f"类型: {ptype}", count])
        lines.append(self._render_table(headers, rows))

        # Build detail section
        lines.append("## 详情")
        lines.append("- 优化建议: `optimize/proposals.json`")

        return "\n".join(lines) + "\n"


class PatchOverviewGenerator(StageOverviewGenerator):
    """Overview generator for the Patch stage.

    Generates markdown report summarizing patch generation and application results.
    """

    def generate(self, data: dict[str, Any]) -> str:
        """Generate Patch stage overview markdown report.

        Args:
            data: Dictionary containing patches from patch stage.

        Returns:
            Markdown string of the overview report.
        """
        patches_data = data.get("patches", {})
        patches = (
            patches_data.get("patches", [])
            if isinstance(patches_data, dict)
            else patches_data
        )

        total_patches = len(patches)
        pending_patches = sum(1 for p in patches if p.get("status") == "pending")
        approved_patches = sum(1 for p in patches if p.get("status") == "approved")
        applied_patches = sum(1 for p in patches if p.get("status") == "applied")

        # Build summary
        summary_parts = [f"补丁生成完成，共 {total_patches} 个补丁"]
        if applied_patches > 0:
            summary_parts.append(f"其中 {applied_patches} 个已应用")
        elif approved_patches > 0:
            summary_parts.append(f"其中 {approved_patches} 个已确认待应用")
        summary = "，".join(summary_parts) + "。"

        # Build header
        lines = [self._render_header("patch", summary)]

        # Build table
        headers = ["指标", "数值"]
        rows = [
            ["补丁总数", total_patches],
            ["待确认", pending_patches],
            ["已确认", approved_patches],
            ["已应用", applied_patches],
        ]
        lines.append(self._render_table(headers, rows))

        # Build detail section
        lines.append("## 详情")
        lines.append("- 补丁数据: `patch/patches.json`")
        lines.append("- 补丁文件: `patch/patches/`")

        return "\n".join(lines) + "\n"
