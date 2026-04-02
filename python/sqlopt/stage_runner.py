"""Stage orchestrator for SQL Optimizer pipeline."""

from __future__ import annotations

import logging
import pathlib
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, cast

from sqlopt.common.config import SQLOptConfig, load_config
from sqlopt.common.progress import STATUS_COMPLETED, STATUS_FAILED, ProgressTracker
from sqlopt.common.progress_display import ProgressDisplay
from sqlopt.common.run_paths import RunPaths
from sqlopt.common.runtime_factory import create_db_connector_from_config, create_llm_provider_from_config

logger = logging.getLogger(__name__)

STAGE_ORDER = ["init", "parse", "recognition", "optimize", "result"]


@dataclass
class StageResult:
    """Result from a single stage."""

    stage_name: str
    output: dict | None = None
    error: str | None = None


@dataclass
class PipelineResult:
    """Result from running the full pipeline."""

    success: bool
    stage_results: dict[str, StageResult] = field(default_factory=dict)


class StageRunner:
    def __init__(
        self,
        config_path: str,
        base_dir: str = "./runs",
        run_id: str | None = None,
        auto_latest: bool = False,
    ) -> None:
        self.config: SQLOptConfig = load_config(config_path)
        self.base_dir = base_dir

        if run_id:
            self.run_id = run_id
        elif auto_latest:
            latest = RunPaths.find_latest_run_id(base_dir)
            if latest is None:
                raise ValueError("No run directory found. Run 'init' first.")
            self.run_id = latest
        else:
            self.run_id = datetime.now().strftime("run-%Y%m%d-%H%M%S")

        self.paths: RunPaths = RunPaths(self.run_id, base_dir)
        self.progress: ProgressTracker = ProgressTracker(self.run_id)
        self.display: ProgressDisplay = ProgressDisplay()
        for stage in STAGE_ORDER:
            self.progress.register_stage(stage)

    def run_stage(self, stage_name: str, use_mock: bool = False) -> None:
        if stage_name not in STAGE_ORDER:
            raise ValueError(f"Invalid stage '{stage_name}'. Must be one of: {STAGE_ORDER}")

        stage_idx = STAGE_ORDER.index(stage_name) + 1
        start_time = time.time()

        self.paths.ensure_dirs()
        self.progress.start_stage(stage_name)

        def progress_cb(message: str = "", sub_progress: tuple[int, int] | None = None) -> None:
            self.display.update(stage_name, stage_idx, message, sub_progress)

        try:
            if stage_name == "init":
                self._run_init_stage(progress_cb)
            elif stage_name == "parse":
                self._run_parse_stage(use_mock=use_mock, progress_cb=progress_cb)
            elif stage_name == "recognition":
                self._run_recognition_stage(use_mock=use_mock, progress_cb=progress_cb)
            elif stage_name == "optimize":
                self._run_optimize_stage(use_mock=use_mock, progress_cb=progress_cb)
            elif stage_name == "result":
                self._run_result_stage(use_mock=use_mock, progress_cb=progress_cb)

            elapsed = time.time() - start_time
            self.progress.complete_stage(stage_name)
            self.display.finish(stage_name, elapsed)
        except Exception as e:
            self.progress.fail_stage(stage_name, str(e))
            elapsed = time.time() - start_time
            self.display.finish(stage_name, elapsed, success=False, details=str(e))
            raise RuntimeError(f"Stage '{stage_name}' failed: {e}") from e

    def run_all(self, use_mock: bool = False) -> PipelineResult:
        logger.info("=" * 60)
        logger.info("[RUNNER] Starting full pipeline execution")
        pipeline_start = time.time()
        self.paths.ensure_dirs()
        self.display.start_pipeline(self.run_id)
        stage_results: dict[str, StageResult] = {}
        try:
            for stage in STAGE_ORDER:
                self.run_stage(stage, use_mock=use_mock)
                stage_results[stage] = StageResult(stage_name=stage, output={"status": "completed"})
            logger.info("[RUNNER] Full pipeline completed successfully")
            src = pathlib.Path(self.config.project_root_path) / "docs" / "current" / "data-contracts.md"
            dst = self.paths.run_dir / "DATA_CONTRACTS.md"
            if src.exists():
                shutil.copy(src, dst)
            self.display.finish_pipeline(success=True, elapsed=time.time() - pipeline_start)
            return PipelineResult(success=True, stage_results=stage_results)
        except RuntimeError as e:
            failed_stage = None
            for s in STAGE_ORDER:
                if self.progress.stages.get(s).status != STATUS_COMPLETED:
                    failed_stage = s
                    break
            if failed_stage:
                stage_results[failed_stage] = StageResult(stage_name=failed_stage, error=str(e))
            logger.error(f"[RUNNER] Full pipeline failed at stage '{failed_stage}': {e}")
            self.display.finish_pipeline(success=False, elapsed=time.time() - pipeline_start)
            return PipelineResult(success=False, stage_results=stage_results)

    def _run_init_stage(self, progress_cb: Any = None) -> None:
        from sqlopt.stages.init import InitStage

        logger.info("[RUNNER] Initializing InitStage...")
        stage = InitStage(self.config, self.run_id, base_dir=self.base_dir)
        stage.run(progress_callback=progress_cb)
        logger.info(f"[RUNNER] Init stage output: {self.paths.init_sql_units}")

    def _run_parse_stage(self, use_mock: bool = True, progress_cb: Any = None) -> None:
        from sqlopt.stages.parse import ParseStage

        logger.info("[RUNNER] Initializing ParseStage...")
        stage = ParseStage(self.run_id, use_mock=use_mock, config=self.config, base_dir=self.base_dir)
        stage.run(progress_callback=progress_cb)
        logger.info(f"[RUNNER] Parse stage output: {self.paths.parse_units_dir}")

    def _run_recognition_stage(self, use_mock: bool = True, progress_cb: Any = None) -> None:
        from sqlopt.stages.recognition import RecognitionStage

        db_connector = create_db_connector_from_config(self.config)
        if db_connector is not None:
            logger.info(
                f"[RUNNER] DB connector created: {self.config.db_platform}://{self.config.db_host}:{self.config.db_port}/{self.config.db_name}"
            )
        llm_provider = create_llm_provider_from_config(self.config, db_connector)
        if llm_provider is not None:
            logger.info("[RUNNER] LLM provider: %s", self.config.llm_provider)
        else:
            logger.info("[RUNNER] LLM disabled - using mock mode")

        logger.info("[RUNNER] Initializing RecognitionStage...")
        stage = RecognitionStage(
            self.run_id,
            llm_provider=llm_provider,
            use_mock=use_mock,
            config=self.config,
            db_connector=db_connector,
            base_dir=self.base_dir,
        )
        stage.run(run_id=self.run_id, progress_callback=progress_cb)
        logger.info(f"[RUNNER] Recognition stage output: {self.paths.recognition_baselines}")

    def _run_optimize_stage(self, use_mock: bool = True, progress_cb: Any = None) -> None:
        from sqlopt.stages.optimize import OptimizeStage

        db_connector = create_db_connector_from_config(self.config)
        llm_provider = create_llm_provider_from_config(self.config, db_connector)

        logger.info("[RUNNER] Initializing OptimizeStage...")
        stage = OptimizeStage(
            self.run_id,
            llm_provider=llm_provider,
            use_mock=use_mock,
            config=self.config,
            db_connector=db_connector,
            base_dir=self.base_dir,
        )
        stage.run(run_id=self.run_id, progress_callback=progress_cb)
        logger.info(f"[RUNNER] Optimize stage output: {self.paths.optimize_proposals}")

    def _run_result_stage(self, use_mock: bool = True, progress_cb: Any = None) -> None:
        from sqlopt.stages.result import ResultStage

        logger.info("[RUNNER] Initializing ResultStage...")
        stage = ResultStage(self.run_id, use_mock=use_mock, base_dir=self.base_dir)
        stage.run(run_id=self.run_id, progress_callback=progress_cb)
        logger.info(f"[RUNNER] Result stage output: {self.paths.result_report}")

    def get_status(self) -> dict[str, Any]:
        return cast("dict[str, Any]", self.progress.get_status())

    def is_complete(self) -> bool:
        return all(self.progress.stages.get(stage).status == STATUS_COMPLETED for stage in STAGE_ORDER)

    def has_failures(self) -> bool:
        return any(self.progress.stages.get(stage).status == STATUS_FAILED for stage in STAGE_ORDER)
