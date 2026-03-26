from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field


@dataclass
class PrioritizedFinding:
    rank: int
    finding_id: str
    statement_key: str
    path_id: str
    case_id: str
    severity: str
    impact_score: float
    best_proposal_id: str | None = None
    recommendation_level: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "PrioritizedFinding":
        return cls(**json.loads(json_str))


@dataclass
class GlobalReportSummary:
    statements_scanned: int = 0
    branches_generated: int = 0
    explain_executed: int = 0
    execution_baselines: int = 0
    verified_slow_sql: int = 0
    high_risk_candidates: int = 0

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "GlobalReportSummary":
        return cls(**json.loads(json_str))


@dataclass
class GlobalReport:
    summary: GlobalReportSummary = field(default_factory=GlobalReportSummary)
    top_findings: list[PrioritizedFinding] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(
            {
                "summary": asdict(self.summary),
                "top_findings": [asdict(item) for item in self.top_findings],
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "GlobalReport":
        data = json.loads(json_str)
        return cls(
            summary=GlobalReportSummary(**data.get("summary", {})),
            top_findings=[PrioritizedFinding(**item) for item in data.get("top_findings", [])],
        )


@dataclass
class NamespaceReport:
    namespace: str
    verified_slow_sql: int = 0
    recommended_actions: int = 0
    findings: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "NamespaceReport":
        return cls(**json.loads(json_str))


@dataclass
class PatchArtifact:
    statement_key: str
    mapper_file: str
    proposal_id: str
    original_xml: str
    patched_xml: str
    diff: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "PatchArtifact":
        return cls(**json.loads(json_str))
