"""
Branch command implementation.

Provides functionality for parsing and analyzing MyBatis mapper XML files
to identify dynamic SQL branches (if, choose, foreach, etc.).
"""

from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET


def parse_mapper_xml(mapper_path: str) -> dict[str, dict[str, Any]]:
    path = Path(mapper_path)
    tree = ET.parse(path)
    root = tree.getroot()

    namespace = root.get("namespace", "")
    result = {}

    for element in root:
        local_tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag
        if local_tag not in ("select", "insert", "update", "delete"):
            continue

        statement_id = element.get("id", "")
        if not statement_id:
            continue

        tag_str = ET.tostring(element, encoding="unicode")
        full_id = f"{namespace}.{statement_id}" if namespace else statement_id

        result[statement_id] = {
            "template_sql": tag_str,
            "type": local_tag,
            "sql_key": full_id,
        }

    return result
