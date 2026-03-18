"""H2 数据库适配器 - 基于 JDBC 兼容接口。

H2 是一个嵌入式 Java 数据库，通常用于 Spring Boot 测试环境。
由于 Python 不支持直接连接 H2，此适配器提供降级支持：
- 连接检测返回警告（需要 JDBC）
- SQL 语法兼容 PostgreSQL 模式
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..base import FunctionPlatformAdapter, PlatformCapabilities


def check_db_connectivity(config: dict[str, Any]) -> dict[str, Any]:
    """检查 H2 数据库连通性。

    H2 是 Java 数据库，Python 无法直接连接。
    返回降级提示，建议用户切换到 PostgreSQL 或 MySQL 进行验证。
    """
    return {
        "ok": False,
        "error": "H2 数据库需要 JDBC 连接，Python 不直接支持。请使用 PostgreSQL 或 MySQL 进行验证，或配置 validate.allow_db_unreachable_fallback: true 启用降级模式。",
        "reason_code": "H2_REQUIRES_JDBC",
        "suggestion": "切换到 PostgreSQL 或 MySQL 进行完整验证",
    }


def collect_sql_evidence(
    config: dict[str, Any], sql: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """收集 SQL 证据（降级模式）。

    由于无法连接 H2，返回静态分析结果。
    """
    return {}, {"status": "degraded", "reason": "H2 requires JDBC"}


def compare_plan(
    config: dict[str, Any],
    original_sql: str,
    rewritten_sql: str,
    evidence_dir: Path,
) -> dict[str, Any]:
    """比较执行计划（降级模式）。"""
    return {"status": "skipped", "reason": "H2 requires JDBC"}


def compare_semantics(
    config: dict[str, Any],
    original_sql: str,
    rewritten_sql: str,
    evidence_dir: Path,
) -> dict[str, Any]:
    """比较语义（降级模式）。"""
    return {"status": "skipped", "reason": "H2 requires JDBC"}


def get_adapter() -> FunctionPlatformAdapter:
    return FunctionPlatformAdapter(
        name="h2",
        capabilities=PlatformCapabilities(
            supports_connectivity_check=True,
            supports_plan_compare=False,  # 降级模式
            supports_semantic_compare=False,  # 降级模式
            supports_sql_evidence=False,  # 降级模式
        ),
        check_db_connectivity_fn=check_db_connectivity,
        collect_sql_evidence_fn=collect_sql_evidence,
        compare_plan_fn=compare_plan,
        compare_semantics_fn=compare_semantics,
    )
