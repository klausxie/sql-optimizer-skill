"""Database connector abstract base class and implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Generator

import psycopg2
import pymysql
from psycopg2.extras import RealDictCursor


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
        """Initialize PostgreSQL connector.

        Args:
            host: Database host address
            port: Database port
            dbname: Database name
            user: Database user
            password: Database password
        """
        self.host = host
        self.port = port
        self.dbname = dbname
        self.user = user
        self.password = password
        self._conn: psycopg2.connection | None = None

    def connect(self) -> None:
        """Establish database connection."""
        if self._conn is None or self._conn.closed:
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
        """Execute EXPLAIN ANALYZE and return plan as JSON.

        Args:
            sql: SQL query to explain

        Returns:
            dict: EXPLAIN ANALYZE output as dictionary
        """
        self.connect()
        if self._conn is None:
            return {}

        explain_sql = f"EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS, FORMAT JSON) {sql}"

        with self._conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(explain_sql)
            result = cursor.fetchone()
            if result and "QUERY PLAN" in result:
                query_plan = result["QUERY PLAN"]
                if isinstance(query_plan, list) and len(query_plan) > 0:
                    return query_plan[0]
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
        """Initialize MySQL connector.

        Args:
            host: Database host address
            port: Database port
            db: Database name
            user: Database user
            password: Database password
            charset: Character set
        """
        self.host = host
        self.port = port
        self.db = db
        self.user = user
        self.password = password
        self.charset = charset
        self._conn: pymysql.Connection | None = None

    def connect(self) -> None:
        """Establish database connection."""
        if self._conn is None or not self._conn.open:
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
    """Factory function to create connector by platform.

    Args:
        platform: 'postgresql' or 'mysql'
        host: Database host address
        port: Database port
        db: Database name
        user: Database user
        password: Database password

    Returns:
        DBConnector instance

    Raises:
        ValueError: If platform is not supported
    """
    if platform == "postgresql":
        return PostgreSQLConnector(
            host=host,
            port=port,
            dbname=db,
            user=user,
            password=password,
        )
    if platform == "mysql":
        return MySQLConnector(
            host=host,
            port=port,
            db=db,
            user=user,
            password=password,
        )
    raise ValueError(f"Unsupported platform: {platform}")
