from __future__ import annotations

import xml.etree.ElementTree as ET


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def is_mybatis_mapper_root(root: ET.Element) -> bool:
    return local_name(str(root.tag)).lower() == "mapper" and bool(str(root.attrib.get("namespace") or "").strip())
