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
            "columns": (db_summary.get("columns", []) or [])[:100],
            "tableStats": db_summary.get("tableStats", []),
            "planSummary": proposal.get("planSummary", {}) or {},
        },
        "rewriteConstraints": {
            "forbidMultiStatement": True,
            "preserveParameterSemantics": True,
            "dynamicTemplateRequiresTemplateAwarePatch": bool(sql_unit.get("dynamicFeatures")),
            "mustProduceCandidateTypes": ["SECURITY_FIX", "PLAN_IMPROVE", "CONSERVATIVE_NOOP_PLUS"],
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

    return {
        "sqlKey": sql_unit["sqlKey"],
        "sql": sql_unit["sql"],
        "templateSql": sql_unit.get("templateSql", ""),
        "dynamicFeatures": sql_unit.get("dynamicFeatures", []),
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
