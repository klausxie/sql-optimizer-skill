"""XML patch engine using stdlib ElementTree."""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET  # noqa: S405
from typing import ClassVar, Optional

from sqlopt.contracts.optimize import OptimizationAction


class XmlPatchEngine:
    """Applies OptimizationAction[] to XML strings using stdlib ElementTree."""

    MYBATIS_NAMESPACES: ClassVar[dict[str, str]] = {
        "mybatis": "http://mybatis.org/schema/mybatis-3",
    }

    @staticmethod
    def apply_actions(actions: list[OptimizationAction], xml_string: str) -> str:
        """Apply actions to XML string, return patched XML string.

        Args:
            actions: List of OptimizationAction to apply.
            xml_string: Original XML string.

        Returns:
            Patched XML string with declaration preserved.

        Raises:
            ValueError: If xpath not found or action invalid.
        """
        if not actions:
            return xml_string

        # Parse XML preserving declaration
        tree = ET.ElementTree(ET.fromstring(xml_string))
        root = tree.getroot()

        # Extract namespaces from root element
        namespaces = XmlPatchEngine._extract_namespaces(root)

        for action in actions:
            if action.operation == "REPLACE":
                XmlPatchEngine._apply_replace(tree, action, namespaces)
            elif action.operation == "ADD":
                XmlPatchEngine._apply_add(tree, action, namespaces)
            elif action.operation == "REMOVE":
                XmlPatchEngine._apply_remove(tree, action, namespaces)
            elif action.operation == "WRAP":
                XmlPatchEngine._apply_wrap(tree, action, namespaces)
            else:
                raise ValueError(f"Unknown operation: {action.operation}")

        # Serialize back to string with declaration
        return XmlPatchEngine._element_to_string(tree, xml_string)

    @staticmethod
    def _extract_namespaces(root: ET.Element) -> dict[str, str]:
        """Extract namespace map from root element."""
        namespaces: dict[str, str] = {}
        # Check root element's tag for namespace
        if root.tag.startswith("{"):
            ns_end = root.tag.index("}")
            if ns_end > 0:
                namespaces[""] = root.tag[1:ns_end]
        for key, value in root.attrib.items():
            if key == "xmlns":
                namespaces[""] = value
            elif key.startswith("xmlns:"):
                prefix = key[6:]
                namespaces[prefix] = value
        return namespaces

    @staticmethod
    def _apply_replace(tree: ET.ElementTree, action: OptimizationAction, namespaces: dict[str, str]) -> None:
        """Apply REPLACE operation.

        REPLACE: Replace the text content of the element at xpath with rewritten_snippet.
        """
        element = XmlPatchEngine._find_element(tree.getroot(), action.xpath, namespaces)
        if element is None:
            raise ValueError(f"Element not found for xpath: {action.xpath}")

        if action.rewritten_snippet is not None:
            element.text = action.rewritten_snippet

    @staticmethod
    def _apply_add(tree: ET.ElementTree, action: OptimizationAction, namespaces: dict[str, str]) -> None:
        """Apply ADD operation.

        ADD: Insert a new sibling element after the element at xpath.
        The new element is created from rewritten_snippet.
        """
        element = XmlPatchEngine._find_element(tree.getroot(), action.xpath, namespaces)
        if element is None:
            raise ValueError(f"Element not found for xpath: {action.xpath}")

        if action.rewritten_snippet is None:
            raise ValueError(f"rewritten_snippet required for ADD operation: {action.action_id}")

        # Parse the new element from snippet
        new_element = ET.fromstring(action.rewritten_snippet)

        # Find parent and insert as sibling
        parent = XmlPatchEngine._find_parent(tree.getroot(), element, namespaces)
        if parent is not None:
            # Insert after the element
            index = list(parent).index(element)
            parent.insert(index + 1, new_element)
        else:
            # element is root, can't add sibling
            raise ValueError(f"Cannot add sibling to root element: {action.xpath}")

    @staticmethod
    def _apply_remove(tree: ET.ElementTree, action: OptimizationAction, namespaces: dict[str, str]) -> None:
        """Apply REMOVE operation.

        REMOVE: Delete the element at xpath.
        """
        element = XmlPatchEngine._find_element(tree.getroot(), action.xpath, namespaces)
        if element is None:
            raise ValueError(f"Element not found for xpath: {action.xpath}")

        parent = XmlPatchEngine._find_parent(tree.getroot(), element, namespaces)
        if parent is not None:
            parent.remove(element)
        else:
            # element is root, can't remove
            raise ValueError(f"Cannot remove root element: {action.xpath}")

    @staticmethod
    def _apply_wrap(tree: ET.ElementTree, action: OptimizationAction, namespaces: dict[str, str]) -> None:
        """Apply WRAP operation.

        WRAP: Surround element at xpath with a new parent element from rewritten_snippet.
        """
        element = XmlPatchEngine._find_element(tree.getroot(), action.xpath, namespaces)
        if element is None:
            raise ValueError(f"Element not found for xpath: {action.xpath}")

        if action.rewritten_snippet is None:
            raise ValueError(f"rewritten_snippet required for WRAP operation: {action.action_id}")

        # Parse the wrapper element
        wrapper = ET.fromstring(action.rewritten_snippet)

        # Find parent
        parent = XmlPatchEngine._find_parent(tree.getroot(), element, namespaces)
        if parent is not None:
            # Replace element with wrapper, make element child of wrapper
            index = list(parent).index(element)
            parent.remove(element)
            wrapper.append(element)
            parent.insert(index, wrapper)
        else:
            # element is root - replace root with wrapper
            tree._setroot(wrapper)  # noqa: SLF001
            wrapper.append(element)

    @staticmethod
    def _find_element(root: ET.Element, xpath: str, namespaces: dict[str, str]) -> Optional[ET.Element]:
        """Find element by xpath, handling namespace prefixes."""
        # Try with namespace registered
        if namespaces:
            try:
                # Register namespaces for xpath query
                for prefix, uri in namespaces.items():
                    if prefix:
                        ET.register_namespace(prefix, uri)
                return root.find(xpath, namespaces)
            except SyntaxError:
                # Fallback to manual search
                pass

        # Manual search without namespaces
        return XmlPatchEngine._find_element_manual(root, xpath)

    @staticmethod
    def _local_name(tag: str) -> str:
        """Extract local name from Clark notation {namespace}tag."""
        if tag.startswith("{"):
            return tag.split("}", 1)[1]
        return tag

    @staticmethod
    def _find_element_manual(element: ET.Element, xpath: str) -> Optional[ET.Element]:
        """Manually find element by xpath without namespace support."""
        parts = xpath.strip("/").split("/")
        current = element
        first = True
        for part in parts:
            if not part or part == ".":
                continue
            if part == "..":
                continue

            # If xpath starts with root tag matching current element, skip it
            if first and XmlPatchEngine._local_name(current.tag) == part:
                first = False
                continue
            first = False

            attr_match: Optional[tuple[str, str]] = None
            tag_part = part
            if "[" in part and "]" in part:
                tag_part = part[: part.index("[")]
                attr_expr = part[part.index("[") + 1 : part.index("]")]
                if "@" in attr_expr:
                    attr_name = attr_expr.split("@")[1].split("=")[0].strip()
                    attr_value = attr_expr.split("=")[1].strip("'\"")
                    attr_match = (attr_name, attr_value)

            found: Optional[ET.Element] = None
            for child in current:
                child_local = XmlPatchEngine._local_name(child.tag)
                if child_local == tag_part or child.tag == tag_part:
                    if attr_match:
                        if child.get(attr_match[0]) == attr_match[1]:
                            found = child
                            break
                    else:
                        found = child
                        break

            if found is None:
                return None
            current = found
        return current

    @staticmethod
    def _find_parent(root: ET.Element, target: ET.Element, _namespaces: dict[str, str]) -> Optional[ET.Element]:
        """Find parent of target element."""
        return XmlPatchEngine._find_parent_manual(root, target)

    @staticmethod
    def _find_parent_manual(element: ET.Element, target: ET.Element) -> Optional[ET.Element]:
        """Manually find parent of target element."""
        for child in element:
            if child is target:
                return element
            parent = XmlPatchEngine._find_parent_manual(child, target)
            if parent is not None:
                return parent
        return None

    @staticmethod
    def _element_to_string(tree: ET.ElementTree, original_xml: str) -> str:
        """Convert ElementTree back to XML string with declaration preserved."""
        has_declaration = original_xml.strip().startswith("<?xml")
        buffer = io.BytesIO()
        tree.write(buffer, encoding="utf-8", xml_declaration=True)
        result = buffer.getvalue().decode("utf-8")
        if not has_declaration and result.startswith("<?xml"):
            end_idx = result.index("?>") + 2
            result = result[end_idx:].lstrip()
        return result
