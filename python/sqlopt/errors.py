from __future__ import annotations

class SqlOptError(Exception):
    pass


class ConfigError(SqlOptError):
    pass


class ContractError(SqlOptError):
    pass


class StageError(SqlOptError):
    def __init__(self, message: str, reason_code: str | None = None):
        super().__init__(message)
        self.reason_code = reason_code
