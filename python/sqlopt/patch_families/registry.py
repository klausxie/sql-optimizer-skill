from __future__ import annotations

from .models import PatchFamilySpec
from .specs import REGISTERED_PATCH_FAMILY_SPECS

_PATCH_FAMILY_REGISTRY = {spec.family: spec for spec in REGISTERED_PATCH_FAMILY_SPECS}


def list_registered_patch_families() -> tuple[PatchFamilySpec, ...]:
    return tuple(_PATCH_FAMILY_REGISTRY[family] for family in sorted(_PATCH_FAMILY_REGISTRY))


def lookup_patch_family_spec(family: str) -> PatchFamilySpec | None:
    return _PATCH_FAMILY_REGISTRY.get(str(family or "").strip())
