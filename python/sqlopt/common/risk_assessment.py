"""
Risk assessment module for SQL optimization.

Provides Severity-tier classification, RiskFactor registry, and RiskAssessment
aggregation following DECISION-006-risk-scoring-overhaul.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Severity(Enum):
    CRITICAL = "CRITICAL"  # will cause full table scan or index bypass
    WARNING = "WARNING"  # inefficient, degrades with data growth
    INFO = "INFO"  # suboptimal, no immediate danger


class Domain(Enum):
    SYNTACTIC = "SYNTACTIC"  # SQL structure issue (deterministic)
    METADATA = "METADATA"  # schema/data distribution issue (conditional)


class ImpactType(Enum):
    FULL_SCAN = "full_scan"
    INDEX_BYPASS = "index_bypass"
    ROW_AMPLIFICATION = "row_amplification"
    MEMORY_PRESSURE = "memory_pressure"
    IO_SPIKE = "io_spike"


@dataclass
class RiskFactor:
    """
    A complete, self-documenting risk finding.

    Attributes:
        code: Internal identifier (e.g., "LIKE_PREFIX", "NO_INDEX_ON_FILTER")
        severity: Severity tier (CRITICAL/WARNING/INFO)
        domain: Evidence source (SYNTACTIC/METADATA)
        weight: Raw weight (retained for compatibility)
        explanation_template: Human-readable problem description (with placeholders)
        impact_type: Database impact category
        remediation_template: How to fix (with placeholders)
        context: Runtime-filled context (e.g., {"column": "search_condition"})
        mysql_note: MySQL-specific hint
        postgresql_note: PostgreSQL-specific hint
    """

    code: str
    severity: Severity
    domain: Domain
    weight: float
    explanation_template: str
    impact_type: ImpactType
    remediation_template: str
    context: dict = field(default_factory=dict)
    mysql_note: str = ""
    postgresql_note: str = ""

    def render_explanation(self) -> str:
        try:
            return self.explanation_template.format(**self.context)
        except KeyError:
            return self.explanation_template

    def render_remediation(self) -> str:
        try:
            return self.remediation_template.format(**self.context)
        except KeyError:
            return self.remediation_template

    def to_dict(self) -> dict:
        """Serialize to dict for JSON output."""
        return {
            "code": self.code,
            "severity": self.severity.value,
            "domain": self.domain.value,
            "weight": self.weight,
            "explanation": self.render_explanation(),
            "remediation": self.render_remediation(),
            "context": self.context,
            "impact_type": self.impact_type.value,
            "mysql_note": self.mysql_note,
            "postgresql_note": self.postgresql_note,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# RISK_FACTOR_REGISTRY — 14 predefined risk factors
# ═══════════════════════════════════════════════════════════════════════════════

RISK_FACTOR_REGISTRY: dict[str, RiskFactor] = {
    # ═══ CRITICAL ═══
    "LIKE_PREFIX": RiskFactor(
        code="LIKE_PREFIX",
        severity=Severity.CRITICAL,
        domain=Domain.SYNTACTIC,
        weight=3.0,
        impact_type=ImpactType.INDEX_BYPASS,
        explanation_template=(
            "LIKE with leading wildcard ('%...') on column `{column}` "
            "prevents index usage. Database must scan every row."
        ),
        remediation_template=(
            "MySQL: Consider full-text index. PostgreSQL: Use pg_trgm GIN index or reverse the pattern."
        ),
        mysql_note="Full-text search: MATCH(col) AGAINST('keyword')",
        postgresql_note="CREATE INDEX USING gin (col gin_trgm_ops)",
    ),
    "FUNCTION_ON_INDEXED_COLUMN": RiskFactor(
        code="FUNCTION_ON_INDEXED_COLUMN",
        severity=Severity.CRITICAL,
        domain=Domain.SYNTACTIC,
        weight=3.0,
        impact_type=ImpactType.INDEX_BYPASS,
        explanation_template=(
            "Function `{function_name}()` wraps column `{column}` in WHERE clause. "
            "This prevents the optimizer from using any index on `{column}`."
        ),
        remediation_template=(
            "Extract function result into a subquery or use expression index. "
            "Alternatively, refactor to: WHERE {column} = 'value' (pre-computed)."
        ),
    ),
    "NO_INDEX_ON_FILTER": RiskFactor(
        code="NO_INDEX_ON_FILTER",
        severity=Severity.CRITICAL,
        domain=Domain.METADATA,
        weight=3.0,
        impact_type=ImpactType.FULL_SCAN,
        explanation_template=(
            "Column `{column}` is used in WHERE/JOIN clause but has no index. "
            "Every query will perform a full table scan on `{table}` "
            "(est. {row_count:,} rows)."
        ),
        remediation_template=("Add index: CREATE INDEX idx_{table}_{column} ON {table}({column})."),
    ),
    "NOT_IN_LARGE_TABLE": RiskFactor(
        code="NOT_IN_LARGE_TABLE",
        severity=Severity.CRITICAL,
        domain=Domain.SYNTACTIC,
        weight=3.0,
        impact_type=ImpactType.FULL_SCAN,
        explanation_template=(
            "NOT IN on subquery result forces a nested loop scan. "
            "For large result sets, this is equivalent to a cross join."
        ),
        remediation_template="Replace with NOT EXISTS or LEFT JOIN WHERE NULL.",
    ),
    # ═══ WARNING ═══
    "DEEP_OFFSET": RiskFactor(
        code="DEEP_OFFSET",
        severity=Severity.WARNING,
        domain=Domain.SYNTACTIC,
        weight=2.0,
        impact_type=ImpactType.ROW_AMPLIFICATION,
        explanation_template=(
            "OFFSET pagination scans and discards {offset_value} rows before "
            "returning results. Performance degrades linearly with page number. "
            "Users typically request pages 1-10; page 10000 still scans 10000 rows."
        ),
        remediation_template=(
            "Replace with keyset pagination: WHERE id > {last_seen_id} LIMIT 10. "
            "This gives consistent ~0ms response regardless of page number."
        ),
    ),
    "SUBQUERY": RiskFactor(
        code="SUBQUERY",
        severity=Severity.WARNING,
        domain=Domain.SYNTACTIC,
        weight=2.0,
        impact_type=ImpactType.ROW_AMPLIFICATION,
        explanation_template=(
            "Correlated subquery executes once per outer row. "
            "Cost = O(outer_rows x inner_rows). "
            "At scale, this causes N+1-like amplification."
        ),
        remediation_template="Rewrite as a JOIN. Most correlated subqueries can be refactored.",
    ),
    "JOIN_WITHOUT_INDEX": RiskFactor(
        code="JOIN_WITHOUT_INDEX",
        severity=Severity.WARNING,
        domain=Domain.METADATA,
        weight=2.0,
        impact_type=ImpactType.ROW_AMPLIFICATION,
        explanation_template=(
            "JOIN on `{column}` lacks a matching index. "
            "Cost grows as O(MxN) where M and N are table sizes. "
            "On large tables this causes nested-loop scans."
        ),
        remediation_template=("Add index on join column: CREATE INDEX idx_{table}_{column} ON {table}({column})."),
    ),
    "IN_CLAUSE_LARGE": RiskFactor(
        code="IN_CLAUSE_LARGE",
        severity=Severity.WARNING,
        domain=Domain.SYNTACTIC,
        weight=2.0,
        impact_type=ImpactType.MEMORY_PRESSURE,
        explanation_template=(
            "IN clause with {value_count}+ values may cause query plan instability. "
            "The optimizer may choose different plans as value count changes."
        ),
        remediation_template=(
            "Use a temp table for the IN values and replace IN with EXISTS or JOIN. "
            "Alternatively, batch large IN clauses into multiple queries."
        ),
    ),
    "UNION_WITHOUT_ALL": RiskFactor(
        code="UNION_WITHOUT_ALL",
        severity=Severity.WARNING,
        domain=Domain.SYNTACTIC,
        weight=2.0,
        impact_type=ImpactType.IO_SPIKE,
        explanation_template=(
            "UNION (without ALL) adds an implicit DISTINCT sort. "
            "This requires memory for the sort buffer and CPU for sorting. "
            "If duplicates are acceptable, UNION ALL is significantly faster."
        ),
        remediation_template="Use UNION ALL if duplicates are acceptable.",
    ),
    "SKEWED_DISTRIBUTION": RiskFactor(
        code="SKEWED_DISTRIBUTION",
        severity=Severity.WARNING,
        domain=Domain.METADATA,
        weight=2.0,
        impact_type=ImpactType.FULL_SCAN,
        explanation_template=(
            "Column `{column}` is highly skewed: top value `{top_value}` "
            "appears in {skew_pct}% of rows. "
            "The optimizer may choose a suboptimal plan for common values."
        ),
        remediation_template=(
            "Consider a partial index or histogram-based statistics. "
            "For extreme skew, investigate whether the data model is correct."
        ),
    ),
    # ═══ INFO ═══
    "SELECT_STAR": RiskFactor(
        code="SELECT_STAR",
        severity=Severity.INFO,
        domain=Domain.SYNTACTIC,
        weight=1.0,
        impact_type=ImpactType.IO_SPIKE,
        explanation_template=(
            "SELECT * retrieves all columns including those not needed by the application. "
            "It also breaks when schema changes (new columns added). "
            "Explicit column lists are more maintainable."
        ),
        remediation_template=(
            "Replace SELECT * with explicit column list. Future-proofs the code against schema changes."
        ),
    ),
    "DISTINCT": RiskFactor(
        code="DISTINCT",
        severity=Severity.INFO,
        domain=Domain.SYNTACTIC,
        weight=1.0,
        impact_type=ImpactType.MEMORY_PRESSURE,
        explanation_template=(
            "DISTINCT triggers a hash or sort operation to deduplicate results. "
            "Verify that duplicates are actually possible from your query structure."
        ),
        remediation_template=(
            "If duplicates cannot occur, remove DISTINCT. If they can, ensure the application needs all duplicate rows."
        ),
    ),
    "HIGH_NULL_RATIO": RiskFactor(
        code="HIGH_NULL_RATIO",
        severity=Severity.INFO,
        domain=Domain.METADATA,
        weight=1.0,
        impact_type=ImpactType.INDEX_BYPASS,
        explanation_template=(
            "Column `{column}` has {null_pct}% NULL values. "
            "Most B-tree indexes exclude NULLs, reducing index effectiveness "
            "for queries like WHERE {column} = 'value'."
        ),
        remediation_template=("Consider a partial index WHERE {column} IS NOT NULL if most queries filter out NULLs."),
    ),
    "LOW_CARDINALITY": RiskFactor(
        code="LOW_CARDINALITY",
        severity=Severity.INFO,
        domain=Domain.METADATA,
        weight=1.0,
        impact_type=ImpactType.INDEX_BYPASS,
        explanation_template=(
            "Column `{column}` has only {distinct_count} distinct values. "
            "A B-tree index has low selectivity — full table scan is often faster."
        ),
        remediation_template=(
            "Low cardinality indexes rarely help. "
            "Consider composite indexes that include high-selectivity columns first."
        ),
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# RiskAssessment aggregation
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class RiskAssessment:
    """
    Aggregated risk assessment for a SQL branch or unit.

    Attributes:
        factors: All matched risk factors (with resolved context)
    """

    factors: list[RiskFactor] = field(default_factory=list)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.factors if f.severity == Severity.CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.factors if f.severity == Severity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for f in self.factors if f.severity == Severity.INFO)

    @property
    def composite_score(self) -> float:
        """
        Severity-count-derived 0.0-1.0 score.
        Replaces sigmoid normalization.

        Ranges:
        - 2+ CRITICAL: 0.95
        - 1 CRITICAL: 0.80-0.95
        - 3+ WARNING: 0.70-0.80
        - 1+ WARNING: 0.50-0.70
        - 2+ INFO: 0.30-0.50
        - else: 0.10-0.30
        """
        if self.critical_count >= 2:
            return 0.95
        if self.critical_count == 1:
            return 0.80 + min(self.warning_count * 0.05, 0.15)
        if self.warning_count >= 3:
            return 0.70 + min(self.info_count * 0.02, 0.10)
        if self.warning_count >= 1:
            return 0.50 + min(self.warning_count * 0.05, 0.20)
        if self.info_count >= 2:
            return 0.30 + min(self.info_count * 0.05, 0.20)
        return 0.10 + min(self.info_count * 0.10, 0.20)

    @property
    def risk_level(self) -> str:
        """HIGH / MEDIUM / LOW — replaces 0.7/0.4 threshold judgment."""
        if self.critical_count > 0:
            return "HIGH"
        if self.warning_count >= 2:
            return "MEDIUM"
        return "LOW"

    @property
    def worst_factor(self) -> Optional[RiskFactor]:
        """Highest-weight factor for 'primary issue' annotation in reports."""
        if not self.factors:
            return None
        return max(self.factors, key=lambda f: f.weight)

    @property
    def score_reasons(self) -> list[str]:
        """Backward compatibility: returns factor code list."""
        return [f.code for f in self.factors]


# ═══════════════════════════════════════════════════════════════════════════════
# Severity resolution with metadata-based upgrade/downgrade
# ═══════════════════════════════════════════════════════════════════════════════


def resolve_severity(base_factor: RiskFactor, context: dict) -> RiskFactor:
    """
    Resolve actual severity based on metadata context.

    May upgrade or downgrade the base_factor severity based on:
    - table_size ("large", "medium", "small")
    - row_count (actual row count)
    - has_index (whether column has an index)
    - has_fulltext_index (whether column has a fulltext index)

    Upgrade rules:
    - INFO → WARNING: large table or row_count > 100,000
    - WARNING → CRITICAL: large table + no index or row_count > 1,000,000

    Downgrade rules:
    - LIKE_PREFIX + has_fulltext_index → WARNING (has alternative)
    """

    # CRITICAL: only downgrade check (LIKE_PREFIX with fulltext index)
    if base_factor.severity == Severity.CRITICAL:
        if base_factor.code == "LIKE_PREFIX" and context.get("has_fulltext_index"):
            return _downgrade_factor(base_factor, Severity.WARNING)
        return base_factor

    # WARNING: upgrade check
    if base_factor.severity == Severity.WARNING:
        is_large_table = context.get("table_size") == "large"
        has_no_index = not context.get("has_index", True)
        row_count = context.get("row_count", 0)

        if is_large_table and has_no_index:
            return _upgrade_factor(base_factor, Severity.CRITICAL)
        if row_count > 1_000_000:
            return _upgrade_factor(base_factor, Severity.CRITICAL)
        return base_factor

    # INFO: upgrade check
    if base_factor.severity == Severity.INFO:
        is_large_table = context.get("table_size") == "large"
        row_count = context.get("row_count", 0)

        if is_large_table or row_count > 100_000:
            return _upgrade_factor(base_factor, Severity.WARNING)
        return base_factor

    return base_factor


def _upgrade_factor(factor: RiskFactor, new_severity: Severity) -> RiskFactor:
    """Return a copy of factor with upgraded severity."""
    import copy

    upgraded = copy.copy(factor)
    upgraded.severity = new_severity
    return upgraded


def _downgrade_factor(factor: RiskFactor, new_severity: Severity) -> RiskFactor:
    """Return a copy of factor with downgraded severity."""
    import copy

    downgraded = copy.copy(factor)
    downgraded.severity = new_severity
    return downgraded
