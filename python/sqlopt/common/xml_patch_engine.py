"""XML patch engine using stdlib ElementTree."""

from __future__ import annotations

import io
import re
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
    def apply_text_replacement(actions: list[OptimizationAction], original_file_content: str) -> str:
        """Apply text replacement directly on original file content.

        This avoids ET serialization issues by doing string replacement
        of SQL snippets in the original file content.

        Args:
            actions: List of OptimizationAction to apply.
            original_file_content: Original full mapper XML file content.

        Returns:
            Modified file content with SQL text replaced.
        """
        if not actions:
            return original_file_content

        result = original_file_content
        for action in actions:
            if action.operation == "REPLACE" and action.rewritten_snippet:
                if action.original_snippet:
                    result = result.replace(action.original_snippet, action.rewritten_snippet)
                elif action.sql_fragment:
                    result = result.replace(action.sql_fragment, action.rewritten_snippet)
            elif action.operation == "ADD" and action.rewritten_snippet:
                # ADD: replace entire element identified by xpath with rewritten_snippet.
                # When original_snippet is null, use the element id from rewritten_snippet.
                replacement = XmlPatchEngine._replace_element_by_snippet(result, action, "ADD")
                if replacement is not None:
                    result = replacement
            elif action.operation == "REMOVE" and action.original_snippet:
                result = result.replace(action.original_snippet, "")
            elif action.operation == "WRAP" and action.rewritten_snippet:
                if action.original_snippet:
                    result = result.replace(action.original_snippet, action.rewritten_snippet)
                else:
                    replacement = XmlPatchEngine._replace_element_by_snippet(result, action, "WRAP")
                    if replacement is not None:
                        result = replacement

        return result

    @staticmethod
    def _replace_element_by_snippet(content: str, action: OptimizationAction, operation: str) -> str | None:
        """Replace entire XML element using rewritten_snippet.

        Used when ADD/WRAP operation has no original_snippet - the complete
        replacement element is provided in rewritten_snippet.

        Locates the target element by matching the opening tag pattern
        (extracted from rewritten_snippet) within content.

        Args:
            content: Current XML content.
            action: The ADD or WRAP action.
            operation: "ADD" or "WRAP".

        Returns:
            Modified content, or None if element not found.
        """
        if not action.rewritten_snippet:
            return None

        snippet = action.rewritten_snippet.strip()

        tag_match = re.match(r"<([a-zA-Z0-9_:-]+)", snippet)
        if not tag_match:
            return None
        tag_name = tag_match.group(1)

        id_match = re.search(r'\bid\s*=\s*["\']([^"\']+)["\']', snippet)
        if id_match:
            element_id = id_match.group(1)
            search_pattern = rf'<{tag_name}\s[^>]*\bid\s*=\s*["\']({re.escape(element_id)})["\']'
        else:
            search_pattern = rf"<{tag_name}(?:\s[^>]*)?>"

        start_idx = -1
        for match in re.finditer(search_pattern, content):
            start_idx = match.start()
            break

        if start_idx == -1:
            return None

        end_idx = content.find(f"</{tag_name}>", start_idx)
        if end_idx == -1:
            return None
        end_idx += len(f"</{tag_name}>")

        return content[:start_idx] + snippet + content[end_idx:]

    @staticmethod
    def _get_element_indices(content: str, element: ET.Element, namespaces: dict[str, str]) -> tuple[int, int]:
        """Get start and end character indices of an element in the source string.

        Uses element tail and iterators to approximate positions since ET
        loses source location info.
        """
        tag = element.tag if "}" not in element.tag else element.tag.split("}", 1)[1]
        qname = f"{{{namespaces.get('', '')}}}{tag}" if namespaces.get("") else tag

        start = content.find(f"<{qname}")
        if start == -1:
            start = content.find(f"<{tag}")

        if start == -1:
            return 0, 0

        end_pattern = f"</{qname}>"
        end = content.find(end_pattern, start)
        if end == -1:
            end_pattern = f"</{tag}>"
            end = content.find(end_pattern, start)

        if end == -1:
            return start, start + len(content)

        return start, end + len(end_pattern)

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

            attr_match: Optional[tuple[str, str]] = None
            tag_part = part
            if "[" in part and "]" in part:
                tag_part = part[: part.index("[")]
                attr_expr = part[part.index("[") + 1 : part.index("]")]
                if "@" in attr_expr:
                    attr_name = attr_expr.split("@")[1].split("=")[0].strip()
                    attr_value = attr_expr.split("=")[1].strip("'\"")
                    attr_match = (attr_name, attr_value)

            # If xpath starts with root tag matching current element, check match
            if first and XmlPatchEngine._local_name(current.tag) == tag_part:
                first = False
                # Check attribute condition on current element
                if attr_match is None or current.get(attr_match[0]) == attr_match[1]:
                    # XPath fully matched current element (no children to traverse)
                    if not attr_match:
                        # No attr condition or matched - check if there are more parts
                        if len([p for p in parts if p and p != "."]) == 1:
                            return current
                    else:
                        return current
                # Tag matched but attr didn't match
                if attr_match and current.get(attr_match[0]) != attr_match[1]:
                    return None
                continue
            first = False

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
