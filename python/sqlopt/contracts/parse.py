from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List


@dataclass
class SQLBranch:
    path_id: str
    condition: str | None
    expanded_sql: str
    is_valid: bool
    risk_flags: list[str] = field(default_factory=list)
    active_conditions: list[str] = field(default_factory=list)
    risk_score: float | None = None
    score_reasons: list[str] = field(default_factory=list)
    branch_type: str | None = None

    def to_json(self) -> str:
        return json.dumps(
            {
                "path_id": self.path_id,
                "condition": self.condition,
                "expanded_sql": self.expanded_sql,
                "is_valid": self.is_valid,
                "risk_flags": self.risk_flags,
                "active_conditions": self.active_conditions,
                "risk_score": self.risk_score,
                "score_reasons": self.score_reasons,
                "branch_type": self.branch_type,
            }
        )

    @classmethod
    def from_json(cls, json_str: str) -> SQLBranch:
        data = json.loads(json_str)
        branch_type = data.get("branch_type")
        return cls(
            path_id=data["path_id"],
            condition=data.get("condition"),
            expanded_sql=data["expanded_sql"],
            is_valid=data["is_valid"],
            risk_flags=data.get("risk_flags", []),
            active_conditions=data.get("active_conditions", []),
            risk_score=data.get("risk_score"),
            score_reasons=data.get("score_reasons", []),
            branch_type=branch_type,
        )


@dataclass
class SQLUnitWithBranches:
    """Represents a SQL unit with multiple branches."""

    sql_unit_id: str
    branches: List[SQLBranch] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(
            {
                "sql_unit_id": self.sql_unit_id,
                "branches": [json.loads(b.to_json()) for b in self.branches],
            }
        )

    @classmethod
    def from_json(cls, json_str: str) -> "SQLUnitWithBranches":
        data = json.loads(json_str)
        return cls(
            sql_unit_id=data["sql_unit_id"],
            branches=[SQLBranch.from_json(json.dumps(b)) for b in data["branches"]],
        )


@dataclass
class ParseOutput:
    """Output of the parse stage containing SQL units with branches."""

    sql_units_with_branches: List[SQLUnitWithBranches] = field(default_factory=list)
    run_id: str = "unknown"

    def to_json(self) -> str:
        return json.dumps(
            {
                "sql_units_with_branches": [json.loads(u.to_json()) for u in self.sql_units_with_branches],
                "run_id": self.run_id,
            }
        )

    @classmethod
    def from_json(cls, json_str: str) -> "ParseOutput":
        data = json.loads(json_str)
        return cls(
            sql_units_with_branches=[
                SQLUnitWithBranches.from_json(json.dumps(u)) for u in data["sql_units_with_branches"]
            ],
            run_id=data.get("run_id", "unknown"),
        )
