from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .rewrite_facts_models import RewriteFacts, SemanticRewriteFacts, WrapperQueryRewriteFacts
from .template_rendering import (
    fragment_is_static_include_safe,
    normalize_sql_text,
    render_fragment_body_sql,
)

_COUNT_WRAPPER_RE = re.compile(
    r'^\s*select\s+count\s*\(\s*(?P<count_expr>[^)]+)\s*\)\s+from\s*\(\s*<include\b[^>]*refid="(?P<refid>[^"]+)"[^>]*/>\s*\)\s*(?P<alias>[a-z_][a-z0-9_]*)?\s*$',
    flags=re.IGNORECASE | re.DOTALL,
)
_COUNT_SQL_RE = re.compile(
    r"^\s*select\s+count\s*\(\s*(?P<count_expr>[^)]+)\s*\)\s+(?P<from_suffix>from\b.+)$",
    flags=re.IGNORECASE | re.DOTALL,
)
_SELECT_FROM_RE = re.compile(r"^\s*select\s+.+?\s+(?P<from_suffix>from\b.+)$", flags=re.IGNORECASE | re.DOTALL)
_PROHIBITED_WRAPPER_PATTERNS = (
    (r"\bdistinct\b", "DISTINCT_PRESENT"),
    (r"\bgroup\s+by\b", "GROUP_BY_PRESENT"),
    (r"\bhaving\b", "HAVING_PRESENT"),
    (r"\bunion\b", "UNION_PRESENT"),
    (r"\bover\s*\(", "WINDOW_PRESENT"),
    (r"\blimit\b", "LIMIT_PRESENT"),
    (r"\boffset\b", "OFFSET_PRESENT"),
    (r"\bfetch\b", "FETCH_PRESENT"),
)


def _fingerprint_strength(equivalence: dict[str, Any], semantic_equivalence: dict[str, Any]) -> str:
    evidence = dict(semantic_equivalence.get("evidence") or {})
    strength = str(evidence.get("fingerprintStrength") or "").strip().upper()
    if strength:
        return strength
    for row in equivalence.get("evidenceRefObjects") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("source") or "").strip().upper() != "DB_FINGERPRINT":
            continue
        matched = str(row.get("match_strength") or "").strip().upper()
        if matched:
            return matched
    return "NONE"


def _wrapper_template_match(template_sql: str) -> re.Match[str] | None:
    return _COUNT_WRAPPER_RE.match(str(template_sql or "").strip())


def _render_primary_fragment(sql_unit: dict[str, Any], fragment_catalog: dict[str, dict[str, Any]]) -> tuple[str | None, dict[str, Any] | None]:
    target_ref = str(sql_unit.get("primaryFragmentTarget") or "").strip()
    if not target_ref:
        bindings = [row for row in (sql_unit.get("includeBindings") or []) if isinstance(row, dict)]
        if len(bindings) == 1:
            target_ref = str(bindings[0].get("ref") or "").strip()
    if not target_ref:
        return None, None
    fragment = fragment_catalog.get(target_ref)
    if fragment is None:
        return None, None
    rendered = render_fragment_body_sql(
        str(fragment.get("templateSql") or ""),
        str(fragment.get("namespace") or ""),
        Path(str(fragment.get("xmlPath") or "")),
        fragment_catalog,
        None,
        {target_ref},
    )
    return rendered, fragment


def _extract_from_suffix(sql: str) -> str | None:
    match = _SELECT_FROM_RE.match(str(sql or "").strip())
    if not match:
        return None
    suffix = normalize_sql_text(match.group("from_suffix"))
    return suffix or None


def _extract_count_from_suffix(sql: str) -> tuple[str | None, str | None]:
    match = _COUNT_SQL_RE.match(str(sql or "").strip())
    if not match:
        return None, None
    count_expr = normalize_sql_text(match.group("count_expr"))
    from_suffix = normalize_sql_text(match.group("from_suffix"))
    return count_expr or None, from_suffix or None


def _wrapper_blockers(inner_sql: str) -> list[str]:
    normalized = normalize_sql_text(inner_sql)
    blockers: list[str] = []
    for pattern, code in _PROHIBITED_WRAPPER_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            blockers.append(code)
    if " from (" in f" {normalized.lower()}":
        blockers.append("NESTED_FROM_SUBQUERY")
    return blockers


def build_rewrite_facts_model(
    sql_unit: dict[str, Any],
    rewritten_sql: str,
    fragment_catalog: dict[str, dict[str, Any]],
    equivalence: dict[str, Any],
    semantic_equivalence: dict[str, Any],
) -> RewriteFacts:
    original_sql = normalize_sql_text(str(sql_unit.get("sql") or ""))
    rewritten = normalize_sql_text(rewritten_sql)
    template_sql = str(sql_unit.get("templateSql") or "")
    wrapper_match = _wrapper_template_match(template_sql)
    inner_sql, inner_fragment = _render_primary_fragment(sql_unit, fragment_catalog)
    inner_sql_normalized = normalize_sql_text(inner_sql or "")
    inner_from_suffix = _extract_from_suffix(inner_sql_normalized) if inner_sql_normalized else None
    rewritten_count_expr, rewritten_from_suffix = _extract_count_from_suffix(rewritten)
    static_include_tree = bool(inner_fragment) and fragment_is_static_include_safe(inner_fragment, fragment_catalog)
    wrapper_blockers = _wrapper_blockers(inner_sql_normalized) if inner_sql_normalized else ["INNER_SQL_UNAVAILABLE"]
    wrapper_query_collapsible = bool(
        wrapper_match
        and inner_fragment
        and static_include_tree
        and inner_from_suffix
        and not wrapper_blockers
    )
    wrapper_collapse_candidate = bool(
        wrapper_query_collapsible
        and rewritten_from_suffix
        and rewritten_from_suffix == inner_from_suffix
        and rewritten_count_expr in {"1", "*"}
    )
    return RewriteFacts(
        effective_change=original_sql != rewritten,
        dynamic_features=[str(x) for x in (sql_unit.get("dynamicFeatures") or []) if str(x).strip()],
        template_anchor_stable=not bool(
            [x for x in (sql_unit.get("dynamicFeatures") or []) if str(x).strip() and str(x).strip() != "INCLUDE"]
        ),
        semantic=SemanticRewriteFacts(
            status=str(semantic_equivalence.get("status") or "UNCERTAIN").strip().upper(),
            confidence=str(semantic_equivalence.get("confidence") or "LOW").strip().upper(),
            evidence_level=str(semantic_equivalence.get("evidenceLevel") or "STRUCTURE").strip().upper(),
            fingerprint_strength=_fingerprint_strength(equivalence, semantic_equivalence),
            hard_conflicts=[str(code) for code in (semantic_equivalence.get("hardConflicts") or []) if str(code).strip()],
        ),
        wrapper_query=WrapperQueryRewriteFacts(
            present=bool(wrapper_match),
            aggregate="COUNT" if wrapper_match else None,
            static_include_tree=static_include_tree,
            inner_sql=inner_sql_normalized or None,
            inner_from_suffix=inner_from_suffix,
            collapsible=wrapper_query_collapsible,
            collapse_candidate=wrapper_collapse_candidate,
            blockers=wrapper_blockers,
            rewritten_count_expr=rewritten_count_expr,
            rewritten_from_suffix=rewritten_from_suffix,
        ),
    )


def build_rewrite_facts(
    sql_unit: dict[str, Any],
    rewritten_sql: str,
    fragment_catalog: dict[str, dict[str, Any]],
    equivalence: dict[str, Any],
    semantic_equivalence: dict[str, Any],
) -> dict[str, Any]:
    return build_rewrite_facts_model(
        sql_unit,
        rewritten_sql,
        fragment_catalog,
        equivalence,
        semantic_equivalence,
    ).to_dict()
