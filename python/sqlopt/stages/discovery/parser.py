"""
Discovery Stage - XML Parser

Parses MyBatis XML mappers into structured data.
"""

from pathlib import Path
from typing import Optional
import xml.etree.ElementTree as ET


class XmlParser:
    """MyBatis XML 解析器"""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}

    def parse_file(self, xml_path: str | Path) -> dict:
        """解析单个 XML 文件"""
        path = Path(xml_path)

        try:
            tree = ET.parse(path)
            root = tree.getroot()
        except ET.ParseError as e:
            raise ValueError(f"XML parse error in {path}: {e}")

        namespace = root.get("namespace", "")
        statements = []

        for tag in root:
            if tag.tag in ("select", "insert", "update", "delete"):
                statement = self._parse_statement(tag, namespace, path)
                statements.append(statement)

        return {
            "path": str(path),
            "namespace": namespace,
            "statements": statements,
        }

    def _parse_statement(self, element, namespace: str, xml_path: Path) -> dict:
        """解析单个 SQL 语句"""
        statement_id = element.get("id", "")
        result_type = element.get("resultType", element.get("resultMap", ""))

        # Extract SQL content
        sql_parts = []
        for child in element:
            if child.text:
                sql_parts.append(child.text.strip())
            if child.tail:
                sql_parts.append(child.tail.strip())

        sql = " ".join(sql_parts)

        # Extract parameter type
        param_type = element.get("parameterType", "")

        return {
            "id": statement_id,
            "type": element.tag,
            "sql": sql,
            "parameterType": param_type,
            "resultType": result_type,
            "sqlKey": f"{namespace}.{statement_id}" if namespace else statement_id,
        }

    def parse_directory(
        self, directory: str | Path, pattern: str = "**/*.xml"
    ) -> list[dict]:
        """解析目录下所有 XML 文件"""
        dir_path = Path(directory)
        results = []

        for xml_file in dir_path.glob(pattern):
            if xml_file.is_file():
                try:
                    result = self.parse_file(xml_file)
                    results.append(result)
                except Exception as e:
                    results.append(
                        {
                            "path": str(xml_file),
                            "error": str(e),
                        }
                    )

        return results


def parse_mappers(mapper_paths: list[str | Path]) -> list[dict]:
    """便捷函数：解析多个 mapper 文件"""
    parser = XmlParser()
    results = []

    for path in mapper_paths:
        result = parser.parse_file(path)
        results.append(result)

    return results
