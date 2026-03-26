from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..platforms.sql.template_rendering import (
    collect_fragments,
    normalize_sql_text,
    qualify_ref,
    render_fragment_body_sql,
    render_template_body_sql,
)

_PLACEHOLDER_RE = re.compile(r"(?:#|\$)\{[^}]+\}")
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


def replay_patch_target(
    *,
    sql_unit: dict[str, Any],
    patch_target: dict[str, Any],
    fragment_catalog: dict[str, dict[str, Any]],
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

    rendered_sql: str | None
    if replay_mode in _FRAGMENT_REPLAY_MODES and fragment_op is not None:
        rendered_sql = _render_fragment_sql(
            template_after,
            sql_unit,
            fragment_catalog,
            fragment_op.get("targetRef"),
        )
    else:
        rendered_sql = _render_statement_sql(template_after, sql_unit, fragment_catalog)

    normalized_rendered_sql = normalize_sql_text(rendered_sql or "")
    normalized_target_sql = normalize_sql_text(str(patch_target.get("targetSql") or ""))
    if normalized_rendered_sql != normalized_target_sql:
        return ReplayResult(False, rendered_sql, normalized_rendered_sql, "PATCH_TARGET_DRIFT")
    return ReplayResult(True, rendered_sql, normalized_rendered_sql, None)
