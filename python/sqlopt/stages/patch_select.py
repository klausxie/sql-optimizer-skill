from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..platforms.sql.patch_strategy_planner import plan_patch_strategy
from ..platforms.sql.patch_utils import (
    apply_static_alias_projection_cleanup_guard,
    derive_patch_target_family,
    dynamic_template_summary,
    patch_template_settings,
)


@dataclass(frozen=True)
class PatchSelectionContext:
    rewritten_sql: str
    selected_candidate_id: str | None
    semantic_equivalence: dict[str, Any]
    semantic_gate_status: str
    semantic_gate_confidence: str
    rewrite_facts: dict[str, Any]
    dynamic_candidate_intent: dict[str, Any] | None
    dynamic_template: dict[str, Any] | None
    patchability: dict[str, Any]
    selected_patch_strategy: dict[str, Any] | None
    patch_strategy_candidates: list[dict[str, Any]]
    rewrite_materialization: dict[str, Any] | None
    template_rewrite_ops: list[dict[str, Any]]
    family: str | None


def _normalize_semantic_equivalence(acceptance: dict[str, Any]) -> dict[str, Any]:
    semantic = acceptance.get("semanticEquivalence")
    if isinstance(semantic, dict):
        return dict(semantic)
    return {}


def build_patch_selection_context(
    *,
    sql_unit: dict[str, Any],
    acceptance: dict[str, Any],
    fragment_catalog: dict[str, dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> PatchSelectionContext:
    rewritten_sql = str(acceptance.get("rewrittenSql") or "").strip()
    selected_candidate_id = str(acceptance.get("selectedCandidateId") or "").strip() or None
    semantic_equivalence = _normalize_semantic_equivalence(acceptance)
    semantic_gate_status = str(semantic_equivalence.get("status") or "PASS").strip().upper()
    semantic_gate_confidence = str(semantic_equivalence.get("confidence") or "HIGH").strip().upper()

    if not rewritten_sql:
        return PatchSelectionContext(
            rewritten_sql="",
            selected_candidate_id=selected_candidate_id,
            semantic_equivalence=semantic_equivalence,
            semantic_gate_status=semantic_gate_status,
            semantic_gate_confidence=semantic_gate_confidence,
            rewrite_facts={},
            dynamic_candidate_intent=None,
            dynamic_template=None,
            patchability={},
            selected_patch_strategy=None,
            patch_strategy_candidates=[],
            rewrite_materialization=None,
            template_rewrite_ops=[],
            family=None,
        )

    template_settings = patch_template_settings(config)
    rewrite_facts, dynamic_candidate_intent, patchability, selected_patch_strategy, patch_strategy_candidates, rewrite_materialization, template_rewrite_ops = (
        plan_patch_strategy(
            sql_unit,
            rewritten_sql,
            fragment_catalog or {},
            dict(acceptance.get("equivalence") or {}),
            semantic_equivalence,
            enable_fragment_materialization=template_settings["enable_fragment_materialization"],
        )
    )
    patchability, selected_patch_strategy, rewrite_materialization, template_rewrite_ops = apply_static_alias_projection_cleanup_guard(
        original_sql=str(sql_unit.get("sql") or ""),
        rewritten_sql=rewritten_sql,
        rewrite_facts=rewrite_facts,
        patchability=patchability,
        selected_patch_strategy=selected_patch_strategy,
        rewrite_materialization=rewrite_materialization,
        template_rewrite_ops=template_rewrite_ops,
    )
    family = derive_patch_target_family(
        original_sql=str(sql_unit.get("sql") or ""),
        rewritten_sql=rewritten_sql,
        rewrite_facts=rewrite_facts,
        rewrite_materialization=rewrite_materialization,
        selected_patch_strategy=selected_patch_strategy,
    )
    return PatchSelectionContext(
        rewritten_sql=rewritten_sql,
        selected_candidate_id=selected_candidate_id,
        semantic_equivalence=semantic_equivalence,
        semantic_gate_status=semantic_gate_status,
        semantic_gate_confidence=semantic_gate_confidence,
        rewrite_facts=rewrite_facts,
        dynamic_candidate_intent=dynamic_candidate_intent,
        dynamic_template=dynamic_template_summary(rewrite_facts, patchability, selected_patch_strategy),
        patchability=patchability,
        selected_patch_strategy=selected_patch_strategy,
        patch_strategy_candidates=list(patch_strategy_candidates or []),
        rewrite_materialization=dict(rewrite_materialization or {}) if rewrite_materialization is not None else None,
        template_rewrite_ops=[dict(row) for row in (template_rewrite_ops or []) if isinstance(row, dict)],
        family=family,
    )


def enrich_acceptance_for_patch(acceptance: dict[str, Any], selection: PatchSelectionContext) -> dict[str, Any]:
    payload = dict(acceptance)
    if selection.patchability and "patchability" not in payload:
        payload["patchability"] = dict(selection.patchability)
    if selection.selected_patch_strategy and "selectedPatchStrategy" not in payload:
        payload["selectedPatchStrategy"] = dict(selection.selected_patch_strategy)
    if selection.rewrite_materialization and "rewriteMaterialization" not in payload:
        payload["rewriteMaterialization"] = dict(selection.rewrite_materialization)
    if selection.template_rewrite_ops and "templateRewriteOps" not in payload:
        payload["templateRewriteOps"] = [dict(row) for row in selection.template_rewrite_ops]
    if selection.patch_strategy_candidates and "patchStrategyCandidates" not in payload:
        payload["patchStrategyCandidates"] = [dict(row) for row in selection.patch_strategy_candidates]
    if selection.dynamic_template and "dynamicTemplate" not in payload:
        payload["dynamicTemplate"] = dict(selection.dynamic_template)
    if selection.rewrite_facts and "rewriteFacts" not in payload:
        payload["rewriteFacts"] = dict(selection.rewrite_facts)
    return payload
