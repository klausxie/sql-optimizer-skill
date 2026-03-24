from __future__ import annotations

from sqlopt.common.mock_data_loader import MockDataLoader
from sqlopt.contracts.init import InitOutput
from sqlopt.contracts.parse import ParseOutput, SQLBranch, SQLUnitWithBranches
from sqlopt.stages.base import Stage

from .expander import expand_branches


class ParseStage(Stage[None, ParseOutput]):
    def __init__(self, run_id: str | None = None, use_mock: bool = True) -> None:
        super().__init__("parse")
        self.run_id = run_id
        self.use_mock = use_mock

    def run(self, _input_data: None = None, run_id: str | None = None, use_mock: bool | None = None) -> ParseOutput:
        rid = run_id or self.run_id
        mock = use_mock if use_mock is not None else self.use_mock

        if rid is None:
            branch = SQLBranch(path_id="p1", condition=None, expanded_sql="SELECT * FROM users", is_valid=True)
            unit_with_branches = SQLUnitWithBranches(sql_unit_id="stub-1", branches=[branch])
            return ParseOutput(sql_units_with_branches=[unit_with_branches])

        loader = MockDataLoader(rid, use_mock=mock)
        init_file = loader.get_init_sql_units_path()

        if not init_file.exists():
            branch = SQLBranch(path_id="p1", condition=None, expanded_sql="SELECT * FROM users", is_valid=True)
            unit_with_branches = SQLUnitWithBranches(sql_unit_id="stub-1", branches=[branch])
            return ParseOutput(sql_units_with_branches=[unit_with_branches])

        init_data = InitOutput.from_json(init_file.read_text(encoding="utf-8"))

        units_with_branches: list[SQLUnitWithBranches] = [
            SQLUnitWithBranches(
                sql_unit_id=sql_unit.id,
                branches=[
                    SQLBranch(
                        path_id=exp.path_id,
                        condition=exp.condition,
                        expanded_sql=exp.expanded_sql,
                        is_valid=exp.is_valid,
                    )
                    for exp in expand_branches(sql_unit.sql_text)
                ],
            )
            for sql_unit in init_data.sql_units
        ]

        return ParseOutput(sql_units_with_branches=units_with_branches)
