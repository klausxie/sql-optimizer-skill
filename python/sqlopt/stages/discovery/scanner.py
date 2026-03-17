"""
Discovery Stage - SQL Scanning and Parsing

Scans MyBatis XML mapper files and parses SQL statements.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import json
import re


@dataclass
class ScanResult:
    """扫描结果"""

    sql_units: list[dict]
    total_count: int
    errors: list[str]


class Scanner:
    """MyBatis XML 扫描器"""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.mapper_globs = self.config.get("scan", {}).get(
            "mapper_globs", ["**/*.xml"]
        )

    def scan(self, root_path: str | Path) -> ScanResult:
        """扫描目录下的所有 MyBatis mapper 文件"""
        root = Path(root_path)
        errors = []
        sql_units = []

        for pattern in self.mapper_globs:
            for xml_file in root.glob(pattern):
                if xml_file.is_file() and "mapper" in xml_file.name.lower():
                    try:
                        units = self._parse_mapper(xml_file)
                        sql_units.extend(units)
                    except Exception as e:
                        errors.append(f"{xml_file}: {e}")

        return ScanResult(
            sql_units=sql_units, total_count=len(sql_units), errors=errors
        )

    def _parse_mapper(self, xml_path: Path) -> list[dict]:
        """解析单个 mapper 文件"""
        import xml.etree.ElementTree as ET

        units = []
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            namespace = root.get("namespace", "")

            # Find all select/insert/update/delete tags
            for tag in (
                root.findall(".//select")
                + root.findall(".//insert")
                + root.findall(".//update")
                + root.findall(".//delete")
            ):
                statement_id = tag.get("id", "")
                sql_key = f"{namespace}.{statement_id}" if namespace else statement_id

                # Get SQL content (handle nested elements)
                sql_content = self._extract_sql(tag)

                units.append(
                    {
                        "sqlKey": sql_key,
                        "xmlPath": str(xml_path),
                        "namespace": namespace,
                        "statementId": statement_id,
                        "sql": sql_content,
                        "statementType": tag.tag,
                    }
                )

        except Exception as e:
            raise RuntimeError(f"Failed to parse {xml_path}: {e}")

        return units

    def _extract_sql(self, element) -> str:
        """提取 SQL 内容（处理文本和子元素）"""
        parts = []

        for child in element:
            if child.text and child.text.strip():
                parts.append(child.text.strip())
            if child.tail and child.tail.strip():
                parts.append(child.tail.strip())

        return " ".join(parts)


class Parser:
    """SQL 解析器"""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}

    def parse(self, sql: str) -> dict:
        """解析 SQL 语句，返回结构化信息"""
        return {
            "raw_sql": sql,
            "type": self._detect_sql_type(sql),
            "tables": self._extract_tables(sql),
            "conditions": self._extract_conditions(sql),
            "joins": self._extract_joins(sql),
        }

    def _detect_sql_type(self, sql: str) -> str:
        """检测 SQL 类型"""
        sql_upper = sql.strip().upper()
        if sql_upper.startswith("SELECT"):
            return "SELECT"
        elif sql_upper.startswith("INSERT"):
            return "INSERT"
        elif sql_upper.startswith("UPDATE"):
            return "UPDATE"
        elif sql_upper.startswith("DELETE"):
            return "DELETE"
        return "UNKNOWN"

    def _extract_tables(self, sql: str) -> list[str]:
        """提取表名"""
        # Simple regex-based extraction
        tables = []
        pattern = r"(?:FROM|JOIN|INTO|UPDATE)\s+(\w+)"
        matches = re.findall(pattern, sql, re.IGNORECASE)
        return list(set(matches))

    def _extract_conditions(self, sql: str) -> list[dict]:
        """提取 WHERE 条件"""
        conditions = []
        where_match = re.search(
            r"WHERE\s+(.+?)(?:GROUP|ORDER|LIMIT|$)", sql, re.IGNORECASE | re.DOTALL
        )
        if where_match:
            where_clause = where_match.group(1)
            # Simple condition extraction
            for cond in re.split(
                r"\s+AND\s+|\s+OR\s+", where_clause, flags=re.IGNORECASE
            ):
                if cond.strip():
                    conditions.append({"condition": cond.strip()})
        return conditions

    def _extract_joins(self, sql: str) -> list[str]:
        """提取 JOIN"""
        joins = []
        pattern = r"(INNER|LEFT|RIGHT|OUTER)?\s*JOIN\s+(\w+)"
        matches = re.findall(pattern, sql, re.IGNORECASE)
        return [j[1] for j in matches]


# Convenience functions for backward compatibility
def scan_mappers(config: dict, root_path: str | Path) -> list[dict]:
    """扫描 mapper 文件"""
    scanner = Scanner(config)
    result = scanner.scan(root_path)
    return result.sql_units


def parse_mappers(mapper_paths: list[str | Path]) -> list[dict]:
    """解析 mapper 文件"""
    parser = Parser()
    results = []

    for path in mapper_paths:
        scanner = Scanner()
        scan_result = scanner.scan(path)
        results.extend(scan_result.sql_units)

    return results
