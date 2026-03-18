"""Parse user input and extract optimization targets.

This stage handles:
- Parse single SQL input
- Parse multiple SQL references
- Parse file/mapper paths
- Generate target list for optimization
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ParseTarget:
    """Parsed optimization target."""
    target_type: str  # "sql", "method", "file", "pattern"
    value: str        # The actual value (SQL text, method name, file path)
    source: str       # Original user input


def parse_user_input(user_input: str) -> list[ParseTarget]:
    """Parse user input and extract optimization targets.
    
    Examples:
        - "优化这条SQL: select * from users"
        - "优化findUsers, findOrders这两个方法"
        - "优化UserMapper.xml"
        - "优化所有Mapper文件"
    
    Args:
        user_input: Raw user input text
        
    Returns:
        List of ParseTarget objects
    """
    targets: list[ParseTarget] = []
    
    # Pattern 1: Single SQL - "优化这条SQL: SELECT ..."
    sql_match = re.search(r'优化这条SQL[:：]\s*(.+)', user_input, re.IGNORECASE)
    if sql_match:
        sql = sql_match.group(1).strip()
        targets.append(ParseTarget(
            target_type="sql",
            value=sql,
            source=user_input
        ))
        return targets
    
    # Pattern 2: Multiple methods - "优化findUsers, findOrders这两个方法"
    method_match = re.search(r'优化([\w,\s]+)(?:这些?|个?)方法', user_input, re.IGNORECASE)
    if method_match:
        methods_text = method_match.group(1).strip()
        # Split by comma or whitespace
        methods = re.split(r'[,，\s]+', methods_text)
        for method in methods:
            method = method.strip()
            if method:
                targets.append(ParseTarget(
                    target_type="method",
                    value=method,
                    source=user_input
                ))
        if targets:
            return targets
    
    # Pattern 3: File path - "优化xxx.xml"
    file_match = re.search(r'优化(.+\.xml)', user_input, re.IGNORECASE)
    if file_match:
        file_path = file_match.group(1).strip()
        targets.append(ParseTarget(
            target_type="file",
            value=file_path,
            source=user_input
        ))
        return targets
    
    # Pattern 4: All mappers - "优化所有Mapper"
    if '所有' in user_input and 'mapper' in user_input.lower():
        targets.append(ParseTarget(
            target_type="pattern",
            value="*_mapper.xml",
            source=user_input
        ))
        return targets
    
    # Fallback: treat as SQL
    targets.append(ParseTarget(
        target_type="sql",
        value=user_input,
        source=user_input
    ))
    
    return targets


def validate_targets(targets: list[ParseTarget]) -> tuple[list[ParseTarget], list[str]]:
    """Validate parsed targets.
    
    Args:
        targets: List of ParseTarget objects
        
    Returns:
        Tuple of (valid targets, error messages)
    """
    valid: list[ParseTarget] = []
    errors: list[str] = []
    
    for target in targets:
        if target.target_type == "sql" and not target.value:
            errors.append(f"Empty SQL for target: {target.source}")
            continue
            
        if target.target_type == "file":
            # Check if file exists
            path = Path(target.value)
            if not path.exists():
                errors.append(f"File not found: {target.value}")
                continue
                
        if target.target_type == "method" and not target.value:
            errors.append(f"Empty method name for target: {target.source}")
            continue
            
        valid.append(target)
    
    return valid, errors
