from __future__ import annotations

from pathlib import Path

from sqlopt.common.config import SQLOptConfig
from sqlopt.contracts.init import InitOutput, SQLUnit
from sqlopt.stages.base import Stage

from .parser import ParsedStatement, parse_mapper_file
from .scanner import find_mapper_files


class InitStage(Stage[None, InitOutput]):
    def __init__(self, config: SQLOptConfig | None = None, run_id: str | None = None) -> None:
        super().__init__("init")
        self.config = config
        self.run_id = run_id

    def run(
        self,
        _input_data: None = None,
        config: SQLOptConfig | None = None,
        run_id: str | None = None,
    ) -> InitOutput:
        cfg = config or self.config
        rid = run_id or self.run_id
        if cfg is None or rid is None:
            unit = SQLUnit(
                id="stub-1",
                mapper_file="UserMapper.xml",
                sql_id="findUser",
                sql_text="SELECT * FROM users WHERE id = #{id}",
                statement_type="SELECT",
            )
            output = InitOutput(sql_units=[unit], run_id="stub-run")
            self._write_output(output)
            return output

        project_root = cfg.project_root_path
        globs = cfg.scan_mapper_globs

        mapper_files = find_mapper_files(project_root, globs)

        sql_units: list[SQLUnit] = []
        for xml_path in mapper_files:
            statements = parse_mapper_file(xml_path)
            for stmt in statements:
                unit = _parsed_to_sqlunit(stmt)
                sql_units.append(unit)

        output = InitOutput(sql_units=sql_units, run_id=rid)
        self._write_output(output)
        return output

    def _write_output(self, output: InitOutput) -> None:
        output_dir = Path("runs") / output.run_id / "init"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "sql_units.json"
        output_file.write_text(output.to_json())


def _parsed_to_sqlunit(stmt: ParsedStatement) -> SQLUnit:
    return SQLUnit(
        id=stmt.sql_key,
        mapper_file=Path(stmt.xml_path).name,
        sql_id=stmt.statement_id,
        sql_text=stmt.xml_content,
        statement_type=stmt.statement_type,
    )
