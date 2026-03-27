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
    artifact_kind: str = "STATEMENT"
    target_file: str | None = None
    target_kind: str | None = None
    target_ref: str | None = None


def _artifact_identity(selection: PatchSelectionContext, sql_unit: dict[str, Any]) -> tuple[str, str | None, str | None]:
    template_ops = [row for row in selection.template_rewrite_ops if isinstance(row, dict)]
    if any(str(row.get("op") or "").strip() == "replace_fragment_body" for row in template_ops):
        target_ref = next(
            (
                str(row.get("fragmentKey") or row.get("refid") or row.get("targetRef") or "").strip()
                for row in template_ops
                if isinstance(row, dict)
            ),
            "",
        )
        return "FRAGMENT", "fragment", target_ref or None
    if template_ops:
        target_ref = next(
            (
                str(row.get("statementId") or row.get("targetRef") or "").strip()
                for row in template_ops
                if isinstance(row, dict)
            ),
            "",
        )
        return "TEMPLATE", "statement", target_ref or None
    if [str(x) for x in (sql_unit.get("dynamicFeatures") or []) if str(x).strip()]:
        target_ref = str(
            ((sql_unit.get("locators") or {}).get("statementId") or sql_unit.get("statementId") or "")
        ).strip()
        return "TEMPLATE", "statement", target_ref or None
    return "STATEMENT", "statement", None


def build_patch_plan(selection: PatchSelectionContext, sql_unit: dict[str, Any]) -> PatchBuildResult:
    artifact_kind, target_kind, target_ref = _artifact_identity(selection, sql_unit)
    return PatchBuildResult(
        selected_patch_strategy=dict(selection.selected_patch_strategy) if selection.selected_patch_strategy is not None else None,
        rewrite_materialization=dict(selection.rewrite_materialization) if selection.rewrite_materialization is not None else None,
        template_rewrite_ops=[dict(row) for row in selection.template_rewrite_ops if isinstance(row, dict)],
        family=selection.family,
        artifact_kind=artifact_kind,
        target_file=str(sql_unit.get("xmlPath") or "").strip() or None,
        target_kind=target_kind,
        target_ref=target_ref,
    )
