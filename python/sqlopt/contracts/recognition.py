from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import List


@dataclass
class PerformanceBaseline:
    sql_unit_id: str
    path_id: str
    plan: dict
    estimated_cost: float
    actual_time_ms: float | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> PerformanceBaseline:
        data = json.loads(json_str)
        return cls(**data)


@dataclass
class RecognitionOutput:
    baselines: List[PerformanceBaseline]

    def to_json(self) -> str:
        data = {
            "baselines": [asdict(baseline) for baseline in self.baselines],
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str) -> RecognitionOutput:
        data = json.loads(json_str)
        baselines = [PerformanceBaseline(**b) for b in data["baselines"]]
        return cls(baselines=baselines)
