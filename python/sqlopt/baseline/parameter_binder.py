"""Baseline parameter binder for mapping data to SQL parameters."""

import re
from typing import Any


def _camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    # First, handle the pattern where lowercase is followed by uppercase
    # e.g., userId -> user_id
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    # Then handle the pattern where uppercase is followed by uppercase then lowercase
    # e.g., userID -> user_id
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _snake_to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    components = name.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def _find_matching_column(param_name: str, data_row: dict) -> Any:
    """Find matching column in data row using name variations.

    Try exact match first, then camelCase/snake_case variations.
    """
    # Exact match
    if param_name in data_row:
        return data_row[param_name]

    # Try camelCase to snake_case
    snake_name = _camel_to_snake(param_name)
    if snake_name in data_row:
        return data_row[snake_name]

    # Try snake_case to camelCase
    camel_name = _snake_to_camel(param_name)
    if camel_name in data_row:
        return data_row[camel_name]

    # Try suffix match: status -> user_status
    for col_name in data_row:
        if col_name.endswith(f"_{param_name}"):
            return data_row[col_name]

    return None


def _generate_fallback_value(param_name: str, column_types: dict) -> Any:
    """Generate fallback value when parameter not found in data."""
    # Try to find type from column_types with name variations
    param_snake = _camel_to_snake(param_name)
    param_camel = _snake_to_camel(param_name)

    for name_var in [param_name, param_snake, param_camel]:
        col_type = column_types.get(name_var, "").lower()
        if "int" in col_type or "numeric" in col_type or "decimal" in col_type:
            return 0
        if "varchar" in col_type or "text" in col_type or "char" in col_type:
            return f"generated_{param_name}"
        if "bool" in col_type:
            return False

    # Default fallback
    return f"fallback_{param_name}"


def bind_parameters(
    params: list[dict], data_rows: list[dict], column_types: dict
) -> list[dict]:
    """Bind parameters to data rows.

    Args:
        params: List of param dicts with 'name' and 'type' keys
        data_rows: List of data row dicts
        column_types: Dict mapping column names to types

    Returns:
        List of bound parameter dicts (one per data row)
    """
    if not params or not data_rows:
        return []

    results: list[dict] = []

    for data_row in data_rows:
        bound: dict = {}

        for param in params:
            param_name = param["name"]

            # Try to find matching column
            value = _find_matching_column(param_name, data_row)

            if value is not None:
                bound[param_name] = value
            else:
                # Fallback to generator
                bound[param_name] = _generate_fallback_value(param_name, column_types)

        results.append(bound)

    return results
