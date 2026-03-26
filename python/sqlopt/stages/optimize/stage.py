"""Optimize stage for SQL query optimization proposal generation."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Callable

from sqlopt.common.concurrent import BatchOptions, ConcurrentExecutor
from sqlopt.common.config import SQLOptConfig
from sqlopt.common.contract_file_manager import ContractFileManager
from sqlopt.common.llm_mock_generator import LLMProviderBase, MockLLMProvider
from sqlopt.common.mock_data_loader import MockDataLoader
from sqlopt.common.summary_generator import StageSummary, generate_summary_markdown
from sqlopt.contracts.optimize import OptimizationProposal, OptimizeOutput
from sqlopt.contracts.recognition import RecognitionOutput
from sqlopt.stages.base import Stage

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, tuple[int, int] | None], None]


class OptimizeStage(Stage[None, OptimizeOutput]):
    """Optimize stage generates optimization proposals for SQL queries."""

    def __init__(
        self,
        run_id: str | None = None,
        llm_provider: LLMProviderBase | None = None,
        use_mock: bool = True,
        config: SQLOptConfig | None = None,
    ) -> None:
        super().__init__("optimize")
        self.run_id = run_id
        self.llm_provider = llm_provider or MockLLMProvider()
        self.use_mock = use_mock
        self.config = config or SQLOptConfig()

    def run(
        self,
        input_data: None = None,
        run_id: str | None = None,
        use_mock: bool | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> OptimizeOutput:
        start_time = time.time()
        rid = run_id or self.run_id
        mock = use_mock if use_mock is not None else self.use_mock
        self._progress_callback = progress_callback
        logger.info("=" * 60)
        logger.info("[OPTIMIZE] Starting Optimize stage")
        logger.info(f"[OPTIMIZE] Run ID: {rid}, Mock mode: {mock}")

        if rid is None:
            logger.warning("[OPTIMIZE] No run_id provided, using stub data")
            return self._create_stub_output()

        loader = MockDataLoader(rid, use_mock=mock)
        baselines_file = loader.get_recognition_baselines_path()
        logger.info(f"[OPTIMIZE] Baselines file: {baselines_file}")

        if not baselines_file.exists():
            logger.warning(f"[OPTIMIZE] Baselines file not found: {baselines_file}, using stub data")
            return self._create_stub_output()

        baselines_data = RecognitionOutput.from_json(baselines_file.read_text(encoding="utf-8"))
        logger.info(f"[OPTIMIZE] Loaded {len(baselines_data.baselines)} baseline(s) from recognition stage")

        proposals: list[OptimizationProposal] = []
        logger.info(f"[OPTIMIZE] Processing {len(baselines_data.baselines)} baseline(s) for optimization")

        if self.config.concurrency.enabled:
            proposals = self._run_concurrent(baselines_data.baselines, self._progress_callback)
        else:
            proposals = self._run_sequential(baselines_data.baselines, self._progress_callback)

        logger.info(f"[OPTIMIZE] Generated {len(proposals)} proposal(s)")
        output = OptimizeOutput(proposals=proposals)
        self._write_output(rid, output)
        logger.info(f"[OPTIMIZE] Output written to: runs/{rid}/optimize/proposals.json")

        # Generate SUMMARY.md (best-effort, don't block on failure)
        self._generate_summary(rid, output, start_time)

        logger.info("[OPTIMIZE] Optimize stage completed")
        return output

    def _run_sequential(
        self, baselines: list, progress_callback: ProgressCallback | None
    ) -> list[OptimizationProposal]:
        proposals: list[OptimizationProposal] = []
        for idx, baseline in enumerate(baselines):
            if progress_callback:
                progress_callback(
                    f"Optimizing {idx + 1}/{len(baselines)}: {baseline.sql_unit_id}.{baseline.path_id}",
                    (idx + 1, len(baselines)),
                )
            if baseline.plan is None:
                logger.info(
                    f"[OPTIMIZE]   [SKIP] Skipping optimization for baseline_only (no plan): {baseline.sql_unit_id}.{baseline.path_id}"
                )
                continue

            try:
                logger.debug(f"[OPTIMIZE]   Generating optimization for {baseline.sql_unit_id}.{baseline.path_id}")
                proposal_json = self.llm_provider.generate_optimization(baseline.original_sql, "")
                proposal_data = json.loads(proposal_json)

                proposal = OptimizationProposal(
                    sql_unit_id=baseline.sql_unit_id,
                    path_id=baseline.path_id,
                    original_sql=baseline.original_sql,
                    optimized_sql=proposal_data["optimized_sql"],
                    rationale=proposal_data["rationale"],
                    confidence=proposal_data["confidence"],
                )
                proposals.append(proposal)
                logger.info(
                    "[OPTIMIZE]   [OK] %s.%s: confidence=%.2f",
                    baseline.sql_unit_id,
                    baseline.path_id,
                    proposal_data["confidence"],
                )
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "[OPTIMIZE]   [FAIL] Failed: %s.%s - %s",
                    baseline.sql_unit_id,
                    baseline.path_id,
                    str(e),
                )
                continue
        return proposals

    def _run_concurrent(
        self, baselines: list, progress_callback: ProgressCallback | None
    ) -> list[OptimizationProposal]:
        tasks = []
        for baseline in baselines:
            if baseline.plan is None:
                logger.info(
                    f"[OPTIMIZE]   [SKIP] Skipping optimization for baseline_only (no plan): {baseline.sql_unit_id}.{baseline.path_id}"
                )
                continue
            tasks.append(baseline)

        if not tasks:
            return []

        options = BatchOptions(
            max_workers=self.config.concurrency.max_workers,
            max_concurrent=self.config.concurrency.llm_max_concurrent,
            timeout_per_task=self.config.concurrency.timeout_per_task,
            retry_count=self.config.concurrency.retry_count,
            retry_delay=float(self.config.concurrency.retry_delay),
        )

        proposals: list[OptimizationProposal] = []
        total = len(tasks)
        completed = 0

        def process_task(baseline) -> OptimizationProposal | None:
            proposal_json = self.llm_provider.generate_optimization(baseline.original_sql, "")
            proposal_data = json.loads(proposal_json)
            return OptimizationProposal(
                sql_unit_id=baseline.sql_unit_id,
                path_id=baseline.path_id,
                original_sql=baseline.original_sql,
                optimized_sql=proposal_data["optimized_sql"],
                rationale=proposal_data["rationale"],
                confidence=proposal_data["confidence"],
            )

        with ConcurrentExecutor(options) as executor:
            results = executor.map(process_task, tasks)

        for result in results:
            completed += 1
            if result.success and result.result:
                proposals.append(result.result)
                if progress_callback:
                    progress_callback(
                        f"Optimizing {completed}/{total}: {result.result.sql_unit_id}.{result.result.path_id}",
                        (completed, total),
                    )
                logger.info(
                    "[OPTIMIZE]   [OK] %s.%s (%d/%d): confidence=%.2f",
                    result.result.sql_unit_id,
                    result.result.path_id,
                    completed,
                    total,
                    result.result.confidence,
                )
            else:
                baseline = result.item
                if progress_callback:
                    progress_callback(
                        f"Optimizing {completed}/{total}: {baseline.sql_unit_id}.{baseline.path_id}",
                        (completed, total),
                    )
                logger.warning(
                    "[OPTIMIZE]   [FAIL] %s.%s (%d/%d): %s",
                    baseline.sql_unit_id,
                    baseline.path_id,
                    completed,
                    total,
                    result.error,
                )

        return proposals

    def _create_stub_output(self) -> OptimizeOutput:
        return OptimizeOutput(
            proposals=[
                OptimizationProposal(
                    sql_unit_id="stub-1",
                    path_id="p1",
                    original_sql="SELECT * FROM users",
                    optimized_sql="SELECT id, name FROM users",
                    rationale="Reduce columns to improve performance",
                    confidence=0.9,
                )
            ]
        )

    def _write_output(self, run_id: str, output: OptimizeOutput) -> None:
        """Write optimize output to per-unit files and backward-compatible single file.

        Creates:
        - runs/{run_id}/optimize/units/{unit_id}.json (per unit)
        - runs/{run_id}/optimize/units/_index.json (unit ID list)
        - runs/{run_id}/optimize/proposals.json (backward compat)
        """
        output_dir = Path("runs") / run_id / "optimize"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Always write backward-compatible proposals.json
        compat_path = output_dir / "proposals.json"
        compat_path.write_text(output.to_json(), encoding="utf-8")

        if not output.proposals:
            logger.debug("[OPTIMIZE] No proposals to write, wrote empty proposals.json")
            return

        file_manager = ContractFileManager(run_id, "optimize")

        proposals_by_unit: dict[str, list[dict]] = {}
        for proposal in output.proposals:
            if proposal.sql_unit_id not in proposals_by_unit:
                proposals_by_unit[proposal.sql_unit_id] = []
            proposals_by_unit[proposal.sql_unit_id].append(
                {
                    "sql_unit_id": proposal.sql_unit_id,
                    "path_id": proposal.path_id,
                    "original_sql": proposal.original_sql,
                    "optimized_sql": proposal.optimized_sql,
                    "rationale": proposal.rationale,
                    "confidence": proposal.confidence,
                }
            )

        unit_ids: list[str] = []
        total_bytes = 0
        for unit_id, proposals in proposals_by_unit.items():
            unit_data = {
                "sql_unit_id": unit_id,
                "proposals": proposals,
            }
            path = file_manager.write_unit_file(unit_id, unit_data)
            total_bytes += file_manager.get_file_size(path)
            unit_ids.append(unit_id)

        # Write index
        index_path = file_manager.write_index(unit_ids)
        total_bytes += file_manager.get_file_size(index_path)

        compat_bytes = file_manager.get_file_size(compat_path)

        logger.info(
            f"[OPTIMIZE] Wrote {len(unit_ids)} unit file(s) ({total_bytes} bytes) "
            f"+ index + compat file ({compat_bytes} bytes)"
        )

    def _generate_summary(
        self,
        run_id: str,
        output: OptimizeOutput,
        start_time: float,
    ) -> None:
        """Generate SUMMARY.md for the optimize stage.

        Best-effort operation - errors are logged but don't block stage completion.
        """
        try:
            duration_seconds = time.time() - start_time
            proposals = output.proposals

            proposals_count = len(proposals)
            avg_confidence = 0.0
            high_confidence_count = 0
            low_confidence_count = 0

            if proposals:
                confidences = [p.confidence for p in proposals]
                avg_confidence = sum(confidences) / len(confidences)
                high_confidence_count = sum(1 for c in confidences if c >= 0.7)
                low_confidence_count = sum(1 for c in confidences if c < 0.7)

            output_dir = Path("runs") / run_id / "optimize"
            file_size_bytes = 0
            files_count = 0

            if output_dir.exists():
                for file_path in output_dir.rglob("*.json"):
                    if file_path.is_file():
                        file_size_bytes += file_path.stat().st_size
                        files_count += 1

            warnings = [
                f"High confidence proposals (>=0.7): {high_confidence_count}",
                f"Low confidence proposals (<0.7): {low_confidence_count}",
                f"Average confidence: {avg_confidence:.2f}",
            ]

            summary = StageSummary(
                stage_name="optimize",
                run_id=run_id,
                duration_seconds=duration_seconds,
                sql_units_count=proposals_count,
                branches_count=0,  # Optimize stage doesn't produce branches
                files_count=files_count,
                file_size_bytes=file_size_bytes,
                warnings=warnings,
            )

            markdown = generate_summary_markdown(summary)
            summary_path = output_dir / "SUMMARY.md"
            summary_path.write_text(markdown, encoding="utf-8")
            logger.info(f"[OPTIMIZE] SUMMARY.md written to: {summary_path}")

        except Exception as e:  # noqa: BLE001
            logger.warning(f"[OPTIMIZE] Failed to generate SUMMARY.md: {e}")
