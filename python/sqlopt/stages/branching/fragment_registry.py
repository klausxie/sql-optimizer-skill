class FragmentRegistry:
    def __init__(self):
        self._fragments = {}

    def register(self, refid: str, fragment):
        self._fragments[refid] = fragment

    def lookup(self, refid: str):
        return self._fragments.get(refid)

    def has(self, refid: str) -> bool:
        return refid in self._fragments


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _inner_xml(node) -> str:
    import xml.etree.ElementTree as ET

    parts = []
    if node.text:
        parts.append(node.text)
    for child in list(node):
        parts.append(ET.tostring(child, encoding="unicode"))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts).strip()


def build_fragment_registry(xml_files):
    """Build a fragment registry from mapper XML files."""
    import xml.etree.ElementTree as ET
    from pathlib import Path

    from sqlopt.stages.branching.xml_script_builder import XMLScriptBuilder

    registry = FragmentRegistry()

    for xml_file in sorted({str(Path(path)) for path in xml_files}):
        path = Path(xml_file)
        if not path.exists() or not path.is_file():
            continue

        try:
            root = ET.parse(path).getroot()
        except Exception:
            continue

        namespace = str(root.attrib.get("namespace") or "").strip()
        builder = XMLScriptBuilder(
            fragment_registry=registry,
            default_namespace=namespace or None,
        )

        for node in root.iter():
            if _local_name(str(node.tag)).lower() != "sql":
                continue

            fragment_id = str(node.attrib.get("id") or "").strip()
            if not fragment_id:
                continue

            qualified_ref = f"{namespace}.{fragment_id}" if namespace else fragment_id
            registry.register(qualified_ref, builder.parse(_inner_xml(node)))

    return registry
