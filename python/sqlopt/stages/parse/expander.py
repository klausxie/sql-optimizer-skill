from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExpandedBranch:
    path_id: str
    condition: str | None
    expanded_sql: str
    is_valid: bool


def expand_branches(sql_text: str) -> list[ExpandedBranch]:
    """Expand SQL branches using BranchExpander.

    This is a backward-compatible wrapper that delegates to BranchExpander.
    """
    from sqlopt.stages.parse.branch_expander import BranchExpander

    expander = BranchExpander(strategy="ladder", max_branches=50)
    raw_branches = expander.expand(sql_text)
    return [
        ExpandedBranch(
            path_id=b.path_id,
            condition=b.condition,
            expanded_sql=b.expanded_sql,
            is_valid=b.is_valid,
        )
        for b in raw_branches
    ]
