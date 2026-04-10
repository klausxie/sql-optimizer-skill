from __future__ import annotations

from typing import Any

from ..dispatch import collect_sql_evidence


def _estimate_actionability(sql_unit: dict[str, Any]) -> dict[str, Any]:
    """Estimate actionability of a SQL unit for automatic optimization."""
    sql = str(sql_unit.get("sql") or "")
    dynamic_features = [str(x) for x in (sql_unit.get("dynamicFeatures") or []) if str(x).strip()]

    if "${" in sql:
        return {
            "score": 0,
            "tier": "BLOCKED",
            "autoPatchLikelihood": "LOW",
            "reasons": ["unsafe dynamic substitution blocks safe auto-fix"],
            "blockedBy": ["DOLLAR_SUBSTITUTION"],
        }

    score = 70
    reasons: list[str] = []

    if dynamic_features:
        score -= 20
        reasons.append("dynamic mapper structure reduces patch stability")
    if "INCLUDE" in dynamic_features:
        score -= 10
        reasons.append("include fragments reduce direct patchability")
    if not dynamic_features:
        score += 10
        reasons.append("static statement is easier to patch automatically")

    score = max(0, min(score, 100))
    if score == 0:
        tier = "BLOCKED"
    elif score >= 80:
        tier = "HIGH"
    elif score >= 60:
        tier = "MEDIUM"
    else:
        tier = "LOW"

    if tier == "BLOCKED":
        auto_patch_likelihood = "LOW"
    elif not dynamic_features:
        auto_patch_likelihood = "HIGH"
    elif "INCLUDE" in dynamic_features:
        auto_patch_likelihood = "LOW"
    else:
        auto_patch_likelihood = "MEDIUM"

    return {
        "score": score,
        "tier": tier,
        "autoPatchLikelihood": auto_patch_likelihood,
        "reasons": reasons,
        "blockedBy": [],
    }


def _build_dynamic_surface_contract(sql_unit: dict[str, Any]) -> dict[str, Any]:
    identity = sql_unit.get("dynamicRenderIdentity") or {}
    surface = str(identity.get("surfaceType") or "").strip().upper()
    if surface != "CHOOSE_BRANCH_BODY":
        return {}
    contract = {
        "targetSurface": "CHOOSE_BRANCH_BODY",
        "branchLocalOnly": True,
        "forbidSetOperations": True,
        "forbidBranchMerge": True,
        "forbidWholeStatementRewrite": True,
        "forbidIndexAdvisoryOnly": True,
        "forbidFlattenedPredicateRewrite": True,
        "forbidDefaultBranchReduction": True,
        "returnNoCandidateWhenContractUnsatisfied": True,
        "allowedTemplateRewriteOps": ["replace_choose_branch_body"],
        "preferredOutcome": "BRANCH_LOCAL_CLEANUP_OR_NO_CANDIDATE",
    }
    rendered_branch_sql = str(identity.get("renderedBranchSql") or "").strip()
    if rendered_branch_sql:
        contract["renderedBranchSql"] = rendered_branch_sql
    branch_ordinal = identity.get("branchOrdinal")
    if branch_ordinal is not None:
        contract["branchOrdinal"] = branch_ordinal
    return contract


def build_optimize_prompt(
    sql_unit: dict[str, Any],
    proposal: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build optimization prompt for LLM.

    Args:
        sql_unit: SQL unit to analyze
        proposal: Current proposal with issues and suggestions
        config: Full configuration (optional)

    Returns:
        Prompt dictionary for LLM
    """
    db_summary = proposal.get("dbEvidenceSummary", {}) or {}
    dynamic_surface_contract = _build_dynamic_surface_contract(sql_unit)

    prompt = {
        "task": "sql_optimize_candidate_generation",
        "sqlKey": sql_unit["sqlKey"],
        "requiredContext": {
            "sql": sql_unit["sql"],
            "templateSql": sql_unit.get("templateSql", ""),
            "dynamicFeatures": sql_unit.get("dynamicFeatures", []),
            "riskFlags": sql_unit.get("riskFlags", []),
            "issues": proposal.get("issues", []),
            "tables": db_summary.get("tables", []),
            "indexes": (db_summary.get("indexes", []) or [])[:20],
        },
        "optionalContext": {
            "includeTrace": sql_unit.get("includeTrace", []),
            "dynamicTrace": sql_unit.get("dynamicTrace") or {},
            "dynamicRenderIdentity": sql_unit.get("dynamicRenderIdentity") or {},
            "columns": (db_summary.get("columns", []) or [])[:100],
            "tableStats": db_summary.get("tableStats", []),
            "planSummary": proposal.get("planSummary", {}) or {},
        },
        "rewriteConstraints": {
            "forbidMultiStatement": True,
            "preserveParameterSemantics": True,
            "dynamicTemplateRequiresTemplateAwarePatch": bool(sql_unit.get("dynamicFeatures")),
            "mustProduceCandidateTypes": ["SECURITY_FIX", "PLAN_IMPROVE", "CONSERVATIVE_NOOP_PLUS"],
            "dynamicSurfaceContract": dynamic_surface_contract,
        },
    }

    return prompt


def build_optimize_replay_request(
    sql_unit: dict[str, Any],
    proposal: dict[str, Any],
    llm_cfg: dict[str, Any],
) -> dict[str, Any]:
    """Build the stable replay request used for optimize-stage cassette fingerprinting."""
    db_summary = proposal.get("dbEvidenceSummary", {}) or {}
    provider = str(llm_cfg.get("provider") or "opencode_builtin").strip()
    model = str(llm_cfg.get("opencode_model") or llm_cfg.get("api_model") or llm_cfg.get("model") or provider or "").strip()
    dynamic_surface_contract = _build_dynamic_surface_contract(sql_unit)

    return {
        "sqlKey": sql_unit["sqlKey"],
        "sql": sql_unit["sql"],
        "templateSql": sql_unit.get("templateSql", ""),
        "dynamicFeatures": sql_unit.get("dynamicFeatures", []),
        "dynamicRenderIdentity": sql_unit.get("dynamicRenderIdentity") or {},
        "dynamicTrace": sql_unit.get("dynamicTrace") or {},
        "dynamicSurfaceContract": dynamic_surface_contract,
        "stableDbEvidence": {
            "tables": db_summary.get("tables", []),
            "indexes": db_summary.get("indexes", []),
            "planSummary": proposal.get("planSummary", {}) or {},
        },
        "promptVersion": str(llm_cfg.get("prompt_version") or llm_cfg.get("promptVersion") or "v1"),
        "provider": provider,
        "model": model,
    }


def generate_proposal(sql_unit: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Generate optimization proposal for a SQL unit.

    Args:
        sql_unit: SQL unit to analyze
        config: Configuration dictionary

    Returns:
        Proposal dictionary with issues, suggestions, and actionability
    """
    db_evidence, plan_summary = collect_sql_evidence(config, sql_unit["sql"])
    proposal = {
        "sqlKey": sql_unit["sqlKey"],
        "issues": [],
        "dbEvidenceSummary": db_evidence,
        "planSummary": plan_summary if plan_summary else {"risk": "none"},
        "suggestions": [],
        "verdict": "NOOP",
        "confidence": "medium",
        "estimatedBenefit": "unknown",
        "triggeredRules": [],
    }
    proposal["actionability"] = _estimate_actionability(sql_unit)
    proposal["recommendedSuggestionIndex"] = None
    return proposal
