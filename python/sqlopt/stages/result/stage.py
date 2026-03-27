"""Result stage - generates optimization reports and patches."""

from __future__ import annotations

import difflib
import json
import logging
import time
from typing import Callable

from sqlopt.common.mock_data_loader import MockDataLoader
from sqlopt.common.summary_generator import StageSummary, generate_summary_markdown
from sqlopt.common.xml_patch_engine import XmlPatchEngine
from sqlopt.contracts.init import InitOutput, TableSchema
from sqlopt.contracts.optimize import OptimizationProposal, OptimizeOutput
from sqlopt.contracts.recognition import PerformanceBaseline, RecognitionOutput
from sqlopt.contracts.result import Patch, Report, ResultOutput
from sqlopt.stages.base import Stage

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, tuple[int, int] | None], None]


class ResultStage(Stage[None, ResultOutput]):
    """Result stage: generates optimization reports and patches.

    Input: None (reads from optimize and init stage outputs)
    Output: ResultOutput with report and patches
    """

    def __init__(self, run_id: str | None = None, use_mock: bool = True, base_dir: str = "./runs") -> None:
        """Initialize the result stage.

        Args:
            run_id: Optional run identifier. If not provided, uses stub data.
            use_mock: If True, use mock data for stage inputs when available.
        """
        super().__init__("result", base_dir=base_dir)
        self.run_id = run_id
        self.use_mock = use_mock

    def run(
        self,
        _input_data: None = None,
        run_id: str | None = None,
        use_mock: bool | None = None,
        progress_callback: ProgressCallback | None = None,
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

        loader = MockDataLoader(rid, use_mock=mock, base_dir=self.base_dir)

        optimize_file = loader.get_optimize_proposals_path()
        logger.info(f"[RESULT] Proposals file: {optimize_file}")
        if not optimize_file.exists():
            logger.warning(f"[RESULT] Proposals file not found: {optimize_file}, using stub data")
            return self._create_stub_output()

        optimize_data = OptimizeOutput.from_json(optimize_file.read_text(encoding="utf-8"))
        logger.info(f"[RESULT] Loaded {len(optimize_data.proposals)} proposal(s) from optimize stage")
        if progress_callback:
            progress_callback(f"Loaded {len(optimize_data.proposals)} proposal(s)")

        init_file = loader.get_init_sql_units_path()
        logger.info(f"[RESULT] Init file: {init_file}")
        if not init_file.exists():
            logger.warning(f"[RESULT] Init file not found: {init_file}, using stub data")
            return self._create_stub_output()

        init_data = InitOutput.from_json(init_file.read_text(encoding="utf-8"))
        logger.info(f"[RESULT] Loaded {len(init_data.sql_units)} SQL unit(s) from init stage")

        sql_unit_map = {unit.id: unit for unit in init_data.sql_units}

        baselines_file = loader.get_recognition_baselines_path()
        baseline_only_risks: list[str] = []
        if baselines_file.exists():
            try:
                baselines_data = RecognitionOutput.from_json(baselines_file.read_text(encoding="utf-8"))
                baseline_only_baselines = [b for b in baselines_data.baselines if b.plan is None]
                if baseline_only_baselines:
                    logger.info(
                        f"[RESULT] Found {len(baseline_only_baselines)} baseline_only branch(es) for static analysis"
                    )
                    table_schemas = self._load_table_schemas(loader)
                    baseline_only_risks = self._analyze_baseline_only_branches(
                        baseline_only_baselines, sql_unit_map, table_schemas
                    )
            except (OSError, TypeError, ValueError, json.JSONDecodeError) as e:
                logger.warning(f"[RESULT] Failed to load baselines for static analysis: {e}")

        patch_candidates = [p for p in optimize_data.proposals if self._should_generate_patch(p)]
        logger.info(f"[RESULT] Patch-ready proposals: {len(patch_candidates)}")

        patches: list[Patch] = []
        unit_ids: list[str] = []
        for proposal in patch_candidates:
            sql_unit = sql_unit_map.get(proposal.sql_unit_id)
            if sql_unit is None:
                logger.debug(f"[RESULT]   Skipping {proposal.sql_unit_id} - not found in init data")
                continue

            patch = self._create_patch(proposal, sql_unit.sql_text, sql_unit)
            patches.append(patch)
            unit_ids.append(proposal.sql_unit_id)
            self._write_unit_patch(proposal.sql_unit_id, patch)
            self._write_unit_meta(proposal.sql_unit_id, proposal, sql_unit)
            logger.info("[RESULT]   [OK] %s: %s...", proposal.sql_unit_id, proposal.rationale[:50])

        self._write_units_index(unit_ids)

        report = self._create_report(optimize_data.proposals, patch_candidates, patches, baseline_only_risks)
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
            high_confidence_count=len(patch_candidates),
        )

        logger.info("[RESULT] Result stage completed")
        return output

    @staticmethod
    def _create_patch(proposal: OptimizationProposal, original_xml: str, sql_unit: InitOutput.SQLUnit) -> Patch:
        """Create a Patch from an optimization proposal.

        Args:
            proposal: The optimization proposal
            original_xml: Original SQL XML content
            sql_unit: The SQL unit containing mapper file path

        Returns:
            Patch with diff in Git Patch format
        """
        if proposal.actions:
            patched_xml = XmlPatchEngine.apply_actions(proposal.actions, original_xml)
        else:
            patched_xml = proposal.optimized_sql

        original_lines = original_xml.splitlines(keepends=True)
        patched_lines = patched_xml.splitlines(keepends=True)

        diff_lines = list(
            difflib.unified_diff(
                original_lines,
                patched_lines,
                fromfile=sql_unit.mapper_file,
                tofile=sql_unit.mapper_file,
                lineterm="",
            )
        )
        diff = "\n".join(diff_lines) if diff_lines else ""

        return Patch(
            sql_unit_id=proposal.sql_unit_id,
            original_xml=original_xml,
            patched_xml=patched_xml,
            diff=diff,
        )

    def _write_unit_patch(self, unit_id: str, patch: Patch) -> None:
        """Write a single unit's .patch file."""
        paths = self.resolve_run_paths(self.run_id or "stub-run")
        patch_file = paths.result_unit_patch(unit_id)
        patch_file.parent.mkdir(parents=True, exist_ok=True)
        patch_file.write_text(patch.diff, encoding="utf-8")

    def _write_unit_meta(self, unit_id: str, proposal: OptimizationProposal, sql_unit: InitOutput.SQLUnit) -> None:
        """Write a single unit's .meta.json file."""
        paths = self.resolve_run_paths(self.run_id or "stub-run")
        action = proposal.actions[0] if proposal.actions else None
        meta = {
            "sql_unit_id": unit_id,
            "sql_id": sql_unit.sql_id,
            "mapper_file": sql_unit.mapper_file,
            "xpath": proposal.unit_summary.unit_xpath if proposal.unit_summary else "",
            "operation": action.operation if action else "UNKNOWN",
            "confidence": proposal.confidence,
            "rationale": proposal.rationale,
            "original_snippet": action.original_snippet if action else "",
            "rewritten_snippet": action.rewritten_snippet if action else "",
            "issue_type": action.issue_type if action else None,
        }
        meta_file = paths.result_unit_meta(unit_id)
        meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_units_index(self, unit_ids: list[str]) -> None:
        """Write index file listing all unit IDs."""
        paths = self.resolve_run_paths(self.run_id or "stub-run")
        index = {"units": unit_ids}
        paths.result_units_dir.mkdir(parents=True, exist_ok=True)
        paths.result_units_index.write_text(json.dumps(index, indent=2), encoding="utf-8")

    def _create_report(
        self,
        all_proposals: list[OptimizationProposal],
        patch_candidates: list[OptimizationProposal],
        patches: list[Patch],
        baseline_only_risks: list[str] | None = None,
    ) -> Report:
        """Create a Report from optimization analysis.

        Args:
            all_proposals: All optimization proposals
            patch_candidates: Proposals considered safe enough to patch
            patches: Generated patches
            baseline_only_risks: Static risk analysis for baseline_only branches

        Returns:
            Report with summary and recommendations
        """
        total_proposals = len(all_proposals)
        verified = self._sort_by_impact([p for p in all_proposals if self._is_verified_improvement(p)])
        needs_validation = self._sort_by_impact([p for p in all_proposals if self._needs_more_validation(p)])
        mismatches = self._sort_by_impact([p for p in all_proposals if self._is_result_mismatch(p)])
        failed_validation = self._sort_by_impact([p for p in all_proposals if self._is_validation_failure(p)])

        if verified:
            summary = f"Found {len(verified)} verified optimization(s) out of {total_proposals} total proposal(s)"
        elif needs_validation:
            summary = f"Found {len(needs_validation)} optimization candidate(s) that still need validation"
        else:
            summary = "No verified optimizations found"

        details_lines = [f"Total proposals analyzed: {total_proposals}"]
        details_lines.append(f"Verified optimizations: {len(verified)}")
        details_lines.append(f"Need more validation: {len(needs_validation)}")
        details_lines.append(f"Validation mismatches: {len(mismatches)}")
        details_lines.append(f"Validation failures: {len(failed_validation)}")
        details_lines.append(f"Patches generated: {len(patches)}")

        if verified:
            details_lines.append("")
            details_lines.append("Verified optimizations:")
            details_lines.extend(self._format_ranked_items(verified))

        if needs_validation:
            details_lines.append("")
            details_lines.append("Need more validation:")
            details_lines.extend(self._format_ranked_items(needs_validation))

        if mismatches:
            details_lines.append("")
            details_lines.append("Result mismatches:")
            details_lines.extend(self._format_ranked_items(mismatches))

        if failed_validation:
            details_lines.append("")
            details_lines.append("Validation failures:")
            details_lines.extend(self._format_ranked_items(failed_validation))

        if baseline_only_risks:
            details_lines.append("")
            details_lines.append("Baseline-only static analysis (no EXPLAIN performed):")
            details_lines.extend(f"  - {risk}" for risk in baseline_only_risks)

        details = "\n".join(details_lines)

        risks: list[str] = []
        risks.extend(
            f"{proposal.sql_unit_id}.{proposal.path_id} result mismatch after optimization" for proposal in mismatches
        )
        risks.extend(
            f"{proposal.sql_unit_id}.{proposal.path_id} validation failed: {proposal.validation_error or 'unknown error'}"
            for proposal in failed_validation
        )
        risks.extend(
            f"{proposal.sql_unit_id}.{proposal.path_id} still needs validation before patching"
            for proposal in needs_validation[:5]
        )
        if baseline_only_risks:
            risks.extend(baseline_only_risks)
        if not risks:
            risks.append("Low risk - verified optimizations preserved baseline behavior")

        recommendations: list[str] = []
        if patch_candidates:
            recommendations.append(f"Apply {len(patches)} verified patch(es) with highest impact first")
        if needs_validation:
            recommendations.append("Run the listed candidates against a representative test dataset before patching")
        if mismatches or failed_validation:
            recommendations.append("Review mismatched or failed validations before accepting those optimizations")
        if not recommendations:
            recommendations.append("Review SQL patterns manually for potential optimizations")

        return Report(
            summary=summary,
            details=details,
            risks=risks,
            recommendations=recommendations,
        )

    @staticmethod
    def _should_generate_patch(proposal: OptimizationProposal) -> bool:
        if proposal.validation_status is None:
            return proposal.confidence > 0.7
        if proposal.validation_status != "validated":
            return False
        if proposal.result_equivalent is False:
            return False
        return not (proposal.gain_ratio is not None and proposal.gain_ratio <= 0)

    @staticmethod
    def _is_verified_improvement(proposal: OptimizationProposal) -> bool:
        if proposal.validation_status == "validated" and proposal.result_equivalent is not False:
            return proposal.gain_ratio is None or proposal.gain_ratio > 0
        return False

    @staticmethod
    def _needs_more_validation(proposal: OptimizationProposal) -> bool:
        if proposal.validation_status is None:
            return proposal.confidence > 0.7
        return proposal.validation_status in {"estimated_only", "explained_only", "validated_without_baseline"}

    @staticmethod
    def _is_result_mismatch(proposal: OptimizationProposal) -> bool:
        return proposal.validation_status == "result_mismatch" or proposal.result_equivalent is False

    @staticmethod
    def _is_validation_failure(proposal: OptimizationProposal) -> bool:
        return proposal.validation_status == "validation_failed"

    def _sort_by_impact(self, proposals: list[OptimizationProposal]) -> list[OptimizationProposal]:
        return sorted(proposals, key=self._proposal_impact_score, reverse=True)

    @staticmethod
    def _proposal_impact_score(proposal: OptimizationProposal) -> float:
        before_metrics = proposal.before_metrics or {}
        baseline_metric = before_metrics.get("actual_time_ms")
        if baseline_metric is None:
            baseline_metric = before_metrics.get("estimated_cost")
        if baseline_metric is None:
            baseline_metric = before_metrics.get("rows_examined", 0.0)
        gain_ratio = proposal.gain_ratio or 0.0
        return float(baseline_metric or 0.0) * max(gain_ratio, 0.0)

    @staticmethod
    def _format_ranked_items(proposals: list[OptimizationProposal]) -> list[str]:
        lines: list[str] = []
        for proposal in proposals:
            gain = f"{proposal.gain_ratio:.2%}" if proposal.gain_ratio is not None else "n/a"
            lines.append(
                f"  - [{proposal.sql_unit_id}.{proposal.path_id}] {proposal.rationale} "
                f"(status: {proposal.validation_status or 'legacy'}, gain: {gain}, confidence: {proposal.confidence:.2f})"
            )
        return lines

    @staticmethod
    def _load_table_schemas(loader: MockDataLoader) -> dict[str, TableSchema]:
        schemas: dict[str, TableSchema] = {}
        try:
            schemas_file = loader.get_init_table_schemas_path()
            if schemas_file.exists():
                schemas_data = json.loads(schemas_file.read_text(encoding="utf-8"))
                schemas = {k: TableSchema(**v) for k, v in schemas_data.items()}
                logger.info(f"[RESULT] Loaded {len(schemas)} table schema(s) for static analysis")
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as e:
            logger.warning(f"[RESULT] Failed to load table schemas: {e}")
        return schemas

    @staticmethod
    def _analyze_baseline_only_branches(
        baselines: list[PerformanceBaseline],
        sql_unit_map: dict[str, InitOutput.SQLUnit],
        table_schemas: dict[str, TableSchema],
    ) -> list[str]:
        risks: list[str] = []
        for baseline in baselines:
            sql_unit = sql_unit_map.get(baseline.sql_unit_id)
            if not sql_unit:
                continue
            sql_lower = sql_unit.sql_text.lower()
            risk_factors: list[str] = []
            table_size = None
            for table_name, schema in table_schemas.items():
                if table_name.lower() in sql_lower:
                    table_size = getattr(schema, "size", None)
                    break
            if table_size == "large":
                if "select *" in sql_lower:
                    risk_factors.append("SELECT * on large table")
                if "limit" not in sql_lower:
                    risk_factors.append("no LIMIT on large table")
                if "where" not in sql_lower:
                    risk_factors.append("no WHERE clause (full scan)")
            if risk_factors:
                risk_level = "HIGH" if len(risk_factors) >= 2 else "MEDIUM"
                risks.append(f"[{baseline.sql_unit_id}.{baseline.path_id}] {risk_level}: {'; '.join(risk_factors)}")
            else:
                risks.append(f"[{baseline.sql_unit_id}.{baseline.path_id}] LOW: baseline only, no obvious issues")
        return risks

    @staticmethod
    def _create_stub_output() -> ResultOutput:
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
        output_dir = self.resolve_run_paths(rid).result_dir
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
            output_dir = self.resolve_run_paths(run_id).result_dir

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
