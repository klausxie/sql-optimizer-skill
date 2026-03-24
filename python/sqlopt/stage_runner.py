"""Stage orchestrator for SQL Optimizer pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, cast

from sqlopt.common import save_json_file
from sqlopt.common.config import SQLOptConfig, load_config
from sqlopt.common.progress import STATUS_COMPLETED, STATUS_FAILED, ProgressTracker
from sqlopt.common.run_paths import RunPaths

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
        for stage in STAGE_ORDER:
            self.progress.register_stage(stage)

    def run_stage(self, stage_name: str, use_mock: bool = True) -> None:
        if stage_name not in STAGE_ORDER:
            raise ValueError(f"Invalid stage '{stage_name}'. Must be one of: {STAGE_ORDER}")
        self.paths.ensure_dirs()
        self.progress.start_stage(stage_name)
        try:
            if stage_name == "init":
                self._run_init_stage()
            elif stage_name == "parse":
                self._run_parse_stage(use_mock=use_mock)
            elif stage_name == "recognition":
                self._run_recognition_stage(use_mock=use_mock)
            elif stage_name == "optimize":
                self._run_optimize_stage(use_mock=use_mock)
            elif stage_name == "result":
                self._run_result_stage(use_mock=use_mock)
            self.progress.complete_stage(stage_name)
        except Exception as e:
            self.progress.fail_stage(stage_name, str(e))
            raise RuntimeError(f"Stage '{stage_name}' failed: {e}") from e

    def run_all(self) -> PipelineResult:
        self.paths.ensure_dirs()
        stage_results: dict[str, StageResult] = {}
        try:
            for stage in STAGE_ORDER:
                self.run_stage(stage)
                stage_results[stage] = StageResult(stage_name=stage, output={"status": "completed"})
            return PipelineResult(success=True, stage_results=stage_results)
        except RuntimeError as e:
            failed_stage = None
            for s in STAGE_ORDER:
                if self.progress.stages.get(s).status != STATUS_COMPLETED:
                    failed_stage = s
                    break
            if failed_stage:
                stage_results[failed_stage] = StageResult(stage_name=failed_stage, error=str(e))
            return PipelineResult(success=False, stage_results=stage_results)

    def _run_init_stage(self) -> None:
        from sqlopt.stages.init import InitStage

        stage = InitStage(self.config, self.run_id)
        result = stage.run()
        save_json_file(result, self.paths.init_sql_units)

    def _run_parse_stage(self, use_mock: bool = True) -> None:
        from sqlopt.stages.parse import ParseStage

        stage = ParseStage(self.run_id, use_mock=use_mock)
        result = stage.run()
        save_json_file(result, self.paths.parse_sql_units_with_branches)

    def _run_recognition_stage(self, use_mock: bool = True) -> None:
        from sqlopt.common.db_connector import create_connector
        from sqlopt.common.llm_mock_generator import OpenAILLMProvider, OpenCodeRunLLMProvider
        from sqlopt.stages.recognition import RecognitionStage

        db_connector = None
        llm_provider = None
        if self.config.db_host and self.config.db_port and self.config.db_name:
            db_connector = create_connector(
                platform=self.config.db_platform,
                host=self.config.db_host,
                port=self.config.db_port,
                db=self.config.db_name,
                user=self.config.db_user or "",
                password=self.config.db_password or "",
            )
        if self.config.llm_enabled:
            if self.config.llm_provider == "openai":
                llm_provider = OpenAILLMProvider(db_connector=db_connector)
            elif self.config.llm_provider == "opencode_run":
                llm_provider = OpenCodeRunLLMProvider(db_connector=db_connector)

        stage = RecognitionStage(self.run_id, llm_provider=llm_provider, use_mock=use_mock)
        result = stage.run(run_id=self.run_id)
        save_json_file(result, self.paths.recognition_baselines)

    def _run_optimize_stage(self, use_mock: bool = True) -> None:
        from sqlopt.common.db_connector import create_connector
        from sqlopt.common.llm_mock_generator import OpenAILLMProvider, OpenCodeRunLLMProvider
        from sqlopt.stages.optimize import OptimizeStage

        db_connector = None
        llm_provider = None
        if self.config.db_host and self.config.db_port and self.config.db_name:
            db_connector = create_connector(
                platform=self.config.db_platform,
                host=self.config.db_host,
                port=self.config.db_port,
                db=self.config.db_name,
                user=self.config.db_user or "",
                password=self.config.db_password or "",
            )
        if self.config.llm_enabled:
            if self.config.llm_provider == "openai":
                llm_provider = OpenAILLMProvider(db_connector=db_connector)
            elif self.config.llm_provider == "opencode_run":
                llm_provider = OpenCodeRunLLMProvider(db_connector=db_connector)

        stage = OptimizeStage(self.run_id, llm_provider=llm_provider, use_mock=use_mock)
        result = stage.run(run_id=self.run_id)
        save_json_file(result, self.paths.optimize_proposals)

    def _run_result_stage(self, use_mock: bool = True) -> None:
        from sqlopt.stages.result import ResultStage

        stage = ResultStage(self.run_id, use_mock=use_mock)
        result = stage.run(run_id=self.run_id)
        save_json_file(result, self.paths.result_report)

    def get_status(self) -> dict[str, Any]:
        return cast("dict[str, Any]", self.progress.get_status())

    def is_complete(self) -> bool:
        return all(self.progress.stages.get(stage).status == STATUS_COMPLETED for stage in STAGE_ORDER)

    def has_failures(self) -> bool:
        return any(self.progress.stages.get(stage).status == STATUS_FAILED for stage in STAGE_ORDER)
