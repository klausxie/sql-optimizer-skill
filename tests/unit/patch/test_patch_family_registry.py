from __future__ import annotations

from dataclasses import replace
import inspect

import pytest

from sqlopt.patch_contracts import FROZEN_AUTO_PATCH_FAMILIES
import sqlopt.patch_families.registry as registry_module
import sqlopt.patch_families.specs as specs_package
from sqlopt.patch_families.registry import (
    _build_patch_family_registry,
    list_registered_patch_families,
    lookup_patch_family_spec,
)


def test_registry_exposes_mvp_template_and_new_family() -> None:
    families = {spec.family for spec in list_registered_patch_families()}
    assert "STATIC_INCLUDE_WRAPPER_COLLAPSE" in families
    assert "STATIC_ALIAS_PROJECTION_CLEANUP" in families


def test_static_alias_projection_cleanup_spec_carries_mvp_contract_sections() -> None:
    spec = lookup_patch_family_spec("STATIC_ALIAS_PROJECTION_CLEANUP")
    assert spec is not None
    assert spec.status == "FROZEN_AUTO_PATCH"
    assert spec.acceptance.semantic_required_status == "PASS"
    assert spec.acceptance.semantic_min_confidence == "HIGH"
    assert spec.scope.statement_types == ("SELECT",)
    assert spec.patch_target_policy.selected_patch_strategy == "EXACT_TEMPLATE_EDIT"
    assert spec.replay.required_template_ops == ("replace_statement_body",)
    assert spec.blockers.block_on_expression_alias is True
    assert spec.verification.require_replay_match is True
    assert spec.fixture_obligations.ready_case_required is True
    assert spec.fixture_obligations.blocked_neighbor_required is False


def test_static_include_wrapper_collapse_spec_exposes_acceptance_policy() -> None:
    spec = lookup_patch_family_spec("STATIC_INCLUDE_WRAPPER_COLLAPSE")
    assert spec is not None
    assert spec.status == "FROZEN_AUTO_PATCH"
    assert spec.acceptance.semantic_required_status == "PASS"
    assert spec.acceptance.semantic_min_confidence == "MEDIUM"


def test_patch_contracts_frozen_family_scope_is_registry_derived() -> None:
    registry_families = {
        spec.family
        for spec in list_registered_patch_families()
        if spec.status == "FROZEN_AUTO_PATCH"
    }
    assert FROZEN_AUTO_PATCH_FAMILIES == registry_families
    assert "STATIC_ALIAS_PROJECTION_CLEANUP" in FROZEN_AUTO_PATCH_FAMILIES


def test_dynamic_filter_cleanup_specs_are_explicit_registry_entries() -> None:
    select_spec = lookup_patch_family_spec("DYNAMIC_FILTER_SELECT_LIST_CLEANUP")
    from_spec = lookup_patch_family_spec("DYNAMIC_FILTER_FROM_ALIAS_CLEANUP")

    assert select_spec is not None
    assert from_spec is not None
    assert select_spec.status == "FROZEN_AUTO_PATCH"
    assert from_spec.status == "FROZEN_AUTO_PATCH"
    assert select_spec.acceptance.semantic_min_confidence == "HIGH"
    assert from_spec.acceptance.semantic_min_confidence == "HIGH"
    assert select_spec.patch_target_policy.selected_patch_strategy == "DYNAMIC_STATEMENT_TEMPLATE_EDIT"
    assert from_spec.patch_target_policy.selected_patch_strategy == "DYNAMIC_STATEMENT_TEMPLATE_EDIT"
    assert select_spec.patch_target_policy.materialization_modes == ("STATEMENT_TEMPLATE_SAFE",)
    assert from_spec.patch_target_policy.materialization_modes == ("STATEMENT_TEMPLATE_SAFE",)
    assert select_spec.patch_target_policy.target_type == "STATEMENT"
    assert from_spec.patch_target_policy.target_type == "STATEMENT"
    assert select_spec.replay.required_template_ops == ("replace_statement_body",)
    assert from_spec.replay.required_template_ops == ("replace_statement_body",)
    assert select_spec.replay.render_mode == "STATEMENT_TEMPLATE_SAFE"
    assert from_spec.replay.render_mode == "STATEMENT_TEMPLATE_SAFE"
    assert "CHOOSE" not in select_spec.scope.forbid_features
    assert select_spec.blockers.block_on_choose is False
    assert select_spec.fixture_obligations.blocked_neighbor_required is False
    assert from_spec.fixture_obligations.blocked_neighbor_required is True


def test_aggregation_baseline_specs_are_explicit_registry_entries() -> None:
    group_by_spec = lookup_patch_family_spec("REDUNDANT_GROUP_BY_WRAPPER")
    having_spec = lookup_patch_family_spec("REDUNDANT_HAVING_WRAPPER")
    distinct_wrapper_spec = lookup_patch_family_spec("REDUNDANT_DISTINCT_WRAPPER")
    group_by_alias_spec = lookup_patch_family_spec("GROUP_BY_FROM_ALIAS_CLEANUP")
    group_by_having_alias_spec = lookup_patch_family_spec("GROUP_BY_HAVING_FROM_ALIAS_CLEANUP")
    distinct_alias_spec = lookup_patch_family_spec("DISTINCT_FROM_ALIAS_CLEANUP")

    assert group_by_spec is not None
    assert having_spec is not None
    assert distinct_wrapper_spec is not None
    assert group_by_alias_spec is not None
    assert group_by_having_alias_spec is not None
    assert distinct_alias_spec is not None

    assert group_by_spec.stage == "MVP_AGGREGATION"
    assert having_spec.stage == "MVP_AGGREGATION"
    assert distinct_wrapper_spec.stage == "MVP_AGGREGATION"
    assert group_by_alias_spec.stage == "MVP_AGGREGATION"
    assert group_by_having_alias_spec.stage == "MVP_AGGREGATION"
    assert distinct_alias_spec.stage == "MVP_AGGREGATION"

    assert group_by_spec.scope.aggregation_shape_families == ("GROUP_BY",)
    assert having_spec.scope.aggregation_shape_families == ("HAVING",)
    assert distinct_wrapper_spec.scope.aggregation_shape_families == ("DISTINCT",)
    assert group_by_alias_spec.scope.aggregation_shape_families == ("GROUP_BY",)
    assert group_by_having_alias_spec.scope.aggregation_shape_families == ("GROUP_BY", "HAVING")
    assert distinct_alias_spec.scope.aggregation_shape_families == ("DISTINCT",)

    assert group_by_spec.patch_target_policy.selected_patch_strategy == "EXACT_TEMPLATE_EDIT"
    assert having_spec.patch_target_policy.selected_patch_strategy == "EXACT_TEMPLATE_EDIT"
    assert distinct_wrapper_spec.patch_target_policy.selected_patch_strategy == "EXACT_TEMPLATE_EDIT"
    assert group_by_alias_spec.patch_target_policy.selected_patch_strategy == "EXACT_TEMPLATE_EDIT"
    assert group_by_having_alias_spec.patch_target_policy.selected_patch_strategy == "EXACT_TEMPLATE_EDIT"
    assert distinct_alias_spec.patch_target_policy.selected_patch_strategy == "EXACT_TEMPLATE_EDIT"

    assert group_by_spec.patch_target_policy.materialization_modes == ("STATEMENT_SQL",)
    assert having_spec.patch_target_policy.materialization_modes == ("STATEMENT_SQL",)
    assert distinct_wrapper_spec.patch_target_policy.materialization_modes == ("STATEMENT_SQL",)
    assert group_by_alias_spec.patch_target_policy.materialization_modes == ("STATEMENT_SQL",)
    assert group_by_having_alias_spec.patch_target_policy.materialization_modes == ("STATEMENT_SQL",)
    assert distinct_alias_spec.patch_target_policy.materialization_modes == ("STATEMENT_SQL",)

    assert group_by_spec.replay.required_template_ops == ()
    assert having_spec.replay.required_template_ops == ()
    assert distinct_wrapper_spec.replay.required_template_ops == ()
    assert group_by_alias_spec.replay.required_template_ops == ()
    assert group_by_having_alias_spec.replay.required_template_ops == ()
    assert distinct_alias_spec.replay.required_template_ops == ()
    assert group_by_spec.replay.render_mode == "STATEMENT_SQL"
    assert having_spec.replay.render_mode == "STATEMENT_SQL"
    assert distinct_wrapper_spec.replay.render_mode == "STATEMENT_SQL"
    assert group_by_alias_spec.replay.render_mode == "STATEMENT_SQL"
    assert group_by_having_alias_spec.replay.render_mode == "STATEMENT_SQL"
    assert distinct_alias_spec.replay.render_mode == "STATEMENT_SQL"

    assert group_by_spec.fixture_obligations.blocked_neighbor_required is True
    assert having_spec.fixture_obligations.blocked_neighbor_required is True
    assert distinct_wrapper_spec.fixture_obligations.blocked_neighbor_required is True
    assert group_by_alias_spec.fixture_obligations.blocked_neighbor_required is True
    assert group_by_having_alias_spec.fixture_obligations.blocked_neighbor_required is True
    assert distinct_alias_spec.fixture_obligations.blocked_neighbor_required is True


def test_remaining_thin_baseline_specs_are_explicit_registry_entries() -> None:
    statement_spec = lookup_patch_family_spec("STATIC_STATEMENT_REWRITE")
    wrapper_spec = lookup_patch_family_spec("STATIC_WRAPPER_COLLAPSE")
    cte_spec = lookup_patch_family_spec("STATIC_CTE_INLINE")
    dynamic_count_spec = lookup_patch_family_spec("DYNAMIC_COUNT_WRAPPER_COLLAPSE")
    dynamic_filter_spec = lookup_patch_family_spec("DYNAMIC_FILTER_WRAPPER_COLLAPSE")

    assert statement_spec is not None
    assert wrapper_spec is not None
    assert cte_spec is not None
    assert dynamic_count_spec is not None
    assert dynamic_filter_spec is not None

    assert statement_spec.stage == "MVP_STATIC_BASELINE"
    assert wrapper_spec.stage == "MVP_STATIC_BASELINE"
    assert cte_spec.stage == "MVP_STATIC_BASELINE"
    assert dynamic_count_spec.stage == "MVP_DYNAMIC_BASELINE"
    assert dynamic_filter_spec.stage == "MVP_DYNAMIC_BASELINE"

    assert statement_spec.scope.patch_surface == "STATEMENT_BODY"
    assert wrapper_spec.scope.patch_surface == "STATEMENT_BODY"
    assert cte_spec.scope.patch_surface == "STATEMENT_BODY"
    assert dynamic_count_spec.scope.dynamic_shape_families == ("IF_GUARDED_COUNT_WRAPPER",)
    assert dynamic_filter_spec.scope.dynamic_shape_families == ("IF_GUARDED_FILTER_STATEMENT",)

    assert statement_spec.patch_target_policy.selected_patch_strategy == "EXACT_TEMPLATE_EDIT"
    assert wrapper_spec.patch_target_policy.selected_patch_strategy == "SAFE_WRAPPER_COLLAPSE"
    assert cte_spec.patch_target_policy.selected_patch_strategy == "EXACT_TEMPLATE_EDIT"
    assert dynamic_count_spec.patch_target_policy.selected_patch_strategy == "DYNAMIC_STATEMENT_TEMPLATE_EDIT"
    assert dynamic_filter_spec.patch_target_policy.selected_patch_strategy == "DYNAMIC_STATEMENT_TEMPLATE_EDIT"

    assert statement_spec.patch_target_policy.materialization_modes == ("STATEMENT_SQL",)
    assert wrapper_spec.patch_target_policy.materialization_modes == ("STATEMENT_TEMPLATE_SAFE_WRAPPER_COLLAPSE",)
    assert cte_spec.patch_target_policy.materialization_modes == ("STATEMENT_SQL",)
    assert dynamic_count_spec.patch_target_policy.materialization_modes == ("STATEMENT_TEMPLATE_SAFE",)
    assert dynamic_filter_spec.patch_target_policy.materialization_modes == ("STATEMENT_TEMPLATE_SAFE",)

    assert statement_spec.replay.required_template_ops == ()
    assert wrapper_spec.replay.required_template_ops == ("replace_statement_body",)
    assert cte_spec.replay.required_template_ops == ()
    assert dynamic_count_spec.replay.required_template_ops == ("replace_statement_body",)
    assert dynamic_filter_spec.replay.required_template_ops == ("replace_statement_body",)

    assert statement_spec.replay.render_mode == "STATEMENT_SQL"
    assert wrapper_spec.replay.render_mode == "STATEMENT_TEMPLATE_SAFE_WRAPPER_COLLAPSE"
    assert cte_spec.replay.render_mode == "STATEMENT_SQL"
    assert dynamic_count_spec.replay.render_mode == "STATEMENT_TEMPLATE_SAFE"
    assert dynamic_filter_spec.replay.render_mode == "STATEMENT_TEMPLATE_SAFE"

    assert statement_spec.fixture_obligations.blocked_neighbor_required is False
    assert wrapper_spec.fixture_obligations.blocked_neighbor_required is False
    assert cte_spec.fixture_obligations.blocked_neighbor_required is False
    assert dynamic_count_spec.fixture_obligations.blocked_neighbor_required is False
    assert dynamic_filter_spec.fixture_obligations.blocked_neighbor_required is False


def test_duplicate_family_registration_fails_fast() -> None:
    spec = lookup_patch_family_spec("STATIC_INCLUDE_WRAPPER_COLLAPSE")
    assert spec is not None

    with pytest.raises(ValueError, match="DUPLICATE_PATCH_FAMILY: STATIC_INCLUDE_WRAPPER_COLLAPSE"):
        _build_patch_family_registry((spec, spec))


def test_whitespace_variant_family_registration_fails_fast() -> None:
    spec = lookup_patch_family_spec("STATIC_INCLUDE_WRAPPER_COLLAPSE")
    assert spec is not None

    with pytest.raises(ValueError, match="NON_CANONICAL_PATCH_FAMILY: STATIC_INCLUDE_WRAPPER_COLLAPSE"):
        _build_patch_family_registry((spec, replace(spec, family=f" {spec.family} ")))


def test_non_canonical_family_registration_fails_fast() -> None:
    spec = lookup_patch_family_spec("STATIC_INCLUDE_WRAPPER_COLLAPSE")
    assert spec is not None

    with pytest.raises(ValueError, match="NON_CANONICAL_PATCH_FAMILY: STATIC_INCLUDE_WRAPPER_COLLAPSE"):
        _build_patch_family_registry((replace(spec, family=f" {spec.family} "),))


def test_lowercase_family_registration_fails_fast() -> None:
    spec = lookup_patch_family_spec("STATIC_INCLUDE_WRAPPER_COLLAPSE")
    assert spec is not None

    with pytest.raises(ValueError, match="NON_CANONICAL_PATCH_FAMILY: STATIC_INCLUDE_WRAPPER_COLLAPSE"):
        _build_patch_family_registry((replace(spec, family=spec.family.lower()),))


def test_registry_imports_concrete_spec_modules_directly() -> None:
    registry_source = inspect.getsource(registry_module)
    specs_source = inspect.getsource(specs_package)

    assert "from .specs import (" not in registry_source
    assert "from .specs.frozen_baselines import FROZEN_BASELINE_SPECS" in registry_source
    assert "from .specs.static_alias_projection_cleanup import STATIC_ALIAS_PROJECTION_CLEANUP_SPEC" in registry_source
    assert "from .specs.static_include_wrapper_collapse import STATIC_INCLUDE_WRAPPER_COLLAPSE_SPEC" in registry_source
    assert "from .specs.static_statement_rewrite import STATIC_STATEMENT_REWRITE_SPEC" in registry_source
    assert "from .specs.static_wrapper_collapse import STATIC_WRAPPER_COLLAPSE_SPEC" in registry_source
    assert "from .specs.static_cte_inline import STATIC_CTE_INLINE_SPEC" in registry_source
    assert "from .specs.dynamic_count_wrapper_collapse import DYNAMIC_COUNT_WRAPPER_COLLAPSE_SPEC" in registry_source
    assert "from .specs.dynamic_filter_wrapper_collapse import DYNAMIC_FILTER_WRAPPER_COLLAPSE_SPEC" in registry_source
    assert "from .specs.redundant_distinct_wrapper import REDUNDANT_DISTINCT_WRAPPER_SPEC" in registry_source
    assert "from .specs.redundant_group_by_wrapper import REDUNDANT_GROUP_BY_WRAPPER_SPEC" in registry_source
    assert "from .specs.redundant_having_wrapper import REDUNDANT_HAVING_WRAPPER_SPEC" in registry_source
    assert "from .specs.group_by_from_alias_cleanup import GROUP_BY_FROM_ALIAS_CLEANUP_SPEC" in registry_source
    assert "from .specs.group_by_having_from_alias_cleanup import GROUP_BY_HAVING_FROM_ALIAS_CLEANUP_SPEC" in registry_source
    assert "from .specs.distinct_from_alias_cleanup import DISTINCT_FROM_ALIAS_CLEANUP_SPEC" in registry_source
    assert "from .frozen_baselines import FROZEN_BASELINE_SPECS" not in specs_source
    assert "from .static_alias_projection_cleanup import STATIC_ALIAS_PROJECTION_CLEANUP_SPEC" not in specs_source
    assert "from .static_include_wrapper_collapse import STATIC_INCLUDE_WRAPPER_COLLAPSE_SPEC" not in specs_source
