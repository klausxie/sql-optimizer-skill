"""Rules Skill - SQL optimization rules.

This module provides rule-based SQL optimization capabilities.
Rules can be loaded on-demand for different optimization scenarios.

Usage:
    from sqlopt.rules import load_rules, get_rule
    
    # Load all rules
    rules = load_rules()
    
    # Load specific rule category
    rules = load_rules(category="canonicalization")
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Any


RULES_INDEX = {
    "canonicalization": {
        "description": "SQL normalization rules",
        "rules": [
            "redundant_subquery",
            "redundant_having", 
            "redundant_groupby",
            "redundant_distinct",
            "count_form",
            "alias_only",
        ]
    },
    "intent": {
        "description": "SQL intent detection rules",
        "rules": [
            "dynamic_filter_wrapper",
            "dynamic_filter_select_list_cleanup",
            "dynamic_filter_from_alias_cleanup",
            "dynamic_count_wrapper",
            "static_include_statement",
        ]
    },
    "patch": {
        "description": "Patch generation rules",
        "rules": []
    }
}


def load_rules(category: str | None = None) -> dict[str, Any]:
    """Load optimization rules.
    
    Args:
        category: Optional category to filter rules
        
    Returns:
        Dictionary of loaded rules
    """
    if category:
        return RULES_INDEX.get(category, {})
    return RULES_INDEX


def get_rule(category: str, rule_name: str) -> Any | None:
    """Get a specific rule.
    
    Args:
        category: Rule category
        rule_name: Rule name
        
    Returns:
        Rule module or None if not found
    """
    if category not in RULES_INDEX:
        return None
        
    if rule_name not in RULES_INDEX[category].get("rules", []):
        return None
    
    # Try to import the rule module
    try:
        module_path = f"sqlopt.platforms.sql.{category}_rules.{rule_name}"
        return importlib.import_module(module_path)
    except ImportError:
        return None


__all__ = ["load_rules", "get_rule", "RULES_INDEX"]
