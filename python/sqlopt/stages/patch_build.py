from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .patch_select import PatchSelectionContext


@dataclass(frozen=True)
class PatchBuildResult:
    selected_patch_strategy: dict[str, Any] | None
    rewrite_materialization: dict[str, Any] | None
    template_rewrite_ops: list[dict[str, Any]]
    family: str | None


def build_patch_plan(selection: PatchSelectionContext) -> PatchBuildResult:
    return PatchBuildResult(
        selected_patch_strategy=dict(selection.selected_patch_strategy) if selection.selected_patch_strategy is not None else None,
        rewrite_materialization=dict(selection.rewrite_materialization) if selection.rewrite_materialization is not None else None,
        template_rewrite_ops=[dict(row) for row in selection.template_rewrite_ops if isinstance(row, dict)],
        family=selection.family,
    )
