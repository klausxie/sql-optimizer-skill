from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from sqlopt.contracts_next.common import PlanFlags, ResultSignature, RootCauseHit


@dataclass
class ParameterCase:
    statement_key: str
    path_id: str
    case_id: str
    generation_strategy: str
    parameter_values: dict[str, Any] = field(default_factory=dict)
    expected_selectivity: float | None = None
    source_columns: list[str] = field(default_factory=list)
    record_type: str = "parameter_case"

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "ParameterCase":
        return cls(**json.loads(json_str))


@dataclass
class ExplainBaseline:
    statement_key: str
    path_id: str
    case_id: str
    plan_engine: str
    estimated_cost: float
    estimated_rows: int | None = None
    plan_flags: PlanFlags = field(default_factory=PlanFlags)
    plan_json: dict[str, Any] = field(default_factory=dict)
    record_type: str = "explain_baseline"

    def to_json(self) -> str:
        return json.dumps(
            {
                "statement_key": self.statement_key,
                "path_id": self.path_id,
                "case_id": self.case_id,
                "plan_engine": self.plan_engine,
                "estimated_cost": self.estimated_cost,
                "estimated_rows": self.estimated_rows,
                "plan_flags": asdict(self.plan_flags),
                "plan_json": self.plan_json,
                "record_type": self.record_type,
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "ExplainBaseline":
        data = json.loads(json_str)
        return cls(
            statement_key=data["statement_key"],
            path_id=data["path_id"],
            case_id=data["case_id"],
            plan_engine=data["plan_engine"],
            estimated_cost=data["estimated_cost"],
            estimated_rows=data.get("estimated_rows"),
            plan_flags=PlanFlags(**data.get("plan_flags", {})),
            plan_json=data.get("plan_json", {}),
            record_type=data.get("record_type", "explain_baseline"),
        )


@dataclass
class ExecutionBaseline:
    statement_key: str
    path_id: str
    case_id: str
    run_count: int
    avg_time_ms: float
    p95_time_ms: float | None = None
    rows_returned: int | None = None
    rows_examined: int | None = None
    result_signature: ResultSignature | None = None
    record_type: str = "execution_baseline"

    def to_json(self) -> str:
        return json.dumps(
            {
                "statement_key": self.statement_key,
                "path_id": self.path_id,
                "case_id": self.case_id,
                "run_count": self.run_count,
                "avg_time_ms": self.avg_time_ms,
                "p95_time_ms": self.p95_time_ms,
                "rows_returned": self.rows_returned,
                "rows_examined": self.rows_examined,
                "result_signature": asdict(self.result_signature) if self.result_signature else None,
                "record_type": self.record_type,
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "ExecutionBaseline":
        data = json.loads(json_str)
        signature = data.get("result_signature")
        return cls(
            statement_key=data["statement_key"],
            path_id=data["path_id"],
            case_id=data["case_id"],
            run_count=data["run_count"],
            avg_time_ms=data["avg_time_ms"],
            p95_time_ms=data.get("p95_time_ms"),
            rows_returned=data.get("rows_returned"),
            rows_examined=data.get("rows_examined"),
            result_signature=ResultSignature(**signature) if signature else None,
            record_type=data.get("record_type", "execution_baseline"),
        )


@dataclass
class SlowSQLFinding:
    finding_id: str
    statement_key: str
    path_id: str
    case_id: str
    is_slow: bool
    severity: str
    impact_score: float
    confidence: float
    root_causes: list[RootCauseHit] = field(default_factory=list)
    explain_ref: str | None = None
    execution_ref: str | None = None
    optimization_ready: bool = False

    def to_json(self) -> str:
        return json.dumps(
            {
                "finding_id": self.finding_id,
                "statement_key": self.statement_key,
                "path_id": self.path_id,
                "case_id": self.case_id,
                "is_slow": self.is_slow,
                "severity": self.severity,
                "impact_score": self.impact_score,
                "confidence": self.confidence,
                "root_causes": [asdict(item) for item in self.root_causes],
                "explain_ref": self.explain_ref,
                "execution_ref": self.execution_ref,
                "optimization_ready": self.optimization_ready,
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "SlowSQLFinding":
        data = json.loads(json_str)
        return cls(
            finding_id=data["finding_id"],
            statement_key=data["statement_key"],
            path_id=data["path_id"],
            case_id=data["case_id"],
            is_slow=data["is_slow"],
            severity=data["severity"],
            impact_score=data["impact_score"],
            confidence=data["confidence"],
            root_causes=[RootCauseHit(**item) for item in data.get("root_causes", [])],
            explain_ref=data.get("explain_ref"),
            execution_ref=data.get("execution_ref"),
            optimization_ready=data.get("optimization_ready", False),
        )
