from __future__ import annotations

from typing import Any

from .patch_safety import assess_patch_safety_model
from .patch_strategy_registry import iter_patch_strategies
from .rewrite_facts import build_rewrite_facts_model
from .template_materializer import build_rewrite_materialization


def plan_patch_strategy(
    sql_unit: dict[str, Any],
    rewritten_sql: str,
    fragment_catalog: dict[str, dict[str, Any]],
    equivalence: dict[str, Any],
    semantic_equivalence: dict[str, Any],
    *,
    enable_fragment_materialization: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None, list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    rewrite_facts_model = build_rewrite_facts_model(sql_unit, rewritten_sql, fragment_catalog, equivalence, semantic_equivalence)
    patchability_model = assess_patch_safety_model(rewrite_facts_model)
    rewrite_facts = rewrite_facts_model.to_dict()
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
        )
        if planned is None:
            prior_strategy_type = registered_strategy.strategy_type
            continue
        candidates.append(planned)
        prior_strategy_type = registered_strategy.strategy_type

    selected = candidates[0] if candidates else None
    if selected is not None:
        selected_summary = selected.to_summary_dict()
        return (
            rewrite_facts,
            patchability,
            selected_summary,
            [row.to_summary_dict() for row in candidates],
            dict(selected.materialization or {}),
            [dict(row) for row in (selected.ops or []) if isinstance(row, dict)],
        )

    return (
        rewrite_facts,
        patchability,
        None,
        [],
        fallback_materialization,
        fallback_ops,
    )
