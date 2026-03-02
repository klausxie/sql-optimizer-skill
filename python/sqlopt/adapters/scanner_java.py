from __future__ import annotations

import glob
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from ..io_utils import write_jsonl
from ..manifest import log_event
from ..subprocess_utils import run_capture_text
from .mapper_catalog import enrich_sql_units_with_catalog


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _is_mybatis_mapper_root(root: ET.Element) -> bool:
    return _local_name(str(root.tag)).lower() == "mapper" and bool(str(root.attrib.get("namespace") or "").strip())


def _build_unit(xml_path: Path, namespace: str, statement_id: str, statement_type: str, sql: str, idx: int) -> dict[str, Any]:
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


def _collect_fragment_meta(root: ET.Element, namespace: str) -> dict[str, dict[str, Any]]:
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


def _resolve_include_trace(namespace: str, refs: list[str], fragments: dict[str, dict[str, Any]]) -> tuple[list[str], list[dict[str, Any]]]:
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
                    "dynamicFeatures": list((fragment or {}).get("dynamicFeatures", [])),
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


def _render_logical_text(node: ET.Element, namespace: str, fragments: dict[str, dict[str, Any]], stack: set[str] | None = None) -> str:
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
                parts.append(_render_logical_text(fragments[qualified]["node"], namespace, fragments, next_stack))
        else:
            parts.append(_render_logical_text(child, namespace, fragments, stack))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def _python_fallback_scan(project_root: Path, mapper_globs: list[str], manifest_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    units: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    files = []
    for pat in mapper_globs:
        files.extend(glob.glob(str(project_root / pat), recursive=True))
    if not files:
        warnings.append({"severity": "fatal", "reason_code": "SCAN_MAPPER_NOT_FOUND", "message": "no mapper files matched"})
        return [], warnings
    for fp in sorted(set(files)):
        path = Path(fp)
        try:
            root = ET.parse(path).getroot()
        except Exception as exc:
            warnings.append({
                "severity": "degradable",
                "reason_code": "SCAN_CLASS_RESOLUTION_DEGRADED",
                "message": f"xml parse degraded: {exc}",
                "xml_path": str(path),
            })
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
            include_trace, include_fragments = _resolve_include_trace(namespace, _extract_include_refs(node, namespace), fragments)
            unit["templateSql"] = _inner_xml(node)
            unit["dynamicFeatures"] = _dynamic_features(node)
            unit["includeTrace"] = include_trace
            unit["dynamicTrace"] = {
                "statementFeatures": unit["dynamicFeatures"],
                "includeFragments": include_fragments,
            } if unit["dynamicFeatures"] or include_trace else None
            units.append(unit)
    return units, warnings


def _resolve_java_jar(project_root: Path, jar_path: str) -> Path:
    jar = Path(jar_path)
    if not jar.is_absolute():
        jar = (project_root / jar).resolve()
    return jar


def _write_fragment_catalog(
    *,
    units: list[dict[str, Any]],
    enable_fragment_catalog: bool,
    project_root: Path,
    mapper_globs: list[str],
    fragments_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not enable_fragment_catalog:
        return units, []
    enriched_units, fragments = enrich_sql_units_with_catalog(units, project_root, mapper_globs)
    write_jsonl(fragments_path, fragments)
    return enriched_units, fragments


def _java_scan_failure(message: str) -> list[dict[str, Any]]:
    return [
        {
            "severity": "fatal",
            "reason_code": "SCAN_UNKNOWN_EXIT",
            "message": message,
        }
    ]


def _read_java_scan_output(out_path: Path) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    for line in out_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            units.append(json.loads(line))
    return units


def _collect_java_warnings(stderr_text: str, manifest_path: Path) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    if not stderr_text.strip():
        return warnings
    for line in stderr_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            payload = {"phase": "scan", "severity": "fatal", "reason_code": "SCAN_UNKNOWN_EXIT", "message": line}
        warnings.append(payload)
        log_event(manifest_path, "scan", "scanner_stderr", payload)
    return warnings


def _run_java_scanner(
    *,
    project_root: Path,
    run_dir: Path,
    manifest_path: Path,
    config: dict[str, Any],
    jar: Path,
    out_path: Path,
    dialect: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    scan_cfg_path = run_dir / "scan.config.json"
    scan_cfg_path.write_text(json.dumps(config.get("scan", {}), ensure_ascii=False), encoding="utf-8")
    cmd = [
        "java",
        "-jar",
        str(jar),
        "--project-root",
        str(project_root),
        "--config-path",
        str(scan_cfg_path),
        "--out-jsonl",
        str(out_path),
        "--dialect",
        dialect,
        "--run-id",
        run_dir.name,
    ]
    proc = run_capture_text(cmd)
    warnings = _collect_java_warnings(proc.stderr, manifest_path)
    if proc.returncode in (0, 10) and out_path.exists():
        units = _read_java_scan_output(out_path)
        if units:
            return units, warnings
        warning = {
            "severity": "fatal",
            "reason_code": "SCAN_XML_PARSE_FATAL",
            "message": "java scan-agent produced no sql units",
        }
        warnings.append(warning)
        log_event(manifest_path, "scan", "failed", warning)
        return [], warnings
    warning = {
        "severity": "fatal",
        "reason_code": "SCAN_UNKNOWN_EXIT",
        "message": f"java scan-agent exit={proc.returncode}",
    }
    warnings.append(warning)
    log_event(manifest_path, "scan", "failed", warning)
    return [], warnings


def _strict_mode_rejects_warnings(class_resolution_mode: str, warnings: list[dict[str, Any]]) -> bool:
    if class_resolution_mode != "strict":
        return False
    degrade_codes = {
        "SCAN_CLASS_RESOLUTION_DEGRADED",
        "SCAN_CLASS_NOT_FOUND",
        "SCAN_TYPE_ATTR_SANITIZED",
        "SCAN_STATEMENT_PARSE_DEGRADED",
    }
    return any(str(w.get("reason_code")) in degrade_codes for w in warnings)


def run_scan(config: dict[str, Any], run_dir: Path, manifest_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    project_root = Path(config["project"]["root_path"]).resolve()
    mapper_globs = config["scan"]["mapper_globs"]
    dialect = str((config.get("db", {}) or {}).get("platform", "sql"))
    scan_cfg = config.get("scan", {}) or {}
    enable_fragment_catalog = bool(scan_cfg.get("enable_fragment_catalog", True))
    java_cfg = scan_cfg.get("java_scanner", {}) or {}
    class_resolution_cfg = scan_cfg.get("class_resolution", {}) or {}
    class_resolution_mode = str(class_resolution_cfg.get("mode", "tolerant")).strip().lower()
    jar_path = str(java_cfg.get("jar_path") or "").strip()
    out_path = run_dir / "scan.sqlunits.jsonl"
    fragments_path = run_dir / "scan.fragments.jsonl"

    if jar_path:
        jar = _resolve_java_jar(project_root, jar_path)
        if not jar.exists():
            return [], _java_scan_failure(f"java scanner jar not found: {jar}")
        units, warnings = _run_java_scanner(
            project_root=project_root,
            run_dir=run_dir,
            manifest_path=manifest_path,
            config=config,
            jar=jar,
            out_path=out_path,
            dialect=dialect,
        )
        if units:
            if _strict_mode_rejects_warnings(class_resolution_mode, warnings):
                return [], _java_scan_failure("class resolution degraded under strict mode")
            units, _ = _write_fragment_catalog(
                units=units,
                enable_fragment_catalog=enable_fragment_catalog,
                project_root=project_root,
                mapper_globs=mapper_globs,
                fragments_path=fragments_path,
            )
        return units, warnings

    units, warnings = _python_fallback_scan(project_root, mapper_globs, manifest_path)
    units, _ = _write_fragment_catalog(
        units=units,
        enable_fragment_catalog=enable_fragment_catalog,
        project_root=project_root,
        mapper_globs=mapper_globs,
        fragments_path=fragments_path,
    )
    return units, warnings
