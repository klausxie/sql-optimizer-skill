"""公共工具函数模块。

此模块存放跨多个 stage 使用的工具函数，避免重复定义。
"""

from __future__ import annotations

from typing import Any


def statement_key(sql_key: str, explicit_statement_key: str | None = None) -> str:
    """从 sql_key 中提取 statement_key（去掉版本后缀）。

    Args:
        sql_key: 完整的 SQL key，如 "demo.user.findUsers#v1"
        explicit_statement_key: 显式 statement_key，若提供则优先返回

    Returns:
        Statement key，如 "demo.user.findUsers"
    """
    explicit = str(explicit_statement_key or "").strip()
    if explicit:
        return explicit
    return str(sql_key or "").split("#", 1)[0]


def statement_key_from_row(row: dict[str, Any] | None) -> str:
    """从对象中稳定提取 statement_key。

    优先读取显式 statementKey/statement_key，兼容旧数据时再从 sqlKey/sql_key 推导。
    """
    payload = row or {}
    explicit = str(payload.get("statementKey") or payload.get("statement_key") or "").strip()
    if explicit:
        return explicit
    sql_key = str(payload.get("sqlKey") or payload.get("sql_key") or "").strip()
    return statement_key(sql_key)


def sql_key_path_component(sql_key: str) -> str:
    """将 sql_key 规范化为可用于路径段的稳定字符串。"""
    normalized = "".join(ch if ch.isalnum() else "_" for ch in str(sql_key or ""))
    compact = "_".join(part for part in normalized.split("_") if part)
    return compact or "unknown_sql"


def is_sql_syntax_error(message: str | None) -> bool:
    """检查错误消息是否为 SQL 语法错误。

    Args:
        message: 错误消息文本

    Returns:
        如果是 SQL 语法错误返回 True，否则返回 False
    """
    text = str(message or "").strip().lower()
    if not text:
        return False
    markers = [
        "syntax error",
        "you have an error in your sql syntax",
        "parse error",
        "(1064,",
    ]
    return any(marker in text for marker in markers)


def truncate_string(text: str | None, max_length: int = 100, suffix: str = "...") -> str | None:
    """截断字符串到指定长度。

    Args:
        text: 原始字符串
        max_length: 最大长度
        suffix: 截断后添加的后缀

    Returns:
        截断后的字符串，如果输入为 None 则返回 None
    """
    if text is None:
        return None
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def safe_get(d: dict | None, *keys: str, default: Any = None) -> Any:
    """安全地从嵌套字典中获取值。

    Args:
        d: 字典
        keys: 嵌套的键序列
        default: 默认值

    Returns:
        键对应的值，如果任何中间步骤失败则返回默认值

    Example:
        >>> safe_get({"a": {"b": 1}}, "a", "b")
        1
        >>> safe_get({"a": {}}, "a", "b", default=0)
        0
    """
    if d is None:
        return default
    current: Any = d
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current
