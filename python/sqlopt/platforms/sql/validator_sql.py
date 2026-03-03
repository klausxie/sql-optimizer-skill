from __future__ import annotations

from pathlib import Path
from typing import Any

from ..dispatch import compare_plan, compare_semantics
from .acceptance_policy import (
    build_acceptance_decision,
    db_unreachable_result,
    invalid_candidate_result,
    security_failure_result,
)
from .candidate_selection import (
    build_candidate_pool,
    evaluate_candidate_selection,
    filter_valid_candidates,
)
from .template_materializer import build_rewrite_materialization
from .validation_strategy import build_compare_policy, run_plan_compare, run_semantics_compare

def _derive_rewrite_materialization(
    sql_unit: dict[str, Any],
    rewritten_sql: str,
    fragment_catalog: dict[str, dict[str, Any]],
    config: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    patch_cfg = ((config or {}).get("patch", {}) if isinstance(config, dict) else {}) or {}
    template_cfg = (patch_cfg.get("template_rewrite", {}) if isinstance(patch_cfg, dict) else {}) or {}
    enable_fragment_materialization = bool(template_cfg.get("enable_fragment_materialization", False))
    return build_rewrite_materialization(
        sql_unit,
        rewritten_sql,
        fragment_catalog or {},
        enable_fragment_materialization=enable_fragment_materialization,
    )


def validate_proposal(
    sql_unit: dict[str, Any],
    proposal: dict[str, Any],
    db_reachable: bool,
    *,
    config: dict[str, Any] | None = None,
    evidence_dir: Path | None = None,
    fragment_catalog: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    sql = sql_unit["sql"]
    validate_cfg = (config.get("validate", {}) if isinstance(config, dict) else {}) or {}
    validation_profile = str(validate_cfg.get("validation_profile", "balanced")).strip().lower()
    if validation_profile not in {"strict", "balanced", "relaxed"}:
        validation_profile = "balanced"
    risk = "high" if "${" in sql else "low"
    risk_flags = ["DOLLAR_SUBSTITUTION"] if risk == "high" else []
    llm_candidates = proposal.get("llmCandidates") or []
    candidates = build_candidate_pool(sql_unit["sqlKey"], proposal)
    valid_candidates, rejected_placeholder_semantics = filter_valid_candidates(sql, candidates)

    if risk == "high":
        return security_failure_result(sql_unit["sqlKey"], validation_profile, risk_flags)
    if candidates and not valid_candidates and rejected_placeholder_semantics == 0:
        return invalid_candidate_result(sql_unit["sqlKey"], risk_flags)
    if not db_reachable:
        return db_unreachable_result(sql_unit["sqlKey"], risk_flags)

    compare_enabled = bool(config and evidence_dir is not None and (config.get("db", {}) or {}).get("dsn"))
    compare_policy = build_compare_policy(config) if compare_enabled else None
    selection = evaluate_candidate_selection(
        sql,
        proposal,
        config,
        evidence_dir,
        compare_policy,
        valid_candidates,
        lambda policy, cfg, orig, rewritten, target_dir: run_semantics_compare(
            policy, compare_semantics, cfg, orig, rewritten, target_dir
        ),
        lambda policy, cfg, orig, rewritten, target_dir: run_plan_compare(
            policy, compare_plan, cfg, orig, rewritten, target_dir
        ),
        compare_enabled=compare_enabled,
    )
    selected_source = str(selection.selected_candidate_source or ("llm" if llm_candidates else "rule"))
    decision = build_acceptance_decision(
        selection.equivalence,
        selection.perf,
        validation_profile,
        rejected_placeholder_semantics,
    )

    rewrite_materialization, template_rewrite_ops = _derive_rewrite_materialization(
        sql_unit,
        selection.rewritten_sql,
        fragment_catalog or {},
        config,
    )

    return {
        "sqlKey": sql_unit["sqlKey"],
        "status": decision.status,
        "rewrittenSql": selection.rewritten_sql,
        "equivalence": selection.equivalence,
        "perfComparison": {**selection.perf, "reasonCodes": decision.reason_codes},
        "securityChecks": {"dollar_substitution_removed": True},
        "semanticRisk": "low",
        "feedback": decision.feedback,
        "selectedCandidateSource": selected_source,
        "selectedCandidateId": selection.selected_candidate_id,
        "candidateEvaluations": selection.candidate_evaluations,
        "warnings": decision.warnings,
        "riskFlags": risk_flags,
        "rewriteMaterialization": rewrite_materialization,
        "templateRewriteOps": template_rewrite_ops,
        "candidateEval": {
            "evaluated": len(selection.candidate_evaluations),
            "valid": len(valid_candidates),
            "improved": sum(1 for x in selection.candidate_evaluations if x.get("improved") and x.get("semanticMatch")),
            "bestAfterCost": (selection.perf.get("afterSummary") or {}).get("totalCost"),
        },
    }
