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

    def to_json(self) -> str:
        return json.dumps(
            {
                "path_id": self.path_id,
                "condition": self.condition,
                "expanded_sql": self.expanded_sql,
                "is_valid": self.is_valid,
            }
        )

    @classmethod
    def from_json(cls, json_str: str) -> SQLBranch:
        data = json.loads(json_str)
        return cls(
            path_id=data["path_id"],
            condition=data.get("condition"),
            expanded_sql=data["expanded_sql"],
            is_valid=data["is_valid"],
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

    def to_json(self) -> str:
        return json.dumps(
            {
                "sql_units_with_branches": [
                    json.loads(u.to_json()) for u in self.sql_units_with_branches
                ]
            }
        )

    @classmethod
    def from_json(cls, json_str: str) -> "ParseOutput":
        data = json.loads(json_str)
        return cls(
            sql_units_with_branches=[
                SQLUnitWithBranches.from_json(json.dumps(u))
                for u in data["sql_units_with_branches"]
            ]
        )


@dataclass
class Risk:
    """Represents a risk identified in a SQL unit."""

    sql_unit_id: str
    risk_type: str
    severity: str  # LOW, MEDIUM, HIGH
    message: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "sql_unit_id": self.sql_unit_id,
                "risk_type": self.risk_type,
                "severity": self.severity,
                "message": self.message,
            }
        )

    @classmethod
    def from_json(cls, json_str: str) -> "Risk":
        data = json.loads(json_str)
        return cls(
            sql_unit_id=data["sql_unit_id"],
            risk_type=data["risk_type"],
            severity=data["severity"],
            message=data["message"],
        )


@dataclass
class RiskOutput:
    """Output containing identified risks."""

    risks: List[Risk] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps({"risks": [json.loads(r.to_json()) for r in self.risks]})

    @classmethod
    def from_json(cls, json_str: str) -> "RiskOutput":
        data = json.loads(json_str)
        return cls(risks=[Risk.from_json(json.dumps(r)) for r in data["risks"]])
