"""Optimize stage for SQL query optimization proposal generation."""

from __future__ import annotations

import collections
import json
import logging
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Any, Callable, Literal

from sqlopt.common.config import SQLOptConfig
from sqlopt.common.contract_file_manager import ContractFileManager
from sqlopt.common.llm_mock_generator import LLMProviderBase, MockLLMProvider
from sqlopt.common.mock_data_loader import MockDataLoader
from sqlopt.common.runtime_factory import create_db_connector_from_config
from sqlopt.common.stage_report_generator import generate_optimize_report
from sqlopt.common.summary_generator import generate_optimize_summary_markdown
from sqlopt.contracts.init import SQLUnit, TableSchema
from sqlopt.contracts.optimize import (
    ActionConflict,
    OptimizationAction,
    OptimizationProposal,
    OptimizeOutput,
    UnitActionSummary,
)
from sqlopt.contracts.parse import ParseOutput
from sqlopt.contracts.recognition import PerformanceBaseline, RecognitionOutput
from sqlopt.stages.base import Stage
from sqlopt.stages.recognition.stage import (
    _build_result_signature,
    _extract_rows_examined,
    _is_select_statement,
    _normalize_baseline_data,
    _resolve_mybatis_params_for_explain,
)

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
        db_connector: Any | None = None,
        base_dir: str = "./runs",
    ) -> None:
        super().__init__("optimize", base_dir=base_dir)
        self.run_id = run_id
        self.llm_provider = llm_provider or MockLLMProvider()
        self.use_mock = use_mock
        self.config = config or SQLOptConfig()
        self.db_connector = db_connector or getattr(self.llm_provider, "db_connector", None)

    def run(
        self,
        _input_data: None = None,
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

        loader = MockDataLoader(rid, use_mock=mock, base_dir=self.base_dir)
        baselines_file = loader.get_recognition_baselines_path()
        logger.info(f"[OPTIMIZE] Baselines file: {baselines_file}")

        if not baselines_file.exists():
            logger.warning(f"[OPTIMIZE] Baselines file not found: {baselines_file}, using stub data")
            return self._create_stub_output()

        baselines_data = RecognitionOutput.from_json(baselines_file.read_text(encoding="utf-8"))
        logger.info(f"[OPTIMIZE] Loaded {len(baselines_data.baselines)} baseline(s) from recognition stage")

        loader = MockDataLoader(rid, use_mock=mock, base_dir=self.base_dir)
        table_schemas = self._load_table_schemas(loader)
        sql_units = self._load_sql_units(loader)
        branch_conditions = self._load_parse_output(loader)
        db_connector = self._get_db_connector()
        self._table_schemas = table_schemas
        self._sql_units = sql_units
        self._branch_conditions = branch_conditions

        proposals: list[OptimizationProposal] = []
        logger.info(f"[OPTIMIZE] Processing {len(baselines_data.baselines)} baseline(s) for optimization")

        try:
            if self.config.concurrency.enabled and db_connector is None:
                proposals = self._run_concurrent(rid, baselines_data.baselines, self._progress_callback)
            else:
                if db_connector is not None and self.config.concurrency.enabled:
                    logger.info("[OPTIMIZE] DB validation enabled, forcing sequential execution")
                proposals = self._run_sequential(rid, baselines_data.baselines, self._progress_callback)
        finally:
            self._disconnect_db_connector()

        logger.info(f"[OPTIMIZE] Generated {len(proposals)} proposal(s)")
        output = OptimizeOutput(proposals=proposals, run_id=rid)
        self._write_output(rid, output)
        logger.info(f"[OPTIMIZE] Output written to: runs/{rid}/optimize/proposals.json")

        # Generate SUMMARY.md (best-effort, don't block on failure)
        self._generate_summary(rid, output, start_time)

        logger.info("[OPTIMIZE] Optimize stage completed")
        return output

    def _run_sequential(
        self,
        rid: str,
        baselines: list[PerformanceBaseline],
        progress_callback: ProgressCallback | None,
    ) -> list[OptimizationProposal]:
        unit_map: dict[str, list[PerformanceBaseline]] = collections.defaultdict(list)
        for baseline in baselines:
            unit_map[baseline.sql_unit_id].append(baseline)

        unit_ids = list(unit_map.keys())
        total_units = len(unit_ids)
        proposals: list[OptimizationProposal] = []

        for unit_idx, unit_id in enumerate(unit_ids):
            unit_start = time.time()
            unit_proposals: list[OptimizationProposal] = []
            unit_baselines = unit_map[unit_id]

            xml_context = self._sql_units.get(unit_id)
            table_schema = str(self._table_schemas.get(unit_id, ""))

            for baseline in unit_baselines:
                branch_condition = self._branch_conditions.get(unit_id, {}).get(baseline.path_id)

                try:
                    logger.debug(f"[OPTIMIZE]   Generating optimization for {baseline.sql_unit_id}.{baseline.path_id}")
                    proposal_json = self.llm_provider.generate_optimization(
                        baseline.original_sql,
                        "",
                        xml_context=xml_context.sql_text if xml_context else None,
                        table_schema=table_schema,
                        branch_condition=branch_condition,
                    )
                    proposal_data = json.loads(proposal_json)
                    validation = self._validate_optimized_sql(
                        baseline=baseline,
                        optimized_sql=proposal_data["optimized_sql"],
                        table_schemas=self._table_schemas,
                    )

                    actions = None
                    if proposal_data.get("actions"):
                        actions = [OptimizationAction.from_dict(a) for a in proposal_data["actions"]]

                    proposal = OptimizationProposal(
                        sql_unit_id=baseline.sql_unit_id,
                        path_id=baseline.path_id,
                        original_sql=baseline.original_sql,
                        optimized_sql=proposal_data["optimized_sql"],
                        rationale=proposal_data["rationale"],
                        confidence=proposal_data["confidence"],
                        before_metrics=self._build_before_metrics(baseline),
                        after_metrics=validation["after_metrics"],
                        result_equivalent=validation["result_equivalent"],
                        validation_status=validation["validation_status"],
                        validation_error=validation["validation_error"],
                        gain_ratio=validation["gain_ratio"],
                        actions=actions,
                    )
                    unit_proposals.append(proposal)
                    proposals.append(proposal)
                    logger.debug(
                        "[OPTIMIZE]   [OK] %s.%s: confidence=%.2f, status=%s",
                        baseline.sql_unit_id,
                        baseline.path_id,
                        proposal_data["confidence"],
                        validation["validation_status"],
                    )
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "[OPTIMIZE]   [FAIL] Failed: %s.%s - %s",
                        baseline.sql_unit_id,
                        baseline.path_id,
                        e,
                    )
                    continue

            if unit_proposals:
                unit_summary = self.aggregate_unit_actions(unit_id, unit_proposals)
                for proposal in unit_proposals:
                    proposal.unit_summary = unit_summary
                self._write_unit_file(rid, unit_id, unit_proposals)

            unit_elapsed = time.time() - unit_start
            logger.info(f"[OPTIMIZE] Unit {unit_id} done in {unit_elapsed:.1f}s ({len(unit_proposals)} proposals)")

            if progress_callback:
                progress_callback(
                    f"Unit {unit_idx + 1}/{total_units}: {unit_id} ({unit_elapsed:.1f}s)", (unit_idx + 1, total_units)
                )

        return proposals

    def _run_concurrent(
        self,
        rid: str,
        baselines: list[PerformanceBaseline],
        progress_callback: ProgressCallback | None,
    ) -> list[OptimizationProposal]:
        unit_map: dict[str, list[PerformanceBaseline]] = collections.defaultdict(list)
        for baseline in baselines:
            if baseline.plan is None:
                key = f"{baseline.sql_unit_id}.{baseline.path_id}"
                logger.debug(f"[OPTIMIZE]   [SKIP] Skipping optimization for baseline_only (no plan): {key}")
                continue
            unit_map[baseline.sql_unit_id].append(baseline)

        unit_ids = list(unit_map.keys())
        total_units = len(unit_ids)
        proposals: list[OptimizationProposal] = []

        max_workers = self.config.concurrency.max_workers

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for unit_idx, (unit_id, unit_baselines) in enumerate(unit_map.items()):
                unit_start = time.time()

                xml_context = self._sql_units.get(unit_id)
                table_schema = str(self._table_schemas.get(unit_id, ""))
                branch_conditions = self._branch_conditions.get(unit_id, {})

                futures = {
                    executor.submit(
                        self._process_baseline,
                        baseline,
                        xml_context.sql_text if xml_context else None,
                        table_schema,
                        branch_conditions.get(baseline.path_id),
                    ): baseline
                    for baseline in unit_baselines
                }
                unit_proposals: list[OptimizationProposal] = []

                while futures:
                    done, _ = wait(futures.keys(), return_when=FIRST_COMPLETED)
                    for future in done:
                        baseline = futures.pop(future)
                        result = future.result()
                        if result is not None:
                            unit_proposals.append(result)
                            proposals.append(result)

                if unit_proposals:
                    unit_summary = self.aggregate_unit_actions(unit_id, unit_proposals)
                    for proposal in unit_proposals:
                        proposal.unit_summary = unit_summary
                    self._write_unit_file(rid, unit_id, unit_proposals)

                unit_elapsed = time.time() - unit_start
                logger.info(f"[OPTIMIZE] Unit {unit_id} done in {unit_elapsed:.1f}s ({len(unit_proposals)} proposals)")

                if progress_callback:
                    progress_callback(
                        f"Unit {unit_idx + 1}/{total_units}: {unit_id} ({unit_elapsed:.1f}s)",
                        (unit_idx + 1, total_units),
                    )

        return proposals

    def _write_unit_file(self, run_id: str, unit_id: str, proposals: list[OptimizationProposal]) -> None:
        file_manager = ContractFileManager(run_id, "optimize", base_dir=self.base_dir)
        unit_summary = proposals[0].unit_summary if proposals else None
        unit_data = {
            "sql_unit_id": unit_id,
            "unit_summary": unit_summary.to_dict() if unit_summary else None,
            "proposals": [
                {
                    "sql_unit_id": p.sql_unit_id,
                    "path_id": p.path_id,
                    "original_sql": p.original_sql,
                    "optimized_sql": p.optimized_sql,
                    "rationale": p.rationale,
                    "confidence": p.confidence,
                    "before_metrics": p.before_metrics,
                    "after_metrics": p.after_metrics,
                    "result_equivalent": p.result_equivalent,
                    "validation_status": p.validation_status,
                    "validation_error": p.validation_error,
                    "gain_ratio": p.gain_ratio,
                    "actions": [a.to_dict() for a in p.actions] if p.actions else None,
                    "unit_summary": p.unit_summary.to_dict() if p.unit_summary else None,
                }
                for p in proposals
            ],
        }
        file_manager.write_unit_file(unit_id, unit_data)

    def _process_baseline(
        self,
        baseline: PerformanceBaseline,
        xml_context: str | None,
        table_schema: str,
        branch_condition: str | None,
    ) -> OptimizationProposal | None:
        try:
            proposal_json = self.llm_provider.generate_optimization(
                baseline.original_sql,
                "",
                xml_context=xml_context,
                table_schema=table_schema,
                branch_condition=branch_condition,
            )
            proposal_data = json.loads(proposal_json)
            validation = self._validate_optimized_sql(
                baseline=baseline,
                optimized_sql=proposal_data["optimized_sql"],
                table_schemas=self._table_schemas,
            )

            actions = None
            if proposal_data.get("actions"):
                actions = [OptimizationAction.from_dict(a) for a in proposal_data["actions"]]

            return OptimizationProposal(
                sql_unit_id=baseline.sql_unit_id,
                path_id=baseline.path_id,
                original_sql=baseline.original_sql,
                optimized_sql=proposal_data["optimized_sql"],
                rationale=proposal_data["rationale"],
                confidence=proposal_data["confidence"],
                before_metrics=self._build_before_metrics(baseline),
                after_metrics=validation["after_metrics"],
                result_equivalent=validation["result_equivalent"],
                validation_status=validation["validation_status"],
                validation_error=validation["validation_error"],
                gain_ratio=validation["gain_ratio"],
                actions=actions,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "[OPTIMIZE]   [FAIL] Failed: %s.%s - %s",
                baseline.sql_unit_id,
                baseline.path_id,
                e,
            )
            return None

    def detect_conflicts(self, actions: list[OptimizationAction]) -> list[ActionConflict]:
        """Detect conflicts between actions with overlapping XPath.

        Conflict types:
        - overlap: same xpath, different operations
        - contradict: REPLACE vs REMOVE on same xpath
        - redundant: multiple REPLACE on same xpath

        Resolution: higher confidence wins
        """
        if not actions:
            return []

        # Group actions by xpath
        xpath_groups: dict[str, list[OptimizationAction]] = collections.defaultdict(list)
        for action in actions:
            xpath_groups[action.xpath].append(action)

        conflicts: list[ActionConflict] = []

        for xpath, xpath_actions in xpath_groups.items():
            if len(xpath_actions) < 2:
                continue

            # Compare all pairs
            for i in range(len(xpath_actions)):
                for j in range(i + 1, len(xpath_actions)):
                    action_a = xpath_actions[i]
                    action_b = xpath_actions[j]

                    conflict_type = self._classify_conflict(action_a, action_b)
                    if conflict_type is None:
                        continue

                    # Resolution: higher confidence wins
                    if action_a.confidence >= action_b.confidence:
                        resolution: Literal["a_wins", "b_wins", "merged", "dropped"] = "a_wins"
                    else:
                        resolution = "b_wins"

                    conflict = ActionConflict(
                        xpath=xpath,
                        action_a=action_a,
                        action_b=action_b,
                        conflict_type=conflict_type,
                        resolution=resolution,
                    )
                    conflicts.append(conflict)

        return conflicts

    @staticmethod
    def _classify_conflict(
        action_a: OptimizationAction,
        action_b: OptimizationAction,
    ) -> Literal["overlap", "contradict", "redundant"] | None:
        """Classify the conflict type between two actions on the same xpath.

        Returns None if no conflict (same operation on same xpath).
        """
        # Same operation = no conflict for ADD (both add to same spot)
        if action_a.operation == action_b.operation:
            if action_a.operation == "ADD":
                return None  # Multiple ADDs to same xpath is allowed
            if action_a.operation == "REPLACE" and action_a.rewritten_snippet == action_b.rewritten_snippet:
                return None  # Same replacement is not a conflict
            return "overlap"

        # Contradict: REPLACE vs REMOVE
        operations = {action_a.operation, action_b.operation}
        if operations == {"REPLACE", "REMOVE"}:
            return "contradict"

        # Redundant: multiple REPLACE (handled above as overlap)
        if operations == {"REPLACE"}:
            return "redundant"

        return "overlap"

    def aggregate_unit_actions(
        self,
        sql_unit_id: str,
        proposals: list[OptimizationProposal],
    ) -> UnitActionSummary:
        """Aggregate branch-level proposals into unit-level action summary.

        Collects all actions across branches of the same SQL unit, detects
        and resolves conflicts, and builds branch coverage.
        """
        # Collect all actions from all branch proposals
        all_actions: list[OptimizationAction] = []
        branch_coverage: dict[str, bool] = {}

        for proposal in proposals:
            # Mark branch as covered if it has actions
            branch_coverage[proposal.path_id] = False

            if proposal.actions:
                all_actions.extend(proposal.actions)
                branch_coverage[proposal.path_id] = True

        # Detect and resolve conflicts
        conflicts = self.detect_conflicts(all_actions)

        # Resolve conflicts: keep only winning actions
        resolved_actions = self._resolve_conflicts(all_actions, conflicts)

        # Calculate overall confidence as weighted average
        overall_confidence = self._calculate_overall_confidence(resolved_actions)

        return UnitActionSummary(
            sql_unit_id=sql_unit_id,
            actions=resolved_actions,
            conflicts=conflicts,
            branch_coverage=branch_coverage,
            overall_confidence=overall_confidence,
        )

    @staticmethod
    def _resolve_conflicts(
        actions: list[OptimizationAction],
        conflicts: list[ActionConflict],
    ) -> list[OptimizationAction]:
        """Resolve conflicts by keeping only winning actions."""
        if not conflicts:
            return actions

        # Track xpath -> winning action
        xpath_winners: dict[str, OptimizationAction] = {}

        for conflict in conflicts:
            winner = conflict.action_a if conflict.resolution == "a_wins" else conflict.action_b
            xpath = conflict.xpath
            if xpath not in xpath_winners or winner.confidence > xpath_winners[xpath].confidence:
                xpath_winners[xpath] = winner

        # Build resolved list: keep one action per xpath
        xpath_actions: dict[str, OptimizationAction] = {}
        for action in actions:
            if action.xpath not in xpath_actions:
                xpath_actions[action.xpath] = action

        # Apply winners
        xpath_actions.update(xpath_winners)

        return list(xpath_actions.values())

    @staticmethod
    def _calculate_overall_confidence(actions: list[OptimizationAction]) -> float:
        """Calculate weighted average confidence across actions."""
        if not actions:
            return 0.0

        total_confidence = sum(a.confidence for a in actions)
        return total_confidence / len(actions)

    @staticmethod
    def _load_table_schemas(loader: MockDataLoader) -> dict[str, TableSchema]:
        schemas: dict[str, TableSchema] = {}
        schemas_file = loader.get_init_table_schemas_path()
        if not schemas_file.exists():
            return schemas
        try:
            schemas_data = json.loads(schemas_file.read_text(encoding="utf-8"))
            schemas = {name: TableSchema(**item) for name, item in schemas_data.items()}
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            logger.debug("[OPTIMIZE] Failed to load table schemas, using heuristics")
        return schemas

    @staticmethod
    def _load_sql_units(loader: MockDataLoader) -> dict[str, SQLUnit]:
        units: dict[str, SQLUnit] = {}
        units_file = loader.get_init_sql_units_path()
        if not units_file.exists():
            return units
        try:
            units_data = json.loads(units_file.read_text(encoding="utf-8"))
            for item in units_data:
                unit = SQLUnit(**item)
                units[unit.id] = unit
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            logger.debug("[OPTIMIZE] Failed to load SQL units")
        return units

    @staticmethod
    def _load_parse_output(loader: MockDataLoader) -> dict[str, dict[str, str]]:
        """Load parse output to get branch conditions.

        Returns:
            Dict mapping sql_unit_id -> (dict mapping path_id -> condition)
        """
        branch_conditions: dict[str, dict[str, str]] = {}
        parse_path = loader.get_parse_sql_units_with_branches_path()
        if not parse_path.exists():
            return branch_conditions
        try:
            if parse_path.is_dir():
                # New per-unit format: load from units directory
                index_path = parse_path / "_index.json"
                if index_path.exists():
                    index_data = json.loads(index_path.read_text(encoding="utf-8"))
                    # ContractFileManager.write_index() writes a list directly
                    unit_ids = index_data if isinstance(index_data, list) else index_data.get("unit_ids", [])
                    for uid in unit_ids:
                        unit_file = parse_path / f"{uid}.json"
                        if unit_file.exists():
                            unit_data = json.loads(unit_file.read_text(encoding="utf-8"))
                            branch_conditions[uid] = {}
                            for branch in unit_data.get("branches", []):
                                branch_conditions[uid][branch["path_id"]] = branch.get("condition")
            else:
                # Legacy single-file format
                parse_data = ParseOutput.from_json(parse_path.read_text(encoding="utf-8"))
                for unit in parse_data.sql_units_with_branches:
                    branch_conditions[unit.sql_unit_id] = {}
                    for branch in unit.branches:
                        branch_conditions[unit.sql_unit_id][branch.path_id] = branch.condition
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            logger.debug("[OPTIMIZE] Failed to load parse output for branch conditions")
        return branch_conditions

    def _get_db_connector(self) -> Any | None:
        if self.db_connector is not None:
            return self.db_connector

        if self.config and self.config.db_host and self.config.db_port and self.config.db_name:
            self.db_connector = create_db_connector_from_config(self.config)
        return self.db_connector

    def _disconnect_db_connector(self) -> None:
        connector = self.db_connector
        if connector is None or not hasattr(connector, "disconnect"):
            return
        try:
            connector.disconnect()
        except Exception:
            logger.debug("[OPTIMIZE] Failed to disconnect DB connector", exc_info=True)

    @staticmethod
    def _build_before_metrics(baseline: PerformanceBaseline) -> dict:
        return {
            "estimated_cost": baseline.estimated_cost,
            "actual_time_ms": baseline.actual_time_ms,
            "rows_returned": baseline.rows_returned,
            "rows_examined": baseline.rows_examined,
            "result_signature": baseline.result_signature,
            "plan": baseline.plan,
        }

    def _validate_optimized_sql(
        self,
        baseline: PerformanceBaseline,
        optimized_sql: str,
        table_schemas: dict[str, TableSchema] | None,
    ) -> dict[str, Any]:
        after_metrics: dict[str, Any] = {
            "estimated_cost": None,
            "actual_time_ms": None,
            "rows_returned": None,
            "rows_examined": None,
            "result_signature": None,
            "plan": None,
        }
        validation_status = "not_validated"
        validation_error = None
        result_equivalent = None

        executable_sql = _resolve_mybatis_params_for_explain(optimized_sql, table_schemas)
        db_connector = self.db_connector

        try:
            if db_connector is not None:
                baseline_data = _normalize_baseline_data(db_connector.execute_explain(executable_sql))
            else:
                baseline_data = _normalize_baseline_data(
                    self.llm_provider.generate_baseline(executable_sql, self.config.db_platform)
                )
        except Exception as e:  # noqa: BLE001
            return {
                "after_metrics": after_metrics,
                "validation_status": "validation_failed",
                "validation_error": f"explain_failed: {e}",
                "result_equivalent": None,
                "gain_ratio": None,
            }

        after_metrics["estimated_cost"] = baseline_data.get("estimated_cost")
        after_metrics["actual_time_ms"] = baseline_data.get("actual_time_ms")
        after_metrics["plan"] = baseline_data.get("plan")
        after_metrics["rows_examined"] = _extract_rows_examined(after_metrics["plan"])

        if db_connector is None:
            validation_status = "estimated_only"
            return {
                "after_metrics": after_metrics,
                "validation_status": validation_status,
                "validation_error": None,
                "result_equivalent": None,
                "gain_ratio": self._calculate_gain_ratio(
                    baseline.actual_time_ms,
                    baseline.estimated_cost,
                    after_metrics["actual_time_ms"],
                    after_metrics["estimated_cost"],
                ),
            }

        if not _is_select_statement(executable_sql):
            validation_status = "explained_only"
            return {
                "after_metrics": after_metrics,
                "validation_status": validation_status,
                "validation_error": None,
                "result_equivalent": None,
                "gain_ratio": self._calculate_gain_ratio(
                    baseline.actual_time_ms,
                    baseline.estimated_cost,
                    after_metrics["actual_time_ms"],
                    after_metrics["estimated_cost"],
                ),
            }

        try:
            query_started_at = time.perf_counter()
            rows = db_connector.execute_query(executable_sql)
            after_metrics["actual_time_ms"] = (time.perf_counter() - query_started_at) * 1000.0
            after_metrics["rows_returned"] = len(rows)
            after_metrics["result_signature"] = _build_result_signature(rows)
            expected_signature = baseline.result_signature
            if expected_signature is not None:
                result_equivalent = expected_signature == after_metrics["result_signature"]
                validation_status = "validated" if result_equivalent else "result_mismatch"
            else:
                validation_status = "validated_without_baseline"
        except Exception as e:  # noqa: BLE001
            validation_status = "validation_failed"
            validation_error = f"query_execution_failed: {e}"

        return {
            "after_metrics": after_metrics,
            "validation_status": validation_status,
            "validation_error": validation_error,
            "result_equivalent": result_equivalent,
            "gain_ratio": self._calculate_gain_ratio(
                baseline.actual_time_ms,
                baseline.estimated_cost,
                after_metrics["actual_time_ms"],
                after_metrics["estimated_cost"],
            ),
        }

    @staticmethod
    def _calculate_gain_ratio(
        before_time_ms: float | None,
        before_cost: float | None,
        after_time_ms: float | None,
        after_cost: float | None,
    ) -> float | None:
        if before_time_ms and after_time_ms is not None and before_time_ms > 0:
            return (before_time_ms - after_time_ms) / before_time_ms
        if before_cost and after_cost is not None and before_cost > 0:
            return (before_cost - after_cost) / before_cost
        return None

    def _write_output(self, run_id: str, output: OptimizeOutput) -> None:
        """Write optimize output to per-unit files and backward-compatible single file.

        Creates:
        - runs/{run_id}/optimize/units/{unit_id}.json (per unit)
        - runs/{run_id}/optimize/units/_index.json (unit ID list)
        - runs/{run_id}/optimize/proposals.json (backward compat)
        """
        output_dir = self.resolve_run_paths(run_id).optimize_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        # Always write backward-compatible proposals.json
        compat_path = output_dir / "proposals.json"
        compat_path.write_text(output.to_json(), encoding="utf-8")

        if not output.proposals:
            logger.debug("[OPTIMIZE] No proposals to write, wrote empty proposals.json")
            return

        file_manager = ContractFileManager(run_id, "optimize", base_dir=self.base_dir)

        proposals_by_unit: dict[str, list[dict]] = {}
        unit_summaries: dict[str, UnitActionSummary] = {}
        for proposal in output.proposals:
            if proposal.sql_unit_id not in proposals_by_unit:
                proposals_by_unit[proposal.sql_unit_id] = []
                unit_summaries[proposal.sql_unit_id] = proposal.unit_summary
            proposals_by_unit[proposal.sql_unit_id].append(
                {
                    "sql_unit_id": proposal.sql_unit_id,
                    "path_id": proposal.path_id,
                    "original_sql": proposal.original_sql,
                    "optimized_sql": proposal.optimized_sql,
                    "rationale": proposal.rationale,
                    "confidence": proposal.confidence,
                    "before_metrics": proposal.before_metrics,
                    "after_metrics": proposal.after_metrics,
                    "result_equivalent": proposal.result_equivalent,
                    "validation_status": proposal.validation_status,
                    "validation_error": proposal.validation_error,
                    "gain_ratio": proposal.gain_ratio,
                    "actions": [a.to_dict() for a in proposal.actions] if proposal.actions else None,
                    "unit_summary": proposal.unit_summary.to_dict() if proposal.unit_summary else None,
                }
            )

        unit_ids: list[str] = []
        total_bytes = 0
        for unit_id, proposals in proposals_by_unit.items():
            unit_data = {
                "sql_unit_id": unit_id,
                "unit_summary": unit_summaries[unit_id].to_dict() if unit_summaries.get(unit_id) else None,
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

        report_path = output_dir / "optimize_report.html"
        generate_optimize_report(output, str(report_path))

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

            output_dir = self.resolve_run_paths(run_id).optimize_dir
            file_size_bytes = 0
            files_count = 0

            if output_dir.exists():
                for file_path in output_dir.rglob("*.json"):
                    if file_path.is_file():
                        file_size_bytes += file_path.stat().st_size
                        files_count += 1

            output_with_run_id = OptimizeOutput(
                proposals=output.proposals,
                run_id=run_id,
            )

            markdown = generate_optimize_summary_markdown(
                output=output_with_run_id,
                duration_seconds=duration_seconds,
                file_size_bytes=file_size_bytes,
                files_count=files_count,
            )
            summary_path = output_dir / "SUMMARY.md"
            summary_path.write_text(markdown, encoding="utf-8")
            logger.info(f"[OPTIMIZE] SUMMARY.md written to: {summary_path}")

        except Exception as e:  # noqa: BLE001
            logger.warning(f"[OPTIMIZE] Failed to generate SUMMARY.md: {e}")

    @staticmethod
    def _create_stub_output() -> OptimizeOutput:
        proposal = OptimizationProposal(
            sql_unit_id="stub-1",
            path_id="p1",
            original_sql="SELECT * FROM users",
            optimized_sql="SELECT id, name FROM users",
            rationale="Reduce columns to improve performance",
            confidence=0.9,
            before_metrics={"estimated_cost": 100.0},
            after_metrics={"estimated_cost": 50.0},
            result_equivalent=True,
            validation_status="estimated_only",
            gain_ratio=0.5,
        )
        return OptimizeOutput(proposals=[proposal])
