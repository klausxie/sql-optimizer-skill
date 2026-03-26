"""Contract definitions for optimize operation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import List


@dataclass
class OptimizationProposal:
    """Represents a single SQL optimization proposal."""

    sql_unit_id: str
    path_id: str
    original_sql: str
    optimized_sql: str
    rationale: str
    confidence: float  # 0.0 to 1.0
    before_metrics: dict | None = None
    after_metrics: dict | None = None
    result_equivalent: bool | None = None
    validation_status: str | None = None
    validation_error: str | None = None
    gain_ratio: float | None = None

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> "OptimizationProposal":
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls(**data)


@dataclass
class OptimizeOutput:
    """Output contract for the optimize operation."""

    proposals: List[OptimizationProposal]

    def to_json(self) -> str:
        """Serialize to JSON string."""
        data = {
            "proposals": [asdict(p) for p in self.proposals],
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str) -> "OptimizeOutput":
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        proposals = [OptimizationProposal(**p) for p in data["proposals"]]
        return cls(proposals=proposals)
