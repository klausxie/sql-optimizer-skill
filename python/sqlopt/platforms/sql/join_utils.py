"""JOIN 工具函数模块

提供 JOIN 分析和转换的通用功能。
"""

from __future__ import annotations
from enum import Enum
from typing import Optional


class JoinType(Enum):
    """JOIN 类型枚举"""
    INNER = "INNER"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    FULL = "FULL OUTER"
    CROSS = "CROSS"
    # 未来可扩展
    # CROSS_APPLY = "CROSS APPLY"
    # LATERAL = "LATERAL"


def contains_join(sql: str) -> bool:
    """检测 SQL 是否包含 JOIN"""
    sql_upper = sql.upper()
    join_keywords = [" JOIN ", " INNER JOIN ", " LEFT JOIN ", " RIGHT JOIN ", " FULL JOIN ", " CROSS JOIN "]
    return any(keyword in sql_upper for keyword in join_keywords)


def detect_join_type(sql: str) -> Optional[JoinType]:
    """检测 JOIN 类型"""
    sql_upper = sql.upper()
    if " LEFT JOIN " in sql_upper:
        return JoinType.LEFT
    elif " RIGHT JOIN " in sql_upper:
        return JoinType.RIGHT
    elif " FULL JOIN " in sql_upper:
        return JoinType.FULL
    elif " CROSS JOIN " in sql_upper:
        return JoinType.CROSS
    elif " JOIN " in sql_upper:
        return JoinType.INNER
    return None


def extract_join_tables(sql: str) -> list[str]:
    """提取 SQL 中所有被 JOIN 的表名"""
    import re
    # 匹配 JOIN ... ON 或 JOIN ... USING
    pattern = r'(?:LEFT|RIGHT|FULL|INNER|CROSS)?\s*JOIN\s+(\w+)\s+(?:ON|USING)'
    matches = re.findall(pattern, sql, re.IGNORECASE)
    return matches


def has_not_null_condition(sql: str, table_name: str) -> bool:
    """检测 WHERE 条件是否保证非空"""
    sql_upper = sql.upper()
    table_name_upper = table_name.upper()
    # 检查 IS NOT NULL 条件
    patterns = [
        rf'{table_name_upper}\.\w+\s+IS\s+NOT\s+NULL',
        rf'{table_name_upper}\.\w+\s+!=\s*NULL',
        rf'{table_name_upper}\.\w+\s+<>\s*NULL',
        rf'IS\s+NOT\s+NULL\s*\(\s*{table_name_upper}\.\w+\s*\)',
    ]
    import re
    for pattern in patterns:
        if re.search(pattern, sql_upper):
            return True
    return False


def left_to_inner_rewrite(sql: str) -> Optional[str]:
    """将 LEFT JOIN 转换为 INNER JOIN

    当 WHERE 条件保证非空时执行转换。
    返回转换后的 SQL，如果不适用则返回 None。
    """
    if not contains_join(sql):
        return None

    join_type = detect_join_type(sql)
    if join_type != JoinType.LEFT:
        return None

    # 提取被 JOIN 的表
    join_tables = extract_join_tables(sql)
    if not join_tables:
        return None

    # 检查是否有 NOT NULL 条件
    for table in join_tables:
        if has_not_null_condition(sql, table):
            # 执行转换
            sql = sql.upper()
            sql = sql.replace("LEFT JOIN", "INNER JOIN")
            return sql

    return None