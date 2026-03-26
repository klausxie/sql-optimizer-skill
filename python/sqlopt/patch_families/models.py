from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PatchFamilyAcceptancePolicy:
    semantic_required_status: str
    semantic_min_confidence: str
    fingerprint_requirement: str | None = None
    requires_unique_pass_winner: bool = True


@dataclass(frozen=True)
class PatchFamilyVerificationPolicy:
    require_replay_match: bool
    require_xml_parse: bool
    require_render_ok: bool
    require_sql_parse: bool
    require_apply_check: bool


@dataclass(frozen=True)
class PatchFamilyFixtureObligations:
    ready_case_required: bool
    blocked_neighbor_required: bool
    replay_assertions_required: bool
    verification_assertions_required: bool


@dataclass(frozen=True)
class PatchFamilyScope:
    statement_types: tuple[str, ...]
    requires_template_preserving: bool
    dynamic_shape_families: tuple[str, ...] = ()
    aggregation_shape_families: tuple[str, ...] = ()
    forbid_features: tuple[str, ...] = ()
    patch_surface: str | None = None


@dataclass(frozen=True)
class PatchFamilyPatchTargetPolicy:
    selected_patch_strategy: str
    requires_replay_contract: bool
    materialization_modes: tuple[str, ...] = ()
    target_type: str | None = None
    target_ref_policy: str | None = None


@dataclass(frozen=True)
class PatchFamilyReplayPolicy:
    required_template_ops: tuple[str, ...]
    render_mode: str
    required_anchors: tuple[str, ...] = ()
    required_includes: tuple[str, ...] = ()
    required_placeholder_shape: tuple[str, ...] = ()
    dialect_syntax_check_required: bool = True


@dataclass(frozen=True)
class PatchFamilyBlockingPolicy:
    block_on_dynamic_subtree: bool = False
    block_on_choose: bool = False
    block_on_bind: bool = False
    block_on_foreach: bool = False
    block_on_expression_alias: bool = False
    custom_blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class PatchFamilySpec:
    family: str
    status: str
    stage: str
    scope: PatchFamilyScope
    acceptance: PatchFamilyAcceptancePolicy
    patch_target_policy: PatchFamilyPatchTargetPolicy
    replay: PatchFamilyReplayPolicy
    verification: PatchFamilyVerificationPolicy
    blockers: PatchFamilyBlockingPolicy
    fixture_obligations: PatchFamilyFixtureObligations
