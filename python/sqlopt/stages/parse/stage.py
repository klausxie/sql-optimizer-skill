from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any, Callable

from sqlopt.common.concurrent import BatchOptions, ConcurrentExecutor
from sqlopt.common.config import SQLOptConfig
from sqlopt.common.contract_file_manager import ContractFileManager
from sqlopt.common.mock_data_loader import MockDataLoader
from sqlopt.common.summary_generator import StageSummary, generate_summary_markdown
from sqlopt.contracts.init import FieldDistribution, InitOutput
from sqlopt.contracts.parse import ParseOutput, SQLBranch, SQLUnitWithBranches
from sqlopt.stages.base import Stage
from sqlopt.stages.branching.fragment_registry import build_fragment_registry
from sqlopt.stages.parse.branch_expander import BranchExpander

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, tuple[int, int] | None], None]


class ParseStage(Stage[None, ParseOutput]):
    def __init__(
        self,
        run_id: str | None = None,
        use_mock: bool = True,
        config: SQLOptConfig | None = None,
        base_dir: str = "./runs",
    ):
        super().__init__("parse", base_dir=base_dir)
        self.run_id = run_id
        self.use_mock = use_mock
        self.config = config

    def run(
        self,
        _input_data: None = None,
        run_id: str | None = None,
        use_mock: bool | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> ParseOutput:
        start_time = time.time()
        rid = run_id or self.run_id
        mock = use_mock if use_mock is not None else self.use_mock
        logger.info("=" * 60)
        logger.info("[PARSE] Starting Parse stage")
        logger.info(f"[PARSE] Run ID: {rid}, Mock mode: {mock}")

        if rid is None:
            logger.warning("[PARSE] No run_id provided, using stub data")
            branch = SQLBranch(
                path_id="p1",
                condition=None,
                expanded_sql="SELECT * FROM users",
                is_valid=True,
                risk_flags=[],
                active_conditions=[],
            )
            unit_with_branches = SQLUnitWithBranches(sql_unit_id="stub-1", branches=[branch])
            return ParseOutput(sql_units_with_branches=[unit_with_branches])

        loader = MockDataLoader(rid, use_mock=mock, base_dir=self.base_dir)
        init_file = loader.get_init_sql_units_path()
        fragments_file = loader.get_init_sql_fragments_path()
        table_schemas_file = loader.get_init_table_schemas_path()
        field_distributions_file = loader.get_init_field_distributions_path()
        logger.info(f"[PARSE] Init file: {init_file}")

        if not init_file.exists():
            logger.warning(f"[PARSE] Init file not found: {init_file}, using stub data")
            branch = SQLBranch(
                path_id="p1",
                condition=None,
                expanded_sql="SELECT * FROM users",
                is_valid=True,
                risk_flags=[],
                active_conditions=[],
            )
            unit_with_branches = SQLUnitWithBranches(sql_unit_id="stub-1", branches=[branch])
            return ParseOutput(sql_units_with_branches=[unit_with_branches])

        init_data = InitOutput.from_json(init_file.read_text(encoding="utf-8"))
        logger.info(f"[PARSE] Loaded {len(init_data.sql_units)} SQL unit(s) from init stage")

        fragment_registry = _load_fragment_registry(fragments_file)
        table_metadata = _load_table_metadata(table_schemas_file)
        field_distributions = _load_field_distributions(field_distributions_file)

        strategy = self.config.parse_strategy if self.config else "ladder"
        max_branches = self.config.parse_max_branches if self.config else 50
        expander = BranchExpander(
            strategy=strategy,
            max_branches=max_branches,
            fragments=fragment_registry,
            table_metadata=table_metadata,
            field_distributions=field_distributions,
        )

        logger.info(f"[PARSE] Expanding branches for {len(init_data.sql_units)} SQL unit(s)")
        if self.config and self.config.concurrency.enabled and len(init_data.sql_units) > 1:
            logger.info("[PARSE] Using concurrent branch expansion")
            units_with_branches, failed_units = self._run_concurrent(init_data, expander, progress_callback)
        else:
            units_with_branches, failed_units = self._run_sequential(init_data, expander, progress_callback)

        total_branches = sum(len(unit.branches) for unit in units_with_branches)

        if progress_callback:
            progress_callback(f"{len(init_data.sql_units)} SQL unit(s), {total_branches} branch(es)")
        logger.info(f"[PARSE] Total: {len(init_data.sql_units)} SQL unit(s), {total_branches} branch(es)")
        logger.info("[PARSE] Parse stage completed")

        output = ParseOutput(sql_units_with_branches=units_with_branches)
        self._write_output(rid, output)
        self._generate_summary(rid, output, total_branches, time.time() - start_time, failed_units)

        return output

    def _run_sequential(
        self,
        init_data: InitOutput,
        expander: BranchExpander,
        progress_callback: ProgressCallback | None,
    ) -> tuple[list[SQLUnitWithBranches], int]:
        units_with_branches: list[SQLUnitWithBranches] = []
        failed_units = 0

        for idx, sql_unit in enumerate(init_data.sql_units):
            unit_with_branches, had_error = self._expand_sql_unit(expander, sql_unit.id, sql_unit.sql_text)
            units_with_branches.append(unit_with_branches)
            if had_error:
                failed_units += 1
            if progress_callback:
                progress_callback(
                    f"Processing SQL unit {idx + 1}/{len(init_data.sql_units)}: {sql_unit.id}",
                    (idx + 1, len(init_data.sql_units)),
                )
            if len(init_data.sql_units) <= 10:
                pct = (idx + 1) * 100 // len(init_data.sql_units) // 10
                logger.info(f"[PARSE] Progress: {idx + 1}/{len(init_data.sql_units)} ({pct}%)")

        return units_with_branches, failed_units

    def _run_concurrent(
        self,
        init_data: InitOutput,
        expander: BranchExpander,
        progress_callback: ProgressCallback | None,
    ) -> tuple[list[SQLUnitWithBranches], int]:
        options = BatchOptions(
            max_workers=self.config.concurrency.max_workers if self.config else 4,
            max_concurrent=self.config.concurrency.max_workers if self.config else 4,
            batch_size=self.config.concurrency.batch_size if self.config else 10,
            timeout_per_task=self.config.concurrency.timeout_per_task if self.config else 300,
            retry_count=self.config.concurrency.retry_count if self.config else 3,
            retry_delay=float(self.config.concurrency.retry_delay) if self.config else 1.0,
        )
        tasks = [(sql_unit.id, sql_unit.sql_text) for sql_unit in init_data.sql_units]

        def process_task(task: tuple[str, str]) -> tuple[SQLUnitWithBranches, bool]:
            sql_unit_id, sql_text = task
            return self._expand_sql_unit(expander, sql_unit_id, sql_text)

        units_with_branches: list[SQLUnitWithBranches] = []
        failed_units = 0
        total = len(tasks)

        with ConcurrentExecutor(options) as executor:
            results = executor.map(process_task, tasks)

        for completed, result in enumerate(results, start=1):
            if result.success and result.result is not None:
                unit_with_branches, had_error = result.result
                units_with_branches.append(unit_with_branches)
                if had_error:
                    failed_units += 1
            else:
                sql_unit_id, sql_text = result.item
                logger.warning("[PARSE] Failed to expand %s after retries: %s", sql_unit_id, result.error)
                unit_with_branches, _had_error = self._build_error_unit(sql_unit_id, sql_text, result.error)
                units_with_branches.append(unit_with_branches)
                failed_units += 1

            if progress_callback:
                progress_callback(
                    f"Processing SQL unit {completed}/{total}: {units_with_branches[-1].sql_unit_id}",
                    (completed, total),
                )

        return units_with_branches, failed_units

    def _expand_sql_unit(
        self,
        expander: BranchExpander,
        sql_unit_id: str,
        sql_text: str,
    ) -> tuple[SQLUnitWithBranches, bool]:
        try:
            expanded = expander.expand(
                sql_text,
                default_namespace=_infer_namespace(sql_unit_id),
            )
            return (
                SQLUnitWithBranches(
                    sql_unit_id=sql_unit_id,
                    branches=[_to_sql_branch(branch) for branch in expanded],
                ),
                False,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[PARSE] Failed to expand %s: %s", sql_unit_id, exc)
            return self._build_error_unit(sql_unit_id, sql_text, str(exc))

    def _build_error_unit(
        self,
        sql_unit_id: str,
        sql_text: str,
        error: str | None,
    ) -> tuple[SQLUnitWithBranches, bool]:
        error_branch = SQLBranch(
            path_id="error",
            condition=None,
            expanded_sql=sql_text,
            is_valid=False,
            risk_flags=["parse_error"],
            active_conditions=[],
            risk_score=None,
            score_reasons=[f"parse_error:{error or 'unknown'}"],
            branch_type="error",
        )
        return SQLUnitWithBranches(sql_unit_id=sql_unit_id, branches=[error_branch]), True

    def _write_output(self, run_id: str | None, output: ParseOutput) -> None:
        """Write parse output to per-unit files and backward-compatible single file.

        Creates:
        - runs/{run_id}/parse/units/{unit_id}.json (per unit)
        - runs/{run_id}/parse/units/_index.json (unit ID list)
        - runs/{run_id}/parse/sql_units_with_branches.json (backward compat)
        """
        if not run_id:
            logger.debug("[PARSE] No run_id, skipping file output")
            return

        parse_dir = self.resolve_run_paths(run_id).parse_dir
        parse_dir.mkdir(parents=True, exist_ok=True)
        file_manager = ContractFileManager(run_id, "parse", base_dir=self.base_dir)
        unit_ids: list[str] = []
        total_bytes = 0

        for unit in output.sql_units_with_branches:
            unit_data = {
                "sql_unit_id": unit.sql_unit_id,
                "branches": [
                    {
                        "path_id": b.path_id,
                        "condition": b.condition,
                        "expanded_sql": b.expanded_sql,
                        "is_valid": b.is_valid,
                        "risk_flags": b.risk_flags,
                        "active_conditions": b.active_conditions,
                        "risk_score": b.risk_score,
                        "score_reasons": b.score_reasons,
                        "branch_type": b.branch_type,
                    }
                    for b in unit.branches
                ],
            }
            path = file_manager.write_unit_file(unit.sql_unit_id, unit_data)
            total_bytes += file_manager.get_file_size(path)
            unit_ids.append(unit.sql_unit_id)

        index_path = file_manager.write_index(unit_ids)
        total_bytes += file_manager.get_file_size(index_path)

        compat_path = parse_dir / "sql_units_with_branches.json"
        compat_path.write_text(output.to_json(), encoding="utf-8")
        compat_bytes = file_manager.get_file_size(compat_path)

        logger.info(
            f"[PARSE] Wrote {len(unit_ids)} unit file(s) ({total_bytes} bytes) "
            f"+ index + compat file ({compat_bytes} bytes)"
        )

    def _generate_summary(
        self,
        run_id: str | None,
        output: ParseOutput,
        total_branches: int,
        duration_seconds: float,
        failed_units: int,
    ) -> None:
        """Generate SUMMARY.md for the parse stage.

        Best-effort operation - errors are logged but don't block stage completion.
        """
        if not run_id:
            return

        try:
            sql_units_count = len(output.sql_units_with_branches)
            invalid_branches = sum(
                1 for unit in output.sql_units_with_branches for branch in unit.branches if not branch.is_valid
            )

            parse_dir = self.resolve_run_paths(run_id).parse_dir
            parse_dir.mkdir(parents=True, exist_ok=True)
            file_size = 0
            files_count = 0

            units_dir = parse_dir / "units"
            if units_dir.exists():
                for f in units_dir.glob("*.json"):
                    file_size += f.stat().st_size
                    files_count += 1

            compat_file = parse_dir / "sql_units_with_branches.json"
            if compat_file.exists():
                file_size += compat_file.stat().st_size
                files_count += 1

            summary = StageSummary(
                stage_name="parse",
                run_id=run_id,
                duration_seconds=duration_seconds,
                sql_units_count=sql_units_count,
                branches_count=total_branches,
                files_count=files_count,
                file_size_bytes=file_size,
                warnings=[
                    *([f"Invalid branches: {invalid_branches}"] if invalid_branches > 0 else []),
                    *([f"Units with expansion fallback: {failed_units}"] if failed_units > 0 else []),
                ],
            )

            summary_content = generate_summary_markdown(summary)
            summary_path = parse_dir / "SUMMARY.md"
            summary_path.write_text(summary_content, encoding="utf-8")

            logger.info(f"[PARSE] Generated SUMMARY.md ({len(summary_content)} bytes)")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[PARSE] Failed to generate SUMMARY.md: {e}")


def _load_fragment_registry(fragments_file: Path):
    if not fragments_file.exists():
        return None

    try:
        fragment_data = json.loads(fragments_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("[PARSE] Failed to load SQL fragments from %s: %s", fragments_file, exc)
        return None

    xml_paths = sorted(
        {str(item.get("xml_path")) for item in fragment_data if isinstance(item, dict) and item.get("xml_path")}
    )
    if not xml_paths:
        return None

    return build_fragment_registry(xml_paths)


def _load_table_metadata(table_schemas_file: Path) -> dict[str, dict[str, Any]]:
    if not table_schemas_file.exists():
        return {}

    try:
        raw_data = json.loads(table_schemas_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("[PARSE] Failed to load table schemas from %s: %s", table_schemas_file, exc)
        return {}

    if not isinstance(raw_data, dict):
        return {}

    table_metadata: dict[str, dict[str, Any]] = {}
    for table_name, schema in raw_data.items():
        if not isinstance(schema, dict):
            continue

        statistics = schema.get("statistics", {})
        row_count = statistics.get("rowCount") if isinstance(statistics, dict) else None
        if isinstance(row_count, int) and row_count >= 1_000_000:
            size = "large"
        elif isinstance(row_count, int) and row_count >= 10_000:
            size = "medium"
        else:
            size = "small"

        indexes: set[str] = set()
        for index in schema.get("indexes", []):
            if not isinstance(index, dict):
                continue
            for column in index.get("columns", []):
                if isinstance(column, str) and column:
                    indexes.add(column)

        table_metadata[table_name] = {
            "size": size,
            "indexes": sorted(indexes),
        }

    return table_metadata


def _load_field_distributions(field_distributions_file: Path) -> dict[str, list[FieldDistribution]]:
    if not field_distributions_file.exists():
        return {}

    try:
        raw_data = json.loads(field_distributions_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("[PARSE] Failed to load field distributions from %s: %s", field_distributions_file, exc)
        return {}

    if not isinstance(raw_data, list):
        return {}

    grouped: dict[str, list[FieldDistribution]] = {}
    for item in raw_data:
        if not isinstance(item, dict):
            continue
        try:
            distribution = FieldDistribution(**item)
        except TypeError as exc:
            logger.debug("[PARSE] Skipping invalid field distribution entry: %s", exc)
            continue
        grouped.setdefault(distribution.table_name.lower(), []).append(distribution)
    return grouped


def _infer_namespace(sql_unit_id: str) -> str | None:
    if "." not in sql_unit_id:
        return None
    namespace, _statement_id = sql_unit_id.rsplit(".", 1)
    return namespace or None


def _to_sql_branch(branch: Any) -> SQLBranch:
    return SQLBranch(
        path_id=branch.path_id,
        condition=branch.condition,
        expanded_sql=branch.expanded_sql,
        is_valid=branch.is_valid,
        risk_flags=list(branch.risk_flags),
        active_conditions=list(branch.active_conditions),
        risk_score=branch.risk_score,
        score_reasons=list(branch.score_reasons),
        branch_type=getattr(branch, "branch_type", None),
    )
