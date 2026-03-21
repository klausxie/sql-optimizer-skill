from __future__ import annotations

from typing import Any

from ..dispatch import collect_sql_evidence
from .rules import evaluate_rules

_ROW_SENSITIVE_RULES = {"SELECT_STAR", "FULL_SCAN_RISK", "NO_LIMIT"}


def _max_estimated_rows(table_stats: list[dict[str, Any]] | None) -> int | None:
    values: list[int] = []
    for row in table_stats or []:
        if not isinstance(row, dict):
            continue
        raw_value = row.get("estimatedRows")
        if isinstance(raw_value, bool):
            continue
        try:
            values.append(int(raw_value))
        except (TypeError, ValueError):
            continue
    if not values:
        return None
    return max(values)


def _estimate_actionability(
    sql_unit: dict[str, Any], proposal: dict[str, Any]
) -> dict[str, Any]:
    sql = str(sql_unit.get("sql") or "")
    dynamic_features = [
        str(x) for x in (sql_unit.get("dynamicFeatures") or []) if str(x).strip()
    ]
    suggestions = [
        row for row in (proposal.get("suggestions") or []) if isinstance(row, dict)
    ]
    issues = [row for row in (proposal.get("issues") or []) if isinstance(row, dict)]
    verdict = str(proposal.get("verdict") or "").strip()
    db_summary = proposal.get("dbEvidenceSummary", {}) or {}
    max_estimated_rows = _max_estimated_rows(db_summary.get("tableStats") or [])
    issue_codes = {
        str(row.get("code") or "").strip()
        for row in issues
        if isinstance(row, dict) and str(row.get("code") or "").strip()
    }
    blocked_trigger_rules = [
        str(row.get("ruleId") or "").strip()
        for row in (proposal.get("triggeredRules") or [])
        if isinstance(row, dict)
        and bool(row.get("blocksActionability"))
        and str(row.get("ruleId") or "").strip()
    ]

    if "${" in sql:
        return {
            "score": 0,
            "tier": "BLOCKED",
            "autoPatchLikelihood": "LOW",
            "reasons": ["unsafe dynamic substitution blocks safe auto-fix"],
            "blockedBy": ["DOLLAR_SUBSTITUTION"],
        }
    if blocked_trigger_rules:
        return {
            "score": 0,
            "tier": "BLOCKED",
            "autoPatchLikelihood": "LOW",
            "reasons": [
                "custom diagnostics rule blocks automatic optimization rollout"
            ],
            "blockedBy": blocked_trigger_rules,
        }

    score = 70
    reasons: list[str] = []
    blocked_by: list[str] = []

    if dynamic_features:
        score -= 20
        reasons.append("dynamic mapper structure reduces patch stability")
    if "INCLUDE" in dynamic_features:
        score -= 10
        reasons.append("include fragments reduce direct patchability")
    if not suggestions:
        score -= 30
        reasons.append("no concrete rewrite suggestion available")
    if verdict and (issues or suggestions):
        score += 10
        reasons.append("proposal includes structured issue and suggestion evidence")
    if not dynamic_features:
        score += 10
        reasons.append("static statement is easier to patch automatically")
    if (
        max_estimated_rows is not None
        and issue_codes
        and issue_codes.issubset(_ROW_SENSITIVE_RULES)
    ):
        if max_estimated_rows < 1000:
            score -= 35
            reasons.append(
                "small-table row count reduces the payoff of generic scan warnings"
            )
        elif max_estimated_rows < 10000:
            score -= 15
            reasons.append(
                "estimated row count suggests this is a medium-priority performance cleanup"
            )

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
        "blockedBy": blocked_by,
    }


def _get_matched_prompt_injections(
    triggered_rules: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[str]:
    """Get Prompt injections that match triggered rules.

    Args:
        triggered_rules: List of triggered rule definitions
        config: Full configuration dictionary

    Returns:
        List of prompt strings to inject
    """
    prompt_cfg = dict(config.get("prompt_injections") or {})
    by_rule = list(prompt_cfg.get("by_rule") or [])

    if not by_rule:
        return []

    # Get triggered rule IDs
    triggered_rule_ids = {str(r.get("ruleId") or "") for r in triggered_rules}

    # Find matching prompts
    matched_prompts = []
    for injection in by_rule:
        rule_id = str(injection.get("rule_id") or "").strip()
        if rule_id and rule_id in triggered_rule_ids:
            prompt = str(injection.get("prompt") or "").strip()
            if prompt:
                matched_prompts.append(prompt)

    return matched_prompts


def _get_system_prompts(config: dict[str, Any]) -> list[str]:
    """Get system-level prompt injections.

    Args:
        config: Full configuration dictionary

    Returns:
        List of system prompt strings
    """
    prompt_cfg = dict(config.get("prompt_injections") or {})
    system_prompts = list(prompt_cfg.get("system") or [])

    prompts = []
    for sp in system_prompts:
        content = str(sp.get("content") or "").strip()
        if content:
            prompts.append(content)

    return prompts


def build_optimize_prompt(
    sql_unit: dict[str, Any],
    proposal: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build optimization prompt with optional prompt injections.

    Args:
        sql_unit: SQL unit to analyze
        proposal: Current proposal with issues and suggestions
        config: Full configuration (optional, for prompt injections)

    Returns:
        Prompt dictionary for LLM
    """
    db_summary = proposal.get("dbEvidenceSummary", {}) or {}

    # Build base prompt
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
            "dynamicTemplateRequiresTemplateAwarePatch": bool(
                sql_unit.get("dynamicFeatures")
            ),
            "mustProduceCandidateTypes": [
                "SECURITY_FIX",
                "PLAN_IMPROVE",
                "CONSERVATIVE_NOOP_PLUS",
            ],
        },
    }

    # Inject prompts if config is provided
    if config:
        # Add system prompts
        system_prompts = _get_system_prompts(config)
        if system_prompts:
            prompt["systemPrompts"] = system_prompts

        # Add rule-matched prompts
        triggered_rules = proposal.get("triggeredRules", [])
        rule_matched_prompts = _get_matched_prompt_injections(triggered_rules, config)
        if rule_matched_prompts:
            prompt["ruleInjectedPrompts"] = rule_matched_prompts

    return prompt


def generate_proposal(
    sql_unit: dict[str, Any],
    config: dict[str, Any],
    schema_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    db_evidence, plan_summary = collect_sql_evidence(
        config, sql_unit["sql"], schema_metadata
    )
    rule_result = evaluate_rules(
        {
            **sql_unit,
            "tableStats": list((db_evidence or {}).get("tableStats") or []),
        },
        config,
    )
    proposal = {
        "sqlKey": sql_unit["sqlKey"],
        "issues": rule_result["issues"],
        "dbEvidenceSummary": db_evidence,
        "planSummary": plan_summary
        if plan_summary
        else {"risk": "low" if rule_result["suggestions"] else "none"},
        "suggestions": rule_result["suggestions"],
        "verdict": rule_result["verdict"],
        "confidence": "medium",
        "estimatedBenefit": "unknown",
        "triggeredRules": rule_result["triggeredRules"],
    }
    proposal["actionability"] = _estimate_actionability(sql_unit, proposal)
    proposal["recommendedSuggestionIndex"] = 0 if rule_result["suggestions"] else None
    return proposal
