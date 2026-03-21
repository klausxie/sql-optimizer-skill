"""
Parameter parser for SQL templates.

Extracts #{param} and ${param} style parameters from SQL.
"""

import re
from typing import Any


def parse_parameters(sql: str) -> list[dict[str, Any]]:
    """
    Parse parameters from SQL template.

    Returns list of dicts with 'name' and 'type' keys.
    type is 'bind' for #{...} and 'literal' for ${...}
    """
    if not sql:
        return []

    params = []

    # Match #{param} style (bind parameters)
    bind_pattern = re.compile(r"#\{([^}]+)\}")
    for match in bind_pattern.finditer(sql):
        param_name = match.group(1)
        params.append({"name": param_name, "type": "bind"})

    # Match ${param} style (literal parameters)
    literal_pattern = re.compile(r"\$\{([^}]+)\}")
    for match in literal_pattern.finditer(sql):
        param_name = match.group(1)
        params.append({"name": param_name, "type": "literal"})

    return params
