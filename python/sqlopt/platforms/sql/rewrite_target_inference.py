from __future__ import annotations

from typing import Any


def infer_rewrite_target(
    sql_unit: dict[str, Any],
    rewritten_sql: str,
) -> dict[str, Any]:
    dynamic_features = [str(x) for x in (sql_unit.get("dynamicFeatures") or []) if str(x).strip()]
    original_sql = " ".join(str(sql_unit.get("sql") or "").split())
    rewritten = " ".join(str(rewritten_sql or "").split())
    statement_key = str(sql_unit.get("sqlKey") or "").split("#", 1)[0]
    primary_fragment_target = str(sql_unit.get("primaryFragmentTarget") or "").strip() or None

    if not dynamic_features:
        return {
            "targetType": "STATEMENT",
            "targetRef": statement_key,
            "modeHint": "STATEMENT_SQL",
            "confidence": "high",
            "reasonCode": "STATIC_STATEMENT",
        }

    if dynamic_features == ["INCLUDE"] or set(dynamic_features) == {"INCLUDE"}:
        include_bindings = [row for row in (sql_unit.get("includeBindings") or []) if isinstance(row, dict)]
        return {
            "targetType": "STATEMENT",
            "targetRef": statement_key if original_sql == rewritten or not include_bindings else (primary_fragment_target or str(include_bindings[0].get("ref") or "").strip() or statement_key),
            "modeHint": "STATEMENT_OR_FRAGMENT_TEMPLATE_CANDIDATE",
            "confidence": "medium",
            "reasonCode": "INCLUDE_TEMPLATE_CANDIDATE",
        }

    return {
        "targetType": "STATEMENT",
        "targetRef": statement_key,
        "modeHint": "UNMATERIALIZABLE",
        "confidence": "high",
        "reasonCode": "DYNAMIC_SUBTREE_PRESENT",
    }
