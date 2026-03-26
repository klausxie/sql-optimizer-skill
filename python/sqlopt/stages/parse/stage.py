from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

from sqlopt.common.config import SQLOptConfig
from sqlopt.common.contract_file_manager import ContractFileManager
from sqlopt.common.mock_data_loader import MockDataLoader
from sqlopt.common.summary_generator import StageSummary, generate_summary_markdown
from sqlopt.contracts.init import InitOutput
from sqlopt.contracts.parse import ParseOutput, SQLBranch, SQLUnitWithBranches
from sqlopt.stages.base import Stage
from sqlopt.stages.branching.fragment_registry import build_fragment_registry
from sqlopt.stages.parse.branch_expander import BranchExpander

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, tuple[int, int] | None], None]


class ParseStage(Stage[None, ParseOutput]):
    def __init__(self, run_id: str | None = None, use_mock: bool = True, config: SQLOptConfig | None = None):
        super().__init__("parse")
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

        loader = MockDataLoader(rid, use_mock=mock)
        init_file = loader.get_init_sql_units_path()
        fragments_file = loader.get_init_sql_fragments_path()
        table_schemas_file = loader.get_init_table_schemas_path()
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

        strategy = self.config.parse_strategy if self.config else "ladder"
        max_branches = self.config.parse_max_branches if self.config else 50
        expander = BranchExpander(
            strategy=strategy,
            max_branches=max_branches,
            fragments=fragment_registry,
            table_metadata=table_metadata,
        )

        units_with_branches: list[SQLUnitWithBranches] = []
        total_branches = 0
        logger.info(f"[PARSE] Expanding branches for {len(init_data.sql_units)} SQL unit(s)")
        for idx, sql_unit in enumerate(init_data.sql_units):
            expanded = expander.expand(
                sql_unit.sql_text,
                default_namespace=_infer_namespace(sql_unit.id),
            )
            total_branches += len(expanded)
            if progress_callback:
                progress_callback(
                    f"Processing SQL unit {idx + 1}/{len(init_data.sql_units)}: {sql_unit.id}",
                    (idx + 1, len(init_data.sql_units)),
                )
            if len(init_data.sql_units) <= 10:
                pct = (idx + 1) * 100 // len(init_data.sql_units) // 10
                logger.info(f"[PARSE] Progress: {idx + 1}/{len(init_data.sql_units)} ({pct}%)")

        if progress_callback:
            progress_callback(f"{len(init_data.sql_units)} SQL unit(s), {total_branches} branch(es)")
        logger.info(f"[PARSE] Total: {len(init_data.sql_units)} SQL unit(s), {total_branches} branch(es)")
        logger.info("[PARSE] Parse stage completed")

        output = ParseOutput(sql_units_with_branches=units_with_branches)
        self._write_output(rid, output)
        self._generate_summary(rid, output, total_branches)

        return output

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

        if not output.sql_units_with_branches:
            logger.debug("[PARSE] No units to write, skipping file output")
            return

        file_manager = ContractFileManager(run_id, "parse")
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

        parse_dir = Path("runs") / run_id / "parse"
        parse_dir.mkdir(parents=True, exist_ok=True)
        compat_path = parse_dir / "sql_units_with_branches.json"
        compat_path.write_text(output.to_json(), encoding="utf-8")
        compat_bytes = file_manager.get_file_size(compat_path)

        logger.info(
            f"[PARSE] Wrote {len(unit_ids)} unit file(s) ({total_bytes} bytes) "
            f"+ index + compat file ({compat_bytes} bytes)"
        )

    def _generate_summary(self, run_id: str | None, output: ParseOutput, total_branches: int) -> None:
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

            parse_dir = Path("runs") / run_id / "parse"
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
                duration_seconds=0.0,  # Duration not tracked in this stage yet
                sql_units_count=sql_units_count,
                branches_count=total_branches,
                files_count=files_count,
                file_size_bytes=file_size,
                warnings=[f"Invalid branches: {invalid_branches}"] if invalid_branches > 0 else [],
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


def _infer_namespace(sql_unit_id: str) -> str | None:
    if "." not in sql_unit_id:
        return None
    namespace, _statement_id = sql_unit_id.rsplit(".", 1)
    return namespace or None
