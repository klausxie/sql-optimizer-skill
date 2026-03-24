from __future__ import annotations

import logging
from pathlib import Path

from sqlopt.common.config import SQLOptConfig
from sqlopt.contracts.init import InitOutput, SQLFragment, SQLUnit
from sqlopt.stages.base import Stage

from .parser import ParsedFragment, ParsedStatement, parse_mapper_file
from .scanner import find_mapper_files

logger = logging.getLogger(__name__)


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
        logger.info("=" * 60)
        logger.info("[INIT] Starting Init stage")
        logger.info(f"[INIT] Run ID: {rid}")

        if cfg is None or rid is None:
            logger.warning("[INIT] No config or run_id provided, using stub data")
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
        logger.info(f"[INIT] Project root: {project_root}")
        logger.info(f"[INIT] Scan globs: {globs}")

        mapper_files = find_mapper_files(project_root, globs)
        logger.info(f"[INIT] Found {len(mapper_files)} mapper file(s)")

        sql_units: list[SQLUnit] = []
        sql_fragments: list = []
        total_statements = 0
        total_fragments = 0
        for xml_path in mapper_files:
            logger.debug(f"[INIT] Parsing: {xml_path}")
            statements, fragments = parse_mapper_file(xml_path)
            stmt_count = len(statements)
            frag_count = len(fragments)
            total_statements += stmt_count
            total_fragments += frag_count
            logger.debug(f"[INIT]   Found {stmt_count} SQL statement(s) in {Path(xml_path).name}")
            for stmt in statements:
                unit = _parsed_to_sqlunit(stmt)
                sql_units.append(unit)
            for frag in fragments:
                sql_fragments.append(_parsed_to_sqlfragment(frag))

        logger.info(f"[INIT] Extracted {total_statements} SQL unit(s) from {len(mapper_files)} mapper file(s)")
        logger.info(f"[INIT] Extracted {total_fragments} SQL fragment(s) from {len(mapper_files)} mapper file(s)")
        logger.info(f"[INIT] SQL units: {[u.sql_id for u in sql_units]}")

        output = InitOutput(sql_units=sql_units, run_id=rid, sql_fragments=sql_fragments)
        self._write_output(output)
        logger.info(f"[INIT] Output written to: runs/{rid}/init/sql_units.json")
        logger.info("[INIT] Init stage completed")
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


def _parsed_to_sqlfragment(frag: ParsedFragment) -> SQLFragment:
    return SQLFragment(
        fragmentId=frag.fragment_id,
        xmlPath=frag.xml_path,
        startLine=frag.start_line,
        endLine=frag.end_line,
        xmlContent=frag.xml_content,
    )
