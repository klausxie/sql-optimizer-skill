from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field


@dataclass
class ColumnMetadata:
    name: str
    type: str
    nullable: bool

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "ColumnMetadata":
        return cls(**json.loads(json_str))


@dataclass
class IndexMetadata:
    name: str
    is_unique: bool
    columns: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "IndexMetadata":
        return cls(**json.loads(json_str))


@dataclass
class SQLUnit:
    statement_key: str
    namespace: str
    statement_id: str
    statement_type: str
    mapper_file: str
    xml_path: str
    raw_sql_xml: str
    has_dynamic_sql: bool = False
    referenced_tables: list[str] = field(default_factory=list)
    referenced_fragments: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "SQLUnit":
        return cls(**json.loads(json_str))


@dataclass
class SQLFragment:
    fragment_id: str
    xml_path: str
    start_line: int
    end_line: int
    xml_content: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "SQLFragment":
        return cls(**json.loads(json_str))


@dataclass
class TableMetadata:
    table_name: str
    row_count: int
    data_bytes: int | None = None
    columns: list[ColumnMetadata] = field(default_factory=list)
    indexes: list[IndexMetadata] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(
            {
                "table_name": self.table_name,
                "row_count": self.row_count,
                "data_bytes": self.data_bytes,
                "columns": [asdict(item) for item in self.columns],
                "indexes": [asdict(item) for item in self.indexes],
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "TableMetadata":
        data = json.loads(json_str)
        return cls(
            table_name=data["table_name"],
            row_count=data["row_count"],
            data_bytes=data.get("data_bytes"),
            columns=[ColumnMetadata(**item) for item in data.get("columns", [])],
            indexes=[IndexMetadata(**item) for item in data.get("indexes", [])],
        )


@dataclass
class TopValueStat:
    value: str
    count: int

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "TopValueStat":
        return cls(**json.loads(json_str))


@dataclass
class HistogramBucket:
    bucket: str
    count: int

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "HistogramBucket":
        return cls(**json.loads(json_str))


@dataclass
class ColumnDistribution:
    table_name: str
    column_name: str
    distinct_count: int
    null_count: int
    null_ratio: float
    top_values: list[TopValueStat] = field(default_factory=list)
    histogram: list[HistogramBucket] = field(default_factory=list)
    skew_score: float | None = None

    def to_json(self) -> str:
        return json.dumps(
            {
                "table_name": self.table_name,
                "column_name": self.column_name,
                "distinct_count": self.distinct_count,
                "null_count": self.null_count,
                "null_ratio": self.null_ratio,
                "top_values": [asdict(item) for item in self.top_values],
                "histogram": [asdict(item) for item in self.histogram],
                "skew_score": self.skew_score,
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "ColumnDistribution":
        data = json.loads(json_str)
        return cls(
            table_name=data["table_name"],
            column_name=data["column_name"],
            distinct_count=data["distinct_count"],
            null_count=data["null_count"],
            null_ratio=data["null_ratio"],
            top_values=[TopValueStat(**item) for item in data.get("top_values", [])],
            histogram=[HistogramBucket(**item) for item in data.get("histogram", [])],
            skew_score=data.get("skew_score"),
        )


@dataclass
class ColumnUsageMap:
    statement_key: str
    where_columns: list[str] = field(default_factory=list)
    join_columns: list[str] = field(default_factory=list)
    group_by_columns: list[str] = field(default_factory=list)
    order_by_columns: list[str] = field(default_factory=list)
    range_columns: list[str] = field(default_factory=list)
    like_columns: list[str] = field(default_factory=list)
    in_columns: list[str] = field(default_factory=list)
    foreach_collections: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "ColumnUsageMap":
        return cls(**json.loads(json_str))
