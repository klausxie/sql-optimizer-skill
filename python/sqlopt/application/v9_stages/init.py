"""
V9 Init Stage - SQL Scanning and Parsing

Scans MyBatis XML mapper files and parses SQL statements.
Self-contained V9 implementation with zero V8 coupling.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ...contracts import ContractValidator
from ...progress import get_progress_reporter
from ...run_paths import canonical_paths
from ...shared.xml_utils import _local_name, _qualify_ref
from .common import normalize_sqlunit


# =============================================================================
# XML Parsing Utilities
# =============================================================================


def _inner_xml(node: ET.Element) -> str:
    parts: list[str] = []
    if node.text:
        parts.append(node.text)
    for child in list(node):
        parts.append(ET.tostring(child, encoding="unicode"))
    return "".join(parts).strip()


def _dynamic_features(node: ET.Element) -> list[str]:
    feature_by_tag = {
        "foreach": "FOREACH",
        "include": "INCLUDE",
        "if": "IF",
        "choose": "CHOOSE",
        "where": "WHERE",
        "trim": "TRIM",
        "set": "SET",
        "bind": "BIND",
    }
    seen: list[str] = []
    for elem in node.iter():
        feature = feature_by_tag.get(_local_name(str(elem.tag)).lower())
        if feature and feature not in seen:
            seen.append(feature)
    return seen


def _is_mybatis_mapper_root(root: ET.Element) -> bool:
    return _local_name(str(root.tag)).lower() == "mapper" and bool(
        str(root.attrib.get("namespace") or "").strip()
    )


def _extract_include_refs(node: ET.Element, namespace: str) -> list[str]:
    refs: list[str] = []
    for elem in node.iter():
        if _local_name(str(elem.tag)).lower() != "include":
            continue
        qualified = _qualify_ref(namespace, elem.attrib.get("refid"))
        if qualified and qualified not in refs:
            refs.append(qualified)
    return refs


def _collect_fragment_meta(
    root: ET.Element, namespace: str
) -> dict[str, dict[str, Any]]:
    """Collect fragment metadata from a single XML file.

    Args:
        root: XML root element.
        namespace: Mapper namespace.

    Returns:
        Dict of qualified_ref -> fragment metadata.
    """
    fragments: dict[str, dict[str, Any]] = {}
    for node in root:
        if _local_name(str(node.tag)).lower() != "sql":
            continue
        fragment_id = node.attrib.get("id")
        qualified = _qualify_ref(namespace, fragment_id)
        if not qualified:
            continue
        fragments[qualified] = {
            "ref": qualified,
            "node": node,
            "dynamicFeatures": _dynamic_features(node),
            "includeRefs": _extract_include_refs(node, namespace),
        }
    return fragments


def _build_global_fragment_registry(
    xml_files: list[Path],
) -> dict[str, dict[str, Any]]:
    """Build a global fragment registry from ALL mapper XML files.

    This is the KEY function for cross-file include resolution.
    It scans all XML files first, collects all <sql> fragments
    into a shared registry. This registry is then used when
    processing individual statements to resolve cross-file <include> refs.

    Args:
        xml_files: List of XML mapper file paths.

    Returns:
        Dict mapping qualified fragment ref -> fragment metadata.
    """
    global_registry: dict[str, dict[str, Any]] = {}

    for xml_file in xml_files:
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
        except Exception:
            continue

        if not _is_mybatis_mapper_root(root):
            continue

        file_namespace = root.attrib.get("namespace", "unknown")

        # Collect fragments from this file
        file_fragments = _collect_fragment_meta(root, file_namespace)

        # Merge into global registry
        for qualified, fragment_meta in file_fragments.items():
            if qualified not in global_registry:
                global_registry[qualified] = fragment_meta

    return global_registry


def _render_logical_text(
    node: ET.Element,
    namespace: str,
    fragments: dict[str, dict[str, Any]],
    stack: set[str] | None = None,
) -> str:
    """Render the logical SQL text from an XML node, expanding <include> refs.

    Args:
        node: The XML element to render.
        namespace: Current mapper namespace.
        fragments: Dict of fragment_id -> fragment metadata.
        stack: Set of visited references (for cycle detection).

    Returns:
        The logical SQL text with includes expanded.
    """
    stack = set() if stack is None else set(stack)
    parts: list[str] = []
    if node.text:
        parts.append(node.text)
    for child in list(node):
        tag = _local_name(str(child.tag)).lower()
        if tag == "include":
            qualified = _qualify_ref(namespace, child.attrib.get("refid"))
            if qualified and qualified in fragments:
                is_cyclic, next_stack = _detect_cyclic_include(qualified, stack)
                if not is_cyclic:
                    parts.append(
                        _render_logical_text(
                            fragments[qualified]["node"],
                            namespace,
                            fragments,
                            next_stack,
                        )
                    )
        else:
            parts.append(_render_logical_text(child, namespace, fragments, stack))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def _build_sql_unit(
    xml_path: Path,
    namespace: str,
    statement_id: str,
    statement_type: str,
    sql: str,
    idx: int,
) -> dict[str, Any]:
    """Build a SQL unit dict with extracted metadata.

    Args:
        xml_path: Path to the XML mapper file.
        namespace: Mapper namespace.
        statement_id: Statement ID from the mapper.
        statement_type: Statement type (SELECT, INSERT, UPDATE, DELETE).
        sql: The SQL text (logical, with includes expanded).
        idx: Index for variant ID generation.

    Returns:
        SQL unit dict conforming to sqlunit schema.
    """
    # Normalize whitespace while preserving string literals
    normalized_sql = _normalize_sql_whitespace(sql)

    return {
        "sqlKey": f"{namespace}.{statement_id}",
        "xmlPath": str(xml_path),
        "namespace": namespace,
        "statementId": statement_id,
        # Keep statement type uppercase for consistency with schema
        "statementType": statement_type,
        "variantId": f"v{idx}",
        "sql": normalized_sql,
        "parameterMappings": [],
        "paramExample": {},
        "locators": {"statementId": statement_id},
        # NOTE: This is a preliminary risk flag for quick scanning.
        # Full risk analysis (prefix_wildcard, function_wrap, n_plus_1, etc.)
        # is performed by RiskDetector in the parse stage.
        "riskFlags": ["DOLLAR_SUBSTITUTION"] if "${" in normalized_sql else [],
        "scanWarnings": None,
    }


def _resolve_include_trace(
    namespace: str,
    refs: list[str],
    fragments: dict[str, dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]]]:
    """Resolve the full trace of include references, detecting cycles.

    Args:
        namespace: Current mapper namespace.
        refs: List of include refids to resolve.
        fragments: Dict of fragment_id -> fragment metadata.

    Returns:
        Tuple of (trace_list, fragment_summaries) where trace_list contains
        all qualified fragment refs and fragment_summaries contains metadata.
    """
    trace: list[str] = []
    summaries: list[dict[str, Any]] = []
    seen_summary: set[str] = set()

    def visit(ref: str, stack: set[str]) -> None:
        qualified = _qualify_ref(namespace, ref)
        if not qualified:
            return
        if qualified not in trace:
            trace.append(qualified)
        fragment = fragments.get(qualified)
        if qualified not in seen_summary:
            summaries.append(
                {
                    "ref": qualified,
                    "dynamicFeatures": list(
                        (fragment or {}).get("dynamicFeatures", [])
                    ),
                }
            )
            seen_summary.add(qualified)

        is_cyclic, next_stack = _detect_cyclic_include(qualified, stack)
        if is_cyclic or not fragment:
            return

        for nested in fragment.get("includeRefs", []):
            visit(str(nested), next_stack)

    for ref in refs:
        visit(ref, set())
    return trace, summaries


# =============================================================================
# Scan Result and Scanner (V9)
# =============================================================================


@dataclass
class ScanResult:
    sql_units: list[dict] = field(default_factory=list)
    total_count: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)


class Scanner:
    _DEFAULT_STATEMENT_TAGS = {"select", "insert", "update", "delete"}

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.mapper_globs = self.config.get("scan", {}).get(
            "mapper_globs", ["**/*.xml"]
        )
        statement_types_cfg = self.config.get("scan", {}).get("statement_types")
        if statement_types_cfg is None:
            self.statement_tags = {"select"}
        else:
            self.statement_tags = {str(t).lower().strip() for t in statement_types_cfg}

    def scan(self, root_path: str | Path) -> ScanResult:
        root = Path(root_path)
        sql_units: list[dict] = []
        errors: list[str] = []
        warnings: list[dict] = []

        files = self._resolve_mapper_files(root)

        if not files:
            warnings.append(
                {
                    "severity": "fatal",
                    "reason_code": "SCAN_MAPPER_NOT_FOUND",
                    "message": "no mapper files matched",
                }
            )
            return ScanResult(
                sql_units=[], total_count=0, errors=errors, warnings=warnings
            )

        # Build global fragment registry for cross-file include resolution
        global_fragments = _build_global_fragment_registry(files)

        for xml_file in files:
            try:
                units = self._parse_mapper(xml_file, global_fragments)
                sql_units.extend(units)
            except Exception as e:
                errors.append(f"{xml_file}: {e}")
                warnings.append(
                    {
                        "severity": "degradable",
                        "reason_code": "SCAN_XML_PARSE_DEGRADED",
                        "message": str(e),
                        "xml_path": str(xml_file),
                    }
                )

        return ScanResult(
            sql_units=sql_units,
            total_count=len(sql_units),
            errors=errors,
            warnings=warnings,
        )

    def _resolve_mapper_files(self, root: Path) -> list[Path]:
        files: list[Path] = []
        for pattern in self.mapper_globs:
            for f in root.glob(pattern):
                if f.is_file():
                    files.append(f)
        return sorted(set(files))

    def _parse_mapper(
        self, xml_path: Path, global_fragments: dict[str, dict[str, Any]] | None = None
    ) -> list[dict]:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        if not _is_mybatis_mapper_root(root):
            return []

        namespace = root.attrib.get("namespace", "unknown")
        local_fragments = _collect_fragment_meta(root, namespace)
        fragments = (
            global_fragments if global_fragments is not None else local_fragments
        )

        units: list[dict] = []
        idx = 0

        for node in root.iter():
            tag = _local_name(str(node.tag)).lower()
            if tag not in self.statement_tags:
                continue

            idx += 1
            statement_id = node.attrib.get("id", f"unknown_{idx}")
            sql = _render_logical_text(node, namespace, fragments).strip()

            if not sql:
                continue

            unit = _build_sql_unit(
                xml_path, namespace, statement_id, tag.upper(), sql, idx
            )

            unit["templateSql"] = _inner_xml(node)
            unit["dynamicFeatures"] = _dynamic_features(node)

            include_refs = _extract_include_refs(node, namespace)
            include_trace, include_fragments = _resolve_include_trace(
                namespace, include_refs, fragments
            )
            unit["includeTrace"] = include_trace
            unit["dynamicTrace"] = (
                {
                    "statementFeatures": unit["dynamicFeatures"],
                    "includeFragments": include_fragments,
                }
                if unit["dynamicFeatures"] or include_trace
                else None
            )

            units.append(unit)

        return units


# =============================================================================
# SQL Normalization Utilities
# =============================================================================


def _normalize_sql_whitespace(sql: str) -> str:
    """Normalize whitespace in SQL while preserving string literal content.

    Uses regex to find string literals and normalize whitespace only in
    non-literal parts.

    Args:
        sql: The SQL string to normalize.

    Returns:
        SQL with normalized whitespace outside of string literals.
    """
    if not sql:
        return "" if sql is None else sql

    pattern = re.compile(r"'(?:[^'\\]|'')*'")

    result = []
    last_end = 0

    for match in pattern.finditer(sql):
        before = sql[last_end : match.start()]
        result.append(re.sub(r"\s+", " ", before))
        result.append(match.group(0))
        last_end = match.end()

    result.append(re.sub(r"\s+", " ", sql[last_end:]))

    return "".join(result)


# =============================================================================
# Circular Reference Detection
# =============================================================================


def _detect_cyclic_include(
    qualified: str,
    stack: set[str],
) -> tuple[bool, set[str]]:
    """Check for cyclic include references.

    Args:
        qualified: The qualified fragment reference to check.
        stack: Current set of visited references.

    Returns:
        Tuple of (is_cyclic, new_stack) where new_stack includes the qualified ref.
    """
    if qualified in stack:
        return True, stack
    new_stack = set(stack)
    new_stack.add(qualified)
    return False, new_stack


# =============================================================================
# V9 Init Stage Helper Functions
# =============================================================================


def _check_db_connectivity(
    config: dict[str, Any],
    paths: Any,
) -> dict[str, Any]:
    """Check database connectivity and write result to db_connectivity.json.

    Args:
        config: Configuration dict with db.platform and db.dsn.
        paths: RunPaths instance for file output.

    Returns:
        DB connectivity result dict with ok, error, driver, db_version fields.
    """
    from ...platforms.sql.db_connectivity import check_db_connectivity

    db_result = check_db_connectivity(config)
    db_connectivity_path = paths.init_db_connectivity_path
    db_connectivity_path.parent.mkdir(parents=True, exist_ok=True)
    with open(db_connectivity_path, "w") as f:
        json.dump(db_result, f, indent=2, ensure_ascii=False)

    return db_result


def _scan_sql_units(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Scan MyBatis XML mappers and extract SQL units.

    Args:
        config: Configuration dict with scan.mapper_globs and project.root_path.

    Returns:
        List of normalized SQL unit dicts.
    """
    scanner = Scanner(config)
    root_path = config.get("project", {}).get("root_path", ".")
    result = scanner.scan(root_path)
    return [normalize_sqlunit(unit) for unit in result.sql_units]


def _collect_schema_metadata(
    config: dict[str, Any],
    sql_units: list[dict[str, Any]],
    db_result: dict[str, Any],
    paths: Any,
) -> dict[str, Any]:
    """Collect schema metadata from database and write to schema_metadata.json.

    Args:
        config: Configuration dict with db settings.
        sql_units: List of SQL units to analyze for table references.
        db_result: DB connectivity result dict.
        paths: RunPaths instance for file output.

    Returns:
        Schema metadata dict with tables, columns, indexes, tableStats fields.
    """
    from ...platforms.sql.schema_metadata import collect_schema_metadata

    schema_metadata: dict[str, Any] = {
        "tables": [],
        "columns": [],
        "indexes": [],
        "tableStats": [],
    }

    if db_result.get("ok"):
        schema_metadata = collect_schema_metadata(config, sql_units)

    schema_metadata_path = paths.init_schema_metadata_path
    with open(schema_metadata_path, "w") as f:
        json.dump(schema_metadata, f, indent=2, ensure_ascii=False)

    return schema_metadata


def _generate_param_examples(
    sql_units: list[dict[str, Any]],
    schema_metadata: dict[str, Any],
    db_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], bool]:
    """Generate parameter examples for SQL units.

    Args:
        sql_units: List of SQL units to enrich with param examples.
        schema_metadata: Schema metadata dict with column information.
        db_result: DB connectivity result dict.

    Returns:
        Tuple of (enriched_sql_units, warning_should_be_logged).
    """
    from .param_example import generate_param_examples

    if db_result.get("ok"):
        return generate_param_examples(sql_units, schema_metadata), False
    else:
        # DB not available - paramExamples will be empty, caller should warn
        return sql_units, True


def _validate_and_write_output(
    sql_units: list[dict[str, Any]],
    validator: ContractValidator,
    paths: Any,
) -> int:
    """Validate SQL units against schema and write to sql_units.json.

    Args:
        sql_units: List of SQL units to validate and write.
        validator: ContractValidator instance for schema validation.
        paths: RunPaths instance for file output.

    Returns:
        Count of SQL units written.
    """
    for unit in sql_units:
        validator.validate_stage_output("init", unit)

    output_path = paths.init_sql_units_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(sql_units, f, indent=2, ensure_ascii=False)

    return len(sql_units)


# =============================================================================
# V9 Init Stage Entry Point
# =============================================================================


def run_init(
    run_dir: Path,
    *,
    config: dict[str, Any],
    validator: ContractValidator,
) -> dict[str, Any]:
    """V9 Init stage: scan MyBatis XML mappers and extract SQL units.

    This is the orchestrator for the init stage. It delegates to focused helper
    functions for each responsibility:

    1. _check_db_connectivity() - DB connectivity check
    2. _scan_sql_units() - XML mapper scanning
    3. _collect_schema_metadata() - Schema metadata collection
    4. _generate_param_examples() - Parameter example generation
    5. _validate_and_write_output() - Validation and output

    Output files:
        - init/db_connectivity.json: DB connectivity status
        - init/schema_metadata.json: Table/column metadata
        - init/sql_units.json: Extracted SQL units
    """
    paths = canonical_paths(run_dir)
    reporter = get_progress_reporter()

    # 1. DB Connectivity Check
    db_result = _check_db_connectivity(config, paths)
    reporter.report_info(
        f"init output: db_connectivity -> {paths.init_db_connectivity_path}"
    )

    # 2. SQL Scanning
    sql_units = _scan_sql_units(config)

    # 3. Schema Metadata Collection
    schema_metadata = _collect_schema_metadata(config, sql_units, db_result, paths)
    reporter.report_info(
        f"init output: schema_metadata -> {paths.init_schema_metadata_path}"
    )

    # 4. Generate ParamExamples
    sql_units, should_warn = _generate_param_examples(
        sql_units, schema_metadata, db_result
    )
    if should_warn:
        reporter.report_info(
            "[WARNING] DB unavailable - paramExamples will be empty. "
            "Full optimization may be limited."
        )

    # 5. Validation & Output
    count = _validate_and_write_output(sql_units, validator, paths)
    reporter.report_info(f"init output: sql_units -> {paths.init_sql_units_path}")
    reporter.report_info(f"init complete: {count} SQL units extracted")

    return {
        "success": True,
        "output_files": [
            str(paths.init_db_connectivity_path),
            str(paths.init_schema_metadata_path),
            str(paths.init_sql_units_path),
        ],
        "sql_units_count": count,
        "db_connectivity_ok": db_result.get("ok", False),
    }
