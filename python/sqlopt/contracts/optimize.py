"""Contract definitions for optimize operation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Literal, Optional


@dataclass
class OptimizationAction:
    """A single XML modification action for a MyBatis SQL statement.

    Attributes:
        action_id: Unique identifier for this action (e.g., "act_001").
        operation: Type of operation: REPLACE, ADD, REMOVE, WRAP.
        xpath: XPath expression targeting the XML element to modify.
        target_tag: The XML tag name being targeted (e.g., "if", "where", "select").
        original_snippet: The original XML fragment before modification.
            Required for REPLACE/REMOVE/WRAP; None for ADD.
        rewritten_snippet: The new XML fragment after modification.
            Required for REPLACE/ADD/WRAP; None for REMOVE.
        sql_fragment: The specific SQL text affected (e.g., "LIKE '%' || #{name}").
            Used for human-readable diff and verification.
        rationale: Human-readable explanation of why this change helps.
        confidence: Confidence score 0.0-1.0 that this action is correct.
        path_id: Which branch this action applies to (None = all branches).
        issue_type: Type of issue detected (e.g., "PREFIX_WILDCARD", "MISSING_LIMIT").
    """

    action_id: str
    operation: Literal["REPLACE", "ADD", "REMOVE", "WRAP"]
    xpath: str
    target_tag: str
    original_snippet: Optional[str] = None
    rewritten_snippet: Optional[str] = None
    sql_fragment: Optional[str] = None
    rationale: str = ""
    confidence: float = 0.75
    path_id: Optional[str] = None
    issue_type: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "OptimizationAction":
        return cls(**data)


@dataclass
class ActionConflict:
    """Represents a conflict between two actions targeting the same or overlapping xpath.

    Attributes:
        xpath: The xpath where conflict occurs.
        action_a: First conflicting action.
        action_b: Second conflicting action.
        conflict_type: Type of conflict: "overlap", "contradict", "redundant".
        resolution: How it was resolved: "a_wins", "b_wins", "merged", "dropped".
        merged_action: If merged, the resulting action.
    """

    xpath: str
    action_a: OptimizationAction
    action_b: OptimizationAction
    conflict_type: Literal["overlap", "contradict", "redundant"] = "overlap"
    resolution: Literal["a_wins", "b_wins", "merged", "dropped"] = "dropped"
    merged_action: Optional[OptimizationAction] = None

    def to_dict(self) -> dict:
        return {
            "xpath": self.xpath,
            "action_a": self.action_a.to_dict(),
            "action_b": self.action_b.to_dict(),
            "conflict_type": self.conflict_type,
            "resolution": self.resolution,
            "merged_action": self.merged_action.to_dict() if self.merged_action else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ActionConflict":
        return cls(
            xpath=data["xpath"],
            action_a=OptimizationAction.from_dict(data["action_a"]),
            action_b=OptimizationAction.from_dict(data["action_b"]),
            conflict_type=data.get("conflict_type", "overlap"),
            resolution=data.get("resolution", "dropped"),
            merged_action=(OptimizationAction.from_dict(data["merged_action"]) if data.get("merged_action") else None),
        )


@dataclass
class UnitActionSummary:
    """Aggregated optimization actions for a single SQL unit across all its branches.

    Attributes:
        sql_unit_id: The SQL unit this summary covers.
        unit_xpath: XPath to the statement element in the XML mapper file.
        actions: All optimization actions for this unit.
        conflicts: Detected conflicts between actions.
        branch_coverage: Map of branch path_ids to whether they are covered by actions.
        overall_confidence: Weighted average confidence across all actions.
    """

    sql_unit_id: str
    unit_xpath: str = ""
    actions: list[OptimizationAction] = field(default_factory=list)
    conflicts: list[ActionConflict] = field(default_factory=list)
    branch_coverage: dict[str, bool] = field(default_factory=dict)
    overall_confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "sql_unit_id": self.sql_unit_id,
            "unit_xpath": self.unit_xpath,
            "actions": [a.to_dict() for a in self.actions],
            "conflicts": [c.to_dict() for c in self.conflicts],
            "branch_coverage": self.branch_coverage,
            "overall_confidence": self.overall_confidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UnitActionSummary":
        return cls(
            sql_unit_id=data["sql_unit_id"],
            unit_xpath=data.get("unit_xpath", ""),
            actions=[OptimizationAction.from_dict(a) for a in data.get("actions", [])],
            conflicts=[ActionConflict.from_dict(c) for c in data.get("conflicts", [])],
            branch_coverage=data.get("branch_coverage", {}),
            overall_confidence=data.get("overall_confidence", 0.0),
        )


@dataclass
class OptimizationProposal:
    """Represents a single SQL optimization proposal."""

    sql_unit_id: str
    path_id: str
    original_sql: str
    optimized_sql: str
    rationale: str
    confidence: float
    before_metrics: dict | None = None
    after_metrics: dict | None = None
    result_equivalent: bool | None = None
    validation_status: str | None = None
    validation_error: str | None = None
    gain_ratio: float | None = None
    actions: list[OptimizationAction] | None = None
    unit_summary: UnitActionSummary | None = None

    def to_json(self) -> str:
        data = asdict(self)
        data["actions"] = [a.to_dict() for a in self.actions] if self.actions else None
        data["unit_summary"] = self.unit_summary.to_dict() if self.unit_summary else None
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str) -> "OptimizationProposal":
        data = json.loads(json_str)
        if data.get("actions"):
            data["actions"] = [OptimizationAction.from_dict(a) for a in data["actions"]]
        if data.get("unit_summary"):
            data["unit_summary"] = UnitActionSummary.from_dict(data["unit_summary"])
        return cls(**data)


@dataclass
class OptimizeOutput:
    """Output contract for the optimize operation."""

    proposals: list[OptimizationProposal]
    run_id: str = "unknown"

    def to_json(self) -> str:
        data = {
            "proposals": [json.loads(p.to_json()) for p in self.proposals],
            "run_id": self.run_id,
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str) -> "OptimizeOutput":
        data = json.loads(json_str)
        proposals = [OptimizationProposal.from_json(json.dumps(p)) for p in data["proposals"]]
        return cls(proposals=proposals, run_id=data.get("run_id", "unknown"))
