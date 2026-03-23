"""
V9-aligned workflow engine.

This orchestrator executes the canonical five-stage pipeline:
init -> parse -> recognition -> optimize -> patch.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Tuple, Type
import json
import time
import logging
import sqlite3

from ..contracts import ContractValidator
from ..progress import get_progress_reporter
from ..run_paths import canonical_paths
from ..v9_pipeline import STAGE_ORDER, require_v9_stage
from .status_resolver import StatusResolver, PhaseExecutionPolicy
from .requests import AdvanceStepRequest, RunStatusRequest
from .v9_stages import build_stage_registry, run_stage

logger = logging.getLogger(__name__)

MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 1

TRANSIENT_ERROR_TYPES: Tuple[Type[Exception], ...] = (
    ConnectionError,
    TimeoutError,
    ConnectionResetError,
    ConnectionRefusedError,
    ConnectionAbortedError,
    BrokenPipeError,
    sqlite3.OperationalError,
    sqlite3.InterfaceError,
)

TRANSIENT_ERROR_PATTERNS: frozenset[str] = frozenset(
    {
        "timeout",
        "timed out",
        "connection",
        "network",
        "transient",
        "temporarily",
        "unavailable",
        "refused",
        "reset",
        "lost connection",
        "deadlock",
        "retry",
        "temporary failure",
    }
)


def _is_transient_error(error: Exception) -> bool:
    if isinstance(error, TRANSIENT_ERROR_TYPES):
        return True

    error_str = str(error).lower()
    for pattern in TRANSIENT_ERROR_PATTERNS:
        if pattern in error_str:
            return True

    return False


def _execute_with_retry(
    func: Callable[..., Any],
    *args: Any,
    max_attempts: int = MAX_RETRY_ATTEMPTS,
    **kwargs: Any,
) -> Any:
    last_error: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_error = e

            if not _is_transient_error(e):
                logger.debug(
                    f"Non-transient error in {func.__name__}: {e}. Not retrying."
                )
                raise

            if attempt < max_attempts:
                logger.warning(
                    f"Transient error in {func.__name__} (attempt {attempt}/{max_attempts}): {e}. "
                    f"Retrying in {RETRY_DELAY_SECONDS}s..."
                )
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                logger.error(
                    f"All {max_attempts} attempts failed for {func.__name__}: {e}"
                )

    if last_error is not None:
        raise last_error


@dataclass
class V9WorkflowState:
    """状态快照，用于持久化"""

    run_id: str = ""
    current_stage: str = ""
    completed_stages: list[str] = field(default_factory=list)
    stage_results: dict[str, dict] = field(default_factory=dict)
    started_at: str = ""
    updated_at: str = ""
    status: str = "pending"


@dataclass
class NextAction:
    """下一步动作"""

    action: str
    stage: Optional[str] = None
    reason: str = ""


DEFAULT_PHASE_POLICIES = {
    "init": PhaseExecutionPolicy(phase="init", allow_regenerate=False),
    "parse": PhaseExecutionPolicy(phase="parse", allow_regenerate=False),
    "recognition": PhaseExecutionPolicy(phase="recognition", allow_regenerate=False),
    "optimize": PhaseExecutionPolicy(phase="optimize", allow_regenerate=False),
    "patch": PhaseExecutionPolicy(phase="patch", allow_regenerate=False),
}


class V9WorkflowEngine:
    def __init__(
        self,
        config: dict,
        repository: Optional[Any] = None,
        run_id: Optional[str] = None,
        status_resolver: Optional[StatusResolver] = None,
        validator: Optional[ContractValidator] = None,
    ):
        self.config = config
        self.repository = repository
        self.run_id = run_id or f"run_{int(time.time())}"
        self.state = V9WorkflowState(
            run_id=self.run_id,
            started_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        self.stages: dict[str, Callable[[Path], dict[str, Any]]] = {}
        self._status_resolver = status_resolver or self._create_default_resolver()
        self._validator = validator or ContractValidator(
            Path(__file__).resolve().parents[3]
        )
        self._register_stages()

    def _create_default_resolver(self) -> StatusResolver:
        return StatusResolver(
            stage_order=STAGE_ORDER,
            phase_policies=DEFAULT_PHASE_POLICIES,
        )

    # -------------------------------------------------------------------------
    # Pipeline Configuration Support
    # -------------------------------------------------------------------------

    def _get_pipeline_config(self) -> dict[str, Any]:
        """Get pipeline configuration from config dict.

        Returns:
            Pipeline config dict with stages list, or empty dict if not defined.
        """
        pipeline = self.config.get("pipeline", {})
        if isinstance(pipeline, dict):
            return pipeline
        return {}

    def _get_stage_enabled_map(self) -> dict[str, bool]:
        """Build a map of stage name to enabled status from config.

        Returns:
            Dict mapping stage name to whether it's enabled.
            Defaults to True for all stages if not specified in config.
        """
        pipeline = self._get_pipeline_config()
        stages_config = pipeline.get("stages", [])

        # Start with all stages enabled by default
        enabled_map = {stage: True for stage in STAGE_ORDER}

        # Apply config overrides
        if isinstance(stages_config, list):
            for stage_config in stages_config:
                if isinstance(stage_config, dict):
                    name = stage_config.get("name")
                    if name in enabled_map:
                        enabled_map[name] = stage_config.get("enabled", True)

        return enabled_map

    def _is_stage_enabled(self, stage_name: str) -> bool:
        """Check if a stage is enabled based on config.

        Args:
            stage_name: Name of the stage to check.

        Returns:
            True if stage should run, False if disabled.
        """
        enabled_map = self._get_stage_enabled_map()
        return enabled_map.get(stage_name, True)

    def get_stage_config(self, stage_name: str) -> dict[str, Any]:
        """Get configuration for a specific stage.

        Args:
            stage_name: Name of the stage.

        Returns:
            Stage-specific config dict, or empty dict if not defined.
        """
        pipeline = self._get_pipeline_config()
        stages_config = pipeline.get("stages", [])

        if isinstance(stages_config, list):
            for stage_config in stages_config:
                if (
                    isinstance(stage_config, dict)
                    and stage_config.get("name") == stage_name
                ):
                    return stage_config.get("config", {})

        return {}

    def _register_stages(self) -> None:
        """Register the canonical V9 stage runners."""
        self.stages = build_stage_registry(
            config=self.config,
            validator=self._validator,
        )

    def _require_known_stage(self, stage_name: str) -> str:
        return require_v9_stage(stage_name)

    def _snapshot(self) -> dict[str, Any]:
        return {
            "run_id": self.state.run_id,
            "current_stage": self.state.current_stage,
            "completed_stages": self.state.completed_stages,
            "status": self.state.status,
        }

    def _update_timestamp(self) -> None:
        """更新时间戳"""
        self.state.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def _persist_state(self) -> None:
        """持久化状态到 repository（如果存在）"""
        self._update_timestamp()
        if self.repository is not None:
            state_dict = {
                "run_id": self.state.run_id,
                "current_stage": self.state.current_stage,
                "completed_stages": self.state.completed_stages,
                "stage_results": self.state.stage_results,
                "started_at": self.state.started_at,
                "updated_at": self.state.updated_at,
                "status": self.state.status,
            }
            self.repository.save_state(state_dict)

    def load_state_from_repo(self) -> None:
        """从 repository 加载当前 V9 状态格式。"""
        if self.repository is not None:
            state_dict = self.repository.load_state()
            if not isinstance(state_dict, dict) or not state_dict:
                return
            self.state.run_id = state_dict.get("run_id", self.state.run_id)
            self.state.current_stage = state_dict.get("current_stage", "")
            self.state.completed_stages = state_dict.get("completed_stages", [])
            self.state.stage_results = state_dict.get("stage_results", {})
            self.state.started_at = state_dict.get("started_at", "")
            self.state.updated_at = state_dict.get("updated_at", "")
            self.state.status = state_dict.get("status", "pending")

    def run(
        self,
        run_dir: Path,
        to_stage: str = "patch",
    ) -> dict[str, Any]:
        target_stage = self._require_known_stage(to_stage)
        results = {}

        # 初始化 repository（如果存在）
        if self.repository is not None:
            self.repository.initialize(self.config, self.run_id)
            self.state.status = "running"
            self._persist_state()

        for stage_name in STAGE_ORDER:
            if stage_name not in self.stages:
                continue

            if not self._is_stage_enabled(stage_name):
                continue

            self.state.current_stage = stage_name
            self._persist_state()

            stage_fn = self.stages[stage_name]
            get_progress_reporter().report_phase_start(
                stage_name, description="starting..."
            )
            try:
                result = _execute_with_retry(stage_fn, run_dir)
                results[stage_name] = result
                self.state.stage_results[stage_name] = result

                if not result.get("success", False):
                    self.state.status = "failed"
                    self._persist_state()
                    break

                self.state.completed_stages.append(stage_name)
                self._persist_state()
                get_progress_reporter().report_phase_complete(stage_name)
                if isinstance(result, dict) and "output_files" in result:
                    for f in result["output_files"]:
                        get_progress_reporter().report_info(f"  output: {f}")

            except Exception as e:
                results[stage_name] = {
                    "success": False,
                    "error": str(e),
                }
                self.state.stage_results[stage_name] = results[stage_name]
                self.state.status = "failed"
                self._persist_state()
                break

            if stage_name == target_stage:
                break

        # 所有阶段完成
        if self.state.status == "running":
            self.state.status = "completed"
        self._persist_state()

        return results

    def advance_one_step(
        self,
        run_dir: Path,
        to_stage: str = "patch",
    ) -> dict[str, Any]:
        """
        单步执行 - 只执行下一个阶段。

        支持可恢复执行，每次调用只推进一个阶段。

        Args:
            run_dir: 运行目录
            to_stage: 目标阶段

        Returns:
            dict with keys:
            - completed: bool - 是否已完成所有阶段（或到达目标）
            - stage: str - 当前执行/已完成的阶段
            - result: dict - 阶段执行结果
            - state: dict - 当前状态快照
        """
        target_stage = self._require_known_stage(to_stage)

        # 初始化 repository 并尝试加载之前保存的状态
        if self.repository is not None:
            self.repository.initialize(self.config, self.run_id)
            self.load_state_from_repo()

        # 确定下一个要执行的阶段
        next_stage = None
        for stage_name in STAGE_ORDER:
            if stage_name not in self.state.completed_stages and self._is_stage_enabled(
                stage_name
            ):
                next_stage = stage_name
                break

        all_enabled_done = all(
            s in self.state.completed_stages or not self._is_stage_enabled(s)
            for s in STAGE_ORDER
        )
        if next_stage is None and all_enabled_done:
            self.state.status = "completed"
            self._persist_state()
            return {
                "completed": True,
                "stage": None,
                "result": None,
                "state": self._snapshot(),
            }

        # 检查是否已完成所有阶段
        if next_stage is None:
            self.state.status = "completed"
            self._persist_state()
            return {
                "completed": True,
                "stage": None,
                "result": None,
                "state": self._snapshot(),
            }

        # 检查是否已到达目标阶段
        if self.state.completed_stages:
            last_completed_idx = STAGE_ORDER.index(self.state.completed_stages[-1])
            to_stage_idx = STAGE_ORDER.index(target_stage)
            if last_completed_idx >= to_stage_idx:
                return {
                    "completed": True,
                    "stage": self.state.completed_stages[-1],
                    "result": self.state.stage_results.get(
                        self.state.completed_stages[-1]
                    ),
                    "state": self._snapshot(),
                }

        # 执行下一个阶段
        self.state.current_stage = next_stage
        self._persist_state()

        if next_stage not in self.stages:
            return {
                "completed": False,
                "stage": next_stage,
                "result": {"success": False, "error": f"Unknown stage: {next_stage}"},
                "state": self._snapshot(),
            }

        stage_fn = self.stages[next_stage]
        get_progress_reporter().report_phase_start(
            next_stage, description="starting..."
        )
        try:
            result = _execute_with_retry(stage_fn, run_dir)
            self.state.stage_results[next_stage] = result

            if result.get("success", False):
                self.state.completed_stages.append(next_stage)
                self._persist_state()
                get_progress_reporter().report_phase_complete(next_stage)
                if isinstance(result, dict) and "output_files" in result:
                    for f in result["output_files"]:
                        get_progress_reporter().report_info(f"  output: {f}")
            else:
                self.state.status = "failed"
                self._persist_state()

            return {
                "completed": False,
                "stage": next_stage,
                "result": result,
                "state": self._snapshot(),
            }

        except Exception as e:
            result = {"success": False, "error": str(e)}
            self.state.stage_results[next_stage] = result
            self.state.status = "failed"
            self._persist_state()
            return {
                "completed": False,
                "stage": next_stage,
                "result": result,
                "state": self._snapshot(),
            }

    def resume(
        self,
        run_dir: Path,
        to_stage: str = "patch",
    ) -> dict[str, Any]:
        """从断点恢复执行。

        检查已完成阶段，只执行未完成的阶段。

        Args:
            run_dir: 运行目录
            to_stage: 目标阶段

        Returns:
            各阶段执行结果
        """
        target_stage = self._require_known_stage(to_stage)
        state = self._load_state(run_dir)
        if state:
            self.state = state

        results = {}

        for stage_name in STAGE_ORDER:
            if stage_name not in self.stages:
                continue

            if not self._is_stage_enabled(stage_name):
                continue

            # 检查阶段是否已完成
            if stage_name in self.state.completed_stages:
                stage_result = self.state.stage_results.get(
                    stage_name, {"success": True, "skipped": True}
                )
                results[stage_name] = stage_result
                continue

            stage_fn = self.stages[stage_name]
            get_progress_reporter().report_phase_start(
                stage_name, description="starting..."
            )
            try:
                result = _execute_with_retry(stage_fn, run_dir)
                results[stage_name] = result

                if result.get("success", False):
                    self.state.completed_stages.append(stage_name)
                    self.state.stage_results[stage_name] = result
                    get_progress_reporter().report_phase_complete(stage_name)
                    if isinstance(result, dict) and "output_files" in result:
                        for f in result["output_files"]:
                            get_progress_reporter().report_info(f"  output: {f}")
                else:
                    self.state.status = "failed"
                    break

            except Exception as e:
                results[stage_name] = {
                    "success": False,
                    "error": str(e),
                }
                self.state.status = "failed"
                break

            self.state.current_stage = stage_name

            if stage_name == target_stage:
                break

        # 更新状态
        self.state.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if self.state.status != "failed":
            if self._is_complete_to_stage(target_stage):
                self.state.status = "completed"

        self._save_state(run_dir)

        return results

    def get_next_action(self, run_dir: Path, to_stage: str = "patch") -> NextAction:
        """获取下一步应该执行的动作。

        Args:
            run_dir: 运行目录
            to_stage: 目标阶段

        Returns:
            NextAction 对象，包含动作、阶段和原因
        """
        target_stage = self._require_known_stage(to_stage)
        state = self._load_state(run_dir)
        if not state:
            for stage_name in STAGE_ORDER:
                if self._is_stage_enabled(stage_name):
                    return NextAction(
                        action="run",
                        stage=stage_name,
                        reason="No previous state found, start fresh run",
                    )
            return NextAction(
                action="none",
                stage=None,
                reason="No enabled stages found in pipeline config",
            )

        self.state = state

        # 检查是否已完成到目标阶段
        if self._is_complete_to_stage(target_stage):
            return NextAction(
                action="none",
                stage=None,
                reason=f"Already completed to stage '{target_stage}'",
            )

        # 找到下一个未完成的阶段
        for stage_name in STAGE_ORDER:
            if stage_name not in self.state.completed_stages and self._is_stage_enabled(
                stage_name
            ):
                # For recognition stage, check if baselines.json exists and is complete
                if stage_name == "recognition":
                    paths = canonical_paths(run_dir)
                    baselines_path = paths.recognition_results_path
                    if baselines_path.exists() and baselines_path.stat().st_size > 0:
                        # Check if baselines file has content
                        try:
                            with open(baselines_path) as f:
                                baselines_data = json.load(f)
                            if baselines_data and len(baselines_data) > 0:
                                # Baselines exist and have content - skip recognition
                                self.state.completed_stages.append("recognition")
                                self._save_state(run_dir)
                                return NextAction(
                                    action="skip",
                                    stage=stage_name,
                                    reason="baselines.json exists and is complete",
                                )
                        except Exception:
                            pass  # If can't read, don't skip

                return NextAction(
                    action="resume",
                    stage=stage_name,
                    reason=f"Resume from incomplete stage '{stage_name}'",
                )

        return NextAction(
            action="none",
            stage=None,
            reason="All enabled stages completed",
        )

    def _is_complete_to_stage(self, to_stage: str) -> bool:
        """检查是否已完成到指定阶段。

        Args:
            to_stage: 目标阶段

        Returns:
            如果已完成返回 True
        """
        # 将状态转换为 StatusResolver 期望的格式
        resolver_state = self._to_resolver_state()

        return self._status_resolver.is_complete_to_stage(
            resolver_state, to_stage, include_report=False
        )

    def _to_resolver_state(self) -> dict[str, Any]:
        """将 V9WorkflowState 转换为 StatusResolver 期望的格式。

        Returns:
            转换后的状态字典
        """
        stage_status = {}
        for stage in STAGE_ORDER:
            if stage in self.state.completed_stages:
                stage_status[stage] = "DONE"
            elif stage == self.state.current_stage:
                stage_status[stage] = "IN_PROGRESS"
            else:
                stage_status[stage] = "PENDING"

        return {
            "stage_status": stage_status,
            "current_stage": self.state.current_stage,
            "statements": {},  # 当前状态快照默认不记录语句级跟踪
        }

    def _load_state(self, run_dir: Path) -> Optional[V9WorkflowState]:
        """从运行目录加载状态。

        Args:
            run_dir: 运行目录

        Returns:
            加载的状态，如果不存在返回 None
        """
        state_path = canonical_paths(run_dir).state_path
        if not state_path.exists():
            return None

        try:
            with open(state_path) as f:
                data = json.load(f)
            return V9WorkflowState(**data)
        except Exception:
            return None

    def _save_state(self, run_dir: Path) -> None:
        """保存状态到运行目录。

        Args:
            run_dir: 运行目录
        """
        state_path = canonical_paths(run_dir).state_path
        state_path.parent.mkdir(parents=True, exist_ok=True)

        with open(state_path, "w") as f:
            json.dump(
                {
                    "run_id": self.state.run_id,
                    "current_stage": self.state.current_stage,
                    "completed_stages": self.state.completed_stages,
                    "stage_results": self.state.stage_results,
                    "started_at": self.state.started_at,
                    "updated_at": self.state.updated_at,
                    "status": self.state.status,
                },
                f,
                indent=2,
            )


def run_v9_workflow(config: dict, run_dir: Path, to_stage: str = "patch") -> dict:
    engine = V9WorkflowEngine(config)
    return engine.run(run_dir, to_stage)


def runs_root(config: dict) -> Path:
    root_path = config.get("project", {}).get("root_path", ".")
    return Path(root_path).resolve() / "runs"


def advance_one_step_request(request: AdvanceStepRequest) -> dict[str, Any]:
    engine = V9WorkflowEngine(
        config=request.config,
        repository=request.repository,
        run_id=request.run_dir.name if request.run_dir else None,
        validator=request.validator,
    )
    return engine.advance_one_step(request.run_dir, request.to_stage)


def build_status_snapshot(request: RunStatusRequest) -> dict[str, Any]:
    root_path = request.config.get("project", {}).get("root_path", ".")
    runs_root_path = Path(root_path).resolve() / "runs"

    return {
        "run_id": request.run_id,
        "status": request.state.get("status", "unknown"),
        "current_stage": request.state.get("current_stage", ""),
        "completed_stages": request.state.get("completed_stages", []),
        "stage_results": request.state.get("stage_results", {}),
        "to_stage": request.plan.get("to_stage", "patch") if request.plan else "patch",
        "runs_root": str(runs_root_path),
        "meta": {
            "status": request.meta.get("status", "") if request.meta else "",
            "started_at": request.state.get("started_at", "") if request.state else "",
            "updated_at": request.state.get("updated_at", "") if request.state else "",
        },
    }
