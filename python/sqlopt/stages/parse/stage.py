from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sqlopt.common.config import SQLOptConfig
from sqlopt.common.mock_data_loader import MockDataLoader
from sqlopt.contracts.init import InitOutput
from sqlopt.contracts.parse import ParseOutput, SQLBranch, SQLUnitWithBranches
from sqlopt.stages.base import Stage
from sqlopt.stages.branching.fragment_registry import build_fragment_registry
from sqlopt.stages.parse.branch_expander import BranchExpander

logger = logging.getLogger(__name__)


class ParseStage(Stage[None, ParseOutput]):
    def __init__(self, run_id: str | None = None, use_mock: bool = True, config: SQLOptConfig | None = None):
        super().__init__("parse")
        self.run_id = run_id
        self.use_mock = use_mock
        self.config = config

    def run(self, _input_data: None = None, run_id: str | None = None, use_mock: bool | None = None) -> ParseOutput:
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
        for sql_unit in init_data.sql_units:
            expanded = expander.expand(
                sql_unit.sql_text,
                default_namespace=_infer_namespace(sql_unit.id),
            )
            total_branches += len(expanded)
            logger.debug(f"[PARSE]   {sql_unit.id}: expanded to {len(expanded)} branch(es)")
            for exp in expanded:
                logger.debug(f"[PARSE]     - {exp.path_id}: {exp.expanded_sql[:60]}...")
            units_with_branches.append(
                SQLUnitWithBranches(
                    sql_unit_id=sql_unit.id,
                    branches=[
                        SQLBranch(
                            path_id=exp.path_id,
                            condition=exp.condition,
                            expanded_sql=exp.expanded_sql,
                            is_valid=exp.is_valid,
                            risk_flags=exp.risk_flags,
                            active_conditions=exp.active_conditions,
                            risk_score=exp.risk_score,
                            score_reasons=exp.score_reasons,
                        )
                        for exp in expanded
                    ],
                )
            )

        logger.info(f"[PARSE] Total: {len(init_data.sql_units)} SQL unit(s), {total_branches} branch(es)")
        logger.info("[PARSE] Parse stage completed")
        return ParseOutput(sql_units_with_branches=units_with_branches)


def _load_fragment_registry(fragments_file: Path):
    if not fragments_file.exists():
        return None

    try:
        fragment_data = json.loads(fragments_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("[PARSE] Failed to load SQL fragments from %s: %s", fragments_file, exc)
        return None

    xml_paths = sorted(
        {
            str(item.get("xmlPath"))
            for item in fragment_data
            if isinstance(item, dict) and item.get("xmlPath")
        }
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
