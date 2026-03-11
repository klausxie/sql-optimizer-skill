from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .materialization_constants import (
    FRAGMENT_TEMPLATE_SAFE_AUTO,
    FRAGMENT_TEMPLATE_SAFE,
    REASON_ANCHOR_ALIGNMENT_FAILED,
    REASON_DYNAMIC_SUBTREE_TOUCHED,
    REASON_FRAGMENT_MATERIALIZATION_DISABLED,
    REASON_FRAGMENT_PROPERTY_CONTEXT_UNSUPPORTED,
    REASON_FRAGMENT_TEMPLATE_REPLAY_MISMATCH,
    REASON_MULTIPLE_FRAGMENT_BINDINGS_MISMATCH,
    REASON_STATIC_FRAGMENT_SAFE,
    REASON_STATIC_FRAGMENT_SAFE_WITH_BINDINGS,
    REASON_STATEMENT_INCLUDE_SAFE,
    REASON_STATEMENT_TEMPLATE_REPLAY_MISMATCH,
    STATEMENT_SQL,
    STATEMENT_TEMPLATE_SAFE,
    UNMATERIALIZABLE,
)
from .rewrite_target_inference import infer_rewrite_target
from .template_rendering import (
    collect_fragments,
    escape_xml_text,
    find_statement_node,
    fragment_is_static_include_safe,
    fragment_key,
    non_include_dynamic,
    normalize_sql_text,
    property_context,
    render_fragment_body_sql,
    render_logical_text,
    render_template_body_sql,
    serialize_without_tail,
)
from .template_segmentation import (
    build_fragment_template_with_preserved_includes,
    extract_repeated_replacement,
    split_by_anchors,
)


def _unmaterializable(
    *,
    target_type: str | None,
    target_ref: str | None,
    reason_code: str,
    reason_message: str,
    feature_flag_applied: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return (
        {
            "mode": UNMATERIALIZABLE,
            "targetType": target_type,
            "targetRef": target_ref,
            "reasonCode": reason_code,
            "reasonMessage": reason_message,
            "replayVerified": False,
            "featureFlagApplied": feature_flag_applied,
        },
        [],
    )


def _statement_template_result(statement_key: str, target_ref: str, template_sql: str, after_template: str, include_tags: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return (
        {
            "mode": STATEMENT_TEMPLATE_SAFE,
            "targetType": "STATEMENT",
            "targetRef": target_ref or statement_key,
            "reasonCode": REASON_STATEMENT_INCLUDE_SAFE,
            "reasonMessage": "statement template can preserve include anchors",
            "replayVerified": True,
            "featureFlagApplied": False,
        },
        [
            {
                "op": "replace_statement_body",
                "targetRef": target_ref or statement_key,
                "beforeTemplate": template_sql,
                "afterTemplate": after_template,
                "preservedAnchors": include_tags,
                "safetyChecks": {"anchorCount": len(include_tags)},
            }
        ],
    )


def _fragment_template_result(target_ref: str, before_template: str, after_template: str, *, binding_props: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    reason_code = REASON_STATIC_FRAGMENT_SAFE_WITH_BINDINGS if binding_props else REASON_STATIC_FRAGMENT_SAFE
    reason_message = (
        "static fragment can be rewritten safely with include property bindings"
        if binding_props
        else "static fragment can be rewritten safely"
    )
    return (
        {
            "mode": FRAGMENT_TEMPLATE_SAFE,
            "targetType": "SQL_FRAGMENT",
            "targetRef": target_ref,
            "reasonCode": reason_code,
            "reasonMessage": reason_message,
            "replayVerified": True,
            "featureFlagApplied": False,
        },
        [
            {
                "op": "replace_fragment_body",
                "targetRef": target_ref,
                "beforeTemplate": before_template,
                "afterTemplate": after_template,
                "preservedAnchors": [],
                "safetyChecks": {"anchorCount": 0},
            }
        ],
    )


def _fragment_template_auto_result(materialization: dict[str, Any]) -> dict[str, Any]:
    out = dict(materialization)
    out["mode"] = FRAGMENT_TEMPLATE_SAFE_AUTO
    out["featureFlagApplied"] = False
    out["reasonMessage"] = "include-only static fragment auto materialized without feature flag"
    return out


def _materialize_statement_template(
    sql_unit: dict[str, Any],
    rewritten_sql: str,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    xml_path = Path(str(sql_unit.get("xmlPath") or ""))
    namespace = str(sql_unit.get("namespace") or "").strip()
    statement_id = str(sql_unit.get("statementId") or (sql_unit.get("locators") or {}).get("statementId") or "").strip()
    statement_key = str(sql_unit.get("sqlKey") or "").split("#", 1)[0]
    template_sql = str(sql_unit.get("templateSql") or "")
    rewritten = normalize_sql_text(rewritten_sql)
    if not xml_path.exists() or not statement_id or not template_sql:
        return None, []
    try:
        root = ET.parse(xml_path).getroot()
    except Exception:
        return None, []
    statement_node = find_statement_node(root, statement_id)
    if statement_node is None or non_include_dynamic(statement_node):
        return None, []
    fragments = collect_fragments(root, namespace, xml_path)
    include_tags: list[str] = []
    include_anchors: list[str] = []
    for child in list(statement_node):
        if child is None or child.tag is None:
            return None, []
        if str(child.tag).rsplit("}", 1)[-1].lower() != "include":
            return None, []
        display_ref = str(child.attrib.get("refid") or "").strip()
        if not display_ref:
            return None, []
        key = fragment_key(xml_path, f"{namespace}.{display_ref}" if "." not in display_ref and namespace else display_ref)
        target = fragments.get(key)
        if target is None:
            return None, []
        include_ctx = property_context(child)
        include_tag = serialize_without_tail(child)
        include_anchor = normalize_sql_text(render_logical_text(target, namespace, xml_path, fragments, include_ctx, {key}))
        if not include_tag or not include_anchor:
            return None, []
        include_tags.append(include_tag)
        include_anchors.append(include_anchor)
    if not include_tags:
        return None, []
    rewritten_parts = split_by_anchors(rewritten, include_anchors)
    if rewritten_parts is None:
        return None, []
    rebuilt_parts: list[str] = []
    for idx, tag in enumerate(include_tags):
        if rewritten_parts[idx]:
            rebuilt_parts.append(escape_xml_text(rewritten_parts[idx]))
        rebuilt_parts.append(tag)
    if rewritten_parts[-1]:
        rebuilt_parts.append(escape_xml_text(rewritten_parts[-1]))
    after_template = " ".join(part for part in rebuilt_parts if part).strip()
    if not after_template:
        return None, []
    replayed = render_template_body_sql(after_template, namespace, xml_path, fragments)
    if replayed != rewritten:
        return _unmaterializable(
            target_type="STATEMENT",
            target_ref=statement_key,
            reason_code=REASON_STATEMENT_TEMPLATE_REPLAY_MISMATCH,
            reason_message="statement template replay does not match rewritten sql",
        )
    return _statement_template_result(statement_key, statement_key, template_sql, after_template, include_tags)


def _materialize_static_fragment(
    sql_unit: dict[str, Any],
    rewritten_sql: str,
    fragment_catalog: dict[str, dict[str, Any]],
    inferred: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    target_ref = str(inferred.get("targetRef") or "").strip()
    fragment = fragment_catalog.get(target_ref)
    if not target_ref or not fragment:
        return None, []
    if not fragment_is_static_include_safe(fragment, fragment_catalog):
        return _unmaterializable(
            target_type="SQL_FRAGMENT",
            target_ref=target_ref,
            reason_code=REASON_DYNAMIC_SUBTREE_TOUCHED,
            reason_message="target fragment contains dynamic or nested include content",
        )
    bindings = [row for row in (sql_unit.get("includeBindings") or []) if str(row.get("ref") or "") == target_ref]
    if not bindings:
        return _unmaterializable(
            target_type="SQL_FRAGMENT",
            target_ref=target_ref,
            reason_code=REASON_FRAGMENT_PROPERTY_CONTEXT_UNSUPPORTED,
            reason_message="fragment materialization requires unsupported include property context",
        )
    binding_hashes = {str(row.get("bindingHash") or "") for row in bindings}
    if len(binding_hashes) > 1:
        return _unmaterializable(
            target_type="SQL_FRAGMENT",
            target_ref=target_ref,
            reason_code=REASON_MULTIPLE_FRAGMENT_BINDINGS_MISMATCH,
            reason_message="fragment is referenced with multiple binding contexts",
        )
    binding_props = [row for row in (bindings[0].get("properties") or []) if isinstance(row, dict)]
    original_sql = normalize_sql_text(str(sql_unit.get("sql") or ""))
    rewritten = normalize_sql_text(rewritten_sql)
    context = {
        str(row.get("name") or "").strip(): str(row.get("valueNormalized") or "").strip()
        for row in binding_props
        if str(row.get("name") or "").strip()
    }
    fragment_namespace = str(fragment.get("namespace") or "")
    fragment_xml_path = Path(str(fragment.get("xmlPath") or ""))
    fragment_text = render_fragment_body_sql(
        str(fragment.get("templateSql") or ""),
        fragment_namespace,
        fragment_xml_path,
        fragment_catalog,
        context if binding_props else None,
        {target_ref},
    )
    if not fragment_text:
        return _unmaterializable(
            target_type="SQL_FRAGMENT",
            target_ref=target_ref,
            reason_code=REASON_ANCHOR_ALIGNMENT_FAILED,
            reason_message="fragment template could not be rendered for anchor matching",
        )
    fragment_text = normalize_sql_text(fragment_text)
    original_parts = split_by_anchors(original_sql, [fragment_text] * len(bindings))
    if original_parts is None:
        return _unmaterializable(
            target_type="SQL_FRAGMENT",
            target_ref=target_ref,
            reason_code=REASON_ANCHOR_ALIGNMENT_FAILED,
            reason_message="rewritten sql does not preserve fragment anchor boundaries",
        )
    new_fragment_rendered = extract_repeated_replacement(rewritten, original_parts)
    if new_fragment_rendered is None:
        return _unmaterializable(
            target_type="SQL_FRAGMENT",
            target_ref=target_ref,
            reason_code=REASON_ANCHOR_ALIGNMENT_FAILED,
            reason_message="rewritten sql does not preserve repeated fragment anchor boundaries",
        )
    new_fragment, ok = build_fragment_template_with_preserved_includes(
        str(fragment.get("templateSql") or ""),
        new_fragment_rendered.strip(),
        fragment_namespace,
        fragment_xml_path,
        fragment_catalog,
        binding_props=binding_props,
        base_context=context if binding_props else None,
    )
    if not ok or not new_fragment:
        return _unmaterializable(
            target_type="SQL_FRAGMENT",
            target_ref=target_ref,
            reason_code=REASON_ANCHOR_ALIGNMENT_FAILED,
            reason_message="rewritten sql does not preserve nested fragment anchor boundaries",
        )
    replay_fragment = render_fragment_body_sql(
        new_fragment,
        fragment_namespace,
        fragment_xml_path,
        fragment_catalog,
        context if binding_props else None,
        {target_ref},
    )
    if replay_fragment != normalize_sql_text(new_fragment_rendered.strip()):
        return _unmaterializable(
            target_type="SQL_FRAGMENT",
            target_ref=target_ref,
            reason_code=REASON_FRAGMENT_TEMPLATE_REPLAY_MISMATCH,
            reason_message="fragment template replay does not match rewritten sql",
        )
    return _fragment_template_result(target_ref, str(fragment.get("templateSql") or ""), new_fragment, binding_props=binding_props)


def build_rewrite_materialization(
    sql_unit: dict[str, Any],
    rewritten_sql: str,
    fragment_catalog: dict[str, dict[str, Any]] | None = None,
    *,
    enable_fragment_materialization: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    fragment_catalog = fragment_catalog or {}
    inferred = infer_rewrite_target(sql_unit, rewritten_sql)
    if inferred.get("modeHint") == STATEMENT_SQL:
        return (
            {
                "mode": STATEMENT_SQL,
                "targetType": "STATEMENT",
                "targetRef": inferred.get("targetRef"),
                "reasonCode": inferred.get("reasonCode"),
                "reasonMessage": "static statement patch path",
                "replayVerified": True,
                "featureFlagApplied": False,
            },
            [],
        )

    if inferred.get("modeHint") == "STATEMENT_OR_FRAGMENT_TEMPLATE_CANDIDATE":
        materialization, ops = _materialize_statement_template(sql_unit, rewritten_sql)
        if materialization is not None:
            return materialization, ops
        if not enable_fragment_materialization:
            materialization, ops = _materialize_static_fragment(sql_unit, rewritten_sql, fragment_catalog, inferred)
            if materialization is not None and str(materialization.get("mode") or "") == FRAGMENT_TEMPLATE_SAFE:
                return _fragment_template_auto_result(materialization), ops
            return _unmaterializable(
                target_type="SQL_FRAGMENT",
                target_ref=inferred.get("targetRef"),
                reason_code=REASON_FRAGMENT_MATERIALIZATION_DISABLED,
                reason_message="fragment template materialization is disabled by feature flag",
            )
        materialization, ops = _materialize_static_fragment(sql_unit, rewritten_sql, fragment_catalog, inferred)
        if materialization is not None:
            materialization["featureFlagApplied"] = True
            return materialization, ops
    return _unmaterializable(
        target_type=inferred.get("targetType"),
        target_ref=inferred.get("targetRef"),
        reason_code=str(inferred.get("reasonCode") or ""),
        reason_message="rewrite target cannot be materialized safely",
    )
