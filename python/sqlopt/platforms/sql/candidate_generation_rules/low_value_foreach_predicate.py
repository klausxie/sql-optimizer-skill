from __future__ import annotations

import re

from .base import CandidateGenerationContext
from ..candidate_generation_models import LowValueAssessment
from ..candidate_generation_support import LIMIT_RE, normalize_sql

_PLACEHOLDER_ONLY_PREDICATE_RE = re.compile(
    r"\bwhere\s+(?:#\{[^}]+\}|\?)(?:\s|$)",
    flags=re.IGNORECASE,
)
_FETCH_FIRST_RE = re.compile(
    r"\bfetch\s+first\b",
    flags=re.IGNORECASE,
)
_IN_PREDICATE_RE = re.compile(
    r"\bwhere\s+(?P<lhs>[a-z_][a-z0-9_\.]*)\s+in\s*\(",
    flags=re.IGNORECASE,
)
_SINGLE_VALUE_PREDICATE_RE = re.compile(
    r"\bwhere\s+(?P<lhs>[a-z_][a-z0-9_\.]*)\s*=\s*(?:#\{[^}]+\}|\?)(?:\s|$)",
    flags=re.IGNORECASE,
)
_SINGLE_VALUE_PLACEHOLDER_RE = re.compile(
    r"\bwhere\s+(?P<lhs>[a-z_][a-z0-9_\.]*)\s*=\s*#\{[^}]+\}(?:\s|$)",
    flags=re.IGNORECASE,
)
_EXPLICIT_IN_PREDICATE_RE = re.compile(
    r"\bwhere\s+(?P<lhs>[a-z_][a-z0-9_\.]*)\s+in\s*\(\s*#\{[^}]+\}\s*\)",
    flags=re.IGNORECASE,
)
_ORDER_BY_RE = re.compile(r"\border\s+by\b", flags=re.IGNORECASE)


class ForeachPredicateSpeculativeRewriteRule:
    rule_id = "FOREACH_PREDICATE_SPECULATIVE_REWRITE"

    def assess(self, context: CandidateGenerationContext, candidate: dict[str, object]) -> LowValueAssessment | None:
        features = {
            str(row).strip().upper()
            for row in (context.sql_unit.get("dynamicFeatures") or [])
            if str(row).strip()
        }
        if "FOREACH" not in features:
            return None

        original_sql = normalize_sql(context.original_sql)
        rewritten_sql = normalize_sql(str(candidate.get("rewrittenSql") or ""))
        if not original_sql or not rewritten_sql:
            return None

        adds_pagination = bool(
            (LIMIT_RE.search(rewritten_sql) and not LIMIT_RE.search(original_sql))
            or (_FETCH_FIRST_RE.search(rewritten_sql) and not _FETCH_FIRST_RE.search(original_sql))
        )
        if adds_pagination:
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="SPECULATIVE_ADDITIVE_REWRITE",
                reason="candidate adds pagination to a foreach predicate template without a safe template-preserving rewrite",
            )

        if _PLACEHOLDER_ONLY_PREDICATE_RE.search(rewritten_sql):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="SPECULATIVE_ADDITIVE_REWRITE",
                reason="candidate collapses a foreach predicate into a placeholder-only predicate that cannot map back to the template safely",
            )

        original_in_match = _IN_PREDICATE_RE.search(original_sql)
        rewritten_single_match = _SINGLE_VALUE_PREDICATE_RE.search(rewritten_sql)
        if (
            original_in_match is not None
            and rewritten_single_match is not None
            and str(original_in_match.group("lhs") or "").lower()
            == str(rewritten_single_match.group("lhs") or "").lower()
        ):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="SPECULATIVE_ADDITIVE_REWRITE",
                reason="candidate collapses a foreach IN predicate into a single-value equality predicate that cannot preserve the template semantics safely",
            )

        if (
            (_PLACEHOLDER_ONLY_PREDICATE_RE.search(original_sql) is not None or original_in_match is not None)
            and _SINGLE_VALUE_PLACEHOLDER_RE.search(rewritten_sql) is not None
        ):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="SPECULATIVE_ADDITIVE_REWRITE",
                reason="candidate collapses a foreach collection predicate into a single placeholder equality predicate that cannot preserve the template semantics safely",
            )

        if (
            _PLACEHOLDER_ONLY_PREDICATE_RE.search(original_sql) is not None
            and _EXPLICIT_IN_PREDICATE_RE.search(rewritten_sql) is not None
        ):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="SPECULATIVE_ADDITIVE_REWRITE",
                reason="candidate materializes a foreach placeholder predicate into an explicit IN predicate that still cannot preserve the template semantics safely",
            )

        if _ORDER_BY_RE.search(rewritten_sql) and not _ORDER_BY_RE.search(original_sql):
            return LowValueAssessment(
                candidate_id=str(candidate.get("id") or ""),
                rule_id=self.rule_id,
                category="SPECULATIVE_ADDITIVE_REWRITE",
                reason="candidate adds ordering to a foreach predicate template without a safe template-preserving rewrite",
            )
        return None
