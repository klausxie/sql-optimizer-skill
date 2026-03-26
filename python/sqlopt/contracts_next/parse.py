from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field


@dataclass
class ParameterSlot:
    param_name: str
    column_name: str
    predicate_type: str
    allows_null: bool = False
    is_collection: bool = False
    value_source: str = "column_distribution"

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "ParameterSlot":
        return cls(**json.loads(json_str))


@dataclass
class BranchCandidate:
    statement_key: str
    path_id: str
    branch_type: str
    expanded_sql: str
    active_conditions: list[str] = field(default_factory=list)
    inactive_conditions: list[str] = field(default_factory=list)
    coverage_tags: list[str] = field(default_factory=list)
    parameter_slots: list[ParameterSlot] = field(default_factory=list)
    static_risks: list[str] = field(default_factory=list)
    static_risk_score: float = 0.0
    priority_tier: str = "medium"

    def to_json(self) -> str:
        return json.dumps(
            {
                "statement_key": self.statement_key,
                "path_id": self.path_id,
                "branch_type": self.branch_type,
                "expanded_sql": self.expanded_sql,
                "active_conditions": self.active_conditions,
                "inactive_conditions": self.inactive_conditions,
                "coverage_tags": self.coverage_tags,
                "parameter_slots": [asdict(item) for item in self.parameter_slots],
                "static_risks": self.static_risks,
                "static_risk_score": self.static_risk_score,
                "priority_tier": self.priority_tier,
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "BranchCandidate":
        data = json.loads(json_str)
        return cls(
            statement_key=data["statement_key"],
            path_id=data["path_id"],
            branch_type=data["branch_type"],
            expanded_sql=data["expanded_sql"],
            active_conditions=data.get("active_conditions", []),
            inactive_conditions=data.get("inactive_conditions", []),
            coverage_tags=data.get("coverage_tags", []),
            parameter_slots=[ParameterSlot(**item) for item in data.get("parameter_slots", [])],
            static_risks=data.get("static_risks", []),
            static_risk_score=data.get("static_risk_score", 0.0),
            priority_tier=data.get("priority_tier", "medium"),
        )


@dataclass
class BranchPriorityEntry:
    statement_key: str
    path_id: str
    static_risk_score: float
    priority_tier: str
    reason_summary: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "BranchPriorityEntry":
        return cls(**json.loads(json_str))
