"""UNION 包装折叠策略实现

SafeUnionCollapseStrategy - 安全折叠 UNION 包装查询
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .materialization_constants import (
    STATEMENT_TEMPLATE_SAFE_UNION_COLLAPSE,
    REASON_STATEMENT_INCLUDE_SAFE,
)
from .patchability_models import PlannedPatchStrategy
from .template_rendering import collect_fragments, normalize_sql_text, render_template_body_sql
from .union_utils import (
    contains_union,
    detect_union_type,
    validate_union_safety,
)


class SafeUnionCollapseStrategy:
    """UNION 包装折叠策略

    处理模式:
    - SELECT * FROM (SELECT ... UNION ALL SELECT ...) t → SELECT ... UNION ALL SELECT ...
    - SELECT * FROM (SELECT ... UNION SELECT ...) t → SELECT ... UNION SELECT ...

    保留:
    - UNION 类型（UNION vs UNION ALL）
    - ORDER BY
    - LIMIT
    """

    strategy_type = "SAFE_UNION_COLLAPSE"
    required_capability = "SAFE_UNION_COLLAPSE"

    def plan(
        self,
        sql_unit: dict[str, Any],
        rewritten_sql: str,
        fragment_catalog: dict[str, dict[str, Any]],
        *,
        enable_fragment_materialization: bool = False,
        fallback_from: str | None = None,
        dynamic_candidate_intent: dict[str, Any] | None = None,
    ) -> PlannedPatchStrategy | None:
        """生成 UNION 折叠策略

        Args:
            sql_unit: SQL 单元
            rewritten_sql: 重写后的 SQL
            fragment_catalog: 片段目录
            enable_fragment_materialization: 是否启用片段物化
            fallback_from: 回退来源策略
            dynamic_candidate_intent: 动态候选意图

        Returns:
            PlannedPatchStrategy 或 None
        """
        _ = fragment_catalog
        _ = enable_fragment_materialization
        _ = dynamic_candidate_intent

        # 1. 检查是否包含 UNION
        if not contains_union(rewritten_sql):
            return None

        # 2. 验证安全性
        is_safe, reason = validate_union_safety(rewritten_sql)
        if not is_safe:
            return None

        # 3. 生成 materialization
        materialization, ops = self._build_materialization(sql_unit, rewritten_sql)

        if materialization is None:
            return None

        return PlannedPatchStrategy(
            strategy_type=self.strategy_type,
            mode=str(materialization.get("mode") or ""),
            reason_code=str(materialization.get("reasonCode") or REASON_STATEMENT_INCLUDE_SAFE),
            replay_verified=materialization.get("replayVerified"),
            fallback_from=fallback_from,
            materialization=materialization,
            ops=ops,
        )

    def _build_materialization(
        self,
        sql_unit: dict[str, Any],
        rewritten_sql: str,
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        """构建 materialization 和 ops

        Args:
            sql_unit: SQL 单元
            rewritten_sql: 重写后的 SQL

        Returns:
            (materialization, ops) 或 (None, [])
        """
        xml_path = Path(str(sql_unit.get("xmlPath") or ""))
        namespace = str(sql_unit.get("namespace") or "").strip()
        statement_key = str(sql_unit.get("sqlKey") or "").split("#", 1)[0]
        template_sql = str(sql_unit.get("templateSql") or "")

        # 验证必要字段
        if not xml_path.exists() or not template_sql or not rewritten_sql.strip():
            return None, []

        # 解析 XML
        try:
            import xml.etree.ElementTree as ET
            root = ET.parse(xml_path).getroot()
        except Exception:
            return None, []

        # 验证回放
        replayed = render_template_body_sql(
            rewritten_sql, namespace, xml_path, collect_fragments(root, namespace, xml_path)
        )

        if normalize_sql_text(replayed or "") != normalize_sql_text(rewritten_sql):
            return None, []

        # 检测 UNION 类型
        union_type = detect_union_type(rewritten_sql)

        # 构建 materialization
        materialization = {
            "mode": STATEMENT_TEMPLATE_SAFE_UNION_COLLAPSE,
            "targetType": "STATEMENT",
            "targetRef": statement_key,
            "reasonCode": "UNION_COLLAPSE_SAFE",
            "reasonMessage": f"wrapper query with {union_type} can be safely collapsed",
            "replayVerified": True,
            "featureFlagApplied": False,
            "unionType": union_type,
        }

        ops = [
            {
                "op": "replace_statement_body",
                "targetRef": statement_key,
                "beforeTemplate": template_sql,
                "afterTemplate": rewritten_sql,
                "preservedAnchors": [],
                "safetyChecks": {"unionCollapse": True},
            }
        ]

        return materialization, ops