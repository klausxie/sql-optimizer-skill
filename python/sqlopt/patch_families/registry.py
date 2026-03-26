from __future__ import annotations

from .models import PatchFamilySpec
from .specs.frozen_baselines import FROZEN_BASELINE_SPECS
from .specs.static_alias_projection_cleanup import STATIC_ALIAS_PROJECTION_CLEANUP_SPEC
from .specs.static_include_wrapper_collapse import STATIC_INCLUDE_WRAPPER_COLLAPSE_SPEC


def _canonicalize_family_id(family: str) -> str:
    return str(family or "").strip()


def _build_patch_family_registry(
    specs: tuple[PatchFamilySpec, ...],
) -> dict[str, PatchFamilySpec]:
    registry: dict[str, PatchFamilySpec] = {}
    for spec in specs:
        canonical_family = _canonicalize_family_id(spec.family)
        if canonical_family in registry:
            raise ValueError(f"DUPLICATE_PATCH_FAMILY: {canonical_family}")
        registry[canonical_family] = spec
    return registry


_REGISTERED_PATCH_FAMILY_SPECS = (
    STATIC_INCLUDE_WRAPPER_COLLAPSE_SPEC,
    STATIC_ALIAS_PROJECTION_CLEANUP_SPEC,
    *FROZEN_BASELINE_SPECS,
)

_PATCH_FAMILY_REGISTRY = _build_patch_family_registry(_REGISTERED_PATCH_FAMILY_SPECS)


def list_registered_patch_families() -> tuple[PatchFamilySpec, ...]:
    return tuple(_PATCH_FAMILY_REGISTRY[family] for family in sorted(_PATCH_FAMILY_REGISTRY))


def lookup_patch_family_spec(family: str) -> PatchFamilySpec | None:
    return _PATCH_FAMILY_REGISTRY.get(_canonicalize_family_id(family))
