"""EXISTS 通用工具模块

提供 EXISTS 相关的检测、重写和验证功能。
设计为可扩展，支持未来 IN → EXISTS 等场景。
"""

from __future__ import annotations

import re
from typing import Any


# 正则表达式定义
_EXISTS_PATTERN = re.compile(r'\bEXISTS\s*\(', re.IGNORECASE)
_NOT_EXISTS_PATTERN = re.compile(r'\bNOT\s+EXISTS\s*\(', re.IGNORECASE)
_CORRELATED_PATTERN = re.compile(r'\b\w+\.\w+\b')  # 检测关联条件


def contains_exists(sql: str) -> bool:
    """检测 SQL 是否包含 EXISTS 关键字

    Args:
        sql: SQL 语句

    Returns:
        True if contains EXISTS or NOT EXISTS
    """
    if not sql:
        return False
    return bool(_EXISTS_PATTERN.search(sql) or _NOT_EXISTS_PATTERN.search(sql))


def detect_exists_pattern(sql: str) -> dict[str, Any] | None:
    """检测 EXISTS 模式

    Args:
        sql: SQL 语句

    Returns:
        {
            "type": "EXISTS" | "NOT_EXISTS",
            "subquery": str,
            "correlation": str | None,
        } 或 None
    """
    if not sql:
        return None

    # 检测 NOT EXISTS
    not_exists_match = _NOT_EXISTS_PATTERN.search(sql)
    if not_exists_match:
        exists_type = "NOT_EXISTS"
        subquery_start = not_exists_match.end()
    else:
        exists_match = _EXISTS_PATTERN.search(sql)
        if not exists_match:
            return None
        exists_type = "EXISTS"
        subquery_start = exists_match.end()

    # 提取子查询（简单实现，假设括号平衡）
    paren_depth = 1
    subquery_end = subquery_start
    for i, char in enumerate(sql[subquery_start:], subquery_start):
        if char == '(':
            paren_depth += 1
        elif char == ')':
            paren_depth -= 1
            if paren_depth == 0:
                subquery_end = i
                break

    subquery = sql[subquery_start:subquery_end].strip()

    # 检测关联条件
    correlation = None
    if _CORRELATED_PATTERN.search(subquery):
        # 提取关联列
        correlation = _CORRELATED_PATTERN.findall(subquery)[0] if _CORRELATED_PATTERN.findall(subquery) else None

    return {
        "type": exists_type,
        "subquery": subquery,
        "correlation": correlation,
    }


def is_correlated(subquery: str) -> bool:
    """检查子查询是否包含关联条件

    Args:
        subquery: 子查询 SQL

    Returns:
        True if correlated
    """
    return bool(_CORRELATED_PATTERN.search(subquery))


def validate_exists_rewrite_safety(
    original_sql: str,
    rewritten_sql: str,
    rewrite_type: str,
) -> tuple[bool, str | None]:
    """验证 EXISTS 重写的安全性

    Args:
        original_sql: 原始 SQL
        rewritten_sql: 重写后的 SQL
        rewrite_type: 重写类型 ("EXISTS_TO_IN", "EXISTS_TO_JOIN")

    Returns:
        (is_safe, reason_code)
    """
    if not original_sql or not rewritten_sql:
        return False, "EMPTY_SQL"

    # NOT IN 需要特别检查 NULL 语义
    if rewrite_type == "NOT_EXISTS_TO_NOT_IN":
        # 检查子查询中是否有可能导致 NULL 的列
        # 这里简化处理：检查是否有 IS NULL 条件
        if "IS NULL" in rewritten_sql.upper():
            return False, "NULL_SEMANTICS_MAY_DIFFER"

    # JOIN 转换需要更严格验证（简单场景）
    if rewrite_type == "EXISTS_TO_JOIN":
        # 检查是否包含复杂的 JOIN 条件
        if rewritten_sql.upper().count("JOIN") > 1:
            return False, "JOIN_COMPLEXITY_TOO_HIGH"

    return True, None