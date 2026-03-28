"""
Patch Decision Context

决策上下文定义，用于向后兼容。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PatchDecisionContext:
    """
    Patch 决策上下文（向后兼容）

    保持与原 patch_decision_engine.py 中 PatchDecisionContext 相同的接口。
    """
    status: str
    semantic_gate_status: str
    semantic_gate_confidence: str
    sql_key: str
    statement_key: str
    same_statement: list[dict[str, Any]]
    pass_rows: list[dict[str, Any]]
    candidates_evaluated: int

    @property
    def is_pass(self) -> bool:
        return self.status == "PASS"

    @property
    def has_single_pass_candidate(self) -> bool:
        return len(self.pass_rows) == 1 and str(self.pass_rows[0].get("sqlKey")) == self.sql_key