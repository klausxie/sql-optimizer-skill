from __future__ import annotations

import glob
import hashlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from ..platforms.sql.dynamic_surface_locator import locate_choose_branch_surface
from ..utils import statement_key_from_row

_NAMESPACE_RE = re.compile(r"<mapper\b[^>]*\bnamespace\s*=\s*(['\"])(.*?)\1", re.IGNORECASE)
_STATEMENT_RE = re.compile(
    r"<(select|update|delete|insert)\b[^>]*\bid\s*=\s*(['\"])(.*?)\2[^>]*>([\s\S]*?)</\1>",
    re.IGNORECASE,
)
_FRAGMENT_RE = re.compile(r"<sql\b[^>]*\bid\s*=\s*(['\"])(.*?)\1[^>]*>([\s\S]*?)</sql>", re.IGNORECASE)

_KNOWN_DYNAMIC_TAGS = {
    "foreach": "FOREACH",
    "include": "INCLUDE",
    "if": "IF",
    "choose": "CHOOSE",
    "where": "WHERE",
    "trim": "TRIM",
    "set": "SET",
    "bind": "BIND",
}
_NON_OPAQUE_TAGS = set(_KNOWN_DYNAMIC_TAGS) | {"when", "otherwise", "property"}
_SAMPLE_RENDER_PARAMS: dict[str, Any] = {
    "id": 1,
    "name": "demo",
    "keyword": "demo",
    "status": "ACTIVE",
    "list": [1, 2, 3],
    "items": ["a", "b"],
    "offset": 0,
    "limit": 10,
}
_TEST_EXPR_RE = re.compile(
    r"^\s*(?P<path>[a-zA-Z_][a-zA-Z0-9_\.]*)\s*(?P<op>==|!=)\s*(?P<value>null|''|\"\"|'[^']*'|\"[^\"]*\"|-?\d+|true|false)\s*$",
    flags=re.IGNORECASE,
)


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _normalize_sql_text(text: str) -> str:
    return " ".join(str(text or "").split())


def _extract_namespace(xml_text: str) -> str:
    match = _NAMESPACE_RE.search(xml_text)
    return match.group(2).strip() if match else "unknown"


def _qualify_display_ref(namespace: str, ref_id: str | None) -> str:
    ref = str(ref_id or "").strip()
    if not ref:
        return ""
    if "." in ref:
        return ref
    return f"{namespace}.{ref}" if namespace else ref


def _fragment_key(xml_path: Path, display_ref: str) -> str:
    return f"{xml_path}::{display_ref}"


def _position_from_offset(text: str, offset: int) -> tuple[int, int]:
    safe_offset = max(0, min(offset, len(text)))
    line = text.count("\n", 0, safe_offset) + 1
    last_newline = text.rfind("\n", 0, safe_offset)
    col = safe_offset + 1 if last_newline < 0 else safe_offset - last_newline
    return line, col


def _range_for_span(text: str, start: int, end: int) -> dict[str, int]:
    start_line, start_col = _position_from_offset(text, start)
    end_line, end_col = _position_from_offset(text, end)
    return {
        "startLine": start_line,
        "startColumn": start_col,
        "endLine": end_line,
        "endColumn": end_col,
        "startOffset": start,
        "endOffset": end,
    }


def _collect_dynamic_features(body: str) -> list[str]:
    text = body or ""
    features: list[str] = []
    for tag, feature in _KNOWN_DYNAMIC_TAGS.items():
        if re.search(rf"(?is)<{tag}\b", text) and feature not in features:
            features.append(feature)
    try:
        root = ET.fromstring(f"<root>{text}</root>")
    except Exception:
        return features
    opaque_found = False
    for elem in root.iter():
        if elem is root:
            continue
        name = _local_name(str(elem.tag)).lower()
        if name not in _NON_OPAQUE_TAGS:
            opaque_found = True
            break
    if opaque_found and "OPAQUE_XML" not in features:
        features.append("OPAQUE_XML")
    return features


def _extract_attr(attrs: dict[str, Any], name: str) -> str:
    return str(attrs.get(name) or "").strip()


def _extract_include_bindings(body: str, namespace: str, xml_path: Path) -> list[dict[str, Any]]:
    if not body.strip():
        return []
    try:
        root = ET.fromstring(f"<root>{body}</root>")
    except Exception:
        return []
    bindings: list[dict[str, Any]] = []
    for elem in root.iter():
        if _local_name(str(elem.tag)).lower() != "include":
            continue
        display_ref = _qualify_display_ref(namespace, elem.attrib.get("refid"))
        if not display_ref:
            continue
        props: list[dict[str, str]] = []
        for child in list(elem):
            if _local_name(str(child.tag)).lower() != "property":
                continue
            name = _extract_attr(child.attrib, "name")
            value = _extract_attr(child.attrib, "value")
            props.append({"name": name, "valueRaw": value, "valueNormalized": value})
        binding_source = display_ref + "|" + "|".join(f"{p['name']}={p['valueNormalized']}" for p in props)
        bindings.append(
            {
                "ref": _fragment_key(xml_path, display_ref),
                "displayRef": display_ref,
                "properties": props,
                "bindingHash": hashlib.sha1(binding_source.encode("utf-8")).hexdigest()[:12],
            }
        )
    return bindings


def _direct_fragment_refs(fragment_row: dict[str, Any]) -> list[str]:
    return [str(binding.get("ref") or "") for binding in fragment_row.get("includeBindings", []) if str(binding.get("ref") or "").strip()]


def _resolve_include_trace(
    direct_refs: list[str],
    fragments_by_key: dict[str, dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]], bool]:
    trace: list[str] = []
    summaries: list[dict[str, Any]] = []
    seen_summary: set[str] = set()
    degraded = False
    max_depth = 16

    def visit(ref: str, stack: set[str], depth: int) -> None:
        nonlocal degraded
        if not ref:
            return
        if ref not in trace:
            trace.append(ref)
        fragment = fragments_by_key.get(ref)
        if ref not in seen_summary:
            summaries.append(
                {
                    "ref": ref,
                    "displayRef": (fragment or {}).get("displayRef", ""),
                    "dynamicFeatures": list((fragment or {}).get("dynamicFeatures", [])),
                }
            )
            seen_summary.add(ref)
        if fragment is None:
            return
        if depth >= max_depth or ref in stack:
            degraded = True
            return
        next_stack = set(stack)
        next_stack.add(ref)
        for nested in _direct_fragment_refs(fragment):
            visit(nested, next_stack, depth + 1)

    for direct in direct_refs:
        visit(direct, set(), 0)
    return trace, summaries, degraded


def _parse_mappers(project_root: Path, mapper_globs: list[str]) -> list[dict[str, Any]]:
    files: list[str] = []
    for pat in mapper_globs:
        files.extend(glob.glob(str(project_root / pat), recursive=True))
    out: list[dict[str, Any]] = []
    for file_name in sorted(set(files)):
        path = Path(file_name)
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        namespace = _extract_namespace(text)
        out.append({"xmlPath": path.resolve(), "namespace": namespace, "xmlText": text})
    return out


def _build_fragment_row(xml_path: Path, namespace: str, xml_text: str, match: re.Match[str]) -> dict[str, Any]:
    fragment_id = match.group(2).strip()
    body = match.group(3)
    display_ref = _qualify_display_ref(namespace, fragment_id)
    return {
        "fragmentKey": _fragment_key(xml_path, display_ref),
        "displayRef": display_ref,
        "xmlPath": str(xml_path),
        "namespace": namespace,
        "fragmentId": fragment_id,
        "templateSql": body,
        "dynamicFeatures": _collect_dynamic_features(body),
        "includeBindings": _extract_include_bindings(body, namespace, xml_path),
        "locators": {
            "nodeType": "SQL_FRAGMENT",
            "fragmentId": fragment_id,
            "range": _range_for_span(xml_text, match.start(3), match.end(3)),
        },
    }


def _build_statement_meta(xml_path: Path, namespace: str, xml_text: str, match: re.Match[str]) -> tuple[str, dict[str, Any]]:
    statement_id = match.group(3).strip()
    statement_key = f"{namespace}.{statement_id}"
    body = match.group(4)
    include_bindings = _extract_include_bindings(body, namespace, xml_path)
    primary_fragment = include_bindings[0]["ref"] if include_bindings else None
    return statement_key, {
        "templateSql": body,
        "dynamicFeatures": _collect_dynamic_features(body),
        "locators": {
            "statementId": statement_id,
            "range": _range_for_span(xml_text, match.start(4), match.end(4)),
        },
        "includeBindings": include_bindings,
        "templateTarget": "SQL_FRAGMENT_DEPENDENT" if include_bindings else "STATEMENT",
        "primaryFragmentTarget": primary_fragment,
    }


def _extract_choose_branch_surfaces(template_sql: str) -> list[dict[str, Any]]:
    text = str(template_sql or "").strip()
    if not text:
        return []
    try:
        wrapper = ET.fromstring(f"<root>{text}</root>")
    except Exception:
        return []
    where_nodes = [child for child in list(wrapper) if _local_name(str(child.tag)).lower() == "where"]
    if len(where_nodes) != 1:
        return []
    where_children = [child for child in list(where_nodes[0]) if child.tag is not None]
    if len(where_children) != 1 or _local_name(str(where_children[0].tag)).lower() != "choose":
        return []
    choose_node = where_children[0]
    branches = [child for child in list(choose_node) if _local_name(str(child.tag)).lower() in {"when", "otherwise"}]
    if not branches or len(branches) != len(list(choose_node)):
        return []
    surfaces: list[dict[str, Any]] = []
    for idx, branch in enumerate(branches):
        branch_kind = _local_name(str(branch.tag)).upper()
        branch_sql = _normalize_sql_text("".join(
            ([branch.text] if branch.text else [])
            + [ET.tostring(child, encoding="unicode") for child in list(branch)]
        ))
        if not branch_sql:
            continue
        row: dict[str, Any] = {
            "surfaceType": "CHOOSE_BRANCH_BODY",
            "chooseOrdinal": 0,
            "branchOrdinal": idx,
            "branchKind": branch_kind,
            "renderedBranchSql": branch_sql,
            "requiredEnvelopeShape": "TOP_LEVEL_WHERE_CHOOSE",
        }
        branch_test = _normalize_sql_text(str(branch.attrib.get("test") or ""))
        if branch_test:
            row["branchTestFingerprint"] = branch_test
        surfaces.append(row)
    return surfaces


def _sample_param_value(path: str) -> Any:
    current: Any = _SAMPLE_RENDER_PARAMS
    for part in str(path or "").strip().split("."):
        if not part:
            return None
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _parse_test_literal(token: str) -> Any:
    value = str(token or "").strip()
    lower = value.lower()
    if lower == "null":
        return None
    if lower == "true":
        return True
    if lower == "false":
        return False
    if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
        return value[1:-1]
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def _split_logical_test(expr: str, operator: str) -> list[str]:
    pattern = re.compile(rf"\s+{operator}\s+", flags=re.IGNORECASE)
    parts = [part.strip() for part in pattern.split(str(expr or "").strip()) if part.strip()]
    return parts if len(parts) > 1 else []


def _evaluate_simple_test(expr: str) -> bool | None:
    match = _TEST_EXPR_RE.match(str(expr or "").strip())
    if match is None:
        return None
    current = _sample_param_value(match.group("path"))
    expected = _parse_test_literal(match.group("value"))
    op = match.group("op")
    return current == expected if op == "==" else current != expected


def _evaluate_choose_test(expr: str) -> bool | None:
    text = str(expr or "").strip()
    if not text:
        return None
    and_parts = _split_logical_test(text, "and")
    if and_parts:
        results = [_evaluate_choose_test(part) for part in and_parts]
        return None if any(result is None for result in results) else all(bool(result) for result in results)
    or_parts = _split_logical_test(text, "or")
    if or_parts:
        results = [_evaluate_choose_test(part) for part in or_parts]
        return None if any(result is None for result in results) else any(bool(result) for result in results)
    return _evaluate_simple_test(text)


def _sample_choose_render_identity(choose_branch_surfaces: list[dict[str, Any]]) -> dict[str, Any] | None:
    for surface in choose_branch_surfaces:
        branch_kind = str(surface.get("branchKind") or "").strip().upper()
        if branch_kind == "WHEN":
            decision = _evaluate_choose_test(str(surface.get("branchTestFingerprint") or ""))
            if decision is not True:
                continue
        elif branch_kind != "OTHERWISE":
            continue
        identity: dict[str, Any] = {
            "surfaceType": "CHOOSE_BRANCH_BODY",
            "renderMode": "CHOOSE_BRANCH_RENDERED",
            "chooseOrdinal": int(surface.get("chooseOrdinal") or 0),
            "branchOrdinal": int(surface.get("branchOrdinal") or 0),
            "branchKind": branch_kind,
            "renderedBranchSql": str(surface.get("renderedBranchSql") or "").strip(),
            "requiredEnvelopeShape": str(surface.get("requiredEnvelopeShape") or "TOP_LEVEL_WHERE_CHOOSE").strip(),
            "requiredSiblingShape": {
                "branchCount": len(choose_branch_surfaces),
            },
        }
        branch_test = str(surface.get("branchTestFingerprint") or "").strip()
        if branch_test:
            identity["branchTestFingerprint"] = branch_test
        return identity
    return None


def _enrich_sql_unit(unit: dict[str, Any], statements_by_key: dict[str, dict[str, Any]]) -> None:
    key = statement_key_from_row(unit)
    meta = statements_by_key.get(key)
    if not meta:
        return
    locators = dict(unit.get("locators") or {})
    locators.update(meta["locators"])
    unit["locators"] = locators
    if not str(unit.get("templateSql") or "").strip():
        unit["templateSql"] = meta["templateSql"]
    if not unit.get("dynamicFeatures"):
        unit["dynamicFeatures"] = list(meta["dynamicFeatures"])
    unit["includeBindings"] = meta["includeBindings"]
    unit["templateTarget"] = meta["templateTarget"]
    unit["primaryFragmentTarget"] = meta["primaryFragmentTarget"]
    choose_branch_surfaces = _extract_choose_branch_surfaces(str(unit.get("templateSql") or ""))
    if choose_branch_surfaces:
        dynamic_trace = dict(unit.get("dynamicTrace") or {})
        dynamic_trace["chooseBranchSurfaces"] = choose_branch_surfaces
        unit["dynamicTrace"] = dynamic_trace
    if not unit.get("dynamicRenderIdentity"):
        template_sql = str(unit.get("templateSql") or "").strip()
        original_sql = str(unit.get("sql") or "").strip()
        choose_surface = locate_choose_branch_surface(template_sql, original_sql) if template_sql and original_sql else None
        if choose_surface:
            target_anchor = dict(choose_surface.get("targetAnchor") or {})
            identity: dict[str, Any] = {
                "surfaceType": "CHOOSE_BRANCH_BODY",
                "renderMode": "CHOOSE_BRANCH_RENDERED",
                "chooseOrdinal": int(target_anchor.get("chooseOrdinal") or 0),
                "branchOrdinal": int(target_anchor.get("branchOrdinal") or 0),
                "branchKind": str(target_anchor.get("branchKind") or "").strip().upper(),
                "renderedBranchSql": str(choose_surface.get("beforeBodySql") or "").strip(),
                "requiredEnvelopeShape": "TOP_LEVEL_WHERE_CHOOSE",
                "requiredSiblingShape": {
                    "branchCount": int(choose_surface.get("siblingBranchCount") or 0),
                },
            }
            branch_test = str(target_anchor.get("branchTestFingerprint") or "").strip()
            if branch_test:
                identity["branchTestFingerprint"] = branch_test
            unit["dynamicRenderIdentity"] = identity
        elif choose_branch_surfaces:
            sampled_identity = _sample_choose_render_identity(choose_branch_surfaces)
            if sampled_identity:
                unit["dynamicRenderIdentity"] = sampled_identity


def build_fragment_catalog(project_root: Path, mapper_globs: list[str]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    fragments: list[dict[str, Any]] = []
    fragments_by_key: dict[str, dict[str, Any]] = {}
    for mapper in _parse_mappers(project_root, mapper_globs):
        xml_path = Path(mapper["xmlPath"])
        namespace = str(mapper["namespace"])
        xml_text = str(mapper["xmlText"])
        for match in _FRAGMENT_RE.finditer(xml_text):
            row = _build_fragment_row(xml_path, namespace, xml_text, match)
            key = str(row["fragmentKey"])
            fragments.append(row)
            fragments_by_key[key] = row
    for row in fragments:
        trace, summaries, degraded = _resolve_include_trace(_direct_fragment_refs(row), fragments_by_key)
        row["includeTrace"] = trace
        row["dynamicTrace"] = {
            "templateFeatures": list(row.get("dynamicFeatures", [])),
            "includeFragments": summaries,
            "resolutionDegraded": degraded,
        }
    return fragments, fragments_by_key


def enrich_sql_units_with_catalog(
    units: list[dict[str, Any]],
    project_root: Path,
    mapper_globs: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fragments, fragments_by_key = build_fragment_catalog(project_root, mapper_globs)
    statements_by_key: dict[str, dict[str, Any]] = {}
    for mapper in _parse_mappers(project_root, mapper_globs):
        xml_path = Path(mapper["xmlPath"])
        namespace = str(mapper["namespace"])
        xml_text = str(mapper["xmlText"])
        for match in _STATEMENT_RE.finditer(xml_text):
            statement_key, statement_meta = _build_statement_meta(xml_path, namespace, xml_text, match)
            statements_by_key[statement_key] = statement_meta
    for unit in units:
        _enrich_sql_unit(unit, statements_by_key)
    return units, fragments
