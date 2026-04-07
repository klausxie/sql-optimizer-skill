from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .materialization_constants import (
    REASON_EXISTS_REWRITE_SAFE,
    REASON_STATEMENT_INCLUDE_SAFE,
    REASON_WRAPPER_QUERY_COLLAPSE_SAFE,
    STATEMENT_TEMPLATE_SAFE_EXISTS_REWRITE,
    STATEMENT_TEMPLATE_SAFE,
    STATEMENT_TEMPLATE_SAFE_WRAPPER_COLLAPSE,
)
from .candidate_generation_support import exists_self_cleanup_sql
from .patchability_models import PlannedPatchStrategy, RegisteredPatchStrategy
from .template_materializer import build_rewrite_materialization
from .template_rendering import collect_fragments, normalize_sql_text, render_template_body_sql
from .union_collapse_strategy import SafeUnionCollapseStrategy

_COUNT_SQL_RE = re.compile(
    r"^\s*select\s+count\s*\(\s*(?P<count_expr>[^)]+)\s*\)\s+(?P<from_suffix>from\b.+)$",
    flags=re.IGNORECASE | re.DOTALL,
)


def _normalize_dynamic_replay_sql(sql: str) -> str:
    match = _COUNT_SQL_RE.match(str(sql or "").strip())
    if match:
        count_expr = normalize_sql_text(match.group("count_expr"))
        from_suffix = normalize_sql_text(match.group("from_suffix"))
        if count_expr in {"1", "*"} and from_suffix:
            return normalize_sql_text(f"SELECT COUNT(*) {from_suffix}")
    return normalize_sql_text(sql)


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
        dynamic_candidate_intent: dict[str, Any] | None = None,
    ) -> PlannedPatchStrategy | None:
        _ = fragment_catalog
        _ = enable_fragment_materialization
        _ = dynamic_candidate_intent
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


class SafeExistsRewriteStrategy:
    strategy_type = "SAFE_EXISTS_REWRITE"
    required_capability = "SAFE_EXISTS_REWRITE"

    def plan(
        self,
        sql_unit: dict[str, Any],
        rewritten_sql: str,
        fragment_catalog: dict[str, dict[str, Any]],
        *,
        enable_fragment_materialization: bool,
        fallback_from: str | None,
        dynamic_candidate_intent: dict[str, Any] | None = None,
    ) -> PlannedPatchStrategy | None:
        _ = fragment_catalog
        _ = enable_fragment_materialization
        _ = dynamic_candidate_intent
        original_sql = str(sql_unit.get("sql") or "")
        expected_rewrite = exists_self_cleanup_sql(original_sql)
        if not expected_rewrite:
            return None
        if normalize_sql_text(expected_rewrite) != normalize_sql_text(rewritten_sql):
            return None
        xml_path = Path(str(sql_unit.get("xmlPath") or ""))
        namespace = str(sql_unit.get("namespace") or "").strip()
        statement_key = str(sql_unit.get("sqlKey") or "").split("#", 1)[0]
        template_sql = str(sql_unit.get("templateSql") or "")
        if not xml_path.exists() or not template_sql or not rewritten_sql.strip():
            return None
        try:
            root = ET.parse(xml_path).getroot()
        except Exception:
            return None
        replayed = render_template_body_sql(
            rewritten_sql,
            namespace,
            xml_path,
            collect_fragments(root, namespace, xml_path),
        )
        if normalize_sql_text(replayed or "") != normalize_sql_text(rewritten_sql):
            return None
        materialization = {
            "mode": STATEMENT_TEMPLATE_SAFE_EXISTS_REWRITE,
            "targetType": "STATEMENT",
            "targetRef": statement_key,
            "reasonCode": REASON_EXISTS_REWRITE_SAFE,
            "reasonMessage": "simple EXISTS identity filter can be safely removed",
            "replayVerified": True,
            "featureFlagApplied": False,
        }
        ops = [
            {
                "op": "replace_statement_body",
                "targetRef": statement_key,
                "beforeTemplate": template_sql,
                "afterTemplate": rewritten_sql,
                "preservedAnchors": [],
                "safetyChecks": {"existsRewrite": True},
            }
        ]
        return PlannedPatchStrategy(
            strategy_type=self.strategy_type,
            mode=str(materialization.get("mode") or ""),
            reason_code=str(materialization.get("reasonCode") or REASON_EXISTS_REWRITE_SAFE),
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
        dynamic_candidate_intent: dict[str, Any] | None = None,
    ) -> PlannedPatchStrategy | None:
        _ = dynamic_candidate_intent
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


class DynamicStatementTemplateEditStrategy:
    strategy_type = "DYNAMIC_STATEMENT_TEMPLATE_EDIT"
    required_capability = "DYNAMIC_STATEMENT_CANONICAL_EDIT"

    def plan(
        self,
        sql_unit: dict[str, Any],
        rewritten_sql: str,
        fragment_catalog: dict[str, dict[str, Any]],
        *,
        enable_fragment_materialization: bool,
        fallback_from: str | None,
        dynamic_candidate_intent: dict[str, Any] | None = None,
    ) -> PlannedPatchStrategy | None:
        _ = enable_fragment_materialization
        rebuilt_template = str((dynamic_candidate_intent or {}).get("rebuiltTemplate") or "").strip()
        if not rebuilt_template:
            return None
        xml_path = Path(str(sql_unit.get("xmlPath") or ""))
        namespace = str(sql_unit.get("namespace") or "").strip()
        statement_key = str(sql_unit.get("sqlKey") or "").split("#", 1)[0]
        template_sql = str(sql_unit.get("templateSql") or "")
        if not xml_path.exists() or not template_sql or not rebuilt_template:
            return None
        try:
            root = ET.parse(xml_path).getroot()
        except Exception:
            return None
        replayed = render_template_body_sql(rebuilt_template, namespace, xml_path, collect_fragments(root, namespace, xml_path))
        if _normalize_dynamic_replay_sql(replayed or "") != _normalize_dynamic_replay_sql(rewritten_sql):
            return None
        return PlannedPatchStrategy(
            strategy_type=self.strategy_type,
            mode=STATEMENT_TEMPLATE_SAFE,
            reason_code="DYNAMIC_STATEMENT_TEMPLATE_SAFE",
            replay_verified=True,
            fallback_from=fallback_from,
            materialization={
                "mode": STATEMENT_TEMPLATE_SAFE,
                "targetType": "STATEMENT",
                "targetRef": statement_key,
                "reasonCode": "DYNAMIC_STATEMENT_TEMPLATE_SAFE",
                "reasonMessage": "dynamic statement template can be safely rewritten while preserving dynamic tags",
                "replayVerified": True,
                "featureFlagApplied": False,
            },
            ops=[
                {
                    "op": "replace_statement_body",
                    "targetRef": statement_key,
                    "beforeTemplate": template_sql,
                    "afterTemplate": rebuilt_template,
                    "preservedAnchors": [],
                    "safetyChecks": {"dynamicIntent": True},
                }
            ],
        )


def iter_patch_strategies() -> tuple[RegisteredPatchStrategy, ...]:
    return (
        RegisteredPatchStrategy(
            strategy_type=SafeExistsRewriteStrategy.strategy_type,
            priority=255,
            required_capability=SafeExistsRewriteStrategy.required_capability,
            implementation=SafeExistsRewriteStrategy(),
        ),
        RegisteredPatchStrategy(
            strategy_type=SafeUnionCollapseStrategy.strategy_type,
            priority=250,
            required_capability=SafeUnionCollapseStrategy.required_capability,
            implementation=SafeUnionCollapseStrategy(),
        ),
        RegisteredPatchStrategy(
            strategy_type=SafeWrapperCollapseStrategy.strategy_type,
            priority=200,
            required_capability=SafeWrapperCollapseStrategy.required_capability,
            implementation=SafeWrapperCollapseStrategy(),
        ),
        RegisteredPatchStrategy(
            strategy_type=DynamicStatementTemplateEditStrategy.strategy_type,
            priority=150,
            required_capability=DynamicStatementTemplateEditStrategy.required_capability,
            implementation=DynamicStatementTemplateEditStrategy(),
        ),
        RegisteredPatchStrategy(
            strategy_type=ExactTemplateEditStrategy.strategy_type,
            priority=100,
            required_capability=ExactTemplateEditStrategy.required_capability,
            implementation=ExactTemplateEditStrategy(),
        ),
    )
