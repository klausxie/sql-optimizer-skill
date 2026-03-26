from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from sqlopt.contracts_next.common import ResultSignature


@dataclass
class OptimizationProposal:
    proposal_id: str
    finding_id: str
    statement_key: str
    path_id: str
    proposal_type: str
    source: str
    original_sql: str
    optimized_sql: str
    index_ddl: list[str] = field(default_factory=list)
    rationale: str = ""
    risk_notes: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "OptimizationProposal":
        return cls(**json.loads(json_str))


@dataclass
class OptimizationValidation:
    proposal_id: str
    finding_id: str
    statement_key: str
    path_id: str
    case_id: str
    result_equivalent: bool
    before_execution_ref: str | None = None
    after_explain_cost: float | None = None
    after_avg_time_ms: float | None = None
    after_rows_examined: int | None = None
    after_result_signature: ResultSignature | None = None
    gain_ratio: float | None = None
    record_type: str = "optimization_validation"

    def to_json(self) -> str:
        return json.dumps(
            {
                "proposal_id": self.proposal_id,
                "finding_id": self.finding_id,
                "statement_key": self.statement_key,
                "path_id": self.path_id,
                "case_id": self.case_id,
                "result_equivalent": self.result_equivalent,
                "before_execution_ref": self.before_execution_ref,
                "after_explain_cost": self.after_explain_cost,
                "after_avg_time_ms": self.after_avg_time_ms,
                "after_rows_examined": self.after_rows_examined,
                "after_result_signature": asdict(self.after_result_signature)
                if self.after_result_signature
                else None,
                "gain_ratio": self.gain_ratio,
                "record_type": self.record_type,
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "OptimizationValidation":
        data = json.loads(json_str)
        signature = data.get("after_result_signature")
        return cls(
            proposal_id=data["proposal_id"],
            finding_id=data["finding_id"],
            statement_key=data["statement_key"],
            path_id=data["path_id"],
            case_id=data["case_id"],
            result_equivalent=data["result_equivalent"],
            before_execution_ref=data.get("before_execution_ref"),
            after_explain_cost=data.get("after_explain_cost"),
            after_avg_time_ms=data.get("after_avg_time_ms"),
            after_rows_examined=data.get("after_rows_examined"),
            after_result_signature=ResultSignature(**signature) if signature else None,
            gain_ratio=data.get("gain_ratio"),
            record_type=data.get("record_type", "optimization_validation"),
        )


@dataclass
class AcceptedAction:
    proposal_id: str
    finding_id: str
    recommended: bool
    recommendation_level: str
    summary: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "AcceptedAction":
        return cls(**json.loads(json_str))
