from __future__ import annotations

from .models import PatchFamilySpec
from .specs.distinct_from_alias_cleanup import DISTINCT_FROM_ALIAS_CLEANUP_SPEC
from .specs.dynamic_count_wrapper_collapse import DYNAMIC_COUNT_WRAPPER_COLLAPSE_SPEC
from .specs.dynamic_filter_from_alias_cleanup import DYNAMIC_FILTER_FROM_ALIAS_CLEANUP_SPEC
from .specs.dynamic_filter_select_list_cleanup import DYNAMIC_FILTER_SELECT_LIST_CLEANUP_SPEC
from .specs.dynamic_filter_wrapper_collapse import DYNAMIC_FILTER_WRAPPER_COLLAPSE_SPEC
from .specs.frozen_baselines import FROZEN_BASELINE_SPECS
from .specs.group_by_from_alias_cleanup import GROUP_BY_FROM_ALIAS_CLEANUP_SPEC
from .specs.group_by_having_from_alias_cleanup import GROUP_BY_HAVING_FROM_ALIAS_CLEANUP_SPEC
from .specs.redundant_distinct_wrapper import REDUNDANT_DISTINCT_WRAPPER_SPEC
from .specs.redundant_group_by_wrapper import REDUNDANT_GROUP_BY_WRAPPER_SPEC
from .specs.redundant_having_wrapper import REDUNDANT_HAVING_WRAPPER_SPEC
from .specs.static_alias_projection_cleanup import STATIC_ALIAS_PROJECTION_CLEANUP_SPEC
from .specs.static_cte_inline import STATIC_CTE_INLINE_SPEC
from .specs.static_include_wrapper_collapse import STATIC_INCLUDE_WRAPPER_COLLAPSE_SPEC
from .specs.static_in_list_simplification import STATIC_IN_LIST_SIMPLIFICATION_SPEC
from .specs.static_limit_optimization import STATIC_LIMIT_OPTIMIZATION_SPEC
from .specs.static_order_by_simplification import STATIC_ORDER_BY_SIMPLIFICATION_SPEC
from .specs.static_or_simplification import STATIC_OR_SIMPLIFICATION_SPEC
from .specs.static_statement_rewrite import STATIC_STATEMENT_REWRITE_SPEC
from .specs.static_distinct_on_simplification import STATIC_DISTINCT_ON_SIMPLIFICATION_SPEC
from .specs.static_subquery_wrapper_collapse import STATIC_SUBQUERY_WRAPPER_COLLAPSE_SPEC
from .specs.static_wrapper_collapse import STATIC_WRAPPER_COLLAPSE_SPEC
from .specs.static_boolean_simplification import STATIC_BOOLEAN_SIMPLIFICATION_SPEC
from .specs.static_case_simplification import STATIC_CASE_SIMPLIFICATION_SPEC
from .specs.static_coalesce_simplification import STATIC_COALESCE_SIMPLIFICATION_SPEC
from .specs.static_expression_folding import STATIC_EXPRESSION_FOLDING_SPEC
from .specs.static_null_comparison import STATIC_NULL_COMPARISON_SPEC
from .specs.static_union_collapse import STATIC_UNION_COLLAPSE_SPEC


def _canonicalize_family_id(family: str) -> str:
    return str(family or "").strip().upper()


def _build_patch_family_registry(
    specs: tuple[PatchFamilySpec, ...],
) -> dict[str, PatchFamilySpec]:
    registry: dict[str, PatchFamilySpec] = {}
    for spec in specs:
        canonical_family = _canonicalize_family_id(spec.family)
        if spec.family != canonical_family:
            raise ValueError(f"NON_CANONICAL_PATCH_FAMILY: {canonical_family}")
        if canonical_family in registry:
            raise ValueError(f"DUPLICATE_PATCH_FAMILY: {canonical_family}")
        registry[canonical_family] = spec
    return registry


_REGISTERED_PATCH_FAMILY_SPECS = (
    STATIC_STATEMENT_REWRITE_SPEC,
    STATIC_WRAPPER_COLLAPSE_SPEC,
    STATIC_CTE_INLINE_SPEC,
    STATIC_INCLUDE_WRAPPER_COLLAPSE_SPEC,
    STATIC_ALIAS_PROJECTION_CLEANUP_SPEC,
    STATIC_IN_LIST_SIMPLIFICATION_SPEC,
    STATIC_LIMIT_OPTIMIZATION_SPEC,
    STATIC_ORDER_BY_SIMPLIFICATION_SPEC,
    STATIC_OR_SIMPLIFICATION_SPEC,
    STATIC_DISTINCT_ON_SIMPLIFICATION_SPEC,
    STATIC_SUBQUERY_WRAPPER_COLLAPSE_SPEC,
    STATIC_BOOLEAN_SIMPLIFICATION_SPEC,
    STATIC_CASE_SIMPLIFICATION_SPEC,
    STATIC_COALESCE_SIMPLIFICATION_SPEC,
    STATIC_EXPRESSION_FOLDING_SPEC,
    STATIC_NULL_COMPARISON_SPEC,
    STATIC_UNION_COLLAPSE_SPEC,
    DYNAMIC_COUNT_WRAPPER_COLLAPSE_SPEC,
    DYNAMIC_FILTER_WRAPPER_COLLAPSE_SPEC,
    DYNAMIC_FILTER_SELECT_LIST_CLEANUP_SPEC,
    DYNAMIC_FILTER_FROM_ALIAS_CLEANUP_SPEC,
    REDUNDANT_DISTINCT_WRAPPER_SPEC,
    REDUNDANT_GROUP_BY_WRAPPER_SPEC,
    REDUNDANT_HAVING_WRAPPER_SPEC,
    GROUP_BY_FROM_ALIAS_CLEANUP_SPEC,
    GROUP_BY_HAVING_FROM_ALIAS_CLEANUP_SPEC,
    DISTINCT_FROM_ALIAS_CLEANUP_SPEC,
    *FROZEN_BASELINE_SPECS,
)

_PATCH_FAMILY_REGISTRY = _build_patch_family_registry(_REGISTERED_PATCH_FAMILY_SPECS)


def list_registered_patch_families() -> tuple[PatchFamilySpec, ...]:
    return tuple(_PATCH_FAMILY_REGISTRY[family] for family in sorted(_PATCH_FAMILY_REGISTRY))


def lookup_patch_family_spec(family: str) -> PatchFamilySpec | None:
    return _PATCH_FAMILY_REGISTRY.get(_canonicalize_family_id(family))
