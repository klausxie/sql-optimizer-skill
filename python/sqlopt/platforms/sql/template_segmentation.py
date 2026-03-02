from __future__ import annotations

from pathlib import Path
from typing import Any

from .template_rendering import (
    desubstitute_props,
    escape_xml_text,
    local_name,
    lookup_fragment_row,
    normalize_sql_text,
    property_context,
    render_fragment_body_sql,
    qualify_ref,
    serialize_without_tail,
)


def split_by_anchors(text: str, anchors: list[str]) -> list[str] | None:
    pos = 0
    parts: list[str] = []
    for anchor in anchors:
        idx = text.find(anchor, pos)
        if idx < 0:
            return None
        parts.append(text[pos:idx].strip())
        pos = idx + len(anchor)
    parts.append(text[pos:].strip())
    return parts


def extract_repeated_replacement(rewritten: str, static_segments: list[str]) -> str | None:
    if not static_segments:
        return None
    pos = 0
    replacements: list[str] = []
    for idx, segment in enumerate(static_segments):
        seg = str(segment or "")
        if seg:
            if not rewritten.startswith(seg, pos):
                return None
            pos += len(seg)
        if idx >= len(static_segments) - 1:
            continue
        next_seg = str(static_segments[idx + 1] or "")
        if next_seg:
            next_idx = rewritten.find(next_seg, pos)
            if next_idx < 0:
                return None
            replacements.append(rewritten[pos:next_idx].strip())
            pos = next_idx
        else:
            if idx + 1 != len(static_segments) - 1:
                return None
            replacements.append(rewritten[pos:].strip())
            pos = len(rewritten)
    if pos != len(rewritten):
        return None
    if not replacements:
        return ""
    first = replacements[0]
    if any(rep != first for rep in replacements[1:]):
        return None
    return first


def build_fragment_template_with_preserved_includes(
    template_sql: str,
    rendered_sql: str,
    namespace: str,
    xml_path: Path,
    fragment_catalog: dict[str, dict[str, Any]],
    *,
    binding_props: list[dict[str, Any]] | None = None,
    base_context: dict[str, str] | None = None,
) -> tuple[str | None, bool]:
    import xml.etree.ElementTree as ET

    try:
        wrapper = ET.fromstring(f"<root>{template_sql}</root>")
    except ET.ParseError:
        return None, False
    include_tags: list[str] = []
    include_anchors: list[str] = []
    for child in list(wrapper):
        if local_name(str(child.tag)).lower() != "include":
            return None, False
        display_ref = qualify_ref(namespace, child.attrib.get("refid"))
        if not display_ref:
            return None, False
        key, nested = lookup_fragment_row(fragment_catalog, xml_path, display_ref)
        if nested is None:
            return None, False
        include_tag = serialize_without_tail(child)
        include_anchor = render_fragment_body_sql(
            str(nested.get("templateSql") or ""),
            str(nested.get("namespace") or namespace),
            Path(str(nested.get("xmlPath") or xml_path)),
            fragment_catalog,
            property_context(child, base_context),
            {key},
        )
        if not include_tag or not include_anchor:
            return None, False
        include_tags.append(include_tag)
        include_anchors.append(normalize_sql_text(include_anchor))
    normalized_rendered = normalize_sql_text(rendered_sql)
    if not include_tags:
        rebuilt = normalized_rendered
        if binding_props:
            rebuilt = desubstitute_props(rebuilt, binding_props)
        return escape_xml_text(rebuilt), True
    rewritten_parts = split_by_anchors(normalized_rendered, include_anchors)
    if rewritten_parts is None:
        return None, False
    rebuilt_parts: list[str] = []
    for idx, tag in enumerate(include_tags):
        part = rewritten_parts[idx]
        if part:
            if binding_props:
                part = desubstitute_props(part, binding_props)
            rebuilt_parts.append(escape_xml_text(part))
        rebuilt_parts.append(tag)
    if rewritten_parts[-1]:
        tail = rewritten_parts[-1]
        if binding_props:
            tail = desubstitute_props(tail, binding_props)
        rebuilt_parts.append(escape_xml_text(tail))
    return " ".join(part for part in rebuilt_parts if part).strip(), True
