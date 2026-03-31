"""SQL validation logic for the validate stage.

This module is responsible for:
- Candidate pool building and filtering
- Semantic equivalence checking
- Performance comparison
- Acceptance decision building

It does NOT depend on patch-related modules.
Patch planning is handled by the patch_generate stage.
"""

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
from .models import AcceptanceDecision, MissingDSNError, ValidationResult
from .candidate_selection import (
    build_candidate_pool,
    evaluate_candidate_selection,
    filter_valid_candidates,
)
from ...stages.proposal_models import LLM_CANDIDATES_KEY
from .semantic_equivalence import build_semantic_equivalence
from .validation_strategy import build_compare_policy, run_plan_compare, run_semantics_compare
from .llm_semantic_check import integrate_llm_semantic_check


def validate_proposal(
    sql_unit: dict[str, Any],
    proposal: dict[str, Any],
    db_reachable: bool,
    *,
    config: dict[str, Any] | None = None,
    evidence_dir: Path | None = None,
) -> ValidationResult:
    """Validate an optimization proposal against the database.

    This function performs semantic and performance validation of SQL candidates.

    Args:
        sql_unit: The SQL unit being validated
        proposal: The optimization proposal with candidates
        db_reachable: Whether database is reachable for validation
        config: Configuration dictionary
        evidence_dir: Directory for evidence storage

    Returns:
        ValidationResult with validation status and evidence

    Raises:
        MissingDSNError: If db.dsn is not configured in config
    """
    sql = sql_unit["sql"]
    validate_cfg = (config.get("validate", {}) if isinstance(config, dict) else {}) or {}
    validation_profile = str(validate_cfg.get("validation_profile", "balanced")).strip().lower()
    if validation_profile not in {"strict", "balanced", "relaxed"}:
        validation_profile = "balanced"

    risk = "high" if "${" in sql else "low"
    risk_flags = ["DOLLAR_SUBSTITUTION"] if risk == "high" else []
    llm_candidates = proposal.get(LLM_CANDIDATES_KEY) or []
    candidates = build_candidate_pool(sql_unit["sqlKey"], proposal)
    valid_candidates, rejected_placeholder_semantics = filter_valid_candidates(sql, candidates)

    # Early exit cases
    if risk == "high":
        return security_failure_result(sql_unit["sqlKey"], validation_profile, risk_flags)
    if candidates and not valid_candidates and rejected_placeholder_semantics == 0:
        return invalid_candidate_result(sql_unit["sqlKey"], risk_flags, validation_profile=validation_profile)
    if not db_reachable:
        return db_unreachable_result(sql_unit["sqlKey"], risk_flags, validation_profile=validation_profile)

    # Perform candidate selection and validation
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

    # Build semantic equivalence result (needed for acceptance decision)
    semantic_equivalence = build_semantic_equivalence(
        original_sql=sql,
        rewritten_sql=selection.rewritten_sql,
        equivalence=selection.equivalence.to_contract(),
    )

    decision = build_acceptance_decision(
        selection.equivalence,
        selection.perf,
        validation_profile,
        rejected_placeholder_semantics,
        semantic_equivalence,
    )

    # LLM semantic equivalence check (optional)
    llm_semantic_result: dict[str, Any] = {}
    llm_semantic_warnings: list[str] = []
    llm_cfg = (config or {}).get("llm", {}) or {}
    if llm_cfg.get("enabled", False) and selection.rewritten_sql != sql:
        should_override, llm_warnings, llm_result = integrate_llm_semantic_check(
            original_sql=sql,
            rewritten_sql=selection.rewritten_sql,
            db_equivalence_result=selection.equivalence.to_contract(),
            llm_cfg=llm_cfg,
            config=config,
        )
        llm_semantic_result = llm_result
        llm_semantic_warnings = llm_warnings

    # Build simple decision layers
    equivalence_contract = selection.equivalence.to_contract()
    perf_contract = selection.perf.to_contract(reason_codes=decision.reason_codes)
    is_degraded = (
        not db_reachable
        or not compare_enabled
        or not bool(equivalence_contract.get("checked"))
        or not bool(perf_contract.get("checked"))
    )
    decision_layers = {
        "feasibility": {
            "candidateAvailable": len(valid_candidates) > 0,
            "dbReachable": db_reachable,
            "ready": len(valid_candidates) > 0 and db_reachable,
        },
        "evidence": {
            "semanticChecked": bool(equivalence_contract.get("checked")),
            "perfChecked": bool(perf_contract.get("checked")),
            "degraded": is_degraded,
        },
        "delivery": {
            "selectedCandidateSource": selected_source,
            "selectedCandidateId": selection.selected_candidate_id,
        },
        "acceptance": {
            "status": decision.status,
            "validationProfile": validation_profile,
        },
    }

    # Merge warnings
    all_warnings = list(decision.warnings) + llm_semantic_warnings

    return ValidationResult(
        sql_key=sql_unit["sqlKey"],
        status=decision.status,
        rewritten_sql=selection.rewritten_sql,
        equivalence=selection.equivalence.to_contract(),
        perf_comparison=selection.perf.to_contract(reason_codes=decision.reason_codes),
        security_checks={"dollar_substitution_removed": True},
        semantic_risk="low",
        feedback=decision.feedback,
        selected_candidate_source=selected_source,
        selected_candidate_id=selection.selected_candidate_id,
        candidate_evaluations=selection.candidate_evaluations_to_contract(),
        warnings=all_warnings,
        risk_flags=risk_flags,
        candidate_eval={
            "evaluated": len(selection.candidate_evaluations),
            "valid": len(valid_candidates),
            "improved": sum(1 for x in selection.candidate_evaluations if x.improved and x.semantic_match),
            "bestAfterCost": (selection.perf.after_summary or {}).get("totalCost"),
        },
        selection_rationale=selection.selection_rationale,
        decision_layers=decision_layers,
        llm_semantic_check=llm_semantic_result or None,
        semantic_equivalence=semantic_equivalence,
        canonicalization=selection.canonicalization,
    )