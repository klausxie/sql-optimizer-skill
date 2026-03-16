from __future__ import annotations

import sys
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIR = ROOT / "python"

if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

# Test isolation: use isolated test database
TEST_DB_NAME = "sqlopt_test"


def get_mysql_dsn(platform: str = "mysql", database: str = TEST_DB_NAME) -> str:
    """Get MySQL DSN from environment or use default test credentials."""
    host = os.environ.get("SQLOPT_TEST_HOST", "127.0.0.1")
    port = int(os.environ.get("SQLOPT_TEST_PORT", "3306"))
    user = os.environ.get("SQLOPT_TEST_USER", "root")
    password = os.environ.get("SQLOPT_TEST_PASSWORD", "root")
    return f"mysql://{user}:{password}@{host}:{port}/{database}"


def get_postgres_dsn(platform: str = "postgresql", database: str = "sqlopt_test") -> str:
    """Get PostgreSQL DSN from environment or use default test credentials."""
    host = os.environ.get("SQLOPT_TEST_HOST", "127.0.0.1")
    port = int(os.environ.get("SQLOPT_TEST_PORT", "5432"))
    user = os.environ.get("SQLOPT_TEST_USER", "postgres")
    password = os.environ.get("SQLOPT_TEST_PASSWORD", "postgres")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


# Export for convenience
__all__ = [
    "get_mysql_dsn",
    "get_postgres_dsn",
    "TEST_DB_NAME",
]
