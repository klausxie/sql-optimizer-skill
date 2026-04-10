from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET
from typing import Any

from .template_rendering import local_name, normalize_sql_text


def _inner_template(node: ET.Element) -> str:
    parts: list[str] = []
    if node.text:
        parts.append(node.text)
    for child in list(node):
        parts.append(ET.tostring(child, encoding="unicode"))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts).strip()


def _set_inner_template(node: ET.Element, template: str) -> None:
    wrapper = ET.fromstring(f"<root>{template}</root>")
    for child in list(node):
        node.remove(child)
    node.text = wrapper.text
    for child in list(wrapper):
        node.append(copy.deepcopy(child))


def locate_choose_branch_surface(template_sql: str, original_sql: str) -> dict[str, Any] | None:
    try:
        wrapper = ET.fromstring(f"<root>{template_sql}</root>")
    except ET.ParseError:
        return None

    where_nodes = [child for child in list(wrapper) if local_name(str(child.tag)).lower() == "where"]
    if len(where_nodes) != 1:
        return None
    where_node = where_nodes[0]
    where_children = [child for child in list(where_node) if child.tag is not None]
    if len(where_children) != 1 or local_name(str(where_children[0].tag)).lower() != "choose":
        return None
    choose_node = where_children[0]

    branches = [child for child in list(choose_node) if local_name(str(child.tag)).lower() in {"when", "otherwise"}]
    if not branches or len(branches) != len(list(choose_node)):
        return None

    normalized_original = normalize_sql_text(original_sql)
    matched: list[tuple[int, ET.Element, str]] = []
    for idx, branch in enumerate(branches):
        body = normalize_sql_text(_inner_template(branch))
        if body and body in normalized_original:
            matched.append((idx, branch, body))
    if len(matched) != 1:
        return None

    branch_ordinal, branch_node, before_template_sql = matched[0]
    branch_tag = local_name(str(branch_node.tag)).upper()
    target_anchor: dict[str, Any] = {
        "surfaceType": "CHOOSE_BRANCH_BODY",
        "chooseOrdinal": 0,
        "branchKind": branch_tag,
        "branchOrdinal": branch_ordinal,
        "whereEnvelopeRequired": True,
    }
    if branch_tag == "WHEN":
        target_anchor["branchTestFingerprint"] = normalize_sql_text(str(branch_node.attrib.get("test") or ""))

    return {
        "targetSurface": "CHOOSE_BRANCH_BODY",
        "targetAnchor": target_anchor,
        "beforeTemplate": _inner_template(branch_node),
        "beforeBodySql": before_template_sql,
        "siblingBranchCount": len(branches),
    }


def replace_choose_branch_body_template(
    template_sql: str,
    *,
    choose_ordinal: int,
    branch_ordinal: int,
    after_template: str,
) -> str | None:
    try:
        wrapper = ET.fromstring(f"<root>{template_sql}</root>")
    except ET.ParseError:
        return None

    choose_nodes = [node for node in wrapper.iter() if local_name(str(node.tag)).lower() == "choose"]
    if choose_ordinal < 0 or choose_ordinal >= len(choose_nodes):
        return None
    choose_node = choose_nodes[choose_ordinal]
    branches = [child for child in list(choose_node) if local_name(str(child.tag)).lower() in {"when", "otherwise"}]
    if branch_ordinal < 0 or branch_ordinal >= len(branches):
        return None
    _set_inner_template(branches[branch_ordinal], after_template)
    parts: list[str] = []
    if wrapper.text:
        parts.append(wrapper.text)
    for child in list(wrapper):
        parts.append(ET.tostring(child, encoding="unicode"))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts).strip()


def inspect_choose_branch_template(template_sql: str, target_anchor: dict[str, Any]) -> dict[str, Any] | None:
    try:
        wrapper = ET.fromstring(f"<root>{template_sql}</root>")
    except ET.ParseError:
        return None

    where_nodes = [child for child in list(wrapper) if local_name(str(child.tag)).lower() == "where"]
    if len(where_nodes) != 1:
        return None
    choose_nodes = [node for node in wrapper.iter() if local_name(str(node.tag)).lower() == "choose"]
    choose_ordinal = int(target_anchor.get("chooseOrdinal") or 0)
    branch_ordinal = int(target_anchor.get("branchOrdinal") or 0)
    if choose_ordinal < 0 or choose_ordinal >= len(choose_nodes):
        return None
    choose_node = choose_nodes[choose_ordinal]
    branches = [child for child in list(choose_node) if local_name(str(child.tag)).lower() in {"when", "otherwise"}]
    if branch_ordinal < 0 or branch_ordinal >= len(branches):
        return None
    branch_node = branches[branch_ordinal]
    branch_kind = local_name(str(branch_node.tag)).upper()
    expected_kind = str(target_anchor.get("branchKind") or "").strip().upper()
    if expected_kind and branch_kind != expected_kind:
        return None
    test_fingerprint = normalize_sql_text(str(branch_node.attrib.get("test") or ""))
    expected_test = normalize_sql_text(str(target_anchor.get("branchTestFingerprint") or ""))
    if expected_test and test_fingerprint != expected_test:
        return None
    return {
        "targetBranchKind": branch_kind,
        "targetBranchTestFingerprint": test_fingerprint,
        "branchCount": len(branches),
        "siblingBranchFingerprints": [
            {
                "branchKind": local_name(str(node.tag)).upper(),
                "bodyFingerprint": normalize_sql_text(_inner_template(node)),
                "testFingerprint": normalize_sql_text(str(node.attrib.get("test") or "")),
            }
            for idx, node in enumerate(branches)
            if idx != branch_ordinal
        ],
        "whereEnvelopePresent": True,
        "outerChooseCount": len(choose_nodes),
        "outerUnsupportedTagsAbsent": True,
    }


def collapse_choose_to_branch_template(template_sql: str, *, choose_ordinal: int, branch_ordinal: int) -> str | None:
    try:
        wrapper = ET.fromstring(f"<root>{template_sql}</root>")
    except ET.ParseError:
        return None

    choose_nodes = [node for node in wrapper.iter() if local_name(str(node.tag)).lower() == "choose"]
    if choose_ordinal < 0 or choose_ordinal >= len(choose_nodes):
        return None
    choose_node = choose_nodes[choose_ordinal]
    branches = [child for child in list(choose_node) if local_name(str(child.tag)).lower() in {"when", "otherwise"}]
    if branch_ordinal < 0 or branch_ordinal >= len(branches):
        return None
    selected_branch = branches[branch_ordinal]
    choose_node.tag = "fragment"
    _set_inner_template(choose_node, _inner_template(selected_branch))
    parts: list[str] = []
    if wrapper.text:
        parts.append(wrapper.text)
    for child in list(wrapper):
        if local_name(str(child.tag)).lower() == "fragment":
            parts.append(_inner_template(child))
        else:
            parts.append(ET.tostring(child, encoding="unicode"))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts).strip()


_CHOOSE_BLOCK_RE = re.compile(r"<choose\b[^>]*>(?P<body>.*?)</choose>", flags=re.IGNORECASE | re.DOTALL)
_CHOOSE_BRANCH_RE = re.compile(
    r"<(?P<tag>when|otherwise)\b[^>]*>(?P<body>.*?)</(?P=tag)>",
    flags=re.IGNORECASE | re.DOTALL,
)


def locate_choose_branch_body_range(xml_text: str, target_anchor: dict[str, Any]) -> dict[str, int] | None:
    choose_ordinal = int(target_anchor.get("chooseOrdinal") or 0)
    branch_ordinal = int(target_anchor.get("branchOrdinal") or 0)

    choose_matches = list(_CHOOSE_BLOCK_RE.finditer(xml_text))
    if choose_ordinal < 0 or choose_ordinal >= len(choose_matches):
        return None
    choose_match = choose_matches[choose_ordinal]
    choose_body = choose_match.group("body")
    branch_matches = list(_CHOOSE_BRANCH_RE.finditer(choose_body))
    if branch_ordinal < 0 or branch_ordinal >= len(branch_matches):
        return None
    branch_match = branch_matches[branch_ordinal]
    body_start = choose_match.start("body") + branch_match.start("body")
    body_end = choose_match.start("body") + branch_match.end("body")
    return {"startOffset": body_start, "endOffset": body_end}
