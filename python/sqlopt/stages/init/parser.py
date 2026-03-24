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


class ParsedFragment:
    """Represents a <sql id=""> fragment extracted from a mapper file."""

    fragment_id: str
    xml_path: str
    start_line: int
    end_line: int
    xml_content: str
    xpath: str

    def __init__(
        self,
        fragment_id: str,
        xml_path: str,
        start_line: int,
        end_line: int,
        xml_content: str,
        xpath: str,
    ) -> None:
        self.fragment_id = fragment_id
        self.xml_path = xml_path
        self.start_line = start_line
        self.end_line = end_line
        self.xml_content = xml_content
        self.xpath = xpath


def _replace_cdata(raw_text: str) -> str:
    cdata_regex = r"(<!\[CDATA\[)([\s\S]*?)(\]\]>)"
    pattern = re.compile(cdata_regex)

    def escape_cdata(match: re.Match) -> str:
        content = str(match.group(2)).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return content

    return pattern.sub(escape_cdata, raw_text)


def _get_line_numbers(text: str, start_pos: int, end_pos: int) -> tuple[int, int]:
    """Compute start and end line numbers (1-indexed) from character positions."""
    start_line = text[:start_pos].count("\n") + 1
    end_line = text[:end_pos].count("\n") + 1
    return start_line, end_line


def _build_xpath(elem: ET.Element, root_tag: str = "mapper") -> str:
    """Build XPath for an element using format: /mapper/tag[@id='xxx']."""
    tag = elem.tag
    elem_id = elem.get("id", "")
    if elem_id:
        return f"/{root_tag}/{tag}[@id='{elem_id}']"
    return f"/{root_tag}/{tag}"


def _find_sql_tag_positions(raw_text: str) -> dict[str, dict]:
    """Find positions of <sql> tags in raw text for line number tracking."""
    positions = {}
    pattern = re.compile(r"<sql\s[^>]*id=[\"']([^\"']+)[\"'][^>]*>")
    for match in pattern.finditer(raw_text):
        fragment_id = match.group(1)
        start_pos = match.start()
        end_pos = match.end()
        start_line = raw_text[:start_pos].count("\n") + 1
        end_line = raw_text[:end_pos].count("\n") + 1
        positions[fragment_id] = {
            "start_pos": start_pos,
            "end_pos": end_pos,
            "start_line": start_line,
            "end_line": end_line,
        }
    return positions


def parse_mapper_file(xml_path: Path) -> tuple[list[ParsedStatement], list[ParsedFragment]]:
    statements: list[ParsedStatement] = []
    fragments: list[ParsedFragment] = []
    try:
        raw_text = Path(xml_path).read_text(encoding="utf-8")
        clean_text = _replace_cdata(raw_text)
        root = ET.fromstring(clean_text)
    except (ET.ParseError, OSError):
        return statements, fragments

    namespace = root.get("namespace", "")
    root_tag = root.tag

    sql_positions = _find_sql_tag_positions(raw_text)

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

    for elem in root.findall("sql"):
        fragment_id = elem.get("id", "")
        if not fragment_id:
            continue

        xpath = _build_xpath(elem, root_tag)
        pos_info = sql_positions.get(fragment_id, {})
        start_line = pos_info.get("start_line", 0)
        end_line = pos_info.get("end_line", 0)
        xml_content = ET.tostring(elem, encoding="unicode")

        frag = ParsedFragment(
            fragment_id=fragment_id,
            xml_path=str(xml_path),
            start_line=start_line,
            end_line=end_line,
            xml_content=xml_content,
            xpath=xpath,
        )
        fragments.append(frag)

    return statements, fragments


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
