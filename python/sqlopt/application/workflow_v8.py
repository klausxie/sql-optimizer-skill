"""
V8 Workflow Engine - 7 Stage Pipeline

Independent implementation with zero coupling to legacy workflow.
Supports resume from interruption point.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Tuple, Type
import json
import time
import logging
import sqlite3

from .status_resolver import StatusResolver, PhaseExecutionPolicy, StatusResolution
from .requests import AdvanceStepRequest, RunStatusRequest

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

TRANSIENT_ERROR_PATTERNS = [
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
]


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
class V8WorkflowState:
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


STAGE_ORDER = [
    "init",
    "parse",
    "recognition",
    "optimize",
    "patch",
]

DEFAULT_PHASE_POLICIES = {
    "init": PhaseExecutionPolicy(phase="init", allow_regenerate=False),
    "parse": PhaseExecutionPolicy(phase="parse", allow_regenerate=False),
    "recognition": PhaseExecutionPolicy(phase="recognition", allow_regenerate=False),
    "optimize": PhaseExecutionPolicy(phase="optimize", allow_regenerate=False),
    "patch": PhaseExecutionPolicy(phase="patch", allow_regenerate=False),
}


class V8WorkflowEngine:
    def __init__(
        self,
        config: dict,
        repository: Optional[Any] = None,
        run_id: Optional[str] = None,
        status_resolver: Optional[StatusResolver] = None,
    ):
        self.config = config
        self.repository = repository
        self.run_id = run_id or f"run_{int(time.time())}"
        self.state = V8WorkflowState(
            run_id=self.run_id,
            started_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        self.stages = {}
        self._status_resolver = status_resolver or self._create_default_resolver()
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

    def _register_stages(self):
        """Register V9 stages: init, parse, recognition, optimize, patch"""
        self.stages["init"] = self._run_init
        self.stages["parse"] = self._run_parse
        self.stages["recognition"] = self._run_recognition
        self.stages["optimize"] = self._run_optimize
        self.stages["patch"] = self._run_patch

    def _build_stage_context(self, run_dir: Path, stage_name: str):
        from ..stages.base import StageContext
        from ..run_paths import canonical_paths

        paths = canonical_paths(run_dir)
        paths.ensure_layout()
        return StageContext(
            run_id=self.run_id,
            config=self.config,
            data_dir=run_dir,
            cache_dir=paths.cache_dir,
            metadata={
                "stage_name": stage_name,
                "db_reachable": bool(((self.config.get("db", {}) or {}).get("dsn"))),
            },
        )

    def _stage_result_to_dict(self, stage_name: str, result: Any) -> dict[str, Any]:
        output_files = [str(path) for path in (result.output_files or [])]
        payload = {
            "success": bool(result.success),
            "output_files": output_files,
            "output_file": output_files[0] if output_files else None,
            "errors": list(result.errors or []),
            "warnings": list(result.warnings or []),
        }
        payload.update(dict(result.artifacts or {}))
        if not payload["success"] and payload["errors"]:
            payload["error"] = payload["errors"][0]
        return payload

    def _run_stage_instance(
        self, stage_name: str, stage_class: type[Any], run_dir: Path
    ) -> dict:
        stage = stage_class(self.config)
        context = self._build_stage_context(run_dir, stage_name)
        result = stage.execute(context)
        return self._stage_result_to_dict(stage_name, result)

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
        """从 repository 加载状态，处理 V8 和 legacy 两种格式"""
        if self.repository is not None:
            state_dict = self.repository.load_state()
            if "completed_stages" in state_dict:
                self.state.run_id = state_dict.get("run_id", self.state.run_id)
                self.state.current_stage = state_dict.get("current_stage", "")
                self.state.completed_stages = state_dict.get("completed_stages", [])
                self.state.stage_results = state_dict.get("stage_results", {})
                self.state.started_at = state_dict.get("started_at", "")
                self.state.updated_at = state_dict.get("updated_at", "")
                self.state.status = state_dict.get("status", "pending")
            elif "phase_status" in state_dict:
                self.state.status = "running"

    def run(
        self,
        run_dir: Path,
        to_stage: str = "patch",
    ) -> dict[str, Any]:
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

            except Exception as e:
                results[stage_name] = {
                    "success": False,
                    "error": str(e),
                }
                self.state.stage_results[stage_name] = results[stage_name]
                self.state.status = "failed"
                self._persist_state()
                break

            if stage_name == to_stage:
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
                "state": {
                    "run_id": self.state.run_id,
                    "current_stage": self.state.current_stage,
                    "completed_stages": self.state.completed_stages,
                    "status": self.state.status,
                },
            }

        # 检查是否已完成所有阶段
        if next_stage is None:
            self.state.status = "completed"
            self._persist_state()
            return {
                "completed": True,
                "stage": None,
                "result": None,
                "state": {
                    "run_id": self.state.run_id,
                    "current_stage": self.state.current_stage,
                    "completed_stages": self.state.completed_stages,
                    "status": self.state.status,
                },
            }

        # 检查是否已到达目标阶段
        if self.state.completed_stages:
            last_completed_idx = STAGE_ORDER.index(self.state.completed_stages[-1])
            to_stage_idx = (
                STAGE_ORDER.index(to_stage)
                if to_stage in STAGE_ORDER
                else len(STAGE_ORDER) - 1
            )
            if last_completed_idx >= to_stage_idx:
                return {
                    "completed": True,
                    "stage": self.state.completed_stages[-1],
                    "result": self.state.stage_results.get(
                        self.state.completed_stages[-1]
                    ),
                    "state": {
                        "run_id": self.state.run_id,
                        "current_stage": self.state.current_stage,
                        "completed_stages": self.state.completed_stages,
                        "status": self.state.status,
                    },
                }

        # 执行下一个阶段
        self.state.current_stage = next_stage
        self._persist_state()

        if next_stage not in self.stages:
            return {
                "completed": False,
                "stage": next_stage,
                "result": {"success": False, "error": f"Unknown stage: {next_stage}"},
                "state": {
                    "run_id": self.state.run_id,
                    "current_stage": self.state.current_stage,
                    "completed_stages": self.state.completed_stages,
                    "status": self.state.status,
                },
            }

        stage_fn = self.stages[next_stage]
        try:
            result = _execute_with_retry(stage_fn, run_dir)
            self.state.stage_results[next_stage] = result

            if result.get("success", False):
                self.state.completed_stages.append(next_stage)
                self._persist_state()
            else:
                self.state.status = "failed"
                self._persist_state()

            return {
                "completed": False,
                "stage": next_stage,
                "result": result,
                "state": {
                    "run_id": self.state.run_id,
                    "current_stage": self.state.current_stage,
                    "completed_stages": self.state.completed_stages,
                    "status": self.state.status,
                },
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
                "state": {
                    "run_id": self.state.run_id,
                    "current_stage": self.state.current_stage,
                    "completed_stages": self.state.completed_stages,
                    "status": self.state.status,
                },
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
            try:
                result = _execute_with_retry(stage_fn, run_dir)
                results[stage_name] = result

                if result.get("success", False):
                    self.state.completed_stages.append(stage_name)
                    self.state.stage_results[stage_name] = result
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

            if stage_name == to_stage:
                break

        # 更新状态
        self.state.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if self.state.status != "failed":
            if self._is_complete_to_stage(to_stage):
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
        if self._is_complete_to_stage(to_stage):
            return NextAction(
                action="none",
                stage=None,
                reason=f"Already completed to stage '{to_stage}'",
            )

        # 找到下一个未完成的阶段
        for stage_name in STAGE_ORDER:
            if stage_name not in self.state.completed_stages and self._is_stage_enabled(
                stage_name
            ):
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
        """将 V8WorkflowState 转换为 StatusResolver 期望的格式。

        Returns:
            转换后的状态字典
        """
        phase_status = {}
        for stage in STAGE_ORDER:
            if stage in self.state.completed_stages:
                phase_status[stage] = "DONE"
            elif stage == self.state.current_stage:
                phase_status[stage] = "IN_PROGRESS"
            else:
                phase_status[stage] = "PENDING"

        return {
            "phase_status": phase_status,
            "current_phase": self.state.current_stage,
            "statements": {},  # V8 没有语句级别的跟踪
        }

    def _load_state(self, run_dir: Path) -> Optional[V8WorkflowState]:
        """从运行目录加载状态。

        Args:
            run_dir: 运行目录

        Returns:
            加载的状态，如果不存在返回 None
        """
        state_path = run_dir / "supervisor" / "v8_state.json"
        if not state_path.exists():
            return None

        try:
            with open(state_path) as f:
                data = json.load(f)
            return V8WorkflowState(**data)
        except Exception:
            return None

    def _save_state(self, run_dir: Path) -> None:
        """保存状态到运行目录。

        Args:
            run_dir: 运行目录
        """
        state_path = run_dir / "supervisor" / "v8_state.json"
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

    def _run_optimize(self, run_dir: Path) -> dict:
        from ..platforms.sql.optimizer_sql import generate_proposal

        # Read baselines from recognition stage
        baselines_path = run_dir / "recognition" / "baselines.json"
        if not baselines_path.exists():
            return {"success": False, "error": "Recognition results not found"}

        with open(baselines_path) as f:
            baselines = json.load(f)

        # Load SQL units from parse stage output
        sql_units_path = run_dir / "parse" / "sql_units_with_branches.json"
        if not sql_units_path.exists():
            return {"success": False, "error": "Parse results not found"}

        with open(sql_units_path) as f:
            sql_units_data = json.load(f)

        # Build sql_units map by sqlKey
        sql_units_map = {unit.get("sqlKey", ""): unit for unit in sql_units_data}

        proposals = []
        for baseline in baselines:
            sql_key = baseline.get("sqlKey", "")
            sql_unit = sql_units_map.get(sql_key)

            if not sql_unit:
                continue

            try:
                proposal = generate_proposal(sql_unit, self.config)
                proposals.append(proposal)
            except Exception as exc:
                # Log error but continue with other proposals
                proposals.append(
                    {
                        "sqlKey": sql_key,
                        "issues": [
                            {"code": "OPTIMIZE_GENERATION_FAILED", "detail": str(exc)}
                        ],
                        "dbEvidenceSummary": {},
                        "planSummary": {},
                        "suggestions": [],
                        "verdict": "NO_ACTION",
                        "confidence": "low",
                        "estimatedBenefit": "unknown",
                    }
                )

        # Write proposals
        output_path = run_dir / "optimize" / "proposals.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(proposals, f, indent=2, ensure_ascii=False)

        actionable_count = sum(
            1 for p in proposals if str(p.get("verdict") or "").upper() == "ACTIONABLE"
        )

        return {
            "success": True,
            "output_file": str(output_path),
            "proposals_count": len(proposals),
            "actionable_count": actionable_count,
        }

    def _run_init(self, run_dir: Path) -> dict:
        from ..stages.discovery import Scanner

        scanner = Scanner(self.config)
        root_path = self.config.get("project", {}).get("root_path", ".")

        result = scanner.scan(root_path)

        output_path = run_dir / "init" / "sql_units.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(result.sql_units, f, indent=2, ensure_ascii=False)

        return {
            "success": True,
            "output_file": str(output_path),
            "sql_units_count": result.total_count,
        }

    def _run_parse(self, run_dir: Path) -> dict:
        from ..stages.branching.brancher import Brancher
        from ..stages.pruning import analyze_risks

        init_path = run_dir / "init" / "sql_units.json"
        if not init_path.exists():
            return {"success": False, "error": "Init results not found"}

        with open(init_path) as f:
            sql_units = json.load(f)

        branch_cfg = self.config.get("branching", {})
        brancher = Brancher(
            strategy=branch_cfg.get("strategy", "all_combinations"),
            max_branches=branch_cfg.get("max_branches", 100),
        )

        for unit in sql_units:
            sql_text = unit.get("templateSql", unit.get("sql", ""))
            branches = brancher.generate(sql_text)
            unit["branches"] = [
                {
                    "branch_id": b.branch_id,
                    "active_conditions": b.active_conditions,
                    "sql": b.sql,
                    "condition_count": b.condition_count,
                    "risk_flags": b.risk_flags,
                }
                for b in branches
            ]
            unit["branchCount"] = len(branches)

        all_risks = analyze_risks(sql_units)

        units_output_path = run_dir / "parse" / "sql_units_with_branches.json"
        units_output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(units_output_path, "w") as f:
            json.dump(sql_units, f, indent=2, ensure_ascii=False)

        risks_output_path = run_dir / "parse" / "risks.json"
        with open(risks_output_path, "w") as f:
            json.dump(all_risks, f, indent=2, ensure_ascii=False)

        return {
            "success": True,
            "sql_units_file": str(units_output_path),
            "risks_file": str(risks_output_path),
            "sql_units_count": len(sql_units),
            "risks_count": len(all_risks),
        }

    def _run_recognition(self, run_dir: Path) -> dict:
        from ..stages.baseline import collect_baseline

        parse_path = run_dir / "parse" / "sql_units_with_branches.json"
        if not parse_path.exists():
            return {"success": False, "error": "Parse results not found"}

        with open(parse_path) as f:
            sql_units = json.load(f)

        baselines = collect_baseline(self.config, sql_units)

        output_path = run_dir / "recognition" / "baselines.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(baselines, f, indent=2, ensure_ascii=False)

        return {
            "success": True,
            "output_file": str(output_path),
            "baselines_count": len(baselines),
        }

    def _run_patch(self, run_dir: Path) -> dict:
        optimize_path = run_dir / "optimize" / "proposals.json"
        if not optimize_path.exists():
            return {"success": False, "error": "Optimize results not found"}

        with open(optimize_path) as f:
            proposals = json.load(f)

        patches = []
        for proposal in proposals:
            if not proposal.get("validated", False):
                continue

            sql_key = proposal.get("sqlKey", "unknown")
            original_sql = proposal.get("originalSql", "")
            optimized_sql = proposal.get("optimizedSql", original_sql)
            rule_name = proposal.get("ruleName", "unknown")

            patch_result = {
                "sqlKey": sql_key,
                "statementKey": sql_key,
                "patchFiles": [],
                "diffSummary": {
                    "filesChanged": 1 if optimized_sql != original_sql else 0,
                    "hunks": 1 if optimized_sql != original_sql else 0,
                    "summary": f"rewrite by {rule_name}"
                    if optimized_sql != original_sql
                    else "no change",
                },
                "applyMode": "manual",
                "rollback": "restore original mapper backup",
                "applicable": optimized_sql != original_sql,
                "originalSql": original_sql,
                "optimizedSql": optimized_sql,
                "ruleName": rule_name,
            }

            if patch_result["applicable"]:
                patch_content = f"-- SQL Optimizer patch: {sql_key}\n-- Rule: {rule_name}\n{optimized_sql}"
                patch_dir = run_dir / "patch" / "patches"
                patch_dir.mkdir(parents=True, exist_ok=True)
                patch_file = patch_dir / f"{sql_key.replace('/', '_')}.sql"
                patch_file.write_text(patch_content, encoding="utf-8")
                patch_result["patchFiles"] = [str(patch_file)]

            patches.append(patch_result)

        output_path = run_dir / "patch" / "patches.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(patches, f, indent=2, ensure_ascii=False)

        return {
            "success": True,
            "output_file": str(output_path),
            "patches_count": len(patches),
            "applicable_count": sum(1 for p in patches if p.get("applicable")),
        }


def run_v8_workflow(config: dict, run_dir: Path, to_stage: str = "patch") -> dict:
    engine = V8WorkflowEngine(config)
    return engine.run(run_dir, to_stage)


def runs_root(config: dict) -> Path:
    root_path = config.get("project", {}).get("root_path", ".")
    return Path(root_path).resolve() / "runs"


def advance_one_step_request(request: AdvanceStepRequest) -> dict[str, Any]:
    engine = V8WorkflowEngine(
        config=request.config,
        repository=request.repository,
        run_id=request.run_dir.name if request.run_dir else None,
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
