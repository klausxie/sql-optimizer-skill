from __future__ import annotations

from pathlib import Path
from typing import Any

from ..dispatch import compare_plan, compare_semantics
from .template_materializer import build_rewrite_materialization


def _numeric_cost(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return float("inf")


def _is_valid_candidate_sql(sql: Any) -> bool:
    if not isinstance(sql, str):
        return False
    stripped = sql.strip()
    return bool(stripped) and "${" not in stripped


def _preserves_mybatis_placeholders(original_sql: str, rewritten_sql: str) -> bool:
    if "#{" not in str(original_sql):
        return True
    rewritten = str(rewritten_sql or "")
    if "#{" in rewritten:
        return True
    return "?" not in rewritten


def _build_candidate_pool(sql_key: str, proposal: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen_sql: set[str] = set()
    for i, row in enumerate(proposal.get("llmCandidates") or [], start=1):
        if not isinstance(row, dict):
            continue
        rewritten = str(row.get("rewrittenSql") or "").strip()
        if not rewritten or rewritten in seen_sql:
            continue
        seen_sql.add(rewritten)
        out.append(
            {
                "id": str(row.get("id") or f"{sql_key}:llm:c{i}"),
                "source": "llm",
                "rewrittenSql": rewritten,
                "rewriteStrategy": str(row.get("rewriteStrategy") or "llm"),
            }
        )
    for i, row in enumerate(proposal.get("suggestions") or [], start=1):
        if not isinstance(row, dict):
            continue
        rewritten = str(row.get("sql") or "").strip()
        if not rewritten or rewritten in seen_sql:
            continue
        seen_sql.add(rewritten)
        out.append(
            {
                "id": f"{sql_key}:rule:c{i}",
                "source": "rule",
                "rewrittenSql": rewritten,
                "rewriteStrategy": str(row.get("action") or "rule"),
            }
        )
    return out


def _security_failure_result(sql_key: str, validation_profile: str, risk_flags: list[str]) -> dict[str, Any]:
    status = "FAIL" if validation_profile == "strict" else "NEED_MORE_PARAMS"
    return {
        "sqlKey": sql_key,
        "status": status,
        "equivalence": {"checked": True, "method": "static", "evidenceRefs": []},
        "perfComparison": {"checked": False, "reasonCodes": ["VALIDATE_SECURITY_DOLLAR_SUBSTITUTION"], "improved": None},
        "securityChecks": {"dollar_substitution_removed": False},
        "semanticRisk": "high",
        "feedback": {"reason_code": "VALIDATE_SECURITY_DOLLAR_SUBSTITUTION", "message": "unsafe ${} pattern"},
        "selectedCandidateSource": "rule",
        "warnings": ["VALIDATE_SECURITY_DOLLAR_SUBSTITUTION"] if status != "FAIL" else [],
        "riskFlags": risk_flags,
    }


def _invalid_candidate_result(sql_key: str, risk_flags: list[str]) -> dict[str, Any]:
    return {
        "sqlKey": sql_key,
        "status": "FAIL",
        "equivalence": {"checked": True, "method": "candidate_sanity", "evidenceRefs": []},
        "perfComparison": {"checked": False, "reasonCodes": ["VALIDATE_EQUIVALENCE_MISMATCH"], "improved": None},
        "securityChecks": {"dollar_substitution_removed": False},
        "semanticRisk": "high",
        "feedback": {"reason_code": "VALIDATE_EQUIVALENCE_MISMATCH", "message": "invalid candidate sql"},
        "selectedCandidateSource": "llm",
        "warnings": [],
        "riskFlags": risk_flags,
    }


def _db_unreachable_result(sql_key: str, risk_flags: list[str]) -> dict[str, Any]:
    return {
        "sqlKey": sql_key,
        "status": "NEED_MORE_PARAMS",
        "equivalence": {"checked": None, "method": "none", "evidenceRefs": []},
        "perfComparison": {"checked": False, "reasonCodes": ["VALIDATE_DB_UNREACHABLE"], "improved": None},
        "securityChecks": {"dollar_substitution_removed": True},
        "semanticRisk": "medium",
        "feedback": {"reason_code": "VALIDATE_PARAM_INSUFFICIENT", "message": "db not reachable"},
        "selectedCandidateSource": "rule",
        "warnings": [],
        "riskFlags": risk_flags,
    }


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
    candidates = _build_candidate_pool(sql_unit["sqlKey"], proposal)
    valid_candidates: list[dict[str, Any]] = []
    rejected_placeholder_semantics = 0
    for candidate in candidates:
        rewritten = str((candidate or {}).get("rewrittenSql") or "")
        if not _is_valid_candidate_sql(rewritten):
            continue
        if not _preserves_mybatis_placeholders(sql, rewritten):
            rejected_placeholder_semantics += 1
            continue
        valid_candidates.append(candidate)

    if risk == "high":
        return _security_failure_result(sql_unit["sqlKey"], validation_profile, risk_flags)
    if candidates and not valid_candidates and rejected_placeholder_semantics == 0:
        return _invalid_candidate_result(sql_unit["sqlKey"], risk_flags)
    if not db_reachable:
        return _db_unreachable_result(sql_unit["sqlKey"], risk_flags)

    candidate_sql = (valid_candidates[0] or {}).get("rewrittenSql") if valid_candidates else None
    rewritten_sql = candidate_sql if isinstance(candidate_sql, str) and candidate_sql.strip() else sql
    equivalence = {"checked": True, "method": "static", "evidenceRefs": []}
    perf = {
        "checked": True,
        "method": "heuristic",
        "beforeSummary": {},
        "afterSummary": {},
        "reasonCodes": [],
        "improved": bool(proposal.get("suggestions")),
        "evidenceRefs": [],
    }
    selected_candidate_id = None
    candidate_evaluations: list[dict[str, Any]] = []
    selected_candidate_source = None
    if config and evidence_dir is not None and (config.get("db", {}) or {}).get("dsn"):
        if valid_candidates:
            best: dict[str, Any] | None = None
            best_cost = float("inf")
            fallback: dict[str, Any] | None = None
            fallback_cost = float("inf")
            for idx, candidate in enumerate(valid_candidates[:5], start=1):
                rewritten_candidate = str((candidate or {}).get("rewrittenSql") or "").strip()
                if not rewritten_candidate:
                    continue
                candidate_dir = evidence_dir / f"candidate_{idx}"
                semantics = compare_semantics(config, sql, rewritten_candidate, candidate_dir)
                plan = compare_plan(config, sql, rewritten_candidate, candidate_dir)
                row_status = ((semantics.get("rowCount") or {}) if isinstance(semantics, dict) else {}).get("status")
                semantic_match = row_status == "MATCH"
                improved_now = bool(plan.get("improved"))
                after_cost = _numeric_cost((plan.get("afterSummary") or {}).get("totalCost"))
                eval_row = {
                    "candidateId": (candidate or {}).get("id"),
                    "source": (candidate or {}).get("source"),
                    "semanticMatch": semantic_match,
                    "improved": improved_now,
                    "afterCost": None if after_cost == float("inf") else after_cost,
                }
                candidate_evaluations.append(eval_row)
                payload = {"candidate": candidate, "semantics": semantics, "plan": plan, "sql": rewritten_candidate}
                if semantic_match and after_cost < fallback_cost:
                    fallback = payload
                    fallback_cost = after_cost
                elif fallback is None:
                    fallback = payload
                if semantic_match and improved_now and after_cost < best_cost:
                    best = payload
                    best_cost = after_cost
            selected = best or fallback
            if selected is not None:
                picked = selected["candidate"] or {}
                rewritten_sql = str(selected["sql"])
                selected_candidate_id = picked.get("id")
                selected_candidate_source = picked.get("source")
                semantics = selected["semantics"] or {}
                plan = selected["plan"] or {}
                equivalence = {
                    "checked": semantics.get("checked"),
                    "method": semantics.get("method", "sql_semantic_compare_v1"),
                    "rowCount": semantics.get("rowCount"),
                    "evidenceRefs": semantics.get("evidenceRefs", []),
                }
                perf = {
                    "checked": plan.get("checked"),
                    "method": plan.get("method", "sql_explain_json_compare"),
                    "beforeSummary": plan.get("beforeSummary"),
                    "afterSummary": plan.get("afterSummary"),
                    "reasonCodes": plan.get("reasonCodes", []),
                    "improved": plan.get("improved"),
                    "evidenceRefs": plan.get("evidenceRefs", []),
                }
        else:
            semantics = compare_semantics(config, sql, rewritten_sql, evidence_dir)
            plan = compare_plan(config, sql, rewritten_sql, evidence_dir)
            equivalence = {
                "checked": semantics.get("checked"),
                "method": semantics.get("method", "sql_semantic_compare_v1"),
                "rowCount": semantics.get("rowCount"),
                "evidenceRefs": semantics.get("evidenceRefs", []),
            }
            perf = {
                "checked": plan.get("checked"),
                "method": plan.get("method", "sql_explain_json_compare"),
                "beforeSummary": plan.get("beforeSummary"),
                "afterSummary": plan.get("afterSummary"),
                "reasonCodes": plan.get("reasonCodes", []),
                "improved": plan.get("improved"),
                "evidenceRefs": plan.get("evidenceRefs", []),
            }

    improved = bool(perf.get("improved"))
    selected_source = str(selected_candidate_source or ("llm" if llm_candidates else "rule"))
    existing_reason_codes = list(perf.get("reasonCodes") or [])
    reason_codes: list[str] = existing_reason_codes
    warnings: list[str] = []
    feedback: dict[str, Any] | None = None
    row_status = ((equivalence.get("rowCount") or {}) if isinstance(equivalence, dict) else {}).get("status")
    semantic_error = row_status == "ERROR"
    semantic_mismatch = row_status == "MISMATCH"
    semantic_match = row_status == "MATCH"
    if semantic_mismatch:
        status = "FAIL"
        if "VALIDATE_EQUIVALENCE_MISMATCH" not in reason_codes:
            reason_codes.append("VALIDATE_EQUIVALENCE_MISMATCH")
        feedback = {"reason_code": "VALIDATE_EQUIVALENCE_MISMATCH", "message": "semantic mismatch"}
    elif semantic_error:
        status = "NEED_MORE_PARAMS"
        if "VALIDATE_SEMANTIC_ERROR" not in reason_codes:
            reason_codes.append("VALIDATE_SEMANTIC_ERROR")
        feedback = {"reason_code": "VALIDATE_SEMANTIC_ERROR", "message": "semantic check error, manual review required"}
    elif improved:
        status = "PASS"
    elif semantic_match and validation_profile in {"balanced", "relaxed"}:
        status = "PASS"
        warnings.append("VALIDATE_PERF_NOT_IMPROVED_WARN")
        if "VALIDATE_PERF_NOT_IMPROVED_WARN" not in reason_codes:
            reason_codes.append("VALIDATE_PERF_NOT_IMPROVED_WARN")
    else:
        status = "NEED_MORE_PARAMS"
        if "VALIDATE_PERF_NOT_IMPROVED" not in reason_codes:
            reason_codes.append("VALIDATE_PERF_NOT_IMPROVED")
        feedback = {"reason_code": "VALIDATE_PERF_NOT_IMPROVED", "message": "no proven performance gain"}
    if rejected_placeholder_semantics:
        warnings.append("VALIDATE_PLACEHOLDER_SEMANTICS_MISMATCH_WARN")

    rewrite_materialization, template_rewrite_ops = _derive_rewrite_materialization(
        sql_unit,
        rewritten_sql,
        fragment_catalog or {},
        config,
    )

    return {
        "sqlKey": sql_unit["sqlKey"],
        "status": status,
        "rewrittenSql": rewritten_sql,
        "equivalence": equivalence,
        "perfComparison": {**perf, "reasonCodes": reason_codes},
        "securityChecks": {"dollar_substitution_removed": True},
        "semanticRisk": "low",
        "feedback": feedback,
        "selectedCandidateSource": selected_source,
        "selectedCandidateId": selected_candidate_id,
        "candidateEvaluations": candidate_evaluations,
        "warnings": warnings,
        "riskFlags": risk_flags,
        "rewriteMaterialization": rewrite_materialization,
        "templateRewriteOps": template_rewrite_ops,
        "candidateEval": {
            "evaluated": len(candidate_evaluations),
            "valid": len(valid_candidates),
            "improved": sum(1 for x in candidate_evaluations if x.get("improved") and x.get("semanticMatch")),
            "bestAfterCost": (perf.get("afterSummary") or {}).get("totalCost"),
        },
    }
