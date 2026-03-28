from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class BranchValidationResult:
    branches: list[dict[str, Any]]


class BranchValidator:
    """Validate and deduplicate rendered branches."""

    @staticmethod
    def validate_sql(sql: str) -> bool:
        sql_upper = sql.upper()

        if re.search(r"\bUPDATE\b", sql_upper):
            if not re.search(r"\bSET\b", sql_upper):
                return False
            if not re.search(r"\bWHERE\b", sql_upper):
                return False

        if re.search(r"\bDELETE\b", sql_upper):
            if not re.search(r"\b(WHERE|FROM)\b", sql_upper):
                return False

        if re.search(r"\bINSERT\b", sql_upper):
            if not re.search(r"\b(VALUES|SELECT)\b", sql_upper):
                return False

        if re.search(r"\bSELECT\b", sql_upper):
            if not re.search(r"\bFROM\b", sql_upper):
                return False

        return True

    def validate_and_deduplicate(
        self,
        branches: list[dict[str, Any]],
        max_branches: int,
    ) -> BranchValidationResult:
        kept: dict[str, dict[str, Any]] = {}

        for branch in branches:
            sql = str(branch.get("sql", "")).strip()
            if not sql:
                continue
            if self._contains_empty_in_clause(sql):
                continue

            existing = kept.get(sql)
            if existing is None or self._is_better_branch(branch, existing):
                kept[sql] = branch

        # "Guarantee baseline + risk-priority fill" strategy (Option B)
        # Always include the all-false branch (no conditions active)
        all_false = None
        risk_ranked: list[dict[str, Any]] = []

        for branch in kept.values():
            if not branch.get("active_conditions"):
                all_false = branch
            else:
                risk_ranked.append(branch)

        # Sort non-baseline branches by risk_score descending
        risk_ranked.sort(
            key=lambda b: (
                float(b.get("risk_score", 0.0)),
                len(b.get("active_conditions", [])),
                b.get("branch_id", 0),
            ),
            reverse=True,
        )

        # Build final list: baseline first, then risk-priority fill
        ordered: list[dict[str, Any]] = []
        if all_false is not None:
            ordered.append(all_false)
        remaining_slots = max_branches - len(ordered)
        ordered.extend(risk_ranked[:remaining_slots])

        for index, branch in enumerate(ordered):
            branch["branch_id"] = index

        return BranchValidationResult(branches=ordered)

    @staticmethod
    def _contains_empty_in_clause(sql: str) -> bool:
        return bool(re.search(r"\b(?:NOT\s+)?IN\s*\(\s*\)", sql, re.IGNORECASE))

    @staticmethod
    def _is_better_branch(
        candidate: dict[str, Any],
        existing: dict[str, Any],
    ) -> bool:
        candidate_score = float(candidate.get("risk_score", 0.0))
        existing_score = float(existing.get("risk_score", 0.0))
        if candidate_score != existing_score:
            return candidate_score > existing_score

        candidate_active = len(candidate.get("active_conditions", []))
        existing_active = len(existing.get("active_conditions", []))
        if candidate_active != existing_active:
            return candidate_active > existing_active

        return int(candidate.get("branch_id", 0)) < int(existing.get("branch_id", 0))
