"""UNION 通用工具模块

提供 UNION 相关的检测、验证和转换功能。
设计为可扩展，支持未来 INTERSECT/EXCEPT 等场景。
"""

from __future__ import annotations

import re
from typing import Any


# 正则表达式定义
_UNION_ALL_PATTERN = re.compile(r'\bUNION\s+ALL\b', re.IGNORECASE)
_UNION_PATTERN = re.compile(r'\bUNION\b(?!\s+ALL)', re.IGNORECASE)
_FOR_UPDATE_PATTERN = re.compile(r'\bFOR\s+UPDATE\b', re.IGNORECASE)


def contains_union(sql: str) -> bool:
    """检测 SQL 是否包含 UNION 关键字

    Args:
        sql: SQL 语句

    Returns:
        True if contains UNION or UNION ALL
    """
    if not sql:
        return False
    sql_upper = sql.upper()
    return 'UNION' in sql_upper


def detect_union_type(sql: str) -> str:
    """检测 UNION 类型

    Args:
        sql: SQL 语句

    Returns:
        'UNION ALL', 'UNION', 或 'NONE'
    """
    if not sql:
        return 'NONE'

    if _UNION_ALL_PATTERN.search(sql):
        return 'UNION ALL'

    if _UNION_PATTERN.search(sql):
        return 'UNION'

    return 'NONE'


def has_nested_union(sql: str) -> bool:
    """检测是否有嵌套 UNION（超过一个 UNION 关键字）

    Args:
        sql: SQL 语句

    Returns:
        True if has nested UNION
    """
    if not sql:
        return False

    # 计算 UNION 关键字数量（排除 UNION ALL 中的 UNION）
    # 简单方法：替换 UNION ALL 后再计数
    temp_sql = _UNION_ALL_PATTERN.sub('', sql)
    union_count = temp_sql.upper().count('UNION')

    return union_count > 1


def validate_union_safety(sql: str) -> tuple[bool, str | None]:
    """验证 UNION 优化的安全性

    Args:
        sql: UNION SQL 语句

    Returns:
        (is_safe, reason_code) - 如果安全返回 (True, None)，否则返回 (False, reason_code)
    """
    if not sql:
        return False, "empty_sql"

    # 检查嵌套 UNION
    if has_nested_union(sql):
        return False, "NESTED_UNION_NOT_SUPPORTED"

    # 检查 FOR UPDATE（UNION 不支持）
    if _FOR_UPDATE_PATTERN.search(sql):
        return False, "FOR_UPDATE_NOT_SUPPORTED"

    # 检查 DISTINCT（UNION 自动去重，外层 DISTINCT 可能有不同语义）
    if re.search(r'^\s*SELECT\s+DISTINCT\b', sql, re.IGNORECASE | re.MULTILINE):
        return False, "DISTINCT_SEMANTICS_MAY_DIFFER"

    return True, None


def is_union_wrapper_pattern(template_sql: str) -> bool:
    """检测模板是否匹配 UNION 包装模式

    模式: SELECT * FROM ( ... UNION ... ) [alias]

    Args:
        template_sql: 模板 SQL

    Returns:
        True if matches UNION wrapper pattern
    """
    if not template_sql:
        return False

    # 匹配模式: SELECT ... FROM ( SELECT ... UNION ... ) [alias]
    pattern = re.compile(
        r'^\s*SELECT\s+\*\s+FROM\s+\(\s*SELECT\s+.*?\s+UNION\s+',
        re.IGNORECASE | re.DOTALL
    )

    return bool(pattern.search(template_sql))