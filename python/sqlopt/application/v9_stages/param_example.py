"""ParamExample Generator - Generate example values for SQL parameters."""

import re
from typing import Any


def _extract_param_names(sql: str) -> list[str]:
    """Extract #{paramName} parameter names from SQL."""
    pattern = r"#\{(\w+)\}"
    return re.findall(pattern, sql)


def _camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    if not name:
        return name
    # Handle already snake_case or all caps
    if "_" not in name and name.isupper():
        return name.lower()
    # Insert underscore before uppercase letters, then lowercase the result
    result = re.sub(r"([A-Z])", r"_\1", name)
    return result.lower().lstrip("_")


def _snake_to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    if not name:
        return name
    components = name.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def _remove_underscores(name: str) -> str:
    """Remove all underscores from a name."""
    return name.replace("_", "")


def _find_matching_column(param_name: str, columns: list[dict]) -> dict | None:
    """Find matching column for a parameter name using priority matching."""
    if not columns:
        return None

    # Priority 1: Exact match (case-sensitive)
    for col in columns:
        col_name = col.get("column", "")
        if col_name == param_name:
            return col

    # Priority 2: camelCase → snake_case conversion
    param_snake = _camel_to_snake(param_name)
    for col in columns:
        col_name = col.get("column", "")
        if col_name == param_snake:
            return col

    # Priority 3: snake_case → camelCase conversion
    param_camel = _snake_to_camel(param_name)
    for col in columns:
        col_name = col.get("column", "")
        if col_name == param_camel:
            return col

    # Priority 4: Remove underscores and match
    param_no_underscore = _remove_underscores(param_name)
    for col in columns:
        col_name = col.get("column", "")
        if _remove_underscores(col_name) == param_no_underscore:
            return col

    return None


def _get_example_value(data_type: str | None, is_nullable: bool) -> Any:
    """Get example value based on column data type."""
    if data_type is None:
        return None

    data_type_upper = data_type.upper()

    # Handle nullable case - return null
    if is_nullable:
        return None

    # Numeric types
    if data_type_upper in ("INTEGER", "INT", "INT4"):
        return 1
    if data_type_upper in ("BIGINT", "INT8"):
        return 1
    if data_type_upper in ("SMALLINT", "INT2"):
        return 1

    # String types
    if data_type_upper in ("VARCHAR", "TEXT", "CHAR"):
        return "example"

    # Boolean
    if data_type_upper in ("BOOLEAN", "BOOL"):
        return True

    # Date/Time types
    if data_type_upper == "DATE":
        return "2024-01-01"
    if data_type_upper in ("TIMESTAMP", "DATETIME"):
        return "2024-01-01T00:00:00"
    if data_type_upper == "TIME":
        return "12:00:00"

    # Float/Decimal types
    if data_type_upper in ("FLOAT", "REAL"):
        return 1.0
    if data_type_upper == "DOUBLE":
        return 1.0
    if data_type_upper in ("DECIMAL", "NUMERIC"):
        return 1.0

    # Binary
    if data_type_upper == "BYTEA":
        return "\\x00"

    # JSON
    if data_type_upper in ("JSON", "JSONB"):
        return {}

    # Array
    if data_type_upper == "ARRAY":
        return []

    # Default fallback
    return None


def generate_param_examples(sql_units: list[dict], schema_metadata: dict) -> list[dict]:
    """
    Generate example values for SQL parameters.

    Args:
        sql_units: List of SQL unit dicts with 'sqlKey', 'sql', and 'paramExample' fields
        schema_metadata: Dict with 'columns' list containing column metadata

    Returns:
        New list of sql_units with populated paramExample field
    """
    # Handle empty schema_metadata gracefully
    if not schema_metadata or "columns" not in schema_metadata:
        return [{**unit, "paramExample": {}} for unit in sql_units]

    columns = schema_metadata["columns"]

    result = []
    for unit in sql_units:
        sql = unit.get("sql", "")
        param_names = _extract_param_names(sql)

        param_example = {}
        for param_name in param_names:
            matched_col = _find_matching_column(param_name, columns)
            if matched_col:
                data_type = matched_col.get("dataType")
                is_nullable = matched_col.get("isNullable", True)
                param_example[param_name] = _get_example_value(data_type, is_nullable)
            else:
                # No matching column found - use None as fallback
                param_example[param_name] = None

        result.append({**unit, "paramExample": param_example})

    return result
