from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import List


@dataclass
class PerformanceBaseline:
    sql_unit_id: str
    path_id: str
    original_sql: str
    plan: dict | None
    estimated_cost: float
    actual_time_ms: float | None = None
    rows_returned: int | None = None
    rows_examined: int | None = None
    result_signature: dict | None = None
    execution_error: str | None = None
    branch_type: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> PerformanceBaseline:
        data = json.loads(json_str)
        return cls(**data)


@dataclass
class RecognitionOutput:
    baselines: List[PerformanceBaseline]
    run_id: str = "unknown"

    def to_json(self) -> str:
        data = {
            "baselines": [asdict(baseline) for baseline in self.baselines],
            "run_id": self.run_id,
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str) -> RecognitionOutput:
        data = json.loads(json_str)
        baselines = [PerformanceBaseline(**b) for b in data["baselines"]]
        run_id = data.get("run_id", "unknown")
        return cls(baselines=baselines, run_id=run_id)
