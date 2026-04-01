import logging
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Generator, Optional

import psycopg2.pool

logger = logging.getLogger(__name__)


class DBPoolBase(ABC):
    @abstractmethod
    def get_connection(self):
        pass

    @abstractmethod
    def return_connection(self, conn):
        pass

    @abstractmethod
    def close_all(self):
        pass

    @contextmanager
    @abstractmethod
    def connection(self) -> Generator:
        pass


class PostgreSQLPool(DBPoolBase):
    def __init__(
        self,
        host,
        port,
        database,
        user,
        password,
        minconn=1,
        maxconn=4,
        connect_options: Optional[dict[str, Any]] = None,
    ):
        if connect_options is None:
            connect_options = {}
        self._connect_options = connect_options
        self._pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=minconn,
            maxconn=maxconn,
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            **connect_options,
        )

    def get_connection(self):
        return self._pool.getconn()

    def return_connection(self, conn):
        self._pool.putconn(conn)

    def close_all(self):
        self._pool.closeall()

    @contextmanager
    def connection(self) -> Generator:
        conn = None
        try:
            conn = self.get_connection()
            yield conn
        finally:
            if conn is not None:
                self.return_connection(conn)


class DBPoolManager:
    _instance = None
    _pools: dict

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._pools = {}
        return cls._instance

    def register_pool(self, name, pool):
        self._pools[name] = pool

    def get_pool(self, name):
        return self._pools.get(name)

    def close_all(self):
        for pool in self._pools.values():
            pool.close_all()
        self._pools.clear()

    def create_postgresql_pool(
        self,
        name,
        host,
        port,
        database,
        user,
        password,
        minconn=1,
        maxconn=4,
        connect_options: Optional[dict[str, Any]] = None,
    ):
        if connect_options is None:
            connect_options = {}
        pool = PostgreSQLPool(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            minconn=minconn,
            maxconn=maxconn,
            connect_options=connect_options,
        )
        self.register_pool(name, pool)
        return pool
