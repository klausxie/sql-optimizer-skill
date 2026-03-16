"""Data generator for test data based on column types."""

from datetime import datetime, date
from typing import Any, Dict
import random


# Type mapping from PostgreSQL types to test values
TYPE_MAPPING = {
    # String types
    "varchar": "test_value",
    "text": "test_value",
    "character varying": "test_value",
    "char": "test_value",
    "character": "test_value",
    # Integer types
    "integer": lambda: random.choice([0, 1]),
    "bigint": lambda: random.choice([0, 1]),
    "smallint": lambda: random.choice([0, 1]),
    "int": lambda: random.choice([0, 1]),
    "int2": lambda: random.choice([0, 1]),
    "int4": lambda: random.choice([0, 1]),
    "int8": lambda: random.choice([0, 1]),
    # Datetime types
    "timestamp": lambda: datetime.now(),
    "timestamptz": lambda: datetime.now(),
    "timestamp without time zone": lambda: datetime.now(),
    "timestamp with time zone": lambda: datetime.now(),
    "datetime": lambda: datetime.now(),
    # Date type
    "date": lambda: date.today(),
    # Boolean type
    "boolean": True,
    "bool": True,
    # Float types
    "numeric": 0.0,
    "decimal": 0.0,
    "real": 0.0,
    "double precision": 0.0,
    "float": 0.0,
    "float4": 0.0,
    "float8": 0.0,
}


def generate_test_value(column_type: str) -> Any:
    """
    Generate a test value based on column type.

    Args:
        column_type: The PostgreSQL column type (e.g., 'varchar', 'integer', 'timestamp')

    Returns:
        A test value appropriate for the column type.
        Unknown types return 'placeholder'.
    """
    if not column_type:
        return "placeholder"

    # Normalize column type (lowercase, strip whitespace)
    normalized_type = column_type.lower().strip()

    # Direct lookup
    if normalized_type in TYPE_MAPPING:
        value = TYPE_MAPPING[normalized_type]
        # If it's a callable, call it to generate the value
        if callable(value):
            return value()
        return value

    # Check for partial matches (e.g., "timestamp without time zone" contains "timestamp")
    for type_key, type_value in TYPE_MAPPING.items():
        if type_key in normalized_type or normalized_type in type_key:
            if callable(type_value):
                return type_value()
            return type_value

    # Default for unknown types
    return "placeholder"


def generate_row(column_types: Dict[str, str]) -> Dict[str, Any]:
    """
    Generate a test row based on column types.

    Args:
        column_types: Dict mapping column names to their PostgreSQL types.
                      Example: {"id": "integer", "name": "varchar"}

    Returns:
        A dict with column names as keys and generated test values as values.
    """
    result = {}
    for column_name, column_type in column_types.items():
        result[column_name] = generate_test_value(column_type)
    return result
