"""Database connector abstract base class and implementations."""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Generator

# Lazy imports for optional dependencies - allows running without psycopg2/pymysql installed
_psycopg2 = None
_pymysql = None
_RealDictCursor = None


def _ensure_psycopg2():
    """Lazy import psycopg2, return None if not available."""
    global _psycopg2, _RealDictCursor
    if _psycopg2 is None:
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor

            _psycopg2 = psycopg2
            _RealDictCursor = RealDictCursor
        except ImportError:
            _psycopg2 = None
    return _psycopg2, _RealDictCursor


def _ensure_pymysql():
    """Lazy import pymysql, return None if not available."""
    global _pymysql
    if _pymysql is None:
        try:
            import pymysql

            _pymysql = pymysql
        except ImportError:
            _pymysql = None
    return _pymysql


class DBConnector(ABC):
    """Abstract base class for database connectors."""

    @abstractmethod
    def connect(self) -> None:
        """Establish database connection."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close database connection."""

    @abstractmethod
    def execute_explain(self, sql: str) -> dict[str, Any]:
        """Execute EXPLAIN and return plan as dict.

        Args:
            sql: SQL query to explain

        Returns:
            dict: EXPLAIN output as dictionary
        """

    @abstractmethod
    def execute_query(self, sql: str) -> list[dict[str, Any]]:
        """Execute query and return results.

        Args:
            sql: SQL query to execute

        Returns:
            List[dict]: Query results as list of row dicts
        """

    @contextmanager
    def transaction(self) -> Generator[None, None, None]:
        """Context manager for database transactions.

        Yields:
            None

        Raises:
            Exception: Re-raises any exception after rollback
        """
        try:
            yield
            self.commit()
        except Exception:
            self.rollback()
            raise

    @abstractmethod
    def commit(self) -> None:
        """Commit current transaction."""

    @abstractmethod
    def rollback(self) -> None:
        """Rollback current transaction."""


class PostgreSQLConnector(DBConnector):
    """PostgreSQL connector implementation."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        dbname: str = "postgres",
        user: str = "postgres",
        password: str = "",
    ) -> None:
        self.host = host
        self.port = port
        self.dbname = dbname
        self.user = user
        self.password = password
        self._conn = None

    def connect(self) -> None:
        if self._conn is None or self._conn.closed:
            psycopg2, RealDictCursor = _ensure_psycopg2()
            if psycopg2 is None:
                raise ImportError("psycopg2 is not installed. Install with: pip install psycopg2-binary")
            self._conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                dbname=self.dbname,
                user=self.user,
                password=self.password,
            )
            self._conn.autocommit = False

    def disconnect(self) -> None:
        """Close database connection."""
        if self._conn is not None and not self._conn.closed:
            self._conn.close()
            self._conn = None

    def commit(self) -> None:
        """Commit current transaction."""
        if self._conn is not None and not self._conn.closed:
            self._conn.commit()

    def rollback(self) -> None:
        """Rollback current transaction."""
        if self._conn is not None and not self._conn.closed:
            self._conn.rollback()

    def execute_explain(self, sql: str) -> dict[str, Any]:
        self.connect()
        if self._conn is None:
            return {}

        _, RealDictCursor = _ensure_psycopg2()
        explain_sql = f"EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS, FORMAT JSON) {sql}"

        with self._conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(explain_sql)
            result = cursor.fetchone()
            if result and "QUERY PLAN" in result:
                query_plan = result["QUERY PLAN"]
                if isinstance(query_plan, list) and len(query_plan) > 0:
                    return dict(query_plan[0])
                return {}
            return {}

    def execute_query(self, sql: str) -> list[dict[str, Any]]:
        """Execute query and return results.

        Args:
            sql: SQL query to execute

        Returns:
            List[dict]: Query results as list of row dicts
        """
        self.connect()
        if self._conn is None:
            return []

        with self._conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql)
            if cursor.description is None:
                return []
            return [dict(row) for row in cursor.fetchall()]

    def __repr__(self) -> str:
        return f"PostgreSQLConnector(host={self.host}, port={self.port}, dbname={self.dbname}, user={self.user})"


class MySQLConnector(DBConnector):
    """MySQL connector implementation."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 3306,
        db: str = "",
        user: str = "root",
        password: str = "",
        charset: str = "utf8mb4",
    ) -> None:
        self.host = host
        self.port = port
        self.db = db
        self.user = user
        self.password = password
        self.charset = charset
        self._conn = None

    def connect(self) -> None:
        if self._conn is None or not self._conn.open:
            pymysql = _ensure_pymysql()
            if pymysql is None:
                raise ImportError("pymysql is not installed. Install with: pip install pymysql")
            self._conn = pymysql.connect(
                host=self.host,
                port=self.port,
                database=self.db,
                user=self.user,
                password=self.password,
                charset=self.charset,
                cursorclass=pymysql.cursors.DictCursor,
            )
            self._conn.autocommit = False

    def disconnect(self) -> None:
        """Close database connection."""
        if self._conn is not None and self._conn.open:
            self._conn.close()
            self._conn = None

    def commit(self) -> None:
        """Commit current transaction."""
        if self._conn is not None and self._conn.open:
            self._conn.commit()

    def rollback(self) -> None:
        """Rollback current transaction."""
        if self._conn is not None and self._conn.open:
            self._conn.rollback()

    def execute_explain(self, sql: str) -> dict[str, Any]:
        """Execute EXPLAIN and return plan as JSON.

        Args:
            sql: SQL query to explain

        Returns:
            dict: EXPLAIN output as dictionary
        """
        self.connect()
        if self._conn is None or not self._conn.open:
            return {}

        explain_sql = f"EXPLAIN FORMAT=JSON {sql}"

        with self._conn.cursor() as cursor:
            cursor.execute(explain_sql)
            result = cursor.fetchone()
            if result:
                return dict(result)
            return {}

    def execute_query(self, sql: str) -> list[dict[str, Any]]:
        """Execute query and return results.

        Args:
            sql: SQL query to execute

        Returns:
            List[dict]: Query results as list of row dicts
        """
        self.connect()
        if self._conn is None or not self._conn.open:
            return []

        with self._conn.cursor() as cursor:
            cursor.execute(sql)
            return [dict(row) for row in cursor.fetchall()]

    def __repr__(self) -> str:
        return f"MySQLConnector(host={self.host}, port={self.port}, db={self.db}, user={self.user})"


def create_connector(
    platform: str,
    host: str,
    port: int,
    db: str,
    user: str,
    password: str,
) -> DBConnector:
    if platform == "postgresql":
        psycopg2 = _ensure_psycopg2()[0]
        if psycopg2 is None:
            raise ImportError(
                "psycopg2 is required for PostgreSQL but not installed. Install with: pip install psycopg2-binary"
            )
        return PostgreSQLConnector(
            host=host,
            port=port,
            dbname=db,
            user=user,
            password=password,
        )
    if platform == "mysql":
        pymysql = _ensure_pymysql()
        if pymysql is None:
            raise ImportError("pymysql is required for MySQL but not installed. Install with: pip install pymysql")
        return MySQLConnector(
            host=host,
            port=port,
            db=db,
            user=user,
            password=password,
        )
    raise ValueError(f"Unsupported platform: {platform}")
