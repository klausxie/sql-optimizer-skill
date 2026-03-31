"""SQL validation logic for the validate stage.

This module is responsible for:
- Candidate pool building and filtering
- Semantic equivalence checking
- Performance comparison
- LLM semantic check integration
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
from .models import AcceptanceDecision, ValidationResult
from .candidate_selection import (
    build_candidate_pool,
    evaluate_candidate_selection,
    filter_valid_candidates,
)
from .semantic_equivalence import build_semantic_equivalence
from .validation_strategy import build_compare_policy, run_plan_compare, run_semantics_compare
from .llm_semantic_check import integrate_llm_semantic_check


def _validate_strategy(validate_cfg: dict[str, Any]) -> dict[str, Any]:
    return {
        "selection_mode": str(validate_cfg.get("selection_mode", "patchability_first")).strip().lower() or "patchability_first",
        "require_semantic_match": bool(validate_cfg.get("require_semantic_match", True)),
        "require_perf_evidence_for_pass": bool(validate_cfg.get("require_perf_evidence_for_pass", False)),
        "require_verified_evidence_for_pass": bool(validate_cfg.get("require_verified_evidence_for_pass", False)),
        "delivery_bias": str(validate_cfg.get("delivery_bias", "conservative")).strip().lower() or "conservative",
    }


def _build_decision_layers(
    *,
    status: str,
    validation_profile: str,
    strategy: dict[str, Any],
    db_reachable: bool,
    compare_enabled: bool,
    selected_candidate_source: str,
    selected_candidate_id: str | None,
    valid_candidate_count: int,
    selected_candidate_count: int,
    equivalence: dict[str, Any],
    perf_comparison: dict[str, Any],
    feedback: dict[str, Any] | None,
) -> dict[str, Any]:
    reason_codes = [str(code) for code in (perf_comparison.get("reasonCodes") or []) if str(code).strip()]
    return {
        "feasibility": {
            "candidateAvailable": valid_candidate_count > 0,
            "validCandidateCount": valid_candidate_count,
            "selectedCandidateCount": selected_candidate_count,
            "dbReachable": db_reachable,
            "compareEnabled": compare_enabled,
            "ready": valid_candidate_count > 0 and db_reachable,
        },
        "evidence": {
            "semanticChecked": bool(equivalence.get("checked")),
            "perfChecked": bool(perf_comparison.get("checked")),
            "degraded": (not db_reachable)
            or (not compare_enabled)
            or (not bool(equivalence.get("checked")))
            or (not bool(perf_comparison.get("checked"))),
            "reasonCodes": reason_codes,
        },
        "delivery": {
            "selectedCandidateSource": selected_candidate_source or None,
            "selectedCandidateId": selected_candidate_id,
            "selectionMode": strategy["selection_mode"],
            "deliveryBias": strategy["delivery_bias"],
        },
        "acceptance": {
            "status": status,
            "validationProfile": validation_profile,
            "requireSemanticMatch": strategy["require_semantic_match"],
            "requirePerfEvidenceForPass": strategy["require_perf_evidence_for_pass"],
            "requireVerifiedEvidenceForPass": strategy["require_verified_evidence_for_pass"],
            "feedbackReasonCode": (feedback or {}).get("reason_code"),
        },
    }


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
    It does NOT evaluate patchability - that is handled by patch_generate stage.
    It does NOT compute rewrite_facts - that is handled by patch_select stage.

    Args:
        sql_unit: The SQL unit being validated
        proposal: The optimization proposal with candidates
        db_reachable: Whether database is reachable for validation
        config: Configuration dictionary
        evidence_dir: Directory for evidence storage

    Returns:
        ValidationResult with validation status and evidence

    Raises:
        ValueError: If db.dsn is not configured in config
    """
    sql = sql_unit["sql"]
    validate_cfg = (config.get("validate", {}) if isinstance(config, dict) else {}) or {}
    validation_profile = str(validate_cfg.get("validation_profile", "balanced")).strip().lower()
    if validation_profile not in {"strict", "balanced", "relaxed"}:
        validation_profile = "balanced"
    strategy = _validate_strategy(validate_cfg)
    risk = "high" if "${" in sql else "low"
    risk_flags = ["DOLLAR_SUBSTITUTION"] if risk == "high" else []
    llm_candidates = proposal.get("llmCandidates") or []
    candidates = build_candidate_pool(sql_unit["sqlKey"], proposal)
    valid_candidates, rejected_placeholder_semantics = filter_valid_candidates(sql, candidates)

    # Early exit cases
    if risk == "high":
        return security_failure_result(sql_unit["sqlKey"], validation_profile, risk_flags, **strategy)
    if candidates and not valid_candidates and rejected_placeholder_semantics == 0:
        return invalid_candidate_result(sql_unit["sqlKey"], risk_flags, validation_profile=validation_profile, **strategy)
    if not db_reachable:
        return db_unreachable_result(sql_unit["sqlKey"], risk_flags, validation_profile=validation_profile, **strategy)

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
    decision = build_acceptance_decision(
        selection.equivalence,
        selection.perf,
        validation_profile,
        rejected_placeholder_semantics,
    )

    # Phase 3: LLM semantic equivalence check (optional)
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

    # Build semantic equivalence result
    semantic_equivalence = build_semantic_equivalence(
        original_sql=sql,
        rewritten_sql=selection.rewritten_sql,
        equivalence=selection.equivalence.to_contract(),
    )

    # Determine rewrite safety level based on semantic gate
    semantic_gate_status = str(semantic_equivalence.get("status") or "PASS").strip().upper()
    semantic_gate_confidence = str(semantic_equivalence.get("confidence") or "HIGH").strip().upper()

    # If semantic gate passes with sufficient confidence and decision is not PASS,
    # check if we can upgrade to PASS (candidate is valid but performance not improved)
    if (
        decision.status != "PASS"
        and semantic_gate_status == "PASS"
        and semantic_gate_confidence in {"MEDIUM", "HIGH"}
    ):
        # Allow PASS if semantic gate passes, even without performance improvement
        # This is for cases where the rewrite is semantically correct but may not be faster
        filtered_reason_codes = [
            str(code)
            for code in (decision.reason_codes or [])
            if str(code).strip().upper() != "VALIDATE_SEMANTIC_ERROR"
        ]
        filtered_warnings = list(decision.warnings)
        if decision.status == "NEED_MORE_PARAMS":
            filtered_warnings.append("VALIDATE_PERF_NOT_IMPROVED_BUT_SEMANTIC_OK")
        decision = AcceptanceDecision(
            status="PASS",
            feedback=None,
            warnings=filtered_warnings,
            reason_codes=filtered_reason_codes,
        )

    # Build decision layers for traceability
    decision_layers = _build_decision_layers(
        status=decision.status,
        validation_profile=validation_profile,
        strategy=strategy,
        db_reachable=db_reachable,
        compare_enabled=compare_enabled,
        selected_candidate_source=selected_source,
        selected_candidate_id=selection.selected_candidate_id,
        valid_candidate_count=len(valid_candidates),
        selected_candidate_count=len(selection.candidate_evaluations),
        equivalence=selection.equivalence.to_contract(),
        perf_comparison=selection.perf.to_contract(reason_codes=decision.reason_codes),
        feedback=decision.feedback,
    )

    # Merge warnings
    all_warnings = list(decision.warnings) + llm_semantic_warnings

    # Note: rewrite_facts is computed by patch_select stage, not validate
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
        candidate_selection_trace=selection.candidate_selection_trace,
    )