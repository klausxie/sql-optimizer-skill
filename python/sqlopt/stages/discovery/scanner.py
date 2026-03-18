"""
Discovery Stage - SQL Scanning and Parsing (V8)

Scans MyBatis XML mapper files and parses SQL statements.
Complete rewrite for V8 - zero coupling with legacy code.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any
import xml.etree.ElementTree as ET


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


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


def _qualify_ref(namespace: str, refid: str | None) -> str:
    ref = str(refid or "").strip()
    if not ref:
        return ""
    if "." in ref:
        return ref
    return f"{namespace}.{ref}" if namespace else ref


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

    def scan_single(self, xml_path: str | Path) -> list[dict]:
        return self._parse_mapper(Path(xml_path))


class Parser:
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}

    def parse(self, sql: str) -> dict:
        import re

        return {
            "raw_sql": sql,
            "type": self._detect_sql_type(sql),
            "tables": self._extract_tables(sql),
            "conditions": self._extract_conditions(sql),
            "joins": self._extract_joins(sql),
        }

    def _detect_sql_type(self, sql: str) -> str:
        sql_upper = sql.strip().upper()
        if sql_upper.startswith("SELECT"):
            return "SELECT"
        elif sql_upper.startswith("INSERT"):
            return "INSERT"
        elif sql_upper.startswith("UPDATE"):
            return "UPDATE"
        elif sql_upper.startswith("DELETE"):
            return "DELETE"
        return "UNKNOWN"

    def _extract_tables(self, sql: str) -> list[str]:
        import re

        pattern = r"(?:FROM|JOIN|INTO|UPDATE)\s+(\w+)"
        matches = re.findall(pattern, sql, re.IGNORECASE)
        return list(set(matches))

    def _extract_conditions(self, sql: str) -> list[dict]:
        import re

        conditions = []
        where_match = re.search(
            r"WHERE\s+(.+?)(?:GROUP|ORDER|LIMIT|$)", sql, re.IGNORECASE | re.DOTALL
        )
        if where_match:
            where_clause = where_match.group(1)
            for cond in re.split(
                r"\s+AND\s+|\s+OR\s+", where_clause, flags=re.IGNORECASE
            ):
                if cond.strip():
                    conditions.append({"condition": cond.strip()})
        return conditions

    def _extract_joins(self, sql: str) -> list[str]:
        import re

        pattern = r"(INNER|LEFT|RIGHT|OUTER)?\s*JOIN\s+(\w+)"
        matches = re.findall(pattern, sql, re.IGNORECASE)
        return [j[1] for j in matches]


def scan_mappers(config: dict, root_path: str | Path) -> list[dict]:
    scanner = Scanner(config)
    result = scanner.scan(root_path)
    return result.sql_units


def parse_mappers(mapper_paths: list[str | Path]) -> list[dict]:
    results = []
    for path in mapper_paths:
        scanner = Scanner()
        scan_result = scanner.scan(path)
        results.extend(scan_result.sql_units)
    return results
