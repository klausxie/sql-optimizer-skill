from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .materialization_constants import (
    REASON_STATEMENT_INCLUDE_SAFE,
    REASON_WRAPPER_QUERY_COLLAPSE_SAFE,
    STATEMENT_TEMPLATE_SAFE_WRAPPER_COLLAPSE,
)
from .patchability_models import PlannedPatchStrategy, RegisteredPatchStrategy
from .template_materializer import build_rewrite_materialization
from .template_rendering import collect_fragments, normalize_sql_text, render_template_body_sql


def _wrapper_collapse_materialization(sql_unit: dict[str, Any], rewritten_sql: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    xml_path = Path(str(sql_unit.get("xmlPath") or ""))
    namespace = str(sql_unit.get("namespace") or "").strip()
    statement_key = str(sql_unit.get("sqlKey") or "").split("#", 1)[0]
    template_sql = str(sql_unit.get("templateSql") or "")
    if not xml_path.exists() or not template_sql or not rewritten_sql.strip():
        return None, []
    try:
        root = ET.parse(xml_path).getroot()
    except Exception:
        return None, []
    replayed = render_template_body_sql(rewritten_sql, namespace, xml_path, collect_fragments(root, namespace, xml_path))
    if normalize_sql_text(replayed or "") != normalize_sql_text(rewritten_sql):
        return None, []
    return (
        {
            "mode": STATEMENT_TEMPLATE_SAFE_WRAPPER_COLLAPSE,
            "targetType": "STATEMENT",
            "targetRef": statement_key,
            "reasonCode": REASON_WRAPPER_QUERY_COLLAPSE_SAFE,
            "reasonMessage": "wrapper query can be safely collapsed into a direct statement rewrite",
            "replayVerified": True,
            "featureFlagApplied": False,
        },
        [
            {
                "op": "replace_statement_body",
                "targetRef": statement_key,
                "beforeTemplate": template_sql,
                "afterTemplate": rewritten_sql,
                "preservedAnchors": [],
                "safetyChecks": {"wrapperCollapse": True},
            }
        ],
    )


class SafeWrapperCollapseStrategy:
    strategy_type = "SAFE_WRAPPER_COLLAPSE"
    required_capability = "SAFE_WRAPPER_COLLAPSE"

    def plan(
        self,
        sql_unit: dict[str, Any],
        rewritten_sql: str,
        fragment_catalog: dict[str, dict[str, Any]],
        *,
        enable_fragment_materialization: bool,
        fallback_from: str | None,
    ) -> PlannedPatchStrategy | None:
        _ = fragment_catalog
        _ = enable_fragment_materialization
        materialization, ops = _wrapper_collapse_materialization(sql_unit, rewritten_sql)
        if materialization is None:
            return None
        return PlannedPatchStrategy(
            strategy_type=self.strategy_type,
            mode=str(materialization.get("mode") or ""),
            reason_code=str(materialization.get("reasonCode") or REASON_WRAPPER_QUERY_COLLAPSE_SAFE),
            replay_verified=materialization.get("replayVerified"),
            fallback_from=fallback_from,
            materialization=materialization,
            ops=ops,
        )


class ExactTemplateEditStrategy:
    strategy_type = "EXACT_TEMPLATE_EDIT"
    required_capability = "EXACT_TEMPLATE_EDIT"

    def plan(
        self,
        sql_unit: dict[str, Any],
        rewritten_sql: str,
        fragment_catalog: dict[str, dict[str, Any]],
        *,
        enable_fragment_materialization: bool,
        fallback_from: str | None,
    ) -> PlannedPatchStrategy | None:
        materialization, ops = build_rewrite_materialization(
            sql_unit,
            rewritten_sql,
            fragment_catalog,
            enable_fragment_materialization=enable_fragment_materialization,
        )
        if str(materialization.get("mode") or "") == "UNMATERIALIZABLE":
            return None
        return PlannedPatchStrategy(
            strategy_type=self.strategy_type,
            mode=str(materialization.get("mode") or ""),
            reason_code=str(materialization.get("reasonCode") or REASON_STATEMENT_INCLUDE_SAFE),
            replay_verified=materialization.get("replayVerified"),
            fallback_from=fallback_from,
            materialization=materialization,
            ops=[dict(row) for row in ops if isinstance(row, dict)],
        )


def iter_patch_strategies() -> tuple[RegisteredPatchStrategy, ...]:
    return (
        RegisteredPatchStrategy(
            strategy_type=SafeWrapperCollapseStrategy.strategy_type,
            priority=200,
            required_capability=SafeWrapperCollapseStrategy.required_capability,
            implementation=SafeWrapperCollapseStrategy(),
        ),
        RegisteredPatchStrategy(
            strategy_type=ExactTemplateEditStrategy.strategy_type,
            priority=100,
            required_capability=ExactTemplateEditStrategy.required_capability,
            implementation=ExactTemplateEditStrategy(),
        ),
    )
