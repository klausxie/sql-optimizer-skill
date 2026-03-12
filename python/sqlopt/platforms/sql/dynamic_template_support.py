from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .canonicalization_support import cleanup_redundant_from_alias, cleanup_redundant_select_aliases
from .template_rendering import collect_fragments, normalize_sql_text, render_template_body_sql

_OUTER_WRAPPER_PREFIX_RE = re.compile(
    r"^\s*select\s+(?P<outer_select>.+?)\s+from\s*\(",
    flags=re.IGNORECASE | re.DOTALL,
)
_INNER_SELECT_RE = re.compile(
    r"^\s*select\s+(?P<inner_select>.+?)\s+(?P<inner_from>from\b.+)$",
    flags=re.IGNORECASE | re.DOTALL,
)
_OUTER_ALIAS_SUFFIX_RE = re.compile(
    r"^\s*(?P<alias>[a-z_][a-z0-9_]*)?\s*(?P<outer_suffix>(?:where\b|order\s+by\b|limit\b|offset\b|fetch\b).*)?$",
    flags=re.IGNORECASE | re.DOTALL,
)


def find_matching_paren(text: str, start_idx: int) -> int:
    depth = 0
    for idx in range(start_idx, len(text)):
        char = text[idx]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return idx
    return -1


def parse_select_wrapper_template(template_sql: str) -> tuple[str | None, str | None, str | None]:
    normalized = normalize_sql_text(template_sql)
    prefix_match = _OUTER_WRAPPER_PREFIX_RE.match(normalized)
    if prefix_match is None:
        return None, None, None
    outer_select = normalize_sql_text(prefix_match.group("outer_select"))
    open_paren_idx = prefix_match.end() - 1
    close_paren_idx = find_matching_paren(normalized, open_paren_idx)
    if close_paren_idx < 0:
        return None, None, None
    inner_sql = normalize_sql_text(normalized[open_paren_idx + 1 : close_paren_idx])
    inner_match = _INNER_SELECT_RE.match(inner_sql)
    if inner_match is None:
        return None, None, None
    inner_select = normalize_sql_text(inner_match.group("inner_select"))
    inner_from = normalize_sql_text(inner_match.group("inner_from"))
    suffix_match = _OUTER_ALIAS_SUFFIX_RE.match(normalized[close_paren_idx + 1 :])
    outer_suffix = normalize_sql_text((suffix_match.group("outer_suffix") if suffix_match else "") or "")
    flattened_from = normalize_sql_text(f"{inner_from} {outer_suffix}").strip() or inner_from
    return outer_select or None, inner_select or None, flattened_from or None


def render_flattened_select_template(select_list: str, from_suffix: str) -> str:
    return normalize_sql_text(f"SELECT {normalize_sql_text(select_list)} {normalize_sql_text(from_suffix)}")


def parse_direct_select_template(template_sql: str) -> tuple[str | None, str | None]:
    normalized = normalize_sql_text(template_sql)
    inner_match = _INNER_SELECT_RE.match(normalized)
    if inner_match is None:
        return None, None
    select_list = normalize_sql_text(inner_match.group("inner_select"))
    from_suffix = normalize_sql_text(inner_match.group("inner_from"))
    return select_list or None, from_suffix or None


def render_direct_select_template(select_list: str, from_suffix: str) -> str:
    return normalize_sql_text(f"SELECT {normalize_sql_text(select_list)} {normalize_sql_text(from_suffix)}")


def render_select_alias_cleanup_template(template_sql: str) -> tuple[str | None, bool]:
    select_list, from_suffix = parse_direct_select_template(template_sql)
    if select_list is None or from_suffix is None:
        return None, False
    cleaned_select_list, changed = cleanup_redundant_select_aliases(select_list)
    if not changed:
        return None, False
    return render_direct_select_template(cleaned_select_list, from_suffix), True


def render_from_alias_cleanup_template(template_sql: str) -> tuple[str | None, bool]:
    select_list, from_suffix = parse_direct_select_template(template_sql)
    if select_list is None or from_suffix is None:
        return None, False
    cleaned_from_suffix, changed = cleanup_redundant_from_alias(from_suffix, select_text=select_list)
    if not changed:
        return None, False
    return render_direct_select_template(select_list, cleaned_from_suffix), True


def replay_template_sql(rebuilt_template: str, namespace: str, xml_path: Path) -> str | None:
    statement_xml_path = Path(xml_path)
    if not statement_xml_path.exists():
        return None
    try:
        root = ET.parse(statement_xml_path).getroot()
    except Exception:
        return None
    fragments = collect_fragments(root, namespace, statement_xml_path)
    return render_template_body_sql(rebuilt_template, namespace, statement_xml_path, fragments)
