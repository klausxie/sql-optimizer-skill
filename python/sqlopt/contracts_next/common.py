from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field


@dataclass
class StageTotals:
    statements: int = 0
    branches: int = 0
    cases: int = 0
    findings: int = 0

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "StageTotals":
        return cls(**json.loads(json_str))


@dataclass
class PartitionRef:
    partition_key: str
    entity: str
    item_count: int
    index_file: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "PartitionRef":
        return cls(**json.loads(json_str))


@dataclass
class EntityRef:
    id: str
    file: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "EntityRef":
        return cls(**json.loads(json_str))


@dataclass
class ShardRef:
    shard: str
    record_count: int
    namespace_range: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "ShardRef":
        return cls(**json.loads(json_str))


@dataclass
class ResultSignature:
    row_count: int
    ordered_key_digest: str
    sample_digest: str
    ordering_columns: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "ResultSignature":
        return cls(**json.loads(json_str))


@dataclass
class PlanFlags:
    full_table_scan: bool = False
    filesort: bool = False
    temporary_table: bool = False
    hash_aggregate: bool = False
    nested_loop_amplification: bool = False

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "PlanFlags":
        return cls(**json.loads(json_str))


@dataclass
class RootCauseHit:
    code: str
    severity: str
    message: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "RootCauseHit":
        return cls(**json.loads(json_str))


@dataclass
class StageManifest:
    schema_version: str
    run_id: str
    stage_name: str
    status: str
    started_at: str | None = None
    completed_at: str | None = None
    totals: StageTotals = field(default_factory=StageTotals)
    index_file: str = "_index.json"

    def to_json(self) -> str:
        return json.dumps(
            {
                "schema_version": self.schema_version,
                "run_id": self.run_id,
                "stage_name": self.stage_name,
                "status": self.status,
                "started_at": self.started_at,
                "completed_at": self.completed_at,
                "totals": asdict(self.totals),
                "index_file": self.index_file,
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "StageManifest":
        data = json.loads(json_str)
        return cls(
            schema_version=data["schema_version"],
            run_id=data["run_id"],
            stage_name=data["stage_name"],
            status=data["status"],
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            totals=StageTotals(**data.get("totals", {})),
            index_file=data.get("index_file", "_index.json"),
        )
