from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

DYNAMIC_TAGS = {"if", "where", "choose", "when", "otherwise", "foreach", "set", "trim"}


class ParsedStatement:
    sql_key: str
    namespace: str
    statement_id: str
    statement_type: str
    xml_path: str
    xml_content: str
    parameter_mappings: list[dict]
    dynamic_features: list[str]

    def __init__(
        self,
        sql_key: str,
        namespace: str,
        statement_id: str,
        statement_type: str,
        xml_path: str,
        xml_content: str,
        parameter_mappings: list[dict],
        dynamic_features: list[str],
    ) -> None:
        self.sql_key = sql_key
        self.namespace = namespace
        self.statement_id = statement_id
        self.statement_type = statement_type
        self.xml_path = xml_path
        self.xml_content = xml_content
        self.parameter_mappings = parameter_mappings
        self.dynamic_features = dynamic_features


def _replace_cdata(raw_text: str) -> str:
    cdata_regex = r"(<!\[CDATA\[)([\s\S]*?)(\]\]>)"
    pattern = re.compile(cdata_regex)

    def escape_cdata(match: re.Match) -> str:
        content = (
            str(match.group(2)).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        return content

    return pattern.sub(escape_cdata, raw_text)


def parse_mapper_file(xml_path: Path) -> list[ParsedStatement]:
    statements: list[ParsedStatement] = []
    try:
        raw_text = Path(xml_path).read_text(encoding="utf-8")
        clean_text = _replace_cdata(raw_text)
        root = ET.fromstring(clean_text)
    except (ET.ParseError, OSError):
        return statements

    namespace = root.get("namespace", "")

    for tag_name in ["select", "insert", "update", "delete"]:
        for elem in root.findall(tag_name):
            statement_id = elem.get("id", "")
            if not statement_id:
                continue

            sql_key = f"{namespace}.{statement_id}" if namespace else statement_id

            xml_content = ET.tostring(elem, encoding="unicode")

            param_mappings = extract_parameter_mappings(elem)

            dyn_features = detect_dynamic_features(elem)

            stmt = ParsedStatement(
                sql_key=sql_key,
                namespace=namespace,
                statement_id=statement_id,
                statement_type=tag_name.upper(),
                xml_path=str(xml_path),
                xml_content=xml_content,
                parameter_mappings=param_mappings,
                dynamic_features=dyn_features,
            )
            statements.append(stmt)

    return statements


def extract_parameter_mappings(elem: ET.Element) -> list[dict]:
    mappings = []
    param_pattern = re.compile(r"#\{([^}:]+)(?::([^}]+))?}")

    for match in param_pattern.finditer(ET.tostring(elem, encoding="unicode")):
        param_name = match.group(1)
        jdbc_type = match.group(2) or "VARCHAR"
        mappings.append({"name": param_name, "jdbcType": jdbc_type})

    seen = set()
    unique_mappings = []
    for m in mappings:
        if m["name"] not in seen:
            seen.add(m["name"])
            unique_mappings.append(m)

    return unique_mappings


def detect_dynamic_features(elem: ET.Element) -> list[str]:
    features = []
    found_tags = set()

    def scan(e: ET.Element) -> None:
        tag = e.tag.lower() if isinstance(e.tag, str) else ""
        if tag in DYNAMIC_TAGS and tag not in found_tags:
            found_tags.add(tag)
            features.append(tag.upper())
        for child in e:
            scan(child)

    scan(elem)
    return sorted(features)
