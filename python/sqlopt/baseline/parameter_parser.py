"""Baseline parameter parser for MyBatis SQL statements."""

import re
from typing import Any


def parse_parameters(sql: str) -> list[dict[str, Any]]:
    """Extract #{param} and ${param} from SQL.

    Args:
        sql: SQL string with MyBatis parameter placeholders

    Returns:
        List of dicts with 'name' and 'type' keys.
        type='bind' for #{...}, type='literal' for ${...}
    """
    if not sql:
        return []

    results: list[dict[str, Any]] = []

    # Match #{param} or #{param, ...} - bind parameters
    bind_pattern = re.compile(r"#\{([^},]+)")
    for match in bind_pattern.finditer(sql):
        param_name = match.group(1).strip()
        if param_name:
            results.append({"name": param_name, "type": "bind"})

    # Match ${param} - literal parameters
    literal_pattern = re.compile(r"\$\{([^}]+)")
    for match in literal_pattern.finditer(sql):
        param_name = match.group(1).strip()
        if param_name:
            results.append({"name": param_name, "type": "literal"})

    return results
