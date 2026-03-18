"""Database validator for SQL optimization validation.

This module provides DBValidator class that performs actual database
validation by executing EXPLAIN and comparing execution plans.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ...platforms.dispatch import compare_plan, compare_semantics, get_platform_adapter
from .semantic_checker import SemanticChecker, ValidationResult


@dataclass
class DBValidationResult:
    """Result of database validation including semantic and performance checks."""

    semantic_equivalent: bool
    semantic_confidence: float
    semantic_reason: str
    plan_improved: Optional[bool] = None
    plan_checked: bool = False
    plan_before_cost: Optional[float] = None
    plan_after_cost: Optional[float] = None
    plan_reason_codes: list[str] = field(default_factory=list)
    plan_error: Optional[str] = None
    db_reachable: bool = True
    equivalence_checked: bool = False
    equivalence_result: Optional[dict[str, Any]] = None
    evidence_refs: list[str] = field(default_factory=list)


class DBValidator:
    """Validates SQL optimizations using database execution and semantic checks.

    This class provides two-tier validation:
    1. Fast path: Semantic equivalence checking (no DB required)
    2. Full path: Database EXPLAIN comparison for performance validation
    """

    def __init__(
        self,
        config: dict[str, Any],
        evidence_dir: Optional[Path] = None,
    ):
        """Initialize the DB validator.

        Args:
            config: Configuration dictionary containing DB settings
            evidence_dir: Directory to store evidence files
        """
        self.config = config
        self.evidence_dir = evidence_dir
        self._semantic_checker = SemanticChecker()

    def validate_proposal(
        self,
        original_sql: str,
        optimized_sql: str,
        skip_semantic: bool = False,
    ) -> DBValidationResult:
        """Validate an optimization proposal.

        Performs semantic equivalence check (fast path) and optionally
        database plan comparison (full path).

        Args:
            original_sql: Original SQL statement
            optimized_sql: Optimized SQL statement
            skip_semantic: If True, skip semantic check (only do DB validation)

        Returns:
            DBValidationResult with validation details
        """
        # Fast path: Semantic equivalence check
        if not skip_semantic:
            semantic_result = self._semantic_checker._perform_validation(
                original_sql, optimized_sql
            )
            if not semantic_result.is_equivalent:
                return DBValidationResult(
                    semantic_equivalent=False,
                    semantic_confidence=semantic_result.confidence,
                    semantic_reason=semantic_result.reason,
                    plan_improved=None,
                    plan_checked=False,
                )
        else:
            semantic_result = None

        # Full path: Database validation
        db_result = self._perform_db_validation(original_sql, optimized_sql)

        # Combine results
        return DBValidationResult(
            semantic_equivalent=True
            if semantic_result is None
            else semantic_result.is_equivalent,
            semantic_confidence=1.0
            if semantic_result is None
            else semantic_result.confidence,
            semantic_reason="Passed semantic check"
            if semantic_result is None
            else semantic_result.reason,
            plan_improved=db_result.get("improved"),
            plan_checked=db_result.get("checked", False),
            plan_before_cost=(db_result.get("beforeSummary") or {}).get("totalCost"),
            plan_after_cost=(db_result.get("afterSummary") or {}).get("totalCost"),
            plan_reason_codes=db_result.get("reasonCodes", []),
            plan_error=db_result.get("error"),
            db_reachable=db_result.get("reasonCategory") != "DB_UNREACHABLE",
            equivalence_checked=db_result.get("checked", False),
            equivalence_result=db_result,
            evidence_refs=db_result.get("evidenceRefs", []),
        )

    def _perform_db_validation(
        self,
        original_sql: str,
        optimized_sql: str,
    ) -> dict[str, Any]:
        """Perform database-based validation using EXPLAIN.

        Args:
            original_sql: Original SQL statement
            optimized_sql: Optimized SQL statement

        Returns:
            Dictionary with validation results
        """
        # Check if DB is configured
        db_cfg = self.config.get("db", {}) or {}
        dsn = db_cfg.get("dsn")

        if not dsn:
            return {
                "checked": False,
                "reason": "dsn_not_set",
                "reasonCategory": "NO_DSN",
                "improved": None,
                "reasonCodes": [],
            }

        # Check if platform adapter is available
        try:
            adapter = get_platform_adapter(self.config)
        except Exception as e:
            return {
                "checked": False,
                "reason": "platform_adapter_error",
                "reasonCategory": "PLATFORM_ERROR",
                "error": str(e),
                "improved": None,
                "reasonCodes": [],
            }

        # Create evidence directory if specified
        evidence_dir = self.evidence_dir
        if evidence_dir is None:
            evidence_dir = Path.cwd() / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)

        # Perform plan comparison
        validate_cfg = self.config.get("validate", {}) or {}
        if validate_cfg.get("plan_compare_enabled", True):
            try:
                plan_result = compare_plan(
                    self.config,
                    original_sql,
                    optimized_sql,
                    evidence_dir,
                )
                return plan_result
            except Exception as e:
                return {
                    "checked": True,
                    "error": str(e),
                    "improved": None,
                    "reasonCodes": [],
                    "reasonCategory": "EXPLAIN_ERROR",
                }
        else:
            return {
                "checked": False,
                "reason": "plan_compare_disabled",
                "reasonCategory": "PLAN_COMPARE_DISABLED",
                "improved": None,
                "reasonCodes": [],
            }

    def validate_semantics_only(
        self,
        original_sql: str,
        optimized_sql: str,
    ) -> ValidationResult:
        """Perform semantic-only validation (fast path without DB).

        Args:
            original_sql: Original SQL statement
            optimized_sql: Optimized SQL statement

        Returns:
            ValidationResult with semantic equivalence details
        """
        return self._semantic_checker._perform_validation(original_sql, optimized_sql)

    def check_db_reachable(self) -> bool:
        """Check if database is reachable.

        Returns:
            True if database connection can be established
        """
        try:
            adapter = get_platform_adapter(self.config)
            result = adapter.check_db_connectivity(self.config)
            return result.get("reachable", False)
        except Exception:
            return False

    def get_semantic_diff(
        self,
        original_sql: str,
        optimized_sql: str,
    ) -> str:
        """Get human-readable diff between SQL statements.

        Args:
            original_sql: Original SQL statement
            optimized_sql: Optimized SQL statement

        Returns:
            Human-readable difference description
        """
        return self._semantic_checker.get_difference(original_sql, optimized_sql)

    def is_semantic_equivalent(
        self,
        original_sql: str,
        optimized_sql: str,
    ) -> bool:
        """Quick check if SQL statements are semantically equivalent.

        Args:
            original_sql: Original SQL statement
            optimized_sql: Optimized SQL statement

        Returns:
            True if semantically equivalent
        """
        return self._semantic_checker.verify_semantics(original_sql, optimized_sql)
