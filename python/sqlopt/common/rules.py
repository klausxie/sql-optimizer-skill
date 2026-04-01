"""Risk rule registry for SQL branch risk scoring.

All risk detection rules are defined here as RiskRule objects and registered
with RiskRuleRegistry.  This is the single source of truth for:
    - Phase 1 (dimension): fast pre-render scoring
    - Phase 2 (SQL): full post-render scoring

New rules can be added by creating RiskRule objects and calling
RiskRuleRegistry.register().  No changes to scoring logic are needed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlopt.stages.branching.dimension_extractor import BranchDimension


# ---------------------------------------------------------------------------
# RiskRule definition
# ---------------------------------------------------------------------------


@dataclass
class RiskRule:
    """A single risk detection rule.

    Attributes:
        name:       Unique identifier, e.g. "sql_select_star".
        signal:     How to match: "keyword" | "regex" | "depth" | "metadata".
        pattern:    Regex string (for "regex") or keyword substring (for "keyword").
        weight:     Score contribution added when rule matches.
        phase:      1 = dimension (pre-render), 2 = SQL (post-render), 3 = both.
        reason_tag: Tag written into reasons list, e.g. "select_star".
        enabled:    Whether this rule is active (can be toggled per-instance).
    """

    name: str
    signal: str
    pattern: str
    weight: float
    phase: int
    reason_tag: str
    enabled: bool = True

    def matches(self, text: str) -> bool:
        if self.signal == "regex":
            return bool(re.search(self.pattern, text, re.IGNORECASE))
        if self.signal == "keyword":
            return self.pattern.lower() in text.lower()
        return False


# ---------------------------------------------------------------------------
# Built-in rules
# ---------------------------------------------------------------------------

_BUILTIN_RULES: dict[str, RiskRule] = {}


def _init_builtin_rules() -> dict[str, RiskRule]:
    """Register all built-in risk rules."""
    rules = {}

    # ── Phase 1: dimension (pre-render) rules ─────────────────────────────

    rules["dim_keyword_join"] = RiskRule(
        name="dim_keyword_join",
        signal="keyword",
        pattern="join",
        weight=2.0,
        phase=1,
        reason_tag="join",
    )
    rules["dim_keyword_or"] = RiskRule(
        name="dim_keyword_or",
        signal="keyword",
        pattern=" or ",
        weight=1.0,
        phase=1,
        reason_tag="or_condition",
    )
    rules["dim_keyword_order_by"] = RiskRule(
        name="dim_keyword_order_by",
        signal="keyword",
        pattern="order by",
        weight=1.0,
        phase=1,
        reason_tag="order_by",
    )
    rules["dim_keyword_group_by"] = RiskRule(
        name="dim_keyword_group_by",
        signal="keyword",
        pattern="group by",
        weight=1.0,
        phase=1,
        reason_tag="group_by",
    )
    rules["dim_keyword_wildcard"] = RiskRule(
        name="dim_keyword_wildcard",
        signal="keyword",
        pattern="%",
        weight=2.0,
        phase=1,
        reason_tag="wildcard",
    )
    rules["dim_keyword_in"] = RiskRule(
        name="dim_keyword_in",
        signal="keyword",
        pattern="in (",
        weight=2.0,
        phase=1,
        reason_tag="in_clause",
    )
    rules["dim_keyword_subquery"] = RiskRule(
        name="dim_keyword_subquery",
        signal="keyword",
        pattern="select",
        weight=2.0,
        phase=1,
        reason_tag="subquery",
    )
    rules["dim_regex_function_wrap"] = RiskRule(
        name="dim_regex_function_wrap",
        signal="regex",
        pattern=r"(year|month|day|date_format|dateadd|datediff|extract|concat|upper|lower|substring|substr|trim|ltrim|rtrim|lpad|rpad|replace|reverse|cast|convert|coalesce|ifnull|nvl|isnull|abs|round|floor|ceil|ceiling|length|char_length|character_length)\s*\(",
        weight=2.5,
        phase=1,
        reason_tag="function_wrap",
    )
    rules["dim_regex_non_sargable"] = RiskRule(
        name="dim_regex_non_sargable",
        signal="regex",
        pattern=r"^(?:%|not\s|\w+\s*\(|\d+\s*[<>])",
        weight=2.0,
        phase=1,
        reason_tag="non_sargable",
    )

    # ── Phase 2: full SQL (post-render) rules ──────────────────────────

    rules["sql_regex_select_star"] = RiskRule(
        name="sql_regex_select_star",
        signal="regex",
        pattern=r"select\s+\*",
        weight=2.0,
        phase=2,
        reason_tag="select_star",
    )
    rules["sql_regex_like_prefix"] = RiskRule(
        name="sql_regex_like_prefix",
        signal="regex",
        pattern=r"like\s+['\"]%",
        weight=3.0,
        phase=2,
        reason_tag="like_prefix",
    )
    rules["sql_regex_not_like"] = RiskRule(
        name="sql_regex_not_like",
        signal="regex",
        pattern=r"not\s+like",
        weight=2.0,
        phase=2,
        reason_tag="not_like",
    )
    rules["sql_regex_not_in"] = RiskRule(
        name="sql_regex_not_in",
        signal="regex",
        pattern=r"not\s+in\s*\(",
        weight=3.0,
        phase=2,
        reason_tag="not_in",
    )
    rules["sql_regex_not_exists"] = RiskRule(
        name="sql_regex_not_exists",
        signal="regex",
        pattern=r"not\s+exists",
        weight=2.0,
        phase=2,
        reason_tag="not_exists",
    )
    rules["sql_regex_offset"] = RiskRule(
        name="sql_regex_offset",
        signal="regex",
        pattern=r"offset\s+\d+",
        weight=2.0,
        phase=2,
        reason_tag="pagination",
    )
    rules["sql_regex_union"] = RiskRule(
        name="sql_regex_union",
        signal="regex",
        pattern=r"\bunion\b",
        weight=2.0,
        phase=2,
        reason_tag="union",
    )
    rules["sql_regex_distinct"] = RiskRule(
        name="sql_regex_distinct",
        signal="regex",
        pattern=r"\bdistinct\b",
        weight=2.0,
        phase=2,
        reason_tag="distinct",
    )
    rules["sql_regex_having"] = RiskRule(
        name="sql_regex_having",
        signal="regex",
        pattern=r"\bhaving\b",
        weight=1.5,
        phase=2,
        reason_tag="having",
    )
    rules["sql_regex_exists_subquery"] = RiskRule(
        name="sql_regex_exists_subquery",
        signal="regex",
        pattern=r"exists\s*\(\s*select",
        weight=2.0,
        phase=2,
        reason_tag="exists",
    )
    rules["sql_regex_subquery"] = RiskRule(
        name="sql_regex_subquery",
        signal="regex",
        pattern=r"\(\s*select\b",
        weight=2.0,
        phase=2,
        reason_tag="subquery",
    )
    rules["sql_regex_in_many"] = RiskRule(
        name="sql_regex_in_many",
        signal="regex",
        pattern=r"in\s*\(\s*\d+\s*(,\s*\d+){10,}",
        weight=2.0,
        phase=2,
        reason_tag="in_many",
    )
    rules["sql_regex_like_concat"] = RiskRule(
        name="sql_regex_like_concat",
        signal="regex",
        pattern=r"like\s+concat\s*\(",
        weight=2.0,
        phase=2,
        reason_tag="like_prefix",
    )
    rules["sql_keyword_order_by"] = RiskRule(
        name="sql_keyword_order_by",
        signal="keyword",
        pattern="order by",
        weight=1.0,
        phase=2,
        reason_tag="order_by",
    )
    rules["sql_keyword_group_by"] = RiskRule(
        name="sql_keyword_group_by",
        signal="keyword",
        pattern="group by",
        weight=1.0,
        phase=2,
        reason_tag="group_by",
    )
    rules["sql_keyword_join"] = RiskRule(
        name="sql_keyword_join",
        signal="keyword",
        pattern=" join ",
        weight=2.0,
        phase=2,
        reason_tag="join",
    )
    rules["sql_keyword_exists"] = RiskRule(
        name="sql_keyword_exists",
        signal="keyword",
        pattern="exists",
        weight=2.0,
        phase=2,
        reason_tag="exists",
    )

    return rules


_BUILTIN_RULES = _init_builtin_rules()


# ---------------------------------------------------------------------------
# RiskRuleRegistry — singleton
# ---------------------------------------------------------------------------


class RiskRuleRegistry:
    """Global registry for risk detection rules.

    All Phase-1 and Phase-2 rules are registered here by default.
    Components receive the global instance and call evaluate_phase1 / evaluate_phase2.

    Usage::

        registry = RiskRuleRegistry.global_instance()
        score, reasons = registry.evaluate_phase1(dimension)
        score, reasons = registry.evaluate_phase2(full_sql, conditions)
    """

    _instance: "RiskRuleRegistry | None" = None
    _rules: dict[str, RiskRule]

    def __init__(self, rules: dict[str, RiskRule] | None = None) -> None:
        # Start from built-in rules so nothing is lost
        self._rules = dict(_BUILTIN_RULES)
        if rules:
            self._rules.update(rules)

    @classmethod
    def global_instance(cls) -> "RiskRuleRegistry":
        """Return the shared global instance (created on first call)."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the global instance (for testing only)."""
        cls._instance = None

    def register(self, rule: RiskRule) -> None:
        """Register a new rule or override an existing one."""
        self._rules[rule.name] = rule

    def get_rule(self, name: str) -> RiskRule | None:
        return self._rules.get(name)

    # ── Phase 1: dimension (pre-render) scoring ─────────────────────────

    def evaluate_phase1(self, dimension: "BranchDimension") -> tuple[float, list[str]]:
        """Fast pre-render scoring for a BranchDimension.

        Uses only the dimension's sql_fragment and condition text plus depth.
        This is used by RiskGuidedLadderPlanner to order candidate combinations.
        """
        score = 0.0
        reasons: list[str] = []

        # Score the sql_fragment
        fragment = dimension.sql_fragment or ""
        for rule in self._rules.values():
            if not rule.enabled or rule.phase not in (1, 3):
                continue
            if rule.signal == "depth":
                score += rule.weight * dimension.depth
                if dimension.depth > 0:
                    reasons.append(rule.reason_tag)
            elif rule.matches(fragment):
                score += rule.weight
                reasons.append(rule.reason_tag)

        # Also check the condition text
        condition = dimension.condition or ""
        for rule in self._rules.values():
            if not rule.enabled or rule.phase not in (1, 3):
                continue
            if rule.signal == "depth":
                continue  # depth only counted once via fragment
            if rule.signal in ("keyword", "regex") and rule.matches(condition) and rule.reason_tag not in reasons:
                score += rule.weight
                reasons.append(rule.reason_tag)

        return score, reasons

    # ── Phase 2: full SQL (post-render) scoring ────────────────────────

    def evaluate_phase2(
        self,
        sql: str,
        conditions: list[str],
        table_metadata: dict | None = None,
        field_distributions: dict | None = None,
    ) -> tuple[float, list[str]]:
        """Full post-render scoring for a complete SQL string.

        This is the authoritative risk score used for final branch selection.
        """
        score = 0.0
        reasons: list[str] = []
        sql_lower = sql.lower().strip()

        for rule in self._rules.values():
            if not rule.enabled or rule.phase not in (2, 3):
                continue
            if rule.signal == "depth":
                continue
            if rule.matches(sql):
                score += rule.weight
                reasons.append(rule.reason_tag)

        # Active conditions get tagged
        reasons.extend(f"active:{cond}" for cond in conditions)

        # Table metadata adjustments
        if table_metadata:
            meta_score, meta_reasons = self._evaluate_metadata(sql_lower, table_metadata)
            score += meta_score
            reasons.extend(meta_reasons)

        # Field distribution adjustments
        if field_distributions:
            fd_score, fd_reasons = self._evaluate_field_distributions(sql_lower, field_distributions)
            score += fd_score
            reasons.extend(fd_reasons)

        # Normalize score to [0, 1] using sigmoid-style mapping
        normalized_score = 1.0 - 1.0 / (1.0 + score)
        return normalized_score, self._dedupe_reasons(reasons)

    def _evaluate_metadata(self, sql_lower: str, table_metadata: dict) -> tuple[float, list[str]]:
        score = 0.0
        reasons: list[str] = []
        for table_name, meta in table_metadata.items():
            if table_name not in sql_lower:
                continue
            size = meta.get("size", "small")
            if size == "large":
                score += 2.0
                reasons.append(f"table:{table_name}:large")
            elif size == "medium":
                score += 1.0
                reasons.append(f"table:{table_name}:medium")
            # Column index coverage
            indexes = meta.get("indexes", [])
            for col in self._extract_columns(sql_lower):
                if col not in indexes:
                    score += 2.0
                    reasons.append(f"no_index:{col}")
        return score, reasons

    @staticmethod
    def _evaluate_field_distributions(sql_lower: str, field_distributions: dict) -> tuple[float, list[str]]:
        score = 0.0
        reasons: list[str] = []
        for table_name, distributions in field_distributions.items():
            if table_name not in sql_lower:
                continue
            for dist in distributions:
                col_name = dist.column_name.lower()
                if col_name not in sql_lower:
                    continue
                total = max(getattr(dist, "total_count", 0) or dist.distinct_count + dist.null_count, 1)
                null_ratio = dist.null_count / total
                if null_ratio > 0.1:
                    score += 2.0
                    reasons.append(f"field_null_high:{col_name}")
                if dist.distinct_count < 10:
                    score += 1.0
                    reasons.append(f"field_low_card:{col_name}")
                if dist.top_values and len(dist.top_values) > 0:
                    top_count = dist.top_values[0].get("count", 0)
                    non_null = max(total - dist.null_count, 1)
                    if top_count / non_null > 0.8:
                        score += 2.0
                        reasons.append(f"field_skewed:{col_name}")
        return score, reasons

    @staticmethod
    def _extract_columns(sql_lower: str) -> set[str]:
        cleaned = re.sub(r"#\{[^}]+\}", "", sql_lower)
        cleaned = re.sub(r"\$\{[^}]+\}", "", cleaned)
        parts = re.split(r"[=<>!\s.()]+", cleaned)
        return {
            p.strip("()\"',")
            for p in parts
            if p.strip()
            and p not in ("and", "or", "not", "in", "is", "null", "true", "false", "from", "where", "select")
        }

    @staticmethod
    def _dedupe_reasons(reasons: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for r in reasons:
            if r and r not in seen:
                seen.add(r)
                out.append(r)
        return out
