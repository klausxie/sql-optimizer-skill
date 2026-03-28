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
    """提取 SQL 中所有被 JOIN 的表名（返回表别名）"""
    import re
    # 匹配 JOIN table AS alias ON 或 JOIN table ON 或 JOIN table alias ON
    # 返回表别名（如果有），否则返回表名
    # 需要两个pattern来处理有别名和无别名的情况
    pattern1 = r'(?:LEFT|RIGHT|FULL|INNER|CROSS)?\s*JOIN\s+(\w+)\s+(?:AS\s+)?(\w+)?\s+(?:ON|USING)'
    pattern2 = r'(?:LEFT|RIGHT|FULL|INNER|CROSS)?\s*JOIN\s+(\w+)\s+(?:ON|USING)'

    # 先尝试匹配有别名的情况
    matches = re.findall(pattern1, sql, re.IGNORECASE)
    result = [m[1] if m[1] else m[0] for m in matches]

    # 如果没有匹配到，尝试匹配没有别名的情况
    if not result:
        matches = re.findall(pattern2, sql, re.IGNORECASE)
        result = matches

    return result


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
    # 分割列名，并去掉表别名
    columns = []
    for col in select_part.split(','):
        col = col.strip()
        # 处理带别名的列，如 "u.id as user_id" 或 "u.id user_id" 或 "u.id"
        # 取最后一部分作为列名（去掉别名），再取点后的部分（去掉表别名）
        parts = col.split()
        col_name = parts[0]  # 取第一部分（可能是 "u.id" 或 "id"）
        if '.' in col_name:
            col_name = col_name.split('.')[-1]  # 取点后的部分
        columns.append(col_name)
    return columns


def is_join_table_used(sql: str, table_name: str) -> bool:
    """检查被 JOIN 的表是否在查询中被使用

    检查 SELECT、WHERE 等子句，但 ON 条件不算"使用"
    （ON 条件中的表引用是 JOIN 必需的，不算真正使用）
    """
    import re
    sql_upper = sql.upper()
    table_name_upper = table_name.upper()

    # 检查是否在 SELECT 中使用
    select_match = re.search(r'SELECT\s+(.+?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
    if select_match:
        select_part = select_match.group(1).upper()
        # 检查 SELECT 列中是否有 表别名.列 形式
        if f'{table_name_upper}.' in select_part:
            return True

    # 检查是否在 WHERE 中使用
    where_match = re.search(r'WHERE\s+(.+?)(?:GROUP|ORDER|LIMIT|$)', sql, re.IGNORECASE | re.DOTALL)
    if where_match:
        where_part = where_match.group(1).upper()
        # 排除 ON 条件中的引用
        # 简单方法：把 ON 部分去掉
        on_pattern = r'ON\s+[^=]+=\s*[^=]+\s*(?=(?:WHERE)|(?:GROUP)|(?:ORDER)|(?:LIMIT)|$)'
        where_clean = re.sub(on_pattern, '', where_part, flags=re.IGNORECASE)
        if f'{table_name_upper}.' in where_clean:
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


def get_join_order(sql: str) -> list[str]:
    """获取 JOIN 的顺序（表列表）"""
    import re
    # 提取 FROM 后所有的表
    tables = []

    # 先提取 FROM 后到 WHERE/GROUP/ORDER/LIMIT 之前的部分
    from_match = re.search(r'FROM\s+(.+?)(?:\s+WHERE|\s+GROUP|\s+ORDER|\s+LIMIT|\s*$)', sql, re.IGNORECASE | re.DOTALL)
    if not from_match:
        return []

    from_part = from_match.group(1)

    # 查找主表（FROM 后第一个表）
    main_table_match = re.match(r'(\w+)\s+(?:as\s+)?(\w+)?', from_part, re.IGNORECASE)
    if main_table_match:
        tables.append(main_table_match.group(1))

    # 查找所有 JOIN 的表
    join_tables = re.findall(r'(?:LEFT|RIGHT|FULL|INNER|CROSS)?\s*JOIN\s+(\w+)', from_part, re.IGNORECASE)
    tables.extend(join_tables)

    return tables


def can_reorder_joins(sql: str) -> bool:
    """检查 JOIN 是否可以重排

    目前检查是否有阻止重排的条件
    """
    # 简化版本：只检查是否有复杂条件
    import re
    # 检查是否有 UNION、DISTINCT、GROUP BY 等可能阻止重排
    blockers = ['UNION', 'DISTINCT', 'GROUP BY', 'HAVING']
    sql_upper = sql.upper()
    for blocker in blockers:
        if blocker in sql_upper:
            return False
    return True


def find_consolidation_candidates(sql: str) -> Optional[list[dict]]:
    """查找可以合并的 JOIN 候选

    检测多个小表是否连接到同一个主表
    """
    if not contains_join(sql):
        return None

    import re
    # 先按 LEFT JOIN 分割
    parts = re.split(r'(?:LEFT|RIGHT|FULL|INNER|CROSS)?\s*JOIN', sql, flags=re.IGNORECASE)

    if len(parts) < 3:  # 需要至少 2 个 JOIN
        return None

    # 解析每个 JOIN 的表和连接条件
    joins = []
    for part in parts[1:]:  # 跳过第一个 FROM 部分
        # 提取表名 - 支持 ON 前有或无别名的情况
        table_match = re.match(r'\s*(\w+)\s+(?:\w+\s+)?ON\s+([\w.]+)\s*=\s*([\w.]+)', part, re.IGNORECASE)
        if table_match:
            join_table = table_match.group(1)
            left_col = table_match.group(2)
            right_col = table_match.group(3)

            # 确定哪个是主表列
            left_table = left_col.split('.')[0] if '.' in left_col else left_col
            right_table = right_col.split('.')[0] if '.' in right_col else right_col

            joins.append({
                "table": join_table,
                "main_table": left_table if left_table != join_table else right_table,
                "join_col": left_col if left_table != join_table else right_col,
            })

    if len(joins) < 2:
        return None

    # 按主表和连接列分组
    connection_map = {}
    for join in joins:
        key = (join["main_table"].lower(), join["join_col"].lower())
        if key not in connection_map:
            connection_map[key] = []
        connection_map[key].append(join["table"])

    # 找出连接到同一个表的多个 JOIN
    candidates = []
    for key, tables in connection_map.items():
        if len(tables) >= 2:
            candidates.append({
                "main_table": key[0],
                "join_key": key[1],
                "tables": tables,
            })

    return candidates if candidates else None