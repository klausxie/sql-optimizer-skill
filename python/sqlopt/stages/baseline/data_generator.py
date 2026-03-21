"""
Test data generator for baseline measurements.

Generates sample values and rows for testing.
"""

from datetime import datetime
from typing import Any


def generate_test_value(column_type: str) -> Any:
    """Generate a test value based on column type."""
    col_type = column_type.lower() if column_type else ""

    if "int" in col_type or "serial" in col_type or "bigint" in col_type:
        return 0
    elif "bool" in col_type:
        return True
    elif "float" in col_type or "numeric" in col_type or "decimal" in col_type:
        return 0.0
    elif "timestamp" in col_type or "date" in col_type or "time" in col_type:
        return datetime.now()
    elif "text" in col_type or "varchar" in col_type or "char" in col_type:
        return "test_value"
    elif col_type == "":
        return "placeholder"
    else:
        return "placeholder"


def generate_row(column_types: dict[str, str]) -> dict[str, Any]:
    """Generate a complete data row with test values."""
    row = {}
    for column, col_type in column_types.items():
        row[column] = generate_test_value(col_type)
    return row
