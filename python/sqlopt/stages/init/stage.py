from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

from sqlopt.common.config import SQLOptConfig
from sqlopt.common.summary_generator import generate_init_summary_markdown
from sqlopt.contracts.init import (
    FieldDistribution,
    FileMapping,
    FragmentMapping,
    InitOutput,
    SQLFragment,
    SQLUnit,
    StatementMapping,
    XMLMapping,
)
from sqlopt.stages.base import Stage

from .parser import ParsedFragment, ParsedStatement, parse_mapper_file
from .scanner import find_mapper_files
from .table_extractor import extract_field_distributions, extract_table_schemas, extract_where_fields_from_sql

if TYPE_CHECKING:
    from sqlopt.common.db_connector import DBConnector

logger = logging.getLogger(__name__)


def extract_table_names_from_sql(sql_text: str) -> list[str]:
    """Extract table names from SQL text by parsing FROM and JOIN clauses.

    Args:
        sql_text: SQL text to parse.

    Returns:
        List of table names found in the SQL text.
    """
    if not sql_text:
        return []

    # Pattern to match table names in FROM and JOIN clauses
    # Handles: FROM table_name, FROM table_name AS alias, JOIN table_name, etc.
    patterns = [
        # FROM clause: FROM table_name (with optional AS alias)
        r"\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*)(?:\s+AS\s+[a-zA-Z_][a-zA-Z0-9_]*)?",
        # JOIN clause: JOIN table_name, INNER JOIN, LEFT JOIN, RIGHT JOIN, etc.
        r"\b(?:INNER|LEFT|RIGHT|OUTER|CROSS)?\s*JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)",
    ]

    table_names: set[str] = set()
    sql_upper = sql_text.upper()

    for pattern in patterns:
        matches = re.finditer(pattern, sql_upper, re.IGNORECASE)
        for match in matches:
            table_name = match.group(1)
            if table_name and table_name.upper() not in ("SELECT", "WHERE", "ON", "AND", "OR", "NOT", "IN", "SET"):
                table_names.add(match.group(1).lower())

    return list(table_names)


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
        start_time = time.time()
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
            self._generate_summary(output, duration_seconds=time.time() - start_time, files_count=0)
            return output

        project_root = cfg.project_root_path
        globs = cfg.scan_mapper_globs
        logger.info(f"[INIT] Project root: {project_root}")
        logger.info(f"[INIT] Scan globs: {globs}")

        mapper_files = find_mapper_files(project_root, globs)
        logger.info(f"[INIT] Found {len(mapper_files)} mapper file(s)")

        sql_units: list[SQLUnit] = []
        sql_fragments: list[SQLFragment] = []
        file_mappings: dict[str, FileMapping] = {}
        total_statements = 0
        total_fragments = 0
        for idx, xml_path in enumerate(mapper_files):
            logger.info(f"[INIT] Processing file {idx + 1}/{len(mapper_files)}: {xml_path.name}")
            statements, fragments = parse_mapper_file(xml_path)
            stmt_count = len(statements)
            frag_count = len(fragments)
            total_statements += stmt_count
            total_fragments += frag_count

            file_mapping = FileMapping(xml_path=str(xml_path))
            for stmt in statements:
                if cfg.statement_types and stmt.statement_type not in cfg.statement_types:
                    logger.debug(f"[INIT]   Skipping {stmt.statement_type} statement: {stmt.statement_id}")
                    continue
                unit = _parsed_to_sqlunit(stmt)
                sql_units.append(unit)
                stmt_xpath = _build_statement_xpath(stmt)
                stmt_mapping = StatementMapping(
                    sql_key=stmt.sql_key,
                    statement_id=stmt.statement_id,
                    xpath=stmt_xpath,
                    tag_name=stmt.statement_type.lower(),
                    id_attr=stmt.statement_id,
                    original_content=stmt.xml_content,
                )
                file_mapping.statements.append(stmt_mapping)

            for frag in fragments:
                sql_fragments.append(_parsed_to_sqlfragment(frag))
                frag_mapping = FragmentMapping(
                    fragment_id=frag.fragment_id,
                    sql_key=None,
                    xpath=frag.xpath,
                    tag_name="sql",
                    id_attr=frag.fragment_id,
                    original_content=frag.xml_content,
                )
                file_mapping.fragments.append(frag_mapping)

            file_mappings[str(xml_path)] = file_mapping

        logger.info(
            f"[INIT] {total_statements} SQL unit(s), {total_fragments} SQL fragment(s) from {len(mapper_files)} mapper file(s)"
        )

        xml_mappings = XMLMapping(files=list(file_mappings.values()))

        table_schemas: dict = {}
        all_table_names: set[str] = set()
        schema_extraction_success = False
        field_distributions: list[FieldDistribution] = []

        for unit in sql_units:
            table_names = extract_table_names_from_sql(unit.sql_text)
            all_table_names.update(table_names)

        if all_table_names:
            db_connector: "DBConnector | None" = None
            if cfg.db_host and cfg.db_port and cfg.db_name:
                from sqlopt.common.db_connector import create_connector

                db_connector = create_connector(
                    platform=cfg.db_platform,
                    host=cfg.db_host,
                    port=cfg.db_port,
                    db=cfg.db_name,
                    user=cfg.db_user or "",
                    password=cfg.db_password or "",
                )
                logger.info(f"[INIT] Extracting schemas for {len(all_table_names)} table(s)")
                table_schemas = extract_table_schemas(
                    table_names=list(all_table_names),
                    db_connector=db_connector,
                    platform=cfg.db_platform,
                )
                logger.info(f"[INIT] Extracted schemas for {len(table_schemas)} table(s)")
                schema_extraction_success = True

                logger.info("[INIT] Extracting WHERE field distributions")
                field_by_table: dict[str, set[str]] = {}
                for unit in sql_units:
                    table_names = extract_table_names_from_sql(unit.sql_text)
                    where_fields = extract_where_fields_from_sql(unit.sql_text)
                    for tbl in table_names:
                        if tbl not in field_by_table:
                            field_by_table[tbl] = set()
                        field_by_table[tbl].update(where_fields)

                for tbl, cols in field_by_table.items():
                    if tbl not in table_schemas:
                        logger.debug(f"[INIT] Skipping {tbl} - not in database schema")
                        continue
                    schema_cols = {col["name"].lower() for col in table_schemas[tbl].columns}
                    valid_cols = cols & schema_cols
                    invalid_cols = cols - schema_cols
                    if invalid_cols:
                        logger.debug(f"[INIT] Skipping invalid fields in {tbl}: {invalid_cols}")
                    cols = valid_cols
                    if cols:
                        dists = extract_field_distributions(
                            table_name=tbl,
                            column_names=list(cols),
                            db_connector=db_connector,
                            platform=cfg.db_platform,
                        )
                        field_distributions.extend(dists)
                logger.info(f"[INIT] Extracted distributions for {len(field_distributions)} field(s)")
            else:
                logger.info("[INIT] No database config available, skipping table schema extraction")
        else:
            logger.info("[INIT] No tables found in SQL units")

        output = InitOutput(
            sql_units=sql_units,
            run_id=rid,
            sql_fragments=sql_fragments,
            xml_mappings=xml_mappings,
            table_schemas=table_schemas,
        )
        self._write_output(output)
        if field_distributions:
            self._write_field_distributions(field_distributions, rid)
        logger.info(
            "[INIT] Output written to: runs/{}/init/{{sql_units,sql_fragments,table_schemas,xml_mappings,field_distributions}}.json".format(
                rid
            )
        )
        self._generate_summary(
            output,
            duration_seconds=time.time() - start_time,
            files_count=len(mapper_files),
            schema_extraction_success=schema_extraction_success,
            field_distributions_count=len(field_distributions),
        )
        logger.info("[INIT] Init stage completed")
        return output

    def _write_output(self, output: InitOutput) -> None:
        output_dir = Path("runs") / output.run_id / "init"
        output_dir.mkdir(parents=True, exist_ok=True)

        # 1. sql_units.json - List[SQLUnit]
        sql_units_file = output_dir / "sql_units.json"
        sql_units_file.write_text(json.dumps([asdict(u) for u in output.sql_units]), encoding="utf-8")

        # 2. sql_fragments.json - List[SQLFragment]
        sql_fragments_file = output_dir / "sql_fragments.json"
        sql_fragments_file.write_text(json.dumps([asdict(f) for f in output.sql_fragments]), encoding="utf-8")

        # 3. table_schemas.json - Dict[str, TableSchema]
        table_schemas_file = output_dir / "table_schemas.json"
        table_schemas_file.write_text(
            json.dumps({k: asdict(v) for k, v in output.table_schemas.items()}), encoding="utf-8"
        )

        # 4. xml_mappings.json - XMLMapping
        xml_mappings_file = output_dir / "xml_mappings.json"
        if output.xml_mappings:
            xml_mappings_file.write_text(output.xml_mappings.to_json(), encoding="utf-8")
        else:
            xml_mappings_file.write_text(json.dumps({"files": []}), encoding="utf-8")

    def _write_field_distributions(
        self,
        field_distributions: list[FieldDistribution],
        run_id: str,
    ) -> None:
        output_dir = Path("runs") / run_id / "init"
        output_dir.mkdir(parents=True, exist_ok=True)
        field_distributions_file = output_dir / "field_distributions.json"
        field_distributions_file.write_text(json.dumps([asdict(fd) for fd in field_distributions]), encoding="utf-8")

    def _generate_summary(
        self,
        output: InitOutput,
        duration_seconds: float,
        files_count: int,
        schema_extraction_success: bool = True,
        field_distributions_count: int = 0,
    ) -> None:
        """Generate SUMMARY.md for the init stage.

        Best-effort operation - failures are logged but do not block stage completion.

        Args:
            output: The InitOutput data to summarize.
            duration_seconds: Total execution time in seconds.
            files_count: Number of mapper files processed.
            schema_extraction_success: Whether schema extraction succeeded.
            field_distributions_count: Number of field distributions collected.
        """
        try:
            output_dir = Path("runs") / output.run_id / "init"

            file_size_bytes = 0
            for filename in [
                "sql_units.json",
                "sql_fragments.json",
                "table_schemas.json",
                "xml_mappings.json",
                "field_distributions.json",
            ]:
                filepath = output_dir / filename
                if filepath.exists():
                    file_size_bytes += filepath.stat().st_size

            summary_content = generate_init_summary_markdown(
                output=output,
                duration_seconds=duration_seconds,
                files_count=files_count,
                file_size_bytes=file_size_bytes,
                schema_extraction_success=schema_extraction_success,
                field_distributions_count=field_distributions_count,
            )
            summary_file = output_dir / "SUMMARY.md"
            summary_file.write_text(summary_content, encoding="utf-8")
            logger.info(f"[INIT] Summary written to: {summary_file}")
        except Exception as e:
            logger.warning(f"[INIT] Failed to generate SUMMARY.md: {e}")


def _build_statement_xpath(stmt: ParsedStatement) -> str:
    tag_name = stmt.statement_type.lower()
    if stmt.namespace:
        return f"/mapper/{stmt.namespace}.{tag_name}[@id='{stmt.statement_id}']"
    return f"/mapper/{tag_name}[@id='{stmt.statement_id}']"


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
        fragment_id=frag.fragment_id,
        xml_path=frag.xml_path,
        start_line=frag.start_line,
        end_line=frag.end_line,
        xml_content=frag.xml_content,
    )
