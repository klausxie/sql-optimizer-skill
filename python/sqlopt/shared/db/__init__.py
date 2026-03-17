"""
Shared DB Module

Database connection management and query execution.
"""

from typing import Any


def check_connectivity(config: dict[str, Any]) -> dict[str, Any]:
    """Check database connectivity.

    Args:
        config: Configuration dictionary with db settings

    Returns:
        Dictionary with connectivity status
    """
    from sqlopt.platforms.dispatch import check_db_connectivity

    return check_db_connectivity(config)


def get_platform(dialect: str) -> str:
    """Get platform name from dialect.

    Args:
        dialect: Database dialect (postgresql, mysql, etc.)

    Returns:
        Platform name
    """
    dialect = dialect.lower()
    if dialect in ("postgresql", "postgres", "pg"):
        return "postgresql"
    elif dialect in ("mysql", "mariadb"):
        return "mysql"
    return dialect


__all__ = [
    "check_connectivity",
    "get_platform",
]
