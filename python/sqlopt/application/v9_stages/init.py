"""
V9 Init Stage - SQL Scanning and Parsing

Scans MyBatis XML mapper files and parses SQL statements.
Self-contained V9 implementation with zero V8 coupling.
"""

from __future__ import annotations

import json
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


def _render_logical_text(
    node: ET.Element,
    namespace: str,
    fragments: dict[str, dict[str, Any]],
    stack: set[str] | None = None,
) -> str:
    stack = set() if stack is None else set(stack)
    parts: list[str] = []
    if node.text:
        parts.append(node.text)
    for child in list(node):
        tag = _local_name(str(child.tag)).lower()
        if tag == "include":
            qualified = _qualify_ref(namespace, child.attrib.get("refid"))
            if qualified and qualified not in stack and qualified in fragments:
                next_stack = set(stack)
                next_stack.add(qualified)
                parts.append(
                    _render_logical_text(
                        fragments[qualified]["node"], namespace, fragments, next_stack
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
    return {
        "sqlKey": f"{namespace}.{statement_id}",
        "xmlPath": str(xml_path),
        "namespace": namespace,
        "statementId": statement_id,
        "statementType": statement_type.lower(),
        "variantId": f"v{idx}",
        "sql": " ".join(sql.split()),
        "parameterMappings": [],
        "paramExample": {},
        "locators": {"statementId": statement_id},
        "riskFlags": ["DOLLAR_SUBSTITUTION"] if "${" in sql else [],
        "scanWarnings": None,
    }


def _resolve_include_trace(
    namespace: str,
    refs: list[str],
    fragments: dict[str, dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]]]:
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
        if not fragment or qualified in stack:
            return
        next_stack = set(stack)
        next_stack.add(qualified)
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
    STATEMENT_TAGS = {"select", "insert", "update", "delete"}

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.mapper_globs = self.config.get("scan", {}).get(
            "mapper_globs", ["**/*.xml"]
        )

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

        for xml_file in files:
            try:
                units = self._parse_mapper(xml_file)
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

    def _parse_mapper(self, xml_path: Path) -> list[dict]:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        if not _is_mybatis_mapper_root(root):
            return []

        namespace = root.attrib.get("namespace", "unknown")
        fragments = _collect_fragment_meta(root, namespace)

        units: list[dict] = []
        idx = 0

        for node in root.iter():
            tag = _local_name(str(node.tag)).lower()
            if tag not in self.STATEMENT_TAGS:
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
# V9 Init Stage Entry Point
# =============================================================================


def run_init(
    run_dir: Path,
    *,
    config: dict[str, Any],
    validator: ContractValidator,
) -> dict[str, Any]:
    """V9 Init stage: scan MyBatis XML mappers and extract SQL units.

    Enhanced workflow:
    1. Check DB connectivity → write db_connectivity.json
    2. Scan XML mappers (existing)
    3. Collect schema metadata → write schema_metadata.json
    4. Generate paramExamples for each SQL unit
    5. Write enhanced sql_units.json
    """
    from ...platforms.sql.db_connectivity import check_db_connectivity
    from ...platforms.sql.schema_metadata import collect_schema_metadata
    from .param_example import generate_param_examples

    paths = canonical_paths(run_dir)

    # 1. DB Connectivity Check
    db_result = check_db_connectivity(config)
    db_connectivity_path = paths.init_db_connectivity_path
    db_connectivity_path.parent.mkdir(parents=True, exist_ok=True)
    with open(db_connectivity_path, "w") as f:
        json.dump(db_result, f, indent=2, ensure_ascii=False)

    # 2. SQL Scanning (existing logic)
    scanner = Scanner(config)
    root_path = config.get("project", {}).get("root_path", ".")
    result = scanner.scan(root_path)
    sql_units = [normalize_sqlunit(unit) for unit in result.sql_units]

    # 3. Schema Metadata Collection (if DB available)
    schema_metadata = {"tables": [], "columns": [], "indexes": [], "tableStats": []}
    if db_result.get("ok"):
        schema_metadata = collect_schema_metadata(config, sql_units)

    schema_metadata_path = paths.init_schema_metadata_path
    with open(schema_metadata_path, "w") as f:
        json.dump(schema_metadata, f, indent=2, ensure_ascii=False)

    # 4. Generate ParamExamples (requires DB connectivity)
    if db_result.get("ok"):
        sql_units = generate_param_examples(sql_units, schema_metadata)

    # 5. Validation & Output
    for unit in sql_units:
        validator.validate_stage_output("init", unit)

    output_path = paths.init_sql_units_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(sql_units, f, indent=2, ensure_ascii=False)

    # Report output files to progress reporter
    reporter = get_progress_reporter()
    reporter.report_info(f"init output: db_connectivity -> {db_connectivity_path}")
    reporter.report_info(f"init output: schema_metadata -> {schema_metadata_path}")
    reporter.report_info(f"init output: sql_units -> {output_path}")
    reporter.report_info(f"init complete: {len(sql_units)} SQL units extracted")

    return {
        "success": True,
        "output_files": [
            str(db_connectivity_path),
            str(schema_metadata_path),
            str(output_path),
        ],
        "sql_units_count": len(sql_units),
        "db_connectivity_ok": db_result.get("ok", False),
    }
