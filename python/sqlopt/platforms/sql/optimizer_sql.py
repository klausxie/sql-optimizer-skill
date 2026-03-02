from __future__ import annotations

from typing import Any

from ..dispatch import collect_sql_evidence


def build_optimize_prompt(sql_unit: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    db_summary = proposal.get("dbEvidenceSummary", {}) or {}
    return {
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


def generate_proposal(sql_unit: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    sql = sql_unit["sql"]
    issues = []
    suggestions = []
    verdict = "NOOP"
    if "${" in sql:
        issues.append({"code": "DOLLAR_SUBSTITUTION", "message": "unsafe ${} dynamic substitution"})
        verdict = "CAN_IMPROVE"
    if "select *" in sql.lower():
        issues.append({"code": "SELECT_STAR", "message": "avoid select *"})
        suggestions.append({"action": "PROJECT_COLUMNS", "sql": sql.replace("*", "id")})
        verdict = "CAN_IMPROVE"
    if " where " not in sql.lower() and sql_unit["statementType"] == "SELECT":
        issues.append({"code": "FULL_SCAN_RISK", "message": "no where filter"})
    db_evidence, plan_summary = collect_sql_evidence(config, sql_unit["sql"])
    proposal = {
        "sqlKey": sql_unit["sqlKey"],
        "issues": issues,
        "dbEvidenceSummary": db_evidence,
        "planSummary": plan_summary if plan_summary else {"risk": "low" if suggestions else "none"},
        "suggestions": suggestions,
        "verdict": verdict,
        "confidence": "medium",
        "estimatedBenefit": "unknown",
    }
    return proposal
