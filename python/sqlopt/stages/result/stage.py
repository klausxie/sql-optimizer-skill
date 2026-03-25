"""Result stage - generates optimization reports and patches."""

from __future__ import annotations

import difflib
import logging
import time
from pathlib import Path

from sqlopt.common.mock_data_loader import MockDataLoader
from sqlopt.common.summary_generator import StageSummary, generate_summary_markdown
from sqlopt.contracts.init import InitOutput
from sqlopt.contracts.optimize import OptimizationProposal, OptimizeOutput
from sqlopt.contracts.result import Patch, Report, ResultOutput
from sqlopt.stages.base import Stage

logger = logging.getLogger(__name__)


class ResultStage(Stage[None, ResultOutput]):
    """Result stage: generates optimization reports and patches.

    Input: None (reads from optimize and init stage outputs)
    Output: ResultOutput with report and patches
    """

    def __init__(self, run_id: str | None = None, use_mock: bool = True) -> None:
        """Initialize the result stage.

        Args:
            run_id: Optional run identifier. If not provided, uses stub data.
            use_mock: If True, use mock data for stage inputs when available.
        """
        super().__init__("result")
        self.run_id = run_id
        self.use_mock = use_mock

    def run(
        self,
        _input_data: None = None,
        run_id: str | None = None,
        use_mock: bool | None = None,
    ) -> ResultOutput:
        """Execute result stage.

        Args:
            input_data: None (not used, reads from previous stages)
            run_id: Optional run identifier override
            use_mock: Override for mock data usage

        Returns:
            ResultOutput with report and patches from real data
        """
        start_time = time.time()
        rid = run_id or self.run_id
        mock = use_mock if use_mock is not None else self.use_mock
        logger.info("=" * 60)
        logger.info("[RESULT] Starting Result stage")
        logger.info(f"[RESULT] Run ID: {rid}, Mock mode: {mock}")

        if rid is None:
            logger.warning("[RESULT] No run_id provided, using stub data")
            return self._create_stub_output()

        loader = MockDataLoader(rid, use_mock=mock)

        optimize_file = loader.get_optimize_proposals_path()
        logger.info(f"[RESULT] Proposals file: {optimize_file}")
        if not optimize_file.exists():
            logger.warning(f"[RESULT] Proposals file not found: {optimize_file}, using stub data")
            return self._create_stub_output()

        optimize_data = OptimizeOutput.from_json(optimize_file.read_text(encoding="utf-8"))
        logger.info(f"[RESULT] Loaded {len(optimize_data.proposals)} proposal(s) from optimize stage")

        init_file = loader.get_init_sql_units_path()
        logger.info(f"[RESULT] Init file: {init_file}")
        if not init_file.exists():
            logger.warning(f"[RESULT] Init file not found: {init_file}, using stub data")
            return self._create_stub_output()

        init_data = InitOutput.from_json(init_file.read_text(encoding="utf-8"))
        logger.info(f"[RESULT] Loaded {len(init_data.sql_units)} SQL unit(s) from init stage")

        sql_unit_map = {unit.id: unit for unit in init_data.sql_units}

        high_confidence_proposals = [p for p in optimize_data.proposals if p.confidence > 0.7]
        logger.info(f"[RESULT] High-confidence proposals (confidence > 0.7): {len(high_confidence_proposals)}")

        patches: list[Patch] = []
        for proposal in high_confidence_proposals:
            sql_unit = sql_unit_map.get(proposal.sql_unit_id)
            if sql_unit is None:
                logger.debug(f"[RESULT]   Skipping {proposal.sql_unit_id} - not found in init data")
                continue

            patch = self._create_patch(proposal, sql_unit.sql_text)
            patches.append(patch)
            logger.info("[RESULT]   [OK] %s: %s...", proposal.sql_unit_id, proposal.rationale[:50])

        report = self._create_report(optimize_data.proposals, high_confidence_proposals, patches)
        logger.info(f"[RESULT] Report summary: {report.summary}")

        output = ResultOutput(
            can_patch=len(patches) > 0,
            report=report,
            patches=patches,
        )

        self._write_output(output, rid)
        logger.info(f"[RESULT] Output written to: runs/{rid}/result/report.json")
        logger.info(f"[RESULT] Generated {len(patches)} patch(es)")

        # Generate SUMMARY.md (best-effort, don't block stage completion)
        duration_seconds = time.time() - start_time
        self._write_summary(
            output=output,
            run_id=rid,
            duration_seconds=duration_seconds,
            high_confidence_count=len(high_confidence_proposals),
        )

        logger.info("[RESULT] Result stage completed")
        return output

    def _create_patch(self, proposal: OptimizationProposal, original_xml: str) -> Patch:
        """Create a Patch from an optimization proposal.

        Args:
            proposal: The optimization proposal
            original_xml: Original SQL XML content

        Returns:
            Patch with diff
        """
        # Generate unified diff between original and optimized SQL
        original_lines = original_xml.splitlines(keepends=True)
        optimized_lines = proposal.optimized_sql.splitlines(keepends=True)

        diff_lines = list(
            difflib.unified_diff(
                original_lines,
                optimized_lines,
                fromfile="original",
                tofile="optimized",
                lineterm="",
            )
        )
        diff = "\n".join(diff_lines) if diff_lines else ""

        return Patch(
            sql_unit_id=proposal.sql_unit_id,
            original_xml=original_xml,
            patched_xml=proposal.optimized_sql,
            diff=diff,
        )

    def _create_report(
        self,
        all_proposals: list[OptimizationProposal],
        high_confidence: list[OptimizationProposal],
        patches: list[Patch],
    ) -> Report:
        """Create a Report from optimization analysis.

        Args:
            all_proposals: All optimization proposals
            high_confidence: Proposals with confidence > 0.7
            patches: Generated patches

        Returns:
            Report with summary and recommendations
        """
        total_proposals = len(all_proposals)
        high_conf_count = len(high_confidence)

        # Build summary
        if high_conf_count == 0:
            summary = "No high-confidence optimizations found (confidence > 0.7)"
        else:
            summary = (
                f"Found {high_conf_count} high-confidence optimization(s) out of {total_proposals} total proposals"
            )

        # Build details
        details_lines = [f"Total proposals analyzed: {total_proposals}"]
        details_lines.append(f"High-confidence proposals (confidence > 0.7): {high_conf_count}")
        details_lines.append(f"Patches generated: {len(patches)}")

        if high_confidence:
            details_lines.append("\nHigh-confidence optimizations:")
            details_lines.extend(
                f"  - [{p.sql_unit_id}] {p.rationale} (confidence: {p.confidence:.2f})" for p in high_confidence
            )

        details = "\n".join(details_lines)

        # Identify risks
        risks: list[str] = [
            f"Medium confidence ({p.confidence:.2f}) for {p.sql_unit_id} - verify before applying"
            for p in high_confidence
            if p.confidence < 0.8
        ]

        if not risks:
            risks.append("Low risk - all changes are straightforward optimizations")

        # Build recommendations
        recommendations: list[str] = []
        if high_confidence:
            recommendations.append(f"Apply {len(patches)} patch(es) to implement high-confidence optimizations")
        else:
            recommendations.append("Review SQL patterns manually for potential optimizations")
            recommendations.append("Consider adjusting confidence threshold if too restrictive")

        return Report(
            summary=summary,
            details=details,
            risks=risks,
            recommendations=recommendations,
        )

    def _create_stub_output(self) -> ResultOutput:
        """Create stub output when no run_id is available.

        Returns:
            Stub ResultOutput for development/testing
        """
        report = Report(
            summary="Optimization analysis complete",
            details="Found 1 optimization opportunity",
            risks=["Low risk"],
            recommendations=["Consider adding index on user_id"],
        )
        patch = Patch(
            sql_unit_id="stub-1",
            original_xml='<select id="findUser">SELECT * FROM users</select>',
            patched_xml='<select id="findUser">SELECT id, name FROM users</select>',
            diff="--- old\n+++ new\n-SELECT *\n+SELECT id, name",
        )
        return ResultOutput(
            can_patch=True,
            report=report,
            patches=[patch],
        )

    def _write_output(self, output: ResultOutput, run_id: str | None = None) -> None:
        """Write stage output to runs directory.

        Args:
            output: The result stage output to persist.
            run_id: Optional run identifier (uses self.run_id if not provided)
        """
        rid = run_id or self.run_id or "stub-run"
        output_dir = Path("runs") / rid / "result"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / "report.json"
        output_file.write_text(output.to_json())

    def _write_summary(
        self,
        output: ResultOutput,
        run_id: str,
        duration_seconds: float,
        high_confidence_count: int,
    ) -> None:
        """Generate and write SUMMARY.md for the result stage.

        Best-effort operation - errors are logged but do not block stage completion.

        Args:
            output: The result stage output.
            run_id: Run identifier.
            duration_seconds: Stage execution duration.
            high_confidence_count: Number of high-confidence proposals.
        """
        try:
            output_dir = Path("runs") / run_id / "result"

            report_size = len(output.report.summary) + len(output.report.details)

            summary = StageSummary(
                stage_name="result",
                run_id=run_id,
                duration_seconds=duration_seconds,
                sql_units_count=len(output.patches),
                branches_count=high_confidence_count,
                files_count=1,
                file_size_bytes=report_size,
                errors=[],
                warnings=output.report.risks[:5],
            )

            summary_content = generate_summary_markdown(summary)

            report_file = output_dir / "report.json"
            if report_file.exists():
                summary_content += f"\n\n## Output Files\n\n| File | Size |\n|------|------|\n| report.json | {report_file.stat().st_size:,} bytes |\n"

            summary_file = output_dir / "SUMMARY.md"
            summary_file.write_text(summary_content, encoding="utf-8")
            logger.info(f"[RESULT] Summary written to: runs/{run_id}/result/SUMMARY.md")
        except OSError as e:
            logger.warning(f"[RESULT] Failed to generate SUMMARY.md: {e}")
