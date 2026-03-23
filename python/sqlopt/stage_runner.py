"""Stage orchestrator for SQL Optimizer pipeline."""

from __future__ import annotations

import uuid

from sqlopt.common import save_json_file
from sqlopt.common.config import SQLOptConfig, load_config
from sqlopt.common.progress import STATUS_COMPLETED, STATUS_FAILED, ProgressTracker
from sqlopt.common.run_paths import RunPaths

STAGE_ORDER = ["init", "parse", "recognition", "optimize", "result"]


class StageRunner:
    def __init__(self, config_path: str, base_dir: str = "./runs") -> None:
        self.config: SQLOptConfig = load_config(config_path)
        self.run_id: str = str(uuid.uuid4())[:8]
        self.paths: RunPaths = RunPaths(self.run_id, base_dir)
        self.progress: ProgressTracker = ProgressTracker(self.run_id)
        for stage in STAGE_ORDER:
            self.progress.register_stage(stage)

    def run_stage(self, stage_name: str) -> None:
        if stage_name not in STAGE_ORDER:
            raise ValueError(f"Invalid stage '{stage_name}'. Must be one of: {STAGE_ORDER}")
        self.progress.start_stage(stage_name)
        try:
            if stage_name == "init":
                self._run_init_stage()
            elif stage_name == "parse":
                self._run_parse_stage()
            elif stage_name == "recognition":
                self._run_recognition_stage()
            elif stage_name == "optimize":
                self._run_optimize_stage()
            elif stage_name == "result":
                self._run_result_stage()
            self.progress.complete_stage(stage_name)
        except Exception as e:
            self.progress.fail_stage(stage_name, str(e))
            raise RuntimeError(f"Stage '{stage_name}' failed: {e}") from e

    def run_all(self) -> None:
        self.paths.ensure_dirs()
        for stage in STAGE_ORDER:
            self.run_stage(stage)

    def _run_init_stage(self) -> None:
        from sqlopt.stages.init import InitStage

        stage = InitStage()
        result = stage.run()
        save_json_file(result, self.paths.init_sql_units)

    def _run_parse_stage(self) -> None:
        from sqlopt.stages.parse import ParseStage

        stage = ParseStage()
        result = stage.run()
        save_json_file(result, self.paths.parse_sql_units_with_branches)

    def _run_recognition_stage(self) -> None:
        from sqlopt.stages.recognition import RecognitionStage

        stage = RecognitionStage()
        result = stage.run()
        save_json_file(result, self.paths.recognition_baselines)

    def _run_optimize_stage(self) -> None:
        from sqlopt.stages.optimize import OptimizeStage

        stage = OptimizeStage()
        result = stage.run()
        save_json_file(result, self.paths.optimize_proposals)

    def _run_result_stage(self) -> None:
        from sqlopt.stages.result import ResultStage

        stage = ResultStage()
        result = stage.run()
        save_json_file(result, self.paths.result_report)

    def get_status(self) -> dict:
        return self.progress.get_status()

    def is_complete(self) -> bool:
        return all(
            self.progress.stages.get(stage).status == STATUS_COMPLETED for stage in STAGE_ORDER
        )

    def has_failures(self) -> bool:
        return any(self.progress.stages.get(stage).status == STATUS_FAILED for stage in STAGE_ORDER)
