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


def get_select_columns(sql: str) -> list[str]:
    """提取 SELECT 子句中的列"""
    import re
    # 提取 SELECT ... FROM 之间的内容
    match = re.search(r'SELECT\s+(.+?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
    if not match:
        return []
    select_part = match.group(1)
    if select_part.strip() == '*':
        return ['*']
    # 分割列名
    columns = [col.strip().split()[-1] for col in select_part.split(',')]
    return columns


def is_join_table_used(sql: str, table_name: str) -> bool:
    """检查被 JOIN 的表是否在查询中被使用

    检查 SELECT、WHERE、ORDER BY、GROUP BY、HAVING 等子句
    """
    import re
    sql_upper = sql.upper()
    table_name_upper = table_name.upper()

    # 检查是否在 SELECT 中使用
    select_match = re.search(r'SELECT\s+(.+?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
    if select_match:
        select_part = select_match.group(1).upper()
        if table_name_upper in select_part and f'{table_name_upper}.' in sql_upper:
            return True

    # 检查是否在 WHERE 中使用（排除 JOIN...ON 条件）
    where_match = re.search(r'WHERE\s+(.+?)(?:GROUP|ORDER|LIMIT|$)', sql, re.IGNORECASE | re.DOTALL)
    if where_match:
        where_part = where_match.group(1).upper()
        # 排除 ON 条件
        on_match = re.search(r'ON\s+.+?(?=\s+WHERE|\s+GROUP|\s+ORDER|\s+LIMIT|$)', sql, re.IGNORECASE | re.DOTALL)
        if on_match:
            on_part = on_match.group(0).upper()
            where_part = where_part.replace(on_part, '')
        if f'{table_name_upper}.' in where_part:
            return True

    return False


def join_elimination_candidate(sql: str) -> Optional[dict]:
    """检测 JOIN 消除候选

    返回候选信息或 None
    """
    if not contains_join(sql):
        return None

    # 提取所有被 JOIN 的表
    join_tables = extract_join_tables(sql)
    if not join_tables:
        return None

    for table in join_tables:
        # 如果表没有被使用，可能是消除候选
        if not is_join_table_used(sql, table):
            return {
                "table": table,
                "reason": "UNUSED_TABLE",
            }

    return None