"""
Patch formatting - backward compatibility wrapper.

This module is deprecated. Use:
- sql_formatter for SQL formatting
- template_formatter for template formatting
"""

from .sql_formatter import format_sql_for_patch
from .template_formatter import (
    detect_duplicate_clause_in_template_ops,
    format_template_ops_for_patch,
)

__all__ = [
    "format_sql_for_patch",
    "format_template_ops_for_patch",
    "detect_duplicate_clause_in_template_ops",
]