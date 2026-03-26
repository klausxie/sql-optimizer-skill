from __future__ import annotations

from sqlopt.patch_contracts import FROZEN_AUTO_PATCH_FAMILIES
from sqlopt.patch_families.registry import (
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
    assert spec.status == "REGISTERED_CANDIDATE"
    assert spec.acceptance.semantic_required_status == "PASS"
    assert spec.acceptance.semantic_min_confidence == "HIGH"
    assert spec.scope.statement_types == ("SELECT",)
    assert spec.patch_target_policy.selected_patch_strategy == "EXACT_TEMPLATE_EDIT"
    assert spec.replay.required_template_ops == ("replace_statement_body",)
    assert spec.blockers.block_on_expression_alias is True
    assert spec.verification.require_replay_match is True
    assert spec.fixture_obligations.ready_case_required is True
    assert spec.fixture_obligations.blocked_neighbor_required is True


def test_patch_contracts_frozen_family_scope_is_registry_derived() -> None:
    registry_families = {
        spec.family
        for spec in list_registered_patch_families()
        if spec.status == "FROZEN_AUTO_PATCH"
    }
    assert FROZEN_AUTO_PATCH_FAMILIES == registry_families
    assert "STATIC_ALIAS_PROJECTION_CLEANUP" not in FROZEN_AUTO_PATCH_FAMILIES
