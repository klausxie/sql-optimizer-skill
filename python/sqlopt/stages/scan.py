"""Scan stage: parse MyBatis XML mappers using pure Python.

This module provides XML parsing and SQL unit extraction for MyBatis mappers.
No Java dependencies - uses xml.etree.ElementTree for all parsing.
"""

from __future__ import annotations

import glob
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from ..contracts import ContractValidator
from ..errors import StageError
from ..io_utils import read_jsonl, write_jsonl
from ..manifest import log_event
from ..progress import get_progress_reporter
from ..adapters.branch_generator import generate_branches
from ..adapters.mapper_catalog import enrich_sql_units_with_catalog
from ..application.sql_id_indexer import (
    build_index,
    load_index,
    lookup_files,
    parse_path_sql_id,
    save_index,
)
from ..scripting.fragment_registry import build_fragment_registry


def _get_index_path(project_root: Path) -> Path:
    return project_root / ".sqlopt" / "index.json"


def _local_name(tag: str) -> str:
    """Extract local name from XML tag (remove namespace prefix)."""
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _is_mybatis_mapper_root(root: ET.Element) -> bool:
    """Check if root element is a valid MyBatis mapper."""
    return _local_name(str(root.tag)).lower() == "mapper" and bool(
        str(root.attrib.get("namespace") or "").strip()
    )


def _build_unit(
    xml_path: Path,
    namespace: str,
    statement_id: str,
    statement_type: str,
    sql: str,
    idx: int,
) -> dict[str, Any]:
    """Build a SqlUnit dictionary."""
    return {
        "sqlKey": f"{namespace}.{statement_id}#v{idx}",
        "xmlPath": str(xml_path),
        "namespace": namespace,
        "statementId": statement_id,
        "statementType": statement_type,
        "variantId": f"v{idx}",
        "sql": " ".join(sql.split()),
        "parameterMappings": [],
        "paramExample": {},
        "locators": {"statementId": statement_id},
        "riskFlags": ["DOLLAR_SUBSTITUTION"] if "${" in sql else [],
        "scanWarnings": None,
    }


def _inner_xml(node: ET.Element) -> str:
    """Get inner XML of a node (preserving dynamic tags)."""
    parts: list[str] = []
    if node.text:
        parts.append(node.text)
    for child in list(node):
        parts.append(ET.tostring(child, encoding="unicode"))
    return "".join(parts).strip()


def _dynamic_features(node: ET.Element) -> list[str]:
    """Extract dynamic features from a node."""
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


def _qualify_ref(namespace: str, refid: str | None) -> str:
    """Qualify a fragment reference with namespace."""
    ref = str(refid or "").strip()
    if not ref:
        return ""
    if "." in ref:
        return ref
    return f"{namespace}.{ref}" if namespace else ref


def _resolve_mapper_files(project_root: Path, mapper_globs: list[str]) -> list[str]:
    files: list[str] = []
    for pat in mapper_globs:
        files.extend(glob.glob(str(project_root / pat), recursive=True))
    return sorted(set(files))


def _extract_include_refs(node: ET.Element, namespace: str) -> list[str]:
    """Extract include references from a node."""
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
    """Collect fragment metadata from mapper."""
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


def _resolve_include_trace(
    namespace: str, refs: list[str], fragments: dict[str, dict[str, Any]]
) -> tuple[list[str], list[dict[str, Any]]]:
    """Resolve include trace and fragment summaries."""
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


def _render_logical_text(
    node: ET.Element,
    namespace: str,
    fragments: dict[str, dict[str, Any]],
    stack: set[str] | None = None,
) -> str:
    """Render logical SQL text (resolving includes)."""
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


def _discover_statement_count(project_root: Path, mapper_globs: list[str]) -> int:
    """Count total statements in mapper files."""
    total = 0
    for fp in _resolve_mapper_files(project_root, mapper_globs):
        try:
            root = ET.parse(fp).getroot()
        except Exception:
            continue
        if not _is_mybatis_mapper_root(root):
            continue
        for elem in root.iter():
            name = _local_name(str(elem.tag)).lower()
            if name in {"select", "update", "delete", "insert"}:
                total += 1
    return total


def _write_fragment_catalog(
    *,
    units: list[dict[str, Any]],
    enable_fragment_catalog: bool,
    project_root: Path,
    mapper_globs: list[str],
    fragments_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Write fragment catalog if enabled."""
    if not enable_fragment_catalog:
        return units, []
    enriched_units, fragments = enrich_sql_units_with_catalog(
        units, project_root, mapper_globs
    )
    write_jsonl(fragments_path, fragments)
    return enriched_units, fragments


def _perform_scan(
    project_root: Path,
    mapper_globs: list[str],
    manifest_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Perform pure Python XML scan of MyBatis mappers."""
    units: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    files = _resolve_mapper_files(project_root, mapper_globs)
    reporter = get_progress_reporter()

    if not files:
        warnings.append(
            {
                "severity": "fatal",
                "reason_code": "SCAN_MAPPER_NOT_FOUND",
                "message": "no mapper files matched",
            }
        )
        return [], warnings

    reporter.report_info(f"Resolved {len(files)} mapper file(s) from scan.mapper_globs")
    total_files = len(files)
    for index, fp in enumerate(files, start=1):
        path = Path(fp)
        if total_files > 1 and (index == 1 or index == total_files or index % 10 == 0):
            reporter.report_info(f"Parsing mapper {index}/{total_files}: {path.name}")
        try:
            root = ET.parse(path).getroot()
        except Exception as exc:
            warnings.append(
                {
                    "severity": "degradable",
                    "reason_code": "SCAN_XML_PARSE_DEGRADED",
                    "message": f"xml parse degraded: {exc}",
                    "xml_path": str(path),
                }
            )
            log_event(manifest_path, "scan", "degraded", warnings[-1])
            continue

        if not _is_mybatis_mapper_root(root):
            continue

        namespace = root.attrib.get("namespace", "unknown")
        fragments = _collect_fragment_meta(root, namespace)
        idx = 0

        for node in root.iter():
            tag = _local_name(str(node.tag)).lower()
            if tag not in {"select", "update", "delete", "insert"}:
                continue

            idx += 1
            statement_id = node.attrib.get("id", f"unknown_{idx}")
            sql = _render_logical_text(node, namespace, fragments).strip()

            if not sql:
                continue

            unit = _build_unit(path, namespace, statement_id, tag.upper(), sql, idx)
            include_trace, include_fragments = _resolve_include_trace(
                namespace, _extract_include_refs(node, namespace), fragments
            )

            unit["templateSql"] = _inner_xml(node)
            unit["dynamicFeatures"] = _dynamic_features(node)
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

    return units, warnings


def run_scan(
    config: dict[str, Any],
    run_dir: Path,
    manifest_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Public API for scanning MyBatis mappers.

    This function provides backward compatibility with the legacy scanner_java.run_scan API.

    Args:
        config: Configuration dict with project.root_path and scan.mapper_globs
        run_dir: Run directory path
        manifest_path: Path to manifest.jsonl

    Returns:
        Tuple of (units, warnings)
    """
    project_root = Path(
        str((config.get("project", {}) or {}).get("root_path") or ".")
    ).resolve()
    mapper_globs = config.get("scan", {}).get("mapper_globs", [])
    return _perform_scan(project_root, mapper_globs, manifest_path)


def execute(
    config: dict[str, Any], run_dir: Path, validator: ContractValidator
) -> list[dict[str, Any]]:
    """Execute scan stage: parse MyBatis XML mappers using pure Python."""
    project_root = Path(
        str((config.get("project", {}) or {}).get("root_path") or ".")
    ).resolve()
    mapper_globs = config.get("scan", {}).get("mapper_globs", [])
    scan_cfg = config.get("scan", {}) or {}
    class_resolution_cfg = scan_cfg.get("class_resolution", {}) or {}
    min_success_ratio = float(class_resolution_cfg.get("min_success_ratio", 0.9))
    enable_fragment_catalog = bool(scan_cfg.get("enable_fragment_catalog", True))

    manifest_path = run_dir / "manifest.jsonl"
    fragments_path = run_dir / "scan.fragments.jsonl"

    discovered_count = _discover_statement_count(project_root, mapper_globs)
    units, warnings = run_scan(config, run_dir, manifest_path)

    if not units:
        for w in warnings:
            log_event(manifest_path, "scan", "failed", w)
        reason_code = "SCAN_MAPPER_NOT_FOUND"
        for warning in warnings:
            code = warning.get("reason_code")
            if isinstance(code, str) and code.strip():
                reason_code = code
                break
        raise StageError("scan produced no sql units", reason_code=reason_code)

    # Filter by target_xml_paths
    target_xml_paths = config.get("target_xml_paths")
    if target_xml_paths:
        target_path_set = set(target_xml_paths)
        original_count = len(units)
        units = [
            u
            for u in units
            if u.get("xmlPath")
            and any(
                p in u.get("xmlPath")
                or u.get("xmlPath", "").endswith("/" + p)
                or u.get("xmlPath", "").endswith("\\" + p)
                for p in target_path_set
            )
        ]
        filtered_count = len(units)
        print(
            f"Filtered {original_count} SQL units to {filtered_count} by target_xml_paths: {target_xml_paths}"
        )
        if not units:
            raise StageError(
                f"No SQL units match target_xml_paths: {target_xml_paths}",
                reason_code="SCAN_XML_PATH_NOT_FOUND",
            )

    # Filter by target_sql_ids - using enhanced matching
    target_sql_ids = config.get("target_sql_ids")
    if target_sql_ids:
        target_sql_ids = [str(x).strip() for x in target_sql_ids if str(x).strip()]

        # Check for absolute path + SQL ID format (e.g., /path/User.xml:findUsers)
        path_sql_pairs = []
        pure_sql_ids = []
        for sql_id in target_sql_ids:
            file_path, sql_id_part = parse_path_sql_id(sql_id)
            if file_path:
                path_sql_pairs.append((file_path, sql_id_part))
            else:
                pure_sql_ids.append(sql_id_part)

        original_count = len(units)

        # If we have absolute path + SQL ID pairs, filter by file path first
        if path_sql_pairs:
            file_set = set(p[0] for p in path_sql_pairs)
            units = [u for u in units if u.get("xmlPath") in file_set]
            filtered_count = len(units)
            print(
                f"Filtered {original_count} SQL units to {filtered_count} by target_xml_paths from sql_ids"
            )

        # Now filter by SQL ID using enhanced matching
        if pure_sql_ids:
            # Build alias map for enhanced matching
            from ..application.sql_id_indexer import _selection_aliases

            alias_map: dict[str, list[dict[str, Any]]] = {}
            for unit in units:
                for alias in _selection_aliases(unit):
                    alias_map.setdefault(alias, []).append(unit)

            selected = []
            for sql_id in pure_sql_ids:
                # Try exact match first
                matches = alias_map.get(sql_id, [])
                if not matches:
                    # Try suffix match
                    for alias, units_list in alias_map.items():
                        if alias.endswith(f".{sql_id}"):
                            matches.extend(units_list)
                if matches:
                    selected.extend(matches)

            # Deduplicate
            seen = set()
            deduped = []
            for u in selected:
                sql_key = str(u.get("sqlKey") or "")
                if sql_key and sql_key not in seen:
                    seen.add(sql_key)
                    deduped.append(u)
            units = deduped

        filtered_count = len(units)
        print(
            f"Filtered {original_count} SQL units to {filtered_count} by target_sql_ids: {target_sql_ids}"
        )
        if not units:
            raise StageError(
                f"No SQL units match target_sql_ids: {target_sql_ids}",
                reason_code="SCAN_SQL_ID_NOT_FOUND",
            )
        discovered_count = filtered_count

    # Coverage check
    if discovered_count > 0:
        parsed_count = len(units)
        success_ratio = parsed_count / discovered_count
        if success_ratio < min_success_ratio:
            payload = {
                "severity": "fatal",
                "reason_code": "SCAN_PARTIAL_COVERAGE_BELOW_THRESHOLD",
                "message": f"scan success ratio {success_ratio:.3f} below threshold {min_success_ratio:.3f}",
                "detail": {
                    "discovered_count": discovered_count,
                    "parsed_count": parsed_count,
                    "min_success_ratio": min_success_ratio,
                },
            }
            log_event(manifest_path, "scan", "failed", payload)
            raise StageError(
                "scan coverage below threshold",
                reason_code="SCAN_PARTIAL_COVERAGE_BELOW_THRESHOLD",
            )

    # Generate branches (enabled by default)
    # NOTE: Scan stage ONLY generates branches, does NOT diagnose problems
    # Problem diagnosis is done in the Analyze stage
    branch_cfg = config.get("branch", {})
    if branch_cfg.get("enabled", True):
        branch_config = dict(config)
        branch_config["_fragment_registry"] = build_fragment_registry(
            _resolve_mapper_files(project_root, mapper_globs)
        )
        for unit in units:
            branches = generate_branches(unit, branch_config)
            unit["branches"] = branches
            unit["branchCount"] = len(branches)

    # Validate and write
    for unit in units:
        validator.validate("sqlunit", unit)
    write_jsonl(run_dir / "scan.sqlunits.jsonl", units)

    # Build and save index for fast lookup
    try:
        index = build_index(units, project_root)
        index_path = _get_index_path(project_root)
        save_index(index, index_path)
        print(f"Built and saved index to {index_path}")
    except Exception as e:
        print(f"Warning: Failed to build index: {e}")

    units, _ = _write_fragment_catalog(
        units=units,
        enable_fragment_catalog=enable_fragment_catalog,
        project_root=project_root,
        mapper_globs=mapper_globs,
        fragments_path=fragments_path,
    )

    # Export branches (streaming write to reduce memory)
    export_cfg = branch_cfg.get("export", {})
    if export_cfg.get("enabled", True):
        export_path = export_cfg.get("path", "branches.jsonl")
        branches_file = run_dir / export_path
        branch_count = 0
        with branches_file.open("w", encoding="utf-8") as f:
            for unit in units:
                unit_branches = unit.get("branches", [])
                template_sql = unit.get("templateSql", unit.get("sql", ""))
                for branch in unit_branches:
                    branch_record = {
                        "sqlKey": unit.get("sqlKey"),
                        "templateSql": template_sql,
                        "xmlPath": unit.get("xmlPath"),
                        "namespace": unit.get("namespace"),
                        "statementId": unit.get("statementId"),
                        "branch": branch,
                    }
                    f.write(json.dumps(branch_record, ensure_ascii=False) + "\n")
                    branch_count += 1
        log_event(
            manifest_path,
            "branch_export",
            "done",
            {"path": str(branches_file), "count": branch_count},
        )

    for fragment in read_jsonl(fragments_path):
        validator.validate("fragment_record", fragment)
    for w in warnings:
        log_event(manifest_path, "scan", "warning", w)
    log_event(
        manifest_path,
        "scan",
        "done",
        {"sql_keys": [u["sqlKey"] for u in units]},
    )
    return units
