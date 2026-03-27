from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..patch_contracts import build_patch_target_contract, semantic_confidence_rank
from ..patch_families.registry import lookup_patch_family_spec
from ..platforms.sql.patch_strategy_planner import plan_patch_strategy
from ..platforms.sql.validator_sql import (
    _apply_static_alias_projection_cleanup_guard,
    _derive_patch_target_family,
    _dynamic_template_summary,
    _patch_template_settings,
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
    patch_target: dict[str, Any] | None


def _normalize_semantic_equivalence(acceptance: dict[str, Any]) -> dict[str, Any]:
    semantic = acceptance.get("semanticEquivalence")
    if isinstance(semantic, dict):
        return dict(semantic)
    return {}


def _build_patch_target_from_selection(
    *,
    sql_unit: dict[str, Any],
    rewritten_sql: str,
    selected_candidate_id: str | None,
    semantic_equivalence: dict[str, Any],
    patchability: dict[str, Any],
    selected_patch_strategy: dict[str, Any] | None,
    rewrite_materialization: dict[str, Any] | None,
    template_rewrite_ops: list[dict[str, Any]],
    rewrite_facts: dict[str, Any],
    acceptance_status: str,
) -> dict[str, Any] | None:
    if acceptance_status != "PASS":
        return None
    if not rewritten_sql or not selected_candidate_id or not selected_patch_strategy:
        return None
    if not bool((patchability or {}).get("eligible")):
        return None

    replay_contract = dict((rewrite_materialization or {}).get("replayContract") or {})
    if not replay_contract:
        return None

    family = _derive_patch_target_family(
        original_sql=str(sql_unit.get("sql") or ""),
        rewritten_sql=rewritten_sql,
        rewrite_facts=rewrite_facts,
        rewrite_materialization=rewrite_materialization,
        selected_patch_strategy=selected_patch_strategy,
    )
    spec = lookup_patch_family_spec(family) if family else None
    if spec is None or spec.status != "FROZEN_AUTO_PATCH":
        return None

    semantic_status = str((semantic_equivalence or {}).get("status") or "").strip().upper()
    if semantic_status != str(spec.acceptance.semantic_required_status or "").strip().upper():
        return None
    semantic_confidence = str((semantic_equivalence or {}).get("confidence") or "").strip().upper()
    if semantic_confidence_rank(semantic_confidence) < semantic_confidence_rank(spec.acceptance.semantic_min_confidence):
        return None

    return build_patch_target_contract(
        sql_key=str(sql_unit.get("sqlKey") or ""),
        target_sql=rewritten_sql,
        selected_candidate_id=selected_candidate_id,
        selected_patch_strategy=selected_patch_strategy,
        family=family,
        semantic_equivalence=semantic_equivalence,
        patchability=dict(patchability or {}),
        rewrite_materialization=dict(rewrite_materialization or {}),
        template_rewrite_ops=[dict(row) for row in template_rewrite_ops if isinstance(row, dict)],
        replay_contract=replay_contract,
        evidence_refs=[],
    )


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
            patch_target=None,
        )

    template_settings = _patch_template_settings(config)
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
    patchability, selected_patch_strategy, rewrite_materialization, template_rewrite_ops = _apply_static_alias_projection_cleanup_guard(
        original_sql=str(sql_unit.get("sql") or ""),
        rewritten_sql=rewritten_sql,
        rewrite_facts=rewrite_facts,
        patchability=patchability,
        selected_patch_strategy=selected_patch_strategy,
        rewrite_materialization=rewrite_materialization,
        template_rewrite_ops=template_rewrite_ops,
    )
    family = _derive_patch_target_family(
        original_sql=str(sql_unit.get("sql") or ""),
        rewritten_sql=rewritten_sql,
        rewrite_facts=rewrite_facts,
        rewrite_materialization=rewrite_materialization,
        selected_patch_strategy=selected_patch_strategy,
    )
    patch_target = _build_patch_target_from_selection(
        sql_unit=sql_unit,
        rewritten_sql=rewritten_sql,
        selected_candidate_id=selected_candidate_id,
        semantic_equivalence=semantic_equivalence,
        patchability=patchability,
        selected_patch_strategy=selected_patch_strategy,
        rewrite_materialization=rewrite_materialization,
        template_rewrite_ops=template_rewrite_ops,
        rewrite_facts=rewrite_facts,
        acceptance_status=str(acceptance.get("status") or ""),
    )

    return PatchSelectionContext(
        rewritten_sql=rewritten_sql,
        selected_candidate_id=selected_candidate_id,
        semantic_equivalence=semantic_equivalence,
        semantic_gate_status=semantic_gate_status,
        semantic_gate_confidence=semantic_gate_confidence,
        rewrite_facts=rewrite_facts,
        dynamic_candidate_intent=dynamic_candidate_intent,
        dynamic_template=_dynamic_template_summary(rewrite_facts, patchability, selected_patch_strategy),
        patchability=patchability,
        selected_patch_strategy=selected_patch_strategy,
        patch_strategy_candidates=list(patch_strategy_candidates or []),
        rewrite_materialization=dict(rewrite_materialization or {}) if rewrite_materialization is not None else None,
        template_rewrite_ops=[dict(row) for row in (template_rewrite_ops or []) if isinstance(row, dict)],
        family=family,
        patch_target=patch_target,
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
    if selection.patch_target and "patchTarget" not in payload:
        payload["patchTarget"] = dict(selection.patch_target)
    return payload
