"""
Parameter binder for matching parameters to data columns.

Handles camelCase/snake_case conversion and fallback value generation.
"""

import re
from typing import Any


def _camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    # Handle special case of all caps (like "ID" -> "id")
    if name.isupper():
        return name.lower()
    # Handle leading underscore
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _snake_to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    components = name.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def _find_matching_column(param_name: str, data_row: dict[str, Any]) -> Any:
    """
    Find a matching column in data_row for the given parameter name.
    Tries exact match first, then camel/snake variations.
    """
    # Exact match
    if param_name in data_row:
        return data_row[param_name]

    # Try camelCase version
    camel_version = _camel_to_snake(param_name)
    if camel_version in data_row:
        return data_row[camel_version]

    # Try snake_case version
    snake_version = _snake_to_camel(param_name)
    if snake_version in data_row:
        return data_row[snake_version]

    # Try suffix match (e.g., "status" matches "user_status")
    for key, value in data_row.items():
        if key.endswith("_" + param_name) or param_name.endswith("_" + key):
            return value

    return None


def _generate_fallback_value(column: str, column_types: dict[str, str]) -> Any:
    """Generate a fallback value based on column type."""
    col_type = column_types.get(column, "").lower()

    if "int" in col_type or "serial" in col_type:
        return 0
    elif "bool" in col_type:
        return False
    elif "float" in col_type or "numeric" in col_type or "decimal" in col_type:
        return 0.0
    elif "timestamp" in col_type or "date" in col_type or "time" in col_type:
        from datetime import datetime

        return datetime.now()
    elif "text" in col_type or "varchar" in col_type or "char" in col_type:
        return f"generated_{column}"
    else:
        return f"fallback_{column}"


def bind_parameters(
    params: list[dict[str, Any]],
    data_rows: list[dict[str, Any]],
    column_types: dict[str, str],
) -> list[dict[str, Any]]:
    """
    Bind parameters to data rows, generating fallback values when needed.
    """
    if not params or not data_rows:
        return []

    result = []
    for data_row in data_rows:
        bound_row = {}
        has_all_params = True

        for param in params:
            param_name = param["name"]
            value = _find_matching_column(param_name, data_row)
            if value is None:
                value = _generate_fallback_value(param_name, column_types)
                has_all_params = False
            bound_row[param_name] = value

        if has_all_params or bound_row:
            result.append(bound_row)

    return result
