from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .aggregation_analysis import analyze_aggregation_query
from .canonicalization_support import cleanup_redundant_from_alias, cleanup_redundant_select_aliases
from .cte_analysis import analyze_simple_inline_cte
from .dynamic_template_support import parse_direct_select_template, parse_select_wrapper_template
from .rewrite_facts_models import (
    AggregationCapabilityProfile,
    AggregationQueryRewriteFacts,
    CteQueryRewriteFacts,
    DynamicTemplateCapabilityProfile,
    DynamicTemplateRewriteFacts,
    RewriteFacts,
    SemanticRewriteFacts,
    WrapperQueryRewriteFacts,
)
from .template_rendering import (
    fragment_is_static_include_safe,
    normalize_sql_text,
    render_fragment_body_sql,
)

_COUNT_WRAPPER_RE = re.compile(
    r'^\s*select\s+count\s*\(\s*(?P<count_expr>[^)]+)\s*\)\s+from\s*\(\s*<include\b[^>]*refid="(?P<refid>[^"]+)"[^>]*/>\s*\)\s*(?P<alias>[a-z_][a-z0-9_]*)?\s*$',
    flags=re.IGNORECASE | re.DOTALL,
)
_DYNAMIC_COUNT_WRAPPER_TEMPLATE_RE = re.compile(
    r"^\s*select\s+count\s*\(\s*(?P<count_expr>[^)]+)\s*\)\s+from\s*\(\s*(?P<inner>.+)\s*\)\s*(?P<alias>[a-z_][a-z0-9_]*)?\s*$",
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


def _dynamic_count_wrapper_template_match(template_sql: str) -> re.Match[str] | None:
    return _DYNAMIC_COUNT_WRAPPER_TEMPLATE_RE.match(str(template_sql or "").strip())


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


def _dynamic_statement_features(sql_unit: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for raw in (sql_unit.get("dynamicFeatures") or []):
        feature = str(raw or "").strip().upper()
        if feature and feature not in out:
            out.append(feature)
    dynamic_trace = dict(sql_unit.get("dynamicTrace") or {})
    for raw in (dynamic_trace.get("statementFeatures") or []):
        feature = str(raw or "").strip().upper()
        if feature and feature not in out:
            out.append(feature)
    return out


def _build_dynamic_template_facts(
    sql_unit: dict[str, Any],
    *,
    statement_features: list[str],
    template_anchor_stable: bool,
) -> DynamicTemplateRewriteFacts:
    if not statement_features:
        return DynamicTemplateRewriteFacts(present=False)

    dynamic_trace = dict(sql_unit.get("dynamicTrace") or {})
    include_fragments = [row for row in (dynamic_trace.get("includeFragments") or []) if isinstance(row, dict)]
    include_bindings = [row for row in (sql_unit.get("includeBindings") or []) if isinstance(row, dict)]
    include_fragment_refs: list[str] = []
    for row in include_fragments:
        ref = str(row.get("ref") or "").strip()
        if ref and ref not in include_fragment_refs:
            include_fragment_refs.append(ref)
    for row in include_bindings:
        ref = str(row.get("ref") or "").strip()
        if ref and ref not in include_fragment_refs:
            include_fragment_refs.append(ref)

    include_dynamic_subtree = any(bool((row or {}).get("dynamicFeatures")) for row in include_fragments)
    include_property_bindings = any(bool((row or {}).get("properties")) for row in include_bindings)
    feature_set = set(statement_features)
    template_sql = str(sql_unit.get("templateSql") or "")
    dynamic_count_wrapper_match = _dynamic_count_wrapper_template_match(template_sql)

    shape_family = "DYNAMIC_TEMPLATE"
    capability_tier = "REVIEW_REQUIRED"
    patch_surface = "STATEMENT_BODY"
    blocker_family = "DYNAMIC_TEMPLATE_COMPLEX"
    blockers = [blocker_family]
    template_preserving_candidate = False
    baseline_family = None

    if "SET" in feature_set:
        shape_family = "SET_SELECTIVE_UPDATE"
        patch_surface = "SET_CLAUSE"
        blocker_family = "DYNAMIC_SET_CLAUSE"
        blockers = [blocker_family]
    elif "FOREACH" in feature_set:
        shape_family = "FOREACH_IN_PREDICATE"
        patch_surface = "WHERE_CLAUSE"
        if "INCLUDE" in feature_set:
            blocker_family = "FOREACH_INCLUDE_PREDICATE"
        elif feature_set & {"IF", "CHOOSE", "TRIM", "BIND"}:
            blocker_family = "FOREACH_COMPLEX_PREDICATE"
        else:
            blocker_family = "FOREACH_COLLECTION_PREDICATE"
        blockers = [blocker_family]
    elif feature_set <= {"IF", "WHERE"} and dynamic_count_wrapper_match is not None:
        shape_family = "IF_GUARDED_COUNT_WRAPPER"
        patch_surface = "STATEMENT_BODY"
        capability_tier = "SAFE_BASELINE"
        blocker_family = None
        blockers = []
        template_preserving_candidate = True
        baseline_family = "DYNAMIC_COUNT_WRAPPER_COLLAPSE"
    elif feature_set & {"IF", "WHERE", "CHOOSE", "TRIM", "BIND"}:
        shape_family = "IF_GUARDED_FILTER_STATEMENT"
        outer_select, inner_select, flattened_from = parse_select_wrapper_template(template_sql)
        direct_select, direct_from = parse_direct_select_template(template_sql)
        if (
            outer_select is not None
            and inner_select is not None
            and flattened_from is not None
            and normalize_sql_text(outer_select) == normalize_sql_text(inner_select)
        ):
            patch_surface = "STATEMENT_BODY"
            capability_tier = "SAFE_BASELINE"
            blocker_family = None
            blockers = []
            template_preserving_candidate = True
            baseline_family = "DYNAMIC_FILTER_WRAPPER_COLLAPSE"
        elif direct_select is not None and direct_from is not None and not (feature_set & {"CHOOSE", "TRIM", "BIND"}):
            _cleaned_select, aliases_changed = cleanup_redundant_select_aliases(direct_select)
            _cleaned_from, from_alias_changed = cleanup_redundant_from_alias(direct_from, select_text=direct_select)
            if aliases_changed:
                patch_surface = "STATEMENT_BODY"
                capability_tier = "SAFE_BASELINE"
                blocker_family = None
                blockers = []
                template_preserving_candidate = True
                baseline_family = "DYNAMIC_FILTER_SELECT_LIST_CLEANUP"
            elif from_alias_changed:
                patch_surface = "STATEMENT_BODY"
                capability_tier = "SAFE_BASELINE"
                blocker_family = None
                blockers = []
                template_preserving_candidate = True
                baseline_family = "DYNAMIC_FILTER_FROM_ALIAS_CLEANUP"
            else:
                patch_surface = "WHERE_CLAUSE"
                if feature_set & {"CHOOSE", "TRIM", "BIND"}:
                    blocker_family = "DYNAMIC_FILTER_UNSAFE_STATEMENT_REWRITE"
                else:
                    blocker_family = "DYNAMIC_FILTER_SUBTREE"
                blockers = [blocker_family]
        else:
            patch_surface = "WHERE_CLAUSE"
            if feature_set & {"CHOOSE", "TRIM", "BIND"}:
                blocker_family = "DYNAMIC_FILTER_UNSAFE_STATEMENT_REWRITE"
            else:
                blocker_family = "DYNAMIC_FILTER_SUBTREE"
            blockers = [blocker_family]
    elif feature_set == {"INCLUDE"} or feature_set <= {"INCLUDE"}:
        patch_surface = "STATEMENT_BODY"
        if include_dynamic_subtree:
            shape_family = "DYNAMIC_INCLUDE_TREE"
            blocker_family = "INCLUDE_DYNAMIC_SUBTREE"
            blockers = [blocker_family]
        elif include_property_bindings:
            shape_family = "STATIC_INCLUDE_ONLY"
            capability_tier = "REVIEW_REQUIRED"
            blocker_family = "STATIC_INCLUDE_FRAGMENT_DEPENDENT"
            blockers = [blocker_family]
        else:
            shape_family = "STATIC_INCLUDE_ONLY"
            capability_tier = "SAFE_BASELINE"
            blocker_family = None
            blockers = []
            template_preserving_candidate = template_anchor_stable
            if re.search(r"\blimit\b", template_sql, flags=re.IGNORECASE) or re.search(r"\boffset\b|\bfetch\b", template_sql, flags=re.IGNORECASE):
                baseline_family = "STATIC_INCLUDE_PAGED_WRAPPER_COLLAPSE"
            else:
                baseline_family = "STATIC_INCLUDE_WRAPPER_COLLAPSE"

    return DynamicTemplateRewriteFacts(
        present=True,
        statement_features=list(statement_features),
        include_fragment_refs=include_fragment_refs,
        include_dynamic_subtree=include_dynamic_subtree,
        include_property_bindings=include_property_bindings,
            capability_profile=DynamicTemplateCapabilityProfile(
                shape_family=shape_family,
                capability_tier=capability_tier,
                patch_surface=patch_surface,
                baseline_family=baseline_family,
                blocker_family=blocker_family,
                template_preserving_candidate=template_preserving_candidate,
                blockers=blockers,
            ),
        )


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
    statement_features = _dynamic_statement_features(sql_unit)
    template_anchor_stable = not bool(
        [x for x in statement_features if str(x).strip() and str(x).strip() != "INCLUDE"]
    )
    wrapper_match = _wrapper_template_match(template_sql)
    inner_sql, inner_fragment = _render_primary_fragment(sql_unit, fragment_catalog)
    inner_sql_normalized = normalize_sql_text(inner_sql or "")
    inner_from_suffix = _extract_from_suffix(inner_sql_normalized) if inner_sql_normalized else None
    rewritten_count_expr, rewritten_from_suffix = _extract_count_from_suffix(rewritten)
    cte_analysis = analyze_simple_inline_cte(original_sql)
    aggregation_analysis = analyze_aggregation_query(original_sql, rewritten)
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
        dynamic_features=list(statement_features),
        template_anchor_stable=template_anchor_stable,
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
        cte_query=CteQueryRewriteFacts(
            present=cte_analysis.present,
            cte_name=cte_analysis.cte_name,
            inner_sql=cte_analysis.inner_sql,
            inner_from_suffix=cte_analysis.inner_from_suffix,
            collapsible=cte_analysis.collapsible,
            inline_candidate=bool(
                cte_analysis.collapsible
                and cte_analysis.inlined_sql
                and normalize_sql_text(cte_analysis.inlined_sql) == rewritten
            ),
            blockers=list(cte_analysis.blockers),
            inlined_sql=cte_analysis.inlined_sql,
        ),
        dynamic_template=_build_dynamic_template_facts(
            sql_unit,
            statement_features=statement_features,
            template_anchor_stable=template_anchor_stable,
        ),
        aggregation_query=AggregationQueryRewriteFacts(
            present=aggregation_analysis.present,
            distinct_present=aggregation_analysis.distinct_present,
            group_by_present=aggregation_analysis.group_by_present,
            having_present=aggregation_analysis.having_present,
            window_present=aggregation_analysis.window_present,
            union_present=aggregation_analysis.union_present,
            distinct_relaxation_candidate=aggregation_analysis.distinct_relaxation_candidate,
            group_by_columns=list(aggregation_analysis.group_by_columns),
            projection_expressions=list(aggregation_analysis.projection_expressions),
            aggregate_functions=list(aggregation_analysis.aggregate_functions),
            having_expression=aggregation_analysis.having_expression,
            order_by_expression=aggregation_analysis.order_by_expression,
            limit_present=aggregation_analysis.limit_present,
            offset_present=aggregation_analysis.offset_present,
            window_functions=list(aggregation_analysis.window_functions),
            union_branches=aggregation_analysis.union_branches,
            blockers=list(aggregation_analysis.blockers),
            capability_profile=AggregationCapabilityProfile(
                shape_family=str((aggregation_analysis.capability_profile or {}).get("shapeFamily") or "NONE"),
                capability_tier=str((aggregation_analysis.capability_profile or {}).get("capabilityTier") or "NONE"),
                constraint_family=str((aggregation_analysis.capability_profile or {}).get("constraintFamily") or "NONE"),
                safe_baseline_family=str((aggregation_analysis.capability_profile or {}).get("safeBaselineFamily") or "").strip() or None,
                wrapper_flatten_candidate=bool((aggregation_analysis.capability_profile or {}).get("wrapperFlattenCandidate")),
                direct_relaxation_candidate=bool((aggregation_analysis.capability_profile or {}).get("directRelaxationCandidate")),
                blockers=[str(x) for x in ((aggregation_analysis.capability_profile or {}).get("blockers") or []) if str(x).strip()],
            ),
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
