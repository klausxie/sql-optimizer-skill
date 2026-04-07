from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..platforms.sql.template_rendering import (
    collect_fragments,
    find_statement_node,
    fragment_key,
    normalize_sql_text,
    qualify_ref,
    render_logical_text,
    render_fragment_body_sql,
    render_template_body_sql,
)
from .patch_artifact import PatchArtifactResult, materialize_patch_artifact

_PLACEHOLDER_RE = re.compile(r"(?:#|\$)\{[^}]+\}")
_COMPARISON_OPERATOR_RE = re.compile(r"\s*(>=|<=|!=|<>|=)\s*")
_UNION_KEYWORD_RE = re.compile(r"\s*\b(UNION(?:\s+ALL)?)\b\s*", flags=re.IGNORECASE)
_STATEMENT_REPLAY_MODES = {
    "STATEMENT_SQL",
    "STATEMENT_TEMPLATE_SAFE",
    "STATEMENT_TEMPLATE_SAFE_WRAPPER_COLLAPSE",
}
_FRAGMENT_REPLAY_MODES = {
    "FRAGMENT_TEMPLATE_SAFE",
    "FRAGMENT_TEMPLATE_SAFE_AUTO",
}


@dataclass(frozen=True)
class ReplayResult:
    matches_target: bool
    rendered_sql: str | None
    normalized_rendered_sql: str | None
    drift_reason: str | None = None


def _normalize_replay_sql(sql: str) -> str:
    normalized = normalize_sql_text(sql)
    if not normalized:
        return normalized
    normalized = _COMPARISON_OPERATOR_RE.sub(r" \1 ", normalized)
    normalized = _UNION_KEYWORD_RE.sub(r" \1 ", normalized)
    return normalize_sql_text(normalized)


def _extract_placeholder_shape(template: str) -> list[str]:
    return _PLACEHOLDER_RE.findall(str(template or ""))


def _extract_required_includes(template: str, namespace: str) -> list[str]:
    try:
        wrapper = ET.fromstring(f"<root>{template}</root>")
    except ET.ParseError:
        return []
    includes: list[str] = []
    for node in wrapper.iter():
        if str(node.tag).rsplit("}", 1)[-1].lower() != "include":
            continue
        refid = qualify_ref(namespace, node.attrib.get("refid"))
        if refid:
            includes.append(refid)
    return includes


def _collect_normalized_if_tests(template: str) -> list[str]:
    try:
        wrapper = ET.fromstring(f"<root>{template}</root>")
    except ET.ParseError:
        return []
    tests: list[str] = []
    for node in wrapper.iter():
        if str(node.tag).rsplit("}", 1)[-1].lower() != "if":
            continue
        tests.append(normalize_sql_text(str(node.attrib.get("test") or "")))
    return tests


def _if_inner_template(node: ET.Element) -> str:
    parts: list[str] = []
    if node.text:
        parts.append(node.text)
    for child in list(node):
        parts.append(ET.tostring(child, encoding="unicode"))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def _node_inner_template(node: ET.Element) -> str:
    parts: list[str] = []
    if node.text:
        parts.append(node.text)
    for child in list(node):
        parts.append(ET.tostring(child, encoding="unicode"))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def _collect_normalized_if_bodies(template: str) -> list[str]:
    try:
        wrapper = ET.fromstring(f"<root>{template}</root>")
    except ET.ParseError:
        return []
    bodies: list[str] = []
    for node in wrapper.iter():
        if str(node.tag).rsplit("}", 1)[-1].lower() != "if":
            continue
        bodies.append(normalize_sql_text(_if_inner_template(node)))
    return bodies


def _render_statement_sql(template: str, sql_unit: dict[str, Any], fragment_catalog: dict[str, dict[str, Any]]) -> str | None:
    xml_path = Path(str(sql_unit.get("xmlPath") or ""))
    namespace = str(sql_unit.get("namespace") or "").strip()
    if xml_path.exists():
        try:
            root = ET.parse(xml_path).getroot()
        except Exception:
            root = None
        if root is not None:
            fragments = collect_fragments(root, namespace, xml_path)
            return render_template_body_sql(template, namespace, xml_path, fragments)
    if fragment_catalog:
        synthetic_fragments: dict[str, ET.Element] = {}
        for ref, row in fragment_catalog.items():
            body = str(row.get("templateSql") or "")
            try:
                synthetic_fragments[ref] = ET.fromstring(f"<sql>{body}</sql>")
            except ET.ParseError:
                continue
        if synthetic_fragments:
            return render_template_body_sql(template, namespace, xml_path, synthetic_fragments)
    return normalize_sql_text(template)


def _render_fragment_sql(
    template: str,
    sql_unit: dict[str, Any],
    fragment_catalog: dict[str, dict[str, Any]],
    target_ref: str | None,
) -> str | None:
    fragment = fragment_catalog.get(str(target_ref or "").strip())
    if not fragment:
        return normalize_sql_text(template)
    xml_path = Path(str(fragment.get("xmlPath") or sql_unit.get("xmlPath") or ""))
    namespace = str(fragment.get("namespace") or sql_unit.get("namespace") or "").strip()
    return render_fragment_body_sql(template, namespace, xml_path, fragment_catalog)


def _render_statement_sql_from_artifact(artifact: PatchArtifactResult, sql_unit: dict[str, Any]) -> str | None:
    if artifact.root is None:
        return None
    xml_path = Path(str(sql_unit.get("xmlPath") or ""))
    namespace = str(sql_unit.get("namespace") or "").strip()
    statement_id = str(((sql_unit.get("locators") or {}) if isinstance(sql_unit.get("locators"), dict) else {}).get("statementId") or sql_unit.get("statementId") or "").strip()
    if not statement_id:
        return None
    statement = find_statement_node(artifact.root, statement_id)
    if statement is None:
        return None
    fragments = collect_fragments(artifact.root, namespace, xml_path)
    return normalize_sql_text(render_logical_text(statement, namespace, xml_path, fragments))


def _render_fragment_sql_from_artifact(
    artifact: PatchArtifactResult,
    sql_unit: dict[str, Any],
    target_ref: str | None,
) -> str | None:
    if artifact.root is None:
        return None
    xml_path = Path(str(sql_unit.get("xmlPath") or ""))
    namespace = str(sql_unit.get("namespace") or "").strip()
    target_ref = str(target_ref or "").strip()
    if not target_ref:
        return None
    fragments = collect_fragments(artifact.root, namespace, xml_path)
    target_candidates = {target_ref}
    fragment_node = next(
        (
            node
            for node in artifact.root
            if str(node.tag).rsplit("}", 1)[-1].lower() == "sql"
            and (
                (qualified_ref := qualify_ref(namespace, node.attrib.get("id"))) in target_candidates
                or fragment_key(xml_path, qualified_ref) in target_candidates
            )
        ),
        None,
    )
    if fragment_node is None:
        return None
    return render_template_body_sql(_node_inner_template(fragment_node), namespace, xml_path, fragments)


def replay_patch_target(
    *,
    sql_unit: dict[str, Any],
    patch_target: dict[str, Any],
    fragment_catalog: dict[str, dict[str, Any]],
    patch_text: str = "",
    artifact: PatchArtifactResult | None = None,
) -> ReplayResult:
    replay_contract = patch_target.get("replayContract") or {}
    ops = [row for row in (patch_target.get("templateRewriteOps") or []) if isinstance(row, dict)]
    statement_op = next((row for row in ops if str(row.get("op") or "") == "replace_statement_body"), None)
    fragment_op = next((row for row in ops if str(row.get("op") or "") == "replace_fragment_body"), None)
    replay_mode = str(replay_contract.get("replayMode") or "").strip()

    template_after = ""
    if statement_op is not None:
        template_after = str(statement_op.get("afterTemplate") or "")
    elif fragment_op is not None:
        template_after = str(fragment_op.get("afterTemplate") or "")
    else:
        target_sql = str(patch_target.get("targetSql") or "")
        normalized_target_sql = normalize_sql_text(target_sql)
        return ReplayResult(True, target_sql, normalized_target_sql, None)

    required_anchors = [str(anchor) for anchor in (replay_contract.get("requiredAnchors") or [])]
    if any(anchor not in template_after for anchor in required_anchors):
        return ReplayResult(False, None, None, "PATCH_ANCHOR_LOSS")

    namespace = str(sql_unit.get("namespace") or "").strip()
    required_includes = [str(ref) for ref in (replay_contract.get("requiredIncludes") or [])]
    actual_includes = _extract_required_includes(template_after, namespace)
    if any(ref not in actual_includes for ref in required_includes):
        return ReplayResult(False, None, None, "PATCH_INCLUDE_LOSS")

    required_placeholders = replay_contract.get("requiredPlaceholderShape") or []
    if isinstance(required_placeholders, str):
        required_placeholders = [] if required_placeholders in {"", "NONE"} else [required_placeholders]
    actual_placeholders = _extract_placeholder_shape(template_after)
    if list(required_placeholders) != actual_placeholders:
        return ReplayResult(False, None, None, "PATCH_PLACEHOLDER_SHAPE_DRIFT")

    required_if_tests = replay_contract.get("requiredIfTestShape")
    if isinstance(required_if_tests, str):
        required_if_tests = [] if required_if_tests in {"", "NONE"} else [required_if_tests]
    if required_if_tests is not None and list(required_if_tests) != _collect_normalized_if_tests(template_after):
        return ReplayResult(False, None, None, "PATCH_DYNAMIC_IF_TEST_DRIFT")

    required_if_bodies = replay_contract.get("requiredIfBodyShape")
    if isinstance(required_if_bodies, str):
        required_if_bodies = [] if required_if_bodies in {"", "NONE"} else [required_if_bodies]
    if required_if_bodies is not None and list(required_if_bodies) != _collect_normalized_if_bodies(template_after):
        return ReplayResult(False, None, None, "PATCH_DYNAMIC_IF_BODY_DRIFT")

    artifact_result: PatchArtifactResult | None = None
    if str(patch_text or "").strip():
        artifact_result = artifact or materialize_patch_artifact(sql_unit=sql_unit, patch_text=patch_text)
        if artifact_result.applied is not True:
            return ReplayResult(False, None, None, artifact_result.reason_code or "PATCH_ARTIFACT_INVALID")
        if artifact_result.xml_parse_ok is not True:
            return ReplayResult(False, None, None, artifact_result.reason_code or "PATCH_XML_PARSE_FAILED")

    rendered_sql: str | None
    if artifact_result is not None:
        if replay_mode in _FRAGMENT_REPLAY_MODES and fragment_op is not None:
            rendered_sql = _render_fragment_sql_from_artifact(
                artifact_result,
                sql_unit,
                fragment_op.get("targetRef"),
            )
        else:
            rendered_sql = _render_statement_sql_from_artifact(artifact_result, sql_unit)
    elif replay_mode in _FRAGMENT_REPLAY_MODES and fragment_op is not None:
        rendered_sql = _render_fragment_sql(
            template_after,
            sql_unit,
            fragment_catalog,
            fragment_op.get("targetRef"),
        )
    else:
        rendered_sql = _render_statement_sql(template_after, sql_unit, fragment_catalog)

    normalized_rendered_sql = _normalize_replay_sql(rendered_sql or "")
    normalized_target_sql = _normalize_replay_sql(str(patch_target.get("targetSql") or ""))
    if normalized_rendered_sql != normalized_target_sql:
        return ReplayResult(False, rendered_sql, normalized_rendered_sql, "PATCH_TARGET_DRIFT")
    return ReplayResult(True, rendered_sql, normalized_rendered_sql, None)
