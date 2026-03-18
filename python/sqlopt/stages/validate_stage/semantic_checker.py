"""V8 semantic equivalence checker for SQL validation."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ValidationResult:
    """Result of semantic equivalence validation."""

    is_equivalent: bool
    confidence: float
    reason: str
    checks_passed: list[str] = field(default_factory=list)
    checks_failed: list[str] = field(default_factory=list)


class SemanticChecker:
    """Checks semantic equivalence between original and optimized SQL."""

    def verify_semantics(self, original: str, optimized: str) -> bool:
        """
        Verify if two SQL statements are semantically equivalent.

        Args:
            original: Original SQL statement
            optimized: Optimized SQL statement

        Returns:
            True if semantically equivalent, False otherwise
        """
        result = self._perform_validation(original, optimized)
        return result.is_equivalent

    def get_difference(self, original: str, optimized: str) -> str:
        """
        Get human-readable diff between two SQL statements.

        Args:
            original: Original SQL statement
            optimized: Optimized SQL statement

        Returns:
            Human-readable difference description
        """
        result = self._perform_validation(original, optimized)

        if result.is_equivalent:
            return f"Semantically equivalent (confidence: {result.confidence:.1%})"

        diff_parts = []
        if result.checks_failed:
            diff_parts.append(f"Failed checks: {', '.join(result.checks_failed)}")
        diff_parts.append(f"Reason: {result.reason}")

        return "; ".join(diff_parts)

    def _perform_validation(self, original: str, optimized: str) -> ValidationResult:
        """Perform full semantic validation."""
        checks_passed = []
        checks_failed = []

        # Normalize SQL for comparison
        orig_norm = self._normalize_sql(original)
        opt_norm = self._normalize_sql(optimized)

        # Check exact match after normalization
        if orig_norm == opt_norm:
            return ValidationResult(
                is_equivalent=True,
                confidence=1.0,
                reason="SQL statements are identical after normalization",
                checks_passed=["exact_match", "normalization"],
            )

        # Check WHERE clause equivalence
        if self._check_where_equivalence(orig_norm, opt_norm):
            checks_passed.append("where_clause")
        else:
            checks_failed.append("where_clause")

        # Check column selections match
        if self._check_selections_match(orig_norm, opt_norm):
            checks_passed.append("selections")
        else:
            checks_failed.append("selections")

        # Check JOIN conditions match
        if self._check_joins_match(orig_norm, opt_norm):
            checks_passed.append("joins")
        else:
            checks_failed.append("joins")

        # Calculate confidence based on passed checks
        total_checks = len(checks_passed) + len(checks_failed)
        if total_checks > 0:
            confidence = len(checks_passed) / total_checks
        else:
            confidence = 0.0

        # Determine equivalence
        is_equivalent = len(checks_failed) == 0 and confidence >= 0.8

        if is_equivalent:
            reason = "All semantic checks passed"
        elif checks_failed:
            reason = f"Failed: {', '.join(checks_failed)}"
        else:
            reason = "Insufficient confidence for equivalence"

        return ValidationResult(
            is_equivalent=is_equivalent,
            confidence=confidence,
            reason=reason,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
        )

    def _normalize_sql(self, sql: str) -> str:
        """Normalize SQL for comparison."""
        import re

        # Lowercase
        normalized = sql.lower()
        # Remove extra whitespace
        normalized = re.sub(r"\s+", " ", normalized).strip()
        # Remove comments
        normalized = re.sub(r"--.*$", "", normalized, flags=re.MULTILINE)
        normalized = re.sub(r"/\*.*?\*/", "", normalized, flags=re.DOTALL)
        # Remove trailing semicolons
        normalized = normalized.rstrip(";").strip()

        return normalized

    def _extract_where_clause(self, sql: str) -> Optional[str]:
        """Extract WHERE clause from SQL."""
        import re

        match = re.search(
            r"\bwhere\b(.+?)(?=\bgroup\b|\border\b|\blimit\b|\bunion\b|\bselect\b|$)",
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            return match.group(1).strip()
        return None

    def _extract_select_columns(self, sql: str) -> set[str]:
        """Extract selected columns from SQL."""
        import re

        columns = set()
        match = re.search(r"\bselect\b(.+?)\bfrom\b", sql, re.IGNORECASE | re.DOTALL)
        if match:
            cols_str = match.group(1).strip()
            # Split by comma
            for col in cols_str.split(","):
                col = col.strip()
                # Remove aliases
                col = re.sub(r"\s+as\s+\w+$", "", col, flags=re.IGNORECASE)
                if col not in ("*", ""):
                    columns.add(col)
        return columns

    def _extract_joins(self, sql: str) -> list[tuple[str, str, str]]:
        """Extract JOIN conditions from SQL."""
        import re

        joins = []
        # Find all JOIN patterns
        pattern = r"\b(join|inner\s+join|left\s+join|right\s+join|full\s+join|cross\s+join)\s+(\w+)\s+on\s+(.+?)(?=\bjoin\b|\bwhere\b|\bgroup\b|\border\b|\blimit\b|$)"
        for match in re.finditer(pattern, sql, re.IGNORECASE | re.DOTALL):
            join_type = match.group(1).strip()
            table = match.group(2).strip()
            condition = match.group(3).strip()
            joins.append((join_type, table, condition))
        return joins

    def _check_where_equivalence(self, orig: str, opt: str) -> bool:
        """Check if WHERE clauses are equivalent."""
        orig_where = self._extract_where_clause(orig)
        opt_where = self._extract_where_clause(opt)

        if orig_where is None and opt_where is None:
            return True
        if orig_where is None or opt_where is None:
            return False

        # Normalize and compare
        return self._normalize_condition(orig_where) == self._normalize_condition(
            opt_where
        )

    def _check_selections_match(self, orig: str, opt: str) -> bool:
        """Check if column selections match."""
        orig_cols = self._extract_select_columns(orig)
        opt_cols = self._extract_select_columns(opt)

        if orig_cols == opt_cols:
            return True

        # Check if they differ only in ordering (for SELECT *)
        if "*" in orig_cols or "*" in opt_cols:
            return True

        return False

    def _check_joins_match(self, orig: str, opt: str) -> bool:
        """Check if JOIN conditions match."""
        orig_joins = self._extract_joins(orig)
        opt_joins = self._extract_joins(opt)

        if len(orig_joins) != len(opt_joins):
            return False

        for (o_type, o_table, o_cond), (i_type, i_table, i_cond) in zip(
            orig_joins, opt_joins
        ):
            if o_type.lower() != i_type.lower():
                return False
            if o_table.lower() != i_table.lower():
                return False
            if self._normalize_condition(o_cond) != self._normalize_condition(i_cond):
                return False

        return True

    def _normalize_condition(self, condition: str) -> str:
        """Normalize a condition for comparison."""
        import re

        normalized = condition.lower().strip()
        normalized = re.sub(r"\s+", " ", normalized)
        # Remove parenthetical wrapping if both sides match
        normalized = re.sub(r"^\((.+)\)$", r"\1", normalized)
        return normalized
