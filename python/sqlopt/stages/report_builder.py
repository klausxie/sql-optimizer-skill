from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..platforms.sql.materialization_constants import FRAGMENT_TEMPLATE_SAFE_AUTO
from ..run_paths import (
    REL_ARTIFACTS_ACCEPTANCE,
    REL_ARTIFACTS_PATCHES,
    REL_ARTIFACTS_PROPOSALS,
    REL_CONTROL_MANIFEST,
    REL_CONTROL_STATE,
    REL_REPORT_JSON,
    REL_SQL_CATALOG,
    canonical_paths,
    to_posix_relative,
)
from ..verification.summary import summarize_records
from .report_models import (
    ReportArtifacts,
    ReportInputs,
    RunReportDocument,
)
from .report_metrics import build_failures
from .report_metrics import summarize_semantic_gates
from .report_metrics import summarize_semantic_gate_quality
from .report_metrics import summarize_semantic_confidence_upgrades
from .report_metrics import build_verification_gate
from .report_metrics import count_llm_timeouts
from .report_metrics import summarize_failures
from .proposal_models import LLM_CANDIDATES_KEY
from .report_stats import (
    build_top_actionable_sql,
    build_prioritized_sql_keys,
    build_proposal_rows,
    build_sql_rows,
    blocker_family_for_patch_row,
    build_top_blockers,
    compute_release_readiness,
    compute_verdict,
    default_next_actions,
    materialization_mode_counts,
    materialization_reason_counts,
    materialization_reason_group_counts,
    report_acceptance_llm_count,
    summarize_actionability,
    _dynamic_template_profile,
)


def _patch_apply_ready(row: dict[str, Any]) -> bool:
    delivery_stage = str(row.get("deliveryStage") or "").strip().upper()
    if delivery_stage:
        return delivery_stage == "APPLY_READY"
    return row.get("applicable") is True


def _build_sql_artifact_rows(
    *,
    run_dir: Path,
    units: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
    acceptance: list[dict[str, Any]],
    patches: list[dict[str, Any]],
    verification_rows: list[dict[str, Any]],
    sql_outcomes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    paths = canonical_paths(run_dir)
    outcome_by_sql_key = {str(row.get("sql_key") or ""): row for row in sql_outcomes if str(row.get("sql_key") or "").strip()}
    proposal_by_sql_key = {str(row.get("sqlKey") or ""): row for row in proposals if str(row.get("sqlKey") or "").strip()}
    acceptance_by_sql_key = {str(row.get("sqlKey") or ""): row for row in acceptance if str(row.get("sqlKey") or "").strip()}
    patch_by_statement = {str(row.get("statementKey") or ""): row for row in patches if str(row.get("statementKey") or "").strip()}
    rows: list[dict[str, Any]] = []
    for unit in units:
        sql_key = str(unit.get("sqlKey") or "").strip()
        if not sql_key:
            continue
        statement_key = sql_key.split("#", 1)[0]
        outcome = outcome_by_sql_key.get(sql_key, {})
        acceptance_row = acceptance_by_sql_key.get(sql_key, {})
        proposal_row = proposal_by_sql_key.get(sql_key, {})
        patch_row = patch_by_statement.get(statement_key, {})
        sql_path = to_posix_relative(run_dir, paths.sql_artifact_dir(sql_key))
        trace_path = paths.sql_trace_path(sql_key)
        candidate_generation_diagnostics_path = paths.sql_candidate_generation_diagnostics_path(sql_key)
        evidence_dir = paths.sql_evidence_dir(sql_key)
        rows.append(
            {
                "sql_key": sql_key,
                "statement_key": statement_key,
                "sql_path": sql_path,
                "sql_index": f"{sql_path}/index.json",
                "delivery_status": outcome.get("delivery_status") or outcome.get("delivery_tier") or "BLOCKED",
                "blocker_primary_code": outcome.get("blocker_primary_code"),
                "blocker_family": outcome.get("blocker_family"),
                "aggregation_shape_family": outcome.get("aggregation_shape_family"),
                "aggregation_capability_tier": outcome.get("aggregation_capability_tier"),
                "aggregation_constraint_family": outcome.get("aggregation_constraint_family"),
                "aggregation_safe_baseline_family": outcome.get("aggregation_safe_baseline_family"),
                "dynamic_shape_family": outcome.get("dynamic_shape_family"),
                "dynamic_capability_tier": outcome.get("dynamic_capability_tier"),
                "dynamic_patch_surface": outcome.get("dynamic_patch_surface"),
                "dynamic_baseline_family": outcome.get("dynamic_baseline_family"),
                "dynamic_blocking_reason": outcome.get("dynamic_blocking_reason"),
                "dynamic_delivery_class": outcome.get("dynamic_delivery_class"),
                "evidence_availability": outcome.get("evidence_availability"),
                "artifact_refs": {
                    "report": REL_REPORT_JSON,
                    "acceptance": REL_ARTIFACTS_ACCEPTANCE if acceptance_row else None,
                    "patches": REL_ARTIFACTS_PATCHES if patch_row else None,
                    "proposals": REL_ARTIFACTS_PROPOSALS if proposal_row else None,
                    "verification": None,
                    "trace": f"{sql_path}/trace.optimize.llm.json" if trace_path.exists() else None,
                    "candidate_generation_diagnostics": f"{sql_path}/candidate_generation_diagnostics.json"
                    if candidate_generation_diagnostics_path.exists()
                    else None,
                    "evidence_dir": f"{sql_path}/evidence" if evidence_dir.exists() else None,
                },
            }
        )
    return rows


def _warning_codes(validation_warnings: list[str]) -> list[str]:
    codes: list[str] = []
    for warning in validation_warnings:
        code = str(warning).split(":", 1)[0].strip()
        if code:
            codes.append(code)
    return codes


def _compact_next_action(
    *,
    phase_status: dict[str, Any],
    stats: dict[str, Any],
    detailed_actions: list[dict[str, Any]],
) -> str:
    normalized_phase_status = {k: str(v or "").strip().upper() for k, v in phase_status.items()}
    incomplete_phases = [status for status in normalized_phase_status.values() if status in {"PENDING", "RUNNING", "FAILED"}]
    if incomplete_phases and normalized_phase_status.get("report") != "DONE":
        return "resume"
    if incomplete_phases:
        return "inspect"
    if stats.get("validation_warnings"):
        return "inspect"
    if int(stats.get("patch_applicable_count") or 0) > 0 and str(stats.get("blocked_sql_count") or 0) == "0":
        return "apply"
    if detailed_actions and str(detailed_actions[0].get("action_id") or "").strip() == "apply":
        return "apply"
    return "inspect"


def _compact_top_blockers(
    *,
    top_blockers: list[dict[str, Any]],
    validation_warnings: list[str],
) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    ordered_codes: list[str] = []
    for row in top_blockers:
        code = str(row.get("code") or "").strip()
        if not code:
            continue
        if code not in counts:
            ordered_codes.append(code)
        counts[code] = int(row.get("count") or 0)
    for code in _warning_codes(validation_warnings):
        if code not in counts:
            ordered_codes.append(code)
            counts[code] = 0
        counts[code] += 1
    ordered_codes.sort(key=lambda code: (-counts[code], code))
    return [{"code": code, "count": counts[code]} for code in ordered_codes[:5]]


def build_report_artifacts(
    run_id: str,
    mode: str,
    config: dict[str, Any],
    run_dir: Path,
    inputs: ReportInputs,
) -> ReportArtifacts:
    phase_status = dict(inputs.state.phase_status)
    llm_enabled = bool(config.get("llm", {}).get("enabled", False))
    llm_generated = sum(len(x.get(LLM_CANDIDATES_KEY, []) or []) for x in inputs.proposals)
    llm_timeout_count = count_llm_timeouts(run_dir, inputs.proposals)
    perf_improved_count = sum(
        1 for x in inputs.acceptance if x.get("status") == "PASS" and (x.get("perfComparison") or {}).get("improved") is True
    )
    perf_not_improved_count = sum(
        1 for x in inputs.acceptance if x.get("status") == "PASS" and (x.get("perfComparison") or {}).get("improved") is False
    )
    blocked_sql_count = sum(
        1
        for row in inputs.acceptance
        if str(row.get("status") or "").upper() != "PASS"
        or str(((row.get("semanticEquivalence") or {}).get("status") or "PASS")).upper() != "PASS"
        or str(((row.get("semanticEquivalence") or {}).get("confidence") or "HIGH")).upper() == "LOW"
    )
    repairable_blocked_count = sum(
        1
        for row in inputs.acceptance
        if str(row.get("status") or "").upper() != "PASS"
        and (
            str(((row.get("repairability") or {}).get("status") or "")).strip().upper() == "REPAIRABLE"
            or str(((row.get("feedback") or {}).get("reason_code") or "")).strip().upper() == "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION"
        )
    )
    patch_file_count = sum(len(x.get("patchFiles", [])) for x in inputs.patches)
    patch_applicable_count = sum(1 for x in inputs.patches if _patch_apply_ready(x))
    materialization_counts = materialization_mode_counts(inputs.acceptance)
    materialization_reason_counts_map = materialization_reason_counts(inputs.acceptance)
    materialization_reason_group_counts_map = materialization_reason_group_counts(materialization_reason_counts_map)
    patch_strategy_counts: dict[str, int] = {}
    canonical_rule_match_counts: dict[str, int] = {}
    aggregation_shape_counts: dict[str, int] = {}
    aggregation_constraint_counts: dict[str, int] = {}
    aggregation_safe_baseline_counts: dict[str, int] = {}
    aggregation_review_only_family_counts: dict[str, int] = {}
    aggregation_ready_family_counts: dict[str, int] = {}
    aggregation_ready_patch_count = 0
    dynamic_baseline_family_counts: dict[str, int] = {}
    dynamic_delivery_class_counts: dict[str, int] = {}
    dynamic_ready_baseline_family_counts: dict[str, int] = {}
    dynamic_ready_patch_count = 0
    dynamic_safe_baseline_blocked_count = 0
    dynamic_review_only_count = 0
    dml_review_only_count = 0
    aggregation_wrapper_review_only_count = 0
    no_safe_baseline_shape_match_count = 0
    canonical_preference_applied_count = 0
    candidate_degradation_counts: dict[str, int] = {}
    candidate_recovery_counts: dict[str, int] = {}
    empty_candidate_blocked_reason_counts: dict[str, int] = {}
    low_value_pruned_count = 0
    low_value_replaced_count = 0
    empty_candidate_recovered_count = 0
    text_fallback_recovered_count = 0
    patch_strategy_by_sql: dict[str, str] = {}
    patch_by_sql_key = {str((row.get("sqlKey") or "")).strip(): row for row in inputs.patches if str((row.get("sqlKey") or "")).strip()}
    unit_by_sql_key = {str((row.get("sqlKey") or "")).strip(): row for row in inputs.units}
    for row in inputs.acceptance:
        sql_key = str(row.get("sqlKey") or "").strip()
        strategy_type = str(((row.get("selectedPatchStrategy") or {}).get("strategyType") or "")).strip()
        if sql_key and strategy_type and sql_key not in patch_strategy_by_sql:
            patch_strategy_by_sql[sql_key] = strategy_type
    for row in inputs.patches:
        sql_key = str(row.get("sqlKey") or "").strip()
        strategy_type = str((row.get("strategyType") or row.get("dynamicTemplateStrategy") or "")).strip()
        if sql_key and strategy_type:
            patch_strategy_by_sql[sql_key] = strategy_type

    for row in inputs.acceptance:
        sql_key = str(row.get("sqlKey") or "").strip()
        patch_row = patch_by_sql_key.get(sql_key, {})
        canonical = dict(row.get("canonicalization") or {})
        canonical_rule = str(canonical.get("ruleId") or "").strip()
        if canonical_rule:
            canonical_rule_match_counts[canonical_rule] = canonical_rule_match_counts.get(canonical_rule, 0) + 1
        if bool(canonical.get("preferred")):
            canonical_preference_applied_count += 1
        aggregation_profile = dict((((row.get("rewriteFacts") or {}).get("aggregationQuery") or {}).get("capabilityProfile") or {}))
        shape_family = str(aggregation_profile.get("shapeFamily") or "").strip().upper()
        if shape_family and shape_family != "NONE":
            aggregation_shape_counts[shape_family] = aggregation_shape_counts.get(shape_family, 0) + 1
        constraint_family = str(aggregation_profile.get("constraintFamily") or "").strip().upper()
        if constraint_family and constraint_family != "NONE":
            aggregation_constraint_counts[constraint_family] = aggregation_constraint_counts.get(constraint_family, 0) + 1
        safe_baseline_family = str(aggregation_profile.get("safeBaselineFamily") or "").strip()
        if safe_baseline_family:
            aggregation_safe_baseline_counts[safe_baseline_family] = aggregation_safe_baseline_counts.get(safe_baseline_family, 0) + 1
            if patch_strategy_by_sql.get(sql_key) == "EXACT_TEMPLATE_EDIT":
                aggregation_ready_patch_count += 1
                aggregation_ready_family_counts[safe_baseline_family] = (
                    aggregation_ready_family_counts.get(safe_baseline_family, 0) + 1
                )
        review_only_family = str(aggregation_profile.get("reviewOnlyFamily") or "").strip()
        if review_only_family:
            aggregation_review_only_family_counts[review_only_family] = (
                aggregation_review_only_family_counts.get(review_only_family, 0) + 1
            )
        dynamic_template = _dynamic_template_profile(row, patch_row)
        dynamic_baseline_family = str(dynamic_template.get("baseline_family") or "").strip()
        if dynamic_baseline_family:
            dynamic_baseline_family_counts[dynamic_baseline_family] = dynamic_baseline_family_counts.get(dynamic_baseline_family, 0) + 1
        dynamic_delivery_class = str(dynamic_template.get("delivery_class") or "").strip()
        if dynamic_delivery_class:
            dynamic_delivery_class_counts[dynamic_delivery_class] = dynamic_delivery_class_counts.get(dynamic_delivery_class, 0) + 1
            normalized_dynamic_delivery_class = dynamic_delivery_class.upper()
            if normalized_dynamic_delivery_class == "READY_DYNAMIC_PATCH":
                dynamic_ready_patch_count += 1
                if dynamic_baseline_family:
                    dynamic_ready_baseline_family_counts[dynamic_baseline_family] = (
                        dynamic_ready_baseline_family_counts.get(dynamic_baseline_family, 0) + 1
                    )
            elif normalized_dynamic_delivery_class in {"SAFE_BASELINE_BLOCKED", "SAFE_BASELINE_NO_DIFF"}:
                dynamic_safe_baseline_blocked_count += 1
            elif normalized_dynamic_delivery_class == "REVIEW_ONLY":
                dynamic_review_only_count += 1
        sql_key = str(row.get("sqlKey") or "").strip()
        statement_type = str((unit_by_sql_key.get(sql_key) or {}).get("statementType") or "").strip().upper()
        if statement_type == "UPDATE" and str((row.get("patchability") or {}).get("blockingReason") or "").strip().upper() == "PATCH_NO_EFFECTIVE_CHANGE":
            dml_review_only_count += 1
        aggregation_profile = dict((((row.get("rewriteFacts") or {}).get("aggregationQuery") or {}).get("capabilityProfile") or {}))
        aggregation_constraint_family = str(aggregation_profile.get("constraintFamily") or "").strip().upper()
        aggregation_safe_baseline_family = str(aggregation_profile.get("safeBaselineFamily") or "").strip()
        if aggregation_constraint_family not in {"", "NONE", "SAFE_BASELINE"} and not aggregation_safe_baseline_family:
            aggregation_wrapper_review_only_count += 1
    for strategy_type in patch_strategy_by_sql.values():
        patch_strategy_counts[strategy_type] = patch_strategy_counts.get(strategy_type, 0) + 1
    for proposal in inputs.proposals:
        diagnostics = dict(proposal.get("candidateGenerationDiagnostics") or {})
        degradation_kind = str(diagnostics.get("degradationKind") or "").strip()
        if degradation_kind:
            candidate_degradation_counts[degradation_kind] = candidate_degradation_counts.get(degradation_kind, 0) + 1
        pruned_low_value = int(diagnostics.get("prunedLowValueCount") or 0)
        low_value_pruned_count += pruned_low_value
        if bool(diagnostics.get("recoverySucceeded")):
            recovery_strategy = str(diagnostics.get("recoveryStrategy") or "").strip() or "RECOVERY_SUCCEEDED"
            candidate_recovery_counts[recovery_strategy] = candidate_recovery_counts.get(recovery_strategy, 0) + 1
            if degradation_kind == "ONLY_LOW_VALUE_CANDIDATES":
                low_value_replaced_count += 1
            if degradation_kind == "EMPTY_CANDIDATES":
                empty_candidate_recovered_count += 1
            if degradation_kind == "TEXT_ONLY_FALLBACK":
                text_fallback_recovered_count += 1
        elif degradation_kind == "EMPTY_CANDIDATES":
            blocked_reason = str(diagnostics.get("recoveryReason") or "").strip()
            if blocked_reason:
                empty_candidate_blocked_reason_counts[blocked_reason] = (
                    empty_candidate_blocked_reason_counts.get(blocked_reason, 0) + 1
                )
                if blocked_reason == "NO_SAFE_BASELINE_SHAPE_MATCH":
                    no_safe_baseline_shape_match_count += 1
    semantic_gate_counts, semantic_gate_reason_counts = summarize_semantic_gates(inputs.acceptance)
    semantic_confidence_distribution, semantic_evidence_level_distribution, semantic_hard_conflict_top_codes = (
        summarize_semantic_gate_quality(inputs.acceptance)
    )
    confidence_upgraded_count, confidence_upgrade_by_evidence_source = summarize_semantic_confidence_upgrades(inputs.acceptance)
    confidence_upgrade_rate = (
        confidence_upgraded_count / len(inputs.acceptance)
        if inputs.acceptance
        else 0.0
    )
    uncertain_upgrade_count = sum(
        1
        for row in inputs.acceptance
        if bool(((row.get("semanticEquivalence") or {}).get("confidenceUpgradeApplied")))
        and str(((row.get("semanticEquivalence") or {}).get("status") or "")).strip().upper() == "PASS"
        and str(((row.get("semanticEquivalence") or {}).get("confidenceBeforeUpgrade") or "LOW")).strip().upper() in {"LOW", "UNKNOWN"}
    )
    semantic_false_block_recovered_count = sum(
        1
        for row in inputs.acceptance
        if bool(((row.get("semanticEquivalence") or {}).get("equivalenceOverrideApplied")))
    )
    include_safe_materialized_count = sum(
        1
        for row in inputs.acceptance
        if str(((row.get("rewriteMaterialization") or {}).get("mode") or "")).strip() == FRAGMENT_TEMPLATE_SAFE_AUTO
    )
    wrapper_collapse_recovered_count = patch_strategy_counts.get("SAFE_WRAPPER_COLLAPSE", 0)
    patchability_lift_rate = (
        repairable_blocked_count / blocked_sql_count
        if blocked_sql_count > 0
        else 0.0
    )

    generated_at = datetime.now(timezone.utc).isoformat()
    stats = {
        "sql_units": len(inputs.units),
        "proposals": len(inputs.proposals),
        "acceptance_pass": sum(1 for x in inputs.acceptance if x.get("status") == "PASS"),
        "pass_with_warn_count": sum(1 for x in inputs.acceptance if x.get("status") == "PASS" and (x.get("warnings") or [])),
        "acceptance_fail": sum(1 for x in inputs.acceptance if x.get("status") == "FAIL"),
        "acceptance_need_more_params": sum(1 for x in inputs.acceptance if x.get("status") == "NEED_MORE_PARAMS"),
        "semantic_error_count": sum(
            1 for x in inputs.acceptance if "VALIDATE_SEMANTIC_ERROR" in ((x.get("perfComparison") or {}).get("reasonCodes") or [])
        ),
        "semantic_gate_pass_count": semantic_gate_counts["pass"],
        "semantic_gate_fail_count": semantic_gate_counts["fail"],
        "semantic_gate_uncertain_count": semantic_gate_counts["uncertain"],
        "semantic_gate_reason_counts": semantic_gate_reason_counts,
        "semantic_confidence_distribution": semantic_confidence_distribution,
        "semantic_evidence_level_distribution": semantic_evidence_level_distribution,
        "semantic_hard_conflict_top_codes": semantic_hard_conflict_top_codes,
        "confidence_upgraded_count": confidence_upgraded_count,
        "confidence_upgrade_rate": round(confidence_upgrade_rate, 4),
        "confidence_upgrade_by_evidence_source": confidence_upgrade_by_evidence_source,
        "dollar_substitution_count": sum(1 for x in inputs.acceptance if "DOLLAR_SUBSTITUTION" in (x.get("riskFlags") or [])),
        "patch_files": patch_file_count,
        "patch_applicable_count": patch_applicable_count,
        "materialization_mode_counts": materialization_counts,
        "materialization_reason_counts": materialization_reason_counts_map,
        "materialization_reason_group_counts": materialization_reason_group_counts_map,
        "patch_strategy_counts": patch_strategy_counts,
        "canonical_rule_match_counts": canonical_rule_match_counts,
        "canonical_preference_applied_count": canonical_preference_applied_count,
        "candidate_degradation_counts": candidate_degradation_counts,
        "candidate_recovery_counts": candidate_recovery_counts,
        "low_value_pruned_count": low_value_pruned_count,
        "low_value_replaced_count": low_value_replaced_count,
        "empty_candidate_recovered_count": empty_candidate_recovered_count,
        "empty_candidate_blocked_reason_counts": empty_candidate_blocked_reason_counts,
        "text_fallback_recovered_count": text_fallback_recovered_count,
        "aggregation_shape_counts": aggregation_shape_counts,
        "aggregation_constraint_counts": aggregation_constraint_counts,
        "aggregation_safe_baseline_counts": aggregation_safe_baseline_counts,
        "aggregation_review_only_family_counts": aggregation_review_only_family_counts,
        "aggregation_ready_family_counts": aggregation_ready_family_counts,
        "aggregation_ready_patch_count": aggregation_ready_patch_count,
        "dynamic_baseline_family_counts": dynamic_baseline_family_counts,
        "dynamic_delivery_class_counts": dynamic_delivery_class_counts,
        "dynamic_ready_baseline_family_counts": dynamic_ready_baseline_family_counts,
        "dynamic_ready_patch_count": dynamic_ready_patch_count,
        "dynamic_safe_baseline_blocked_count": dynamic_safe_baseline_blocked_count,
        "dynamic_review_only_count": dynamic_review_only_count,
        "dml_review_only_count": dml_review_only_count,
        "aggregation_wrapper_review_only_count": aggregation_wrapper_review_only_count,
        "no_safe_baseline_shape_match_count": no_safe_baseline_shape_match_count,
        "perf_improved_count": perf_improved_count,
        "perf_compared_but_not_improved_count": perf_not_improved_count,
        "blocked_sql_count": blocked_sql_count,
        "repairable_blocked_count": repairable_blocked_count,
        "uncertain_upgrade_count": uncertain_upgrade_count,
        "semantic_false_block_recovered_count": semantic_false_block_recovered_count,
        "include_safe_materialized_count": include_safe_materialized_count,
        "wrapper_collapse_recovered_count": wrapper_collapse_recovered_count,
        "patchability_lift_rate": round(patchability_lift_rate, 4),
        "db_unreachable_count": sum(
            1 for x in inputs.acceptance if "VALIDATE_DB_UNREACHABLE" in (x.get("perfComparison", {}).get("reasonCodes") or [])
        ),
        "llm_candidates_generated": llm_generated,
        "llm_candidates_accepted": report_acceptance_llm_count(inputs.acceptance),
        "llm_candidates_rejected": max(llm_generated - report_acceptance_llm_count(inputs.acceptance), 0),
        "llm_timeout_count": llm_timeout_count,
        "preflight_failure_count": 0,
        "phase_reason_code_counts": {},
        "ineffective_reason_counts": {},
        "fatal_count": 0,
        "retryable_count": 0,
        "degradable_count": 0,
    }

    failures = build_failures(inputs.acceptance, inputs.manifest_rows)
    stats["preflight_failure_count"] = sum(
        1 for row in inputs.manifest_rows if row.stage == "preflight" and row.event == "failed"
    )
    reason_counts, phase_reason_counts, class_counts = summarize_failures(failures)
    stats["ineffective_reason_counts"] = reason_counts
    stats["phase_reason_code_counts"] = phase_reason_counts
    stats["fatal_count"] = class_counts.get("fatal", 0)
    stats["retryable_count"] = class_counts.get("retryable", 0)
    stats["degradable_count"] = class_counts.get("degradable", 0)
    stats["pipeline_coverage"] = phase_status
    verification_summary = summarize_records(run_id, inputs.verification_rows, total_sql=len(inputs.units)).to_contract()
    stats["verification"] = {k: v for k, v in verification_summary.items() if k != "generated_at"}
    validation_warnings, evidence_confidence, verification_gate = build_verification_gate(
        inputs.acceptance,
        inputs.patches,
        inputs.verification_rows,
    )
    stats["verification"].update(verification_gate)
    stats["validation_warnings"] = validation_warnings
    stats["evidence_confidence"] = evidence_confidence
    stats["actionability"] = summarize_actionability(inputs.proposals, inputs.acceptance, inputs.patches)
    all_sql_outcomes = build_top_actionable_sql(
        inputs.units,
        inputs.proposals,
        inputs.acceptance,
        inputs.patches,
        inputs.verification_rows,
        limit=None,
    )
    blocker_family_counts = {}
    blocker_family_rows = inputs.patches if inputs.patches else all_sql_outcomes
    if inputs.patches:
        for row in blocker_family_rows:
            family = blocker_family_for_patch_row(row)
            if family:
                blocker_family_counts[family] = blocker_family_counts.get(family, 0) + 1
    else:
        for row in blocker_family_rows:
            family = str(row.get("blocker_family") or "").strip().upper()
            if family:
                blocker_family_counts[family] = blocker_family_counts.get(family, 0) + 1
    stats["blocker_family_counts"] = blocker_family_counts
    stats["top_actionable_sql"] = all_sql_outcomes[:10]
    sql_artifact_rows = _build_sql_artifact_rows(
        run_dir=run_dir,
        units=inputs.units,
        proposals=inputs.proposals,
        acceptance=inputs.acceptance,
        patches=inputs.patches,
        verification_rows=inputs.verification_rows,
        sql_outcomes=all_sql_outcomes,
    )

    verdict = compute_verdict(stats)
    failure_rows = [row.to_contract() for row in failures]
    top_blockers = build_top_blockers(failure_rows, reason_counts)

    sql_rows = build_sql_rows(inputs.units, inputs.acceptance, inputs.patches)
    proposal_rows = build_proposal_rows(inputs.proposals)
    next_actions = default_next_actions(
        run_id,
        verdict,
        reason_counts,
        top_actionable_sql=stats["top_actionable_sql"],
        verification=stats["verification"],
    )
    compact_phase_status = dict(phase_status)
    compact_phase_status["report"] = "DONE"
    compact_top_blockers = _compact_top_blockers(
        top_blockers=top_blockers,
        validation_warnings=validation_warnings,
    )

    report = RunReportDocument(
        run_id=run_id,
        generated_at=generated_at,
        target_stage="report",
        status="DONE",
        verdict=verdict,
        next_action=_compact_next_action(
            phase_status=compact_phase_status,
            stats=stats,
            detailed_actions=next_actions,
        ),
        phase_status=compact_phase_status,
        stats=stats,
        top_blockers=compact_top_blockers,
        selection_scope=inputs.state.selection_scope,
        validation_warnings=validation_warnings or None,
        evidence_confidence=evidence_confidence,
    )

    return ReportArtifacts(
        report=report,
        failures=failures,
        state=inputs.state,
        next_actions=next_actions,
        top_blockers=top_blockers,
        sql_rows=sql_rows,
        proposal_rows=proposal_rows,
        diagnostics_sql_outcomes=all_sql_outcomes,
        diagnostics_sql_artifacts=sql_artifact_rows,
        verification_summary=verification_summary,
        validation_warnings=validation_warnings or None,
        evidence_confidence=evidence_confidence,
    )
