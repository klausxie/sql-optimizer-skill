"""Contract definitions for init operation."""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import List


@dataclass
class SQLUnit:
    """Represents a single SQL unit extracted from a mapper file."""

    id: str
    mapper_file: str
    sql_id: str
    sql_text: str
    statement_type: str  # SELECT, INSERT, UPDATE, DELETE

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> "SQLUnit":
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls(**data)


@dataclass
class InitOutput:
    """Output contract for the init operation."""

    sql_units: List[SQLUnit]
    run_id: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_json(self) -> str:
        """Serialize to JSON string."""
        data = {
            "sql_units": [asdict(unit) for unit in self.sql_units],
            "run_id": self.run_id,
            "timestamp": self.timestamp,
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str) -> "InitOutput":
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        sql_units = [SQLUnit(**unit) for unit in data["sql_units"]]
        return cls(
            sql_units=sql_units,
            run_id=data["run_id"],
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
        )
