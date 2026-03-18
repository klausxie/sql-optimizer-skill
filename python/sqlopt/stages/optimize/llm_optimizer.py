"""
V8 LLM Optimizer for SQL Optimization

Provides LLM-based SQL optimization capabilities.
Uses the llm/ module for LLM provider integration.
Maintains rule engine as a fast path for simple optimizations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from .rule_engine import RuleEngine, RuleResult


@dataclass
class OptimizationCandidate:
    """Single optimization candidate from LLM."""

    id: str
    source: str  # "llm" or "rule"
    rewritten_sql: str
    rewrite_strategy: str
    semantic_risk: str  # "low", "medium", "high"
    confidence: str  # "low", "medium", "high"
    improvement: str | None = None


@dataclass
class OptimizationResult:
    """Result from optimization process."""

    sql_key: str
    original_sql: str
    candidates: list[OptimizationCandidate]
    trace: dict[str, Any]
    used_fast_path: bool = False


class LLMOptimizer:
    """
    V8 LLM Optimizer for SQL Optimization.

    Combines rule-based fast path with LLM-based deep optimization.

    Usage:
        optimizer = LLMOptimizer(config, llm_provider=generate_llm_candidates)
        result = optimizer.generate_optimizations(sql_unit)
    """

    def __init__(
        self,
        config: dict[str, Any],
        llm_provider: Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]]
        | None = None,
    ):
        """
        Initialize the LLM Optimizer.

        Args:
            config: Configuration dictionary containing llm settings
            llm_provider: Optional LLM provider function. If not provided,
                          will use the default from llm.provider module.
        """
        self.config = config
        self.llm_cfg = dict(config.get("llm", {}) or {})
        self.rule_engine = RuleEngine()

        # Lazy import to avoid circular dependency
        self._llm_provider = llm_provider

    def _get_llm_provider(self):
        """Get the LLM provider function."""
        if self._llm_provider is not None:
            return self._llm_provider
        from ...llm.provider import generate_llm_candidates

        return generate_llm_candidates

    def _rule_results_to_candidates(
        self,
        rule_results: list[RuleResult],
        sql_key: str,
    ) -> list[OptimizationCandidate]:
        """Convert rule results to optimization candidates."""
        candidates = []
        for idx, rr in enumerate(rule_results):
            candidate = OptimizationCandidate(
                id=f"{sql_key}:rule:{idx + 1}",
                source="rule",
                rewritten_sql=rr.optimized_sql,
                rewrite_strategy=rr.rule_name,
                semantic_risk="low",  # Rules are conservative
                confidence="high",  # Rules are deterministic
                improvement=rr.improvement,
            )
            candidates.append(candidate)
        return candidates

    def _llm_results_to_candidates(
        self,
        llm_candidates: list[dict[str, Any]],
    ) -> list[OptimizationCandidate]:
        """Convert LLM results to optimization candidates."""
        candidates = []
        for lc in llm_candidates:
            candidate = OptimizationCandidate(
                id=str(lc.get("id", "unknown")),
                source="llm",
                rewritten_sql=str(lc.get("rewrittenSql", "")),
                rewrite_strategy=str(lc.get("rewriteStrategy", "unknown")),
                semantic_risk=str(lc.get("semanticRisk", "medium")),
                confidence=str(lc.get("confidence", "medium")),
            )
            candidates.append(candidate)
        return candidates

    def _try_fast_path(
        self,
        sql: str,
        sql_key: str,
    ) -> tuple[list[OptimizationCandidate], bool]:
        """
        Try rule-based fast path optimization.

        Returns:
            Tuple of (candidates, should_use_llm)
        """
        rule_results = self.rule_engine.apply_all(sql)

        if not rule_results:
            # No rules applied, need LLM
            return [], True

        # Check if any rule made actual changes
        has_actual_optimization = any(
            rr.original_sql != rr.optimized_sql for rr in rule_results
        )

        if has_actual_optimization:
            # Rules found actionable optimizations
            candidates = self._rule_results_to_candidates(rule_results, sql_key)
            return candidates, False

        # Rules only generated suggestions, still try LLM for deeper analysis
        return [], True

    def generate_optimizations(
        self,
        sql_unit: dict[str, Any],
        proposal: dict[str, Any] | None = None,
    ) -> OptimizationResult:
        """
        Generate optimization candidates for a SQL unit.

        This method first tries the rule-based fast path, and only
        falls back to LLM if rules don't find actionable optimizations.

        Args:
            sql_unit: SQL unit containing sqlKey and sql
            proposal: Optional proposal with context (issues, tables, indexes)

        Returns:
            OptimizationResult with candidates and trace
        """
        sql_key = sql_unit.get("sqlKey", "unknown")
        sql = str(sql_unit.get("sql", ""))

        trace: dict[str, Any] = {
            "stage": "optimize",
            "mode": "optimization",
            "sql_key": sql_key,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fast_path_tried": True,
            "llm_path_tried": False,
        }

        # Skip if SQL contains unsafe substitutions
        if "${" in sql:
            trace["degrade_reason"] = "RISKY_DOLLAR_SUBSTITUTION"
            trace["fast_path_result"] = "skipped"
            return OptimizationResult(
                sql_key=sql_key,
                original_sql=sql,
                candidates=[],
                trace=trace,
                used_fast_path=False,
            )

        # Try fast path first
        fast_candidates, use_llm = self._try_fast_path(sql, sql_key)
        trace["fast_path_result"] = (
            "candidates_found" if fast_candidates else "no_candidates"
        )

        if not use_llm or not self.llm_cfg.get("enabled", False):
            # Fast path succeeded or LLM disabled
            trace["fast_path_candidates"] = len(fast_candidates)
            return OptimizationResult(
                sql_key=sql_key,
                original_sql=sql,
                candidates=fast_candidates,
                trace=trace,
                used_fast_path=bool(fast_candidates),
            )

        # Use LLM for deeper optimization
        trace["llm_path_tried"] = True
        llm_provider = self._get_llm_provider()

        # Build prompt if proposal is available
        prompt = None
        if proposal:
            prompt = self._build_prompt(sql_unit, proposal)

        try:
            raw_candidates, llm_trace = llm_provider(
                sql_key,
                sql,
                self.llm_cfg,
                prompt=prompt,
            )

            trace["llm_trace"] = llm_trace
            llm_candidates = self._llm_results_to_candidates(raw_candidates)

            # Combine with fast path candidates (suggestions only)
            all_candidates = fast_candidates + llm_candidates
            trace["total_candidates"] = len(all_candidates)

            return OptimizationResult(
                sql_key=sql_key,
                original_sql=sql,
                candidates=all_candidates,
                trace=trace,
                used_fast_path=False,
            )

        except Exception as exc:
            trace["error"] = str(exc)
            trace["error_type"] = type(exc).__name__

            # Fallback to fast path candidates on LLM error
            return OptimizationResult(
                sql_key=sql_key,
                original_sql=sql,
                candidates=fast_candidates,
                trace=trace,
                used_fast_path=bool(fast_candidates),
            )

    def _build_prompt(
        self,
        sql_unit: dict[str, Any],
        proposal: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Build optimization prompt for LLM.

        Args:
            sql_unit: SQL unit with sqlKey and sql
            proposal: Proposal with issues and suggestions

        Returns:
            Prompt dictionary for LLM
        """
        db_summary = proposal.get("dbEvidenceSummary", {}) or {}

        return {
            "task": "sql_optimize_candidate_generation",
            "sqlKey": sql_unit["sqlKey"],
            "requiredContext": {
                "sql": sql_unit["sql"],
                "templateSql": sql_unit.get("templateSql", ""),
                "dynamicFeatures": sql_unit.get("dynamicFeatures", []),
                "riskFlags": sql_unit.get("riskFlags", []),
                "issues": proposal.get("issues", []),
                "tables": db_summary.get("tables", []),
                "indexes": (db_summary.get("indexes", []) or [])[:20],
            },
            "optionalContext": {
                "includeTrace": sql_unit.get("includeTrace", []),
                "dynamicTrace": sql_unit.get("dynamicTrace") or {},
                "columns": (db_summary.get("columns", []) or [])[:100],
                "tableStats": db_summary.get("tableStats", []),
                "planSummary": proposal.get("planSummary", {}) or {},
            },
            "rewriteConstraints": {
                "forbidMultiStatement": True,
                "preserveParameterSemantics": True,
                "dynamicTemplateRequiresTemplateAwarePatch": bool(
                    sql_unit.get("dynamicFeatures")
                ),
            },
        }


def create_optimizer(
    config: dict[str, Any],
    llm_provider: Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]]
    | None = None,
) -> LLMOptimizer:
    """
    Factory function to create an LLMOptimizer.

    Args:
        config: Configuration dictionary
        llm_provider: Optional custom LLM provider

    Returns:
        Configured LLMOptimizer instance
    """
    return LLMOptimizer(config, llm_provider=llm_provider)


if __name__ == "__main__":
    # Example usage
    config = {
        "llm": {
            "enabled": True,
            "provider": "opencode_builtin",
        }
    }

    optimizer = LLMOptimizer(config)

    sql_unit = {
        "sqlKey": "test.select_users",
        "sql": "SELECT * FROM users WHERE id = 1",
    }

    result = optimizer.generate_optimizations(sql_unit)

    print(f"SQL Key: {result.sql_key}")
    print(f"Used Fast Path: {result.used_fast_path}")
    print(f"Candidates: {len(result.candidates)}")

    for candidate in result.candidates:
        print(f"  - {candidate.id}: {candidate.rewrite_strategy}")
        print(
            f"    Risk: {candidate.semantic_risk}, Confidence: {candidate.confidence}"
        )
