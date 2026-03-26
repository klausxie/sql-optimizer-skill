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
    assert spec.fixture_obligations.blocked_neighbor_required is True


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
    assert "from .frozen_baselines import FROZEN_BASELINE_SPECS" not in specs_source
    assert "from .static_alias_projection_cleanup import STATIC_ALIAS_PROJECTION_CLEANUP_SPEC" not in specs_source
    assert "from .static_include_wrapper_collapse import STATIC_INCLUDE_WRAPPER_COLLAPSE_SPEC" not in specs_source
