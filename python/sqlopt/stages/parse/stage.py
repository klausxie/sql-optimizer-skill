from __future__ import annotations

import logging

from sqlopt.common.config import SQLOptConfig
from sqlopt.common.mock_data_loader import MockDataLoader
from sqlopt.contracts.init import InitOutput
from sqlopt.contracts.parse import ParseOutput, SQLBranch, SQLUnitWithBranches
from sqlopt.stages.base import Stage
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

        strategy = self.config.parse_strategy if self.config else "ladder"
        max_branches = self.config.parse_max_branches if self.config else 50
        expander = BranchExpander(strategy=strategy, max_branches=max_branches)

        units_with_branches: list[SQLUnitWithBranches] = []
        total_branches = 0
        for sql_unit in init_data.sql_units:
            expanded = expander.expand(sql_unit.sql_text)
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
                            risk_flags=[],
                            active_conditions=[],
                        )
                        for exp in expanded
                    ],
                )
            )

        logger.info(f"[PARSE] Total: {len(init_data.sql_units)} SQL unit(s), {total_branches} branch(es)")
        logger.info("[PARSE] Parse stage completed")
        return ParseOutput(sql_units_with_branches=units_with_branches)
