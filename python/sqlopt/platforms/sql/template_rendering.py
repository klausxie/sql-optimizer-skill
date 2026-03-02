from __future__ import annotations

import copy
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


def normalize_sql_text(text: str) -> str:
    return " ".join(str(text or "").split())


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def qualify_ref(namespace: str, refid: str | None) -> str:
    ref = str(refid or "").strip()
    if not ref:
        return ""
    if "." in ref:
        return ref
    return f"{namespace}.{ref}" if namespace else ref


def fragment_key(xml_path: Path, display_ref: str) -> str:
    return f"{xml_path.resolve()}::{display_ref}"


def lookup_fragment_row(
    fragment_catalog: dict[str, dict[str, Any]],
    xml_path: Path,
    display_ref: str,
) -> tuple[str, dict[str, Any] | None]:
    resolved_key = fragment_key(xml_path, display_ref)
    row = fragment_catalog.get(resolved_key)
    if row is not None:
        return resolved_key, row
    raw_key = f"{xml_path}::{display_ref}"
    row = fragment_catalog.get(raw_key)
    if row is not None:
        return raw_key, row
    return resolved_key, None


def substitute_props(text: str, context: dict[str, str]) -> str:
    if not context:
        return text
    out = str(text or "")
    for key, value in context.items():
        out = out.replace("${" + key + "}", value)
    return out


def property_context(node: ET.Element, base_context: dict[str, str] | None = None) -> dict[str, str]:
    ctx = dict(base_context or {})
    for child in list(node):
        if local_name(str(child.tag)).lower() != "property":
            continue
        name = str(child.attrib.get("name") or "").strip()
        value = str(child.attrib.get("value") or "").strip()
        if name:
            ctx[name] = substitute_props(value, ctx)
    return ctx


def desubstitute_props(text: str, properties: list[dict[str, Any]]) -> str:
    out = str(text or "")
    ordered = sorted(
        [row for row in properties if str(row.get("valueNormalized") or "").strip() and str(row.get("name") or "").strip()],
        key=lambda row: len(str(row.get("valueNormalized") or "")),
        reverse=True,
    )
    for row in ordered:
        value = str(row.get("valueNormalized") or "")
        name = str(row.get("name") or "")
        out = out.replace(value, "${" + name + "}")
    return out


def collect_fragments(root: ET.Element, namespace: str, xml_path: Path) -> dict[str, ET.Element]:
    fragments: dict[str, ET.Element] = {}
    for node in root:
        if local_name(str(node.tag)).lower() != "sql":
            continue
        display_ref = qualify_ref(namespace, node.attrib.get("id"))
        if display_ref:
            fragments[fragment_key(xml_path, display_ref)] = node
    return fragments


def render_logical_text(
    node: ET.Element,
    namespace: str,
    xml_path: Path,
    fragments: dict[str, ET.Element],
    context: dict[str, str] | None = None,
    stack: set[str] | None = None,
) -> str:
    stack = set() if stack is None else set(stack)
    ctx = dict(context or {})
    parts: list[str] = []
    if node.text:
        parts.append(substitute_props(node.text, ctx))
    for child in list(node):
        tag = local_name(str(child.tag)).lower()
        if tag == "include":
            display_ref = qualify_ref(namespace, child.attrib.get("refid"))
            key = fragment_key(xml_path, display_ref) if display_ref else ""
            target = fragments.get(key)
            if key and target is not None and key not in stack:
                next_stack = set(stack)
                next_stack.add(key)
                include_ctx = property_context(child, ctx)
                parts.append(render_logical_text(target, namespace, xml_path, fragments, include_ctx, next_stack))
        else:
            parts.append(render_logical_text(child, namespace, xml_path, fragments, ctx, stack))
        if child.tail:
            parts.append(substitute_props(child.tail, ctx))
    return "".join(parts)


def find_statement_node(root: ET.Element, statement_id: str) -> ET.Element | None:
    for node in root:
        if local_name(str(node.tag)).lower() not in {"select", "update", "delete", "insert"}:
            continue
        if str(node.attrib.get("id") or "").strip() == statement_id:
            return node
    return None


def non_include_dynamic(node: ET.Element) -> bool:
    dynamic_tags = {"foreach", "if", "choose", "where", "trim", "set", "bind"}
    for child in list(node):
        if local_name(str(child.tag)).lower() in dynamic_tags:
            return True
    return False


def serialize_without_tail(node: ET.Element) -> str:
    clone = copy.deepcopy(node)
    clone.tail = None
    return ET.tostring(clone, encoding="unicode").strip()


def render_template_body_sql(body: str, namespace: str, xml_path: Path, fragments: dict[str, ET.Element]) -> str | None:
    try:
        wrapper = ET.fromstring(f"<root>{body}</root>")
    except ET.ParseError:
        return None
    return normalize_sql_text(render_logical_text(wrapper, namespace, xml_path, fragments))


def escape_xml_text(text: str) -> str:
    return escape(str(text or ""), {"'": "&apos;", '"': "&quot;"})


def render_fragment_body_sql(
    body: str,
    namespace: str,
    xml_path: Path,
    fragment_catalog: dict[str, dict[str, Any]],
    context: dict[str, str] | None = None,
    stack: set[str] | None = None,
) -> str | None:
    try:
        wrapper = ET.fromstring(f"<root>{body}</root>")
    except ET.ParseError:
        return None
    stack = set() if stack is None else set(stack)
    ctx = dict(context or {})
    parts: list[str] = []
    if wrapper.text:
        parts.append(substitute_props(wrapper.text, ctx))
    for child in list(wrapper):
        tag = local_name(str(child.tag)).lower()
        if tag == "include":
            display_ref = qualify_ref(namespace, child.attrib.get("refid"))
            key, fragment = lookup_fragment_row(fragment_catalog, xml_path, display_ref) if display_ref else ("", None)
            if key and fragment is not None and key not in stack:
                next_stack = set(stack)
                next_stack.add(key)
                nested_ctx = property_context(child, ctx)
                nested_namespace = str(fragment.get("namespace") or namespace)
                nested_xml_path = Path(str(fragment.get("xmlPath") or xml_path))
                rendered = render_fragment_body_sql(
                    str(fragment.get("templateSql") or ""),
                    nested_namespace,
                    nested_xml_path,
                    fragment_catalog,
                    nested_ctx,
                    next_stack,
                )
                if rendered is None:
                    return None
                parts.append(rendered)
        else:
            rendered = render_fragment_body_sql(
                ET.tostring(child, encoding="unicode"),
                namespace,
                xml_path,
                fragment_catalog,
                ctx,
                stack,
            )
            if rendered is None:
                return None
            parts.append(rendered)
        if child.tail:
            parts.append(substitute_props(child.tail, ctx))
    return normalize_sql_text("".join(parts))


def fragment_is_static_include_safe(
    fragment: dict[str, Any],
    fragment_catalog: dict[str, dict[str, Any]],
    stack: set[str] | None = None,
) -> bool:
    features = {str(x) for x in (fragment.get("dynamicFeatures") or []) if str(x).strip()}
    if features - {"INCLUDE"}:
        return False
    key = str(fragment.get("fragmentKey") or "").strip()
    stack = set() if stack is None else set(stack)
    if key:
        if key in stack:
            return False
        stack = set(stack)
        stack.add(key)
    for binding in fragment.get("includeBindings") or []:
        if not isinstance(binding, dict):
            return False
        nested_ref = str(binding.get("ref") or "").strip()
        nested = fragment_catalog.get(nested_ref)
        if not nested:
            return False
        if not fragment_is_static_include_safe(nested, fragment_catalog, stack):
            return False
    return True
