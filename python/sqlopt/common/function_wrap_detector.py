"""AST-based function-wrapped column detection for SQL optimization.

Detects columns wrapped in functions that can bypass indexes in WHERE clauses.
"""

from __future__ import annotations

import sqlglot.expressions as exp
from sqlglot.errors import SqlglotError

# Functions that can bypass indexes when applied to columns in WHERE clauses
INDEX_BYPASS_FUNCTIONS = {
    # Case manipulation
    "UPPER",
    "LOWER",
    # Date extraction
    "DATE",
    "YEAR",
    "MONTH",
    "DAY",
    "HOUR",
    "MINUTE",
    "SECOND",
    "WEEK",
    "QUARTER",
    "DAYNAME",
    "MONTHNAME",
    # Date manipulation
    "DATE_FORMAT",
    "DATE_ADD",
    "DATE_SUB",
    "DATEDIFF",
    "TIMESTAMPDIFF",
    "TIMESTAMPADD",
    # String trimming
    "TRIM",
    "LTRIM",
    "RTRIM",
    # String extraction
    "SUBSTRING",
    "SUBSTR",
    "MID",
    "LEFT",
    "RIGHT",
    # String manipulation
    "CONCAT",
    "REVERSE",
    "REPLACE",
    # Math
    "ABS",
    "ROUND",
    "FLOOR",
    "CEIL",
    "CEILING",
    "MOD",
    # Type conversion
    "CAST",
    "CONVERT",
    # Null handling
    "COALESCE",
    "IFNULL",
    "NVL",
    "ISNULL",
    # Length
    "LENGTH",
    "CHAR_LENGTH",
    "CHARACTER_LENGTH",
}

# Normalized function names that sqlglot uses for certain dialects
# (e.g., MySQL normalizes DATE() to CAST)
NORMALIZED_FUNCTION_MAP = {
    "TS_OR_DS_TO_DATE": "DATE",
    "TIME_TO_STR": "DATE_FORMAT",
}

# Aggregate/window functions to skip (these don't bypass indexes in the same way)
AGGREGATE_WINDOW_FUNCTIONS = {
    "COUNT",
    "SUM",
    "AVG",
    "MIN",
    "MAX",
    "ROW_NUMBER",
    "RANK",
    "DENSE_RANK",
    "LEAD",
    "LAG",
    "FIRST_VALUE",
    "LAST_VALUE",
    "NTILE",
    "CUME_DIST",
    "PERCENT_RANK",
    "LISTAGG",
    "STRING_AGG",
    "ARRAY_AGG",
    "JSON_AGG",
    "XMLAGG",
}


def detect_function_wrapped_columns(sql: str, dialect: str | None = None) -> list[tuple[str, str]]:
    """Detect columns wrapped in functions that can bypass indexes.

    Args:
        sql: SQL statement to analyze
        dialect: SQL dialect (e.g., 'mysql', 'postgresql'). If None, uses default.

    Returns:
        List of (column_name, function_name) tuples for columns wrapped in
        risky functions in WHERE clauses.
    """
    results: list[tuple[str, str]] = []

    try:
        tree = exp.maybe_parse(sql, dialect=dialect)
    except SqlglotError:
        return results

    # Find all WHERE clauses in the SQL
    for where_clause in tree.find_all(exp.Where):
        _check_where_clause_for_risky_functions(where_clause, results)

    return results


def _check_where_clause_for_risky_functions(where_node: exp.Where, results: list[tuple[str, str]]) -> None:
    for func in where_node.find_all(exp.Func):
        func_name_upper = func.sql_name().upper()

        # Handle Anonymous functions (e.g., DATE_FORMAT in some dialects)
        if func_name_upper == "ANONYMOUS" and hasattr(func, "this"):
            func_name_upper = str(func.this).upper()

        if func_name_upper in AGGREGATE_WINDOW_FUNCTIONS:
            continue

        # Check if function is in our risky list (either directly or via normalized name)
        if func_name_upper not in INDEX_BYPASS_FUNCTIONS:
            # Check normalized map for dialect-specific transformations
            original_name = NORMALIZED_FUNCTION_MAP.get(func_name_upper)
            if original_name is None or original_name not in INDEX_BYPASS_FUNCTIONS:
                continue
            func_name_upper = original_name

        for arg in func.args.values():
            if arg is None:
                continue

            if isinstance(arg, exp.Column):
                column_name = arg.name
                results.append((column_name, func_name_upper))
                continue

            if isinstance(arg, list):
                for item in arg:
                    if isinstance(item, exp.Column):
                        column_name = item.name
                        results.append((column_name, func_name_upper))
                continue

            if hasattr(arg, "find_all"):
                for col in arg.find_all(exp.Column):
                    column_name = col.name
                    if (column_name, func_name_upper) not in results:
                        results.append((column_name, func_name_upper))
