"""Contract definitions for init operation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class SQLUnit:
    """Represents a single SQL unit extracted from a mapper file."""

    id: str
    mapper_file: str
    sql_id: str
    sql_text: str
    statement_type: str

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> SQLUnit:
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls(**data)


@dataclass
class SQLFragment:
    """Represents a reusable SQL fragment (<sql id="">) from mapper files."""

    fragmentId: str  # noqa: N815
    xmlPath: str  # noqa: N815
    startLine: int  # noqa: N815
    endLine: int  # noqa: N815
    xmlContent: str  # noqa: N815

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> SQLFragment:
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls(**data)


@dataclass
class TableSchema:
    """Represents table schema with columns, indexes, and statistics."""

    columns: List[Dict[str, Any]]
    indexes: List[Dict[str, Any]]
    statistics: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> TableSchema:
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls(**data)


@dataclass
class FragmentMapping:
    """Mapping for a SQL fragment within an XML file."""

    fragmentId: str  # noqa: N815
    sqlKey: Optional[str]  # noqa: N815
    xpath: str
    tagName: str  # noqa: N815
    idAttr: str  # noqa: N815
    originalContent: str  # noqa: N815

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> FragmentMapping:
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls(**data)


@dataclass
class StatementMapping:
    """Mapping for a SQL statement within an XML file."""

    sqlKey: str  # noqa: N815
    statementId: str  # noqa: N815
    xpath: str
    tagName: str  # noqa: N815
    idAttr: str  # noqa: N815
    originalContent: str  # noqa: N815

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> StatementMapping:
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls(**data)


@dataclass
class FileMapping:
    """Mapping for a single XML file containing fragments and statements."""

    xmlPath: str  # noqa: N815
    fragments: List[FragmentMapping] = field(default_factory=list)
    statements: List[StatementMapping] = field(default_factory=list)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> FileMapping:
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        fragments = [FragmentMapping(**f) for f in data.get("fragments", [])]
        statements = [StatementMapping(**s) for s in data.get("statements", [])]
        return cls(
            xmlPath=data["xmlPath"],
            fragments=fragments,
            statements=statements,
        )


@dataclass
class XMLMapping:
    """Complete XML mapping structure for all mapper files."""

    files: List[FileMapping] = field(default_factory=list)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> XMLMapping:
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        files = [FileMapping(**f) for f in data.get("files", [])]
        return cls(files=files)


@dataclass
class InitOutput:
    """Output contract for the init operation."""

    sql_units: List[SQLUnit]
    run_id: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    sql_fragments: List[SQLFragment] = field(default_factory=list)
    table_schemas: Dict[str, TableSchema] = field(default_factory=dict)
    xml_mappings: Optional[XMLMapping] = None

    def to_json(self) -> str:
        """Serialize to JSON string."""
        data = {
            "sql_units": [asdict(unit) for unit in self.sql_units],
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "sql_fragments": [asdict(frag) for frag in self.sql_fragments],
            "table_schemas": {k: asdict(v) for k, v in self.table_schemas.items()},
            "xml_mappings": asdict(self.xml_mappings) if self.xml_mappings else None,
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str) -> InitOutput:
        """Deserialize from JSON string (backward compatible).

        Supports two formats:
        1. Full InitOutput object: {"sql_units": [...], "run_id": "...", ...}
        2. SQL units list only: [...] (for backward compatibility with sql_units.json files)
        """
        data = json.loads(json_str)

        # Handle both list format (sql_units.json) and full object format
        if isinstance(data, list):
            # sql_units.json contains just the list of SQL units
            sql_units = [SQLUnit(**unit) for unit in data]
            return cls(
                sql_units=sql_units,
                run_id="unknown",
                sql_fragments=[],
                table_schemas={},
                xml_mappings=None,
            )

        # Full InitOutput object format
        sql_units = [SQLUnit(**unit) for unit in data["sql_units"]]
        sql_fragments = [SQLFragment(**frag) for frag in data.get("sql_fragments", [])]
        table_schemas = {k: TableSchema(**v) for k, v in data.get("table_schemas", {}).items()}
        xml_mappings_data = data.get("xml_mappings")
        xml_mappings = XMLMapping.from_json(json.dumps(xml_mappings_data)) if xml_mappings_data else None
        return cls(
            sql_units=sql_units,
            run_id=data["run_id"],
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            sql_fragments=sql_fragments,
            table_schemas=table_schemas,
            xml_mappings=xml_mappings,
        )
