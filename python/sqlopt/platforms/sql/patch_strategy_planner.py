from __future__ import annotations

from dataclasses import replace
from typing import Any

from .dynamic_candidate_intent_engine import assess_dynamic_candidate_intent_model
from .patch_safety import assess_patch_safety_model
from .patch_strategy_registry import iter_patch_strategies
from .rewrite_facts import build_rewrite_facts_model
from .template_materializer import build_replay_contract, build_rewrite_materialization


def _blocked_strategy_hints(patchability: dict[str, Any]) -> list[dict[str, Any]]:
    dynamic_shape_family = str(patchability.get("dynamicShapeFamily") or "").strip().upper()
    dynamic_capability_tier = str(patchability.get("dynamicCapabilityTier") or "").strip().upper()
    dynamic_blocking_reason = str(patchability.get("dynamicBlockingReason") or "").strip().upper()
    if dynamic_shape_family not in {"", "NONE"} and dynamic_capability_tier == "REVIEW_REQUIRED":
        return [
            {
                "strategyType": "DYNAMIC_STATEMENT_TEMPLATE_EDIT",
                "mode": "BLOCKED",
                "reasonCode": "DYNAMIC_TEMPLATE_CONSTRAINT_BLOCKED",
                "fallbackFrom": None,
                "blocked": True,
                "blockedBy": "DYNAMIC_TEMPLATE",
                "dynamicShapeFamily": dynamic_shape_family,
                "dynamicBlockingReason": dynamic_blocking_reason or None,
            }
        ]

    constraint_family = str(patchability.get("aggregationConstraintFamily") or "").strip().upper()
    capability_tier = str(patchability.get("aggregationCapabilityTier") or "").strip().upper()
    if constraint_family in {"", "NONE", "SAFE_BASELINE"}:
        return []
    if capability_tier != "REVIEW_REQUIRED":
        return []
    return [
        {
            "strategyType": "EXACT_TEMPLATE_EDIT",
            "mode": "BLOCKED",
            "reasonCode": "AGGREGATION_CONSTRAINT_BLOCKED",
            "fallbackFrom": None,
            "blocked": True,
            "blockedBy": "AGGREGATION_CONSTRAINT",
            "aggregationConstraintFamily": constraint_family,
        }
    ]


def plan_patch_strategy(
    sql_unit: dict[str, Any],
    rewritten_sql: str,
    fragment_catalog: dict[str, dict[str, Any]],
    equivalence: dict[str, Any],
    semantic_equivalence: dict[str, Any],
    *,
    enable_fragment_materialization: bool,
) -> tuple[
    dict[str, Any],
    dict[str, Any] | None,
    dict[str, Any],
    dict[str, Any] | None,
    list[dict[str, Any]],
    dict[str, Any],
    list[dict[str, Any]],
]:
    rewrite_facts_model = build_rewrite_facts_model(sql_unit, rewritten_sql, fragment_catalog, equivalence, semantic_equivalence)
    dynamic_candidate_intent_model = None
    if rewrite_facts_model.dynamic_template.present and not rewrite_facts_model.wrapper_query.present:
        dynamic_candidate_intent_model = assess_dynamic_candidate_intent_model(
            sql_unit,
            str(sql_unit.get("sql") or ""),
            rewritten_sql,
            rewrite_facts_model,
        )
    if dynamic_candidate_intent_model is not None and dynamic_candidate_intent_model.template_effective_change:
        rewrite_facts_model = replace(rewrite_facts_model, effective_change=True)
    patchability_model = assess_patch_safety_model(
        rewrite_facts_model,
        dynamic_candidate_intent_model.to_dict() if dynamic_candidate_intent_model is not None else None,
    )
    rewrite_facts = rewrite_facts_model.to_dict()
    dynamic_candidate_intent = dynamic_candidate_intent_model.to_dict() if dynamic_candidate_intent_model is not None else None
    patchability = patchability_model.to_dict()
    fallback_materialization, fallback_ops = build_rewrite_materialization(
        sql_unit,
        rewritten_sql,
        fragment_catalog,
        enable_fragment_materialization=enable_fragment_materialization,
    )
    candidates = []
    prior_strategy_type: str | None = None
    for registered_strategy in iter_patch_strategies():
        if registered_strategy.required_capability not in patchability_model.allowed_capabilities:
            continue
        planned = registered_strategy.implementation.plan(
            sql_unit,
            rewritten_sql,
            fragment_catalog,
            enable_fragment_materialization=enable_fragment_materialization,
            fallback_from=prior_strategy_type,
            dynamic_candidate_intent=dynamic_candidate_intent,
        )
        if planned is None:
            prior_strategy_type = registered_strategy.strategy_type
            continue
        candidates.append(planned)
        prior_strategy_type = registered_strategy.strategy_type

    selected = candidates[0] if candidates else None
    if selected is not None:
        selected_summary = selected.to_summary_dict()
        selected_materialization = dict(selected.materialization or {})
        selected_ops = [dict(row) for row in (selected.ops or []) if isinstance(row, dict)]
        if "replayContract" not in selected_materialization:
            selected_materialization["replayContract"] = build_replay_contract(
                sql_unit,
                rewritten_sql,
                selected_materialization,
                selected_ops,
                fragment_catalog,
            )
        return (
            rewrite_facts,
            dynamic_candidate_intent,
            patchability,
            selected_summary,
            [row.to_summary_dict() for row in candidates],
            selected_materialization,
            selected_ops,
        )

    return (
        rewrite_facts,
        dynamic_candidate_intent,
        patchability,
        None,
        _blocked_strategy_hints(patchability),
        fallback_materialization,
        fallback_ops,
    )
