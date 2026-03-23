"""Error hierarchy for SQL Optimizer.

All exceptions are JSON-serializable via to_dict() method.
"""

from __future__ import annotations


class SQLOptError(Exception):
    """Base exception for all SQL Optimizer errors."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """Serialize error to JSON-compatible dict."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


class ConfigError(SQLOptError):
    """Configuration related errors."""


class StageError(SQLOptError):
    """Stage execution errors."""


class ContractError(SQLOptError):
    """Contract validation errors."""


class LLMError(SQLOptError):
    """LLM provider errors."""


class DBError(SQLOptError):
    """Database connection/execution errors."""
