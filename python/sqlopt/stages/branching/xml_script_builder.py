"""XMLScriptBuilder for parsing MyBatis XML to SqlNode tree.

This module provides the XMLScriptBuilder class, mirroring the MyBatis
org.apache.ibatis.scripting.xmltags.XMLScriptBuilder to parse XML
templates into SqlNode trees for dynamic SQL processing.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

from sqlopt.stages.branching.sql_node import (
    ChooseSqlNode,
    ForEachSqlNode,
    IfSqlNode,
    IncludeSqlNode,
    MixedSqlNode,
    OtherwiseSqlNode,
    SetSqlNode,
    SqlNode,
    StaticTextSqlNode,
    TextSqlNode,
    TrimSqlNode,
    VarDeclSqlNode,
    WhenSqlNode,
    WhereSqlNode,
)

if TYPE_CHECKING:
    from sqlopt.stages.branching.fragment_registry import FragmentRegistry


class XMLScriptBuilder:
    """Builder for parsing MyBatis XML templates into SqlNode trees.

    This class mirrors the MyBatis XMLScriptBuilder which parses XML
    elements and constructs a tree of SqlNode instances representing
    dynamic SQL templates.

    The parser handles:
    - Static text content
    - ${} placeholder text
    - Dynamic tags: if, choose/when/otherwise, where, set, trim, foreach, include, bind

    Attributes:
        fragment_registry: Registry for SQL fragments (for <include> resolution).
    """

    # Node handler strategy mapping: tag_name -> handler_method_name
    NODE_HANDLER_MAP: dict[str, str] = {
        "if": "_handle_if_node",
        "choose": "_handle_choose_node",
        "when": "_handle_when_node",
        "otherwise": "_handle_otherwise_node",
        "where": "_handle_where_node",
        "set": "_handle_set_node",
        "trim": "_handle_trim_node",
        "foreach": "_handle_foreach_node",
        "include": "_handle_include_node",
        "bind": "_handle_bind_node",
    }

    # Pattern to detect ${...} placeholders in text
    _PLACEHOLDER_PATTERN: re.Pattern[str] = re.compile(r"\$\{[^}]+\}")

    def __init__(
        self,
        fragment_registry: FragmentRegistry | None = None,
        default_namespace: str | None = None,
    ) -> None:
        """Initialize XMLScriptBuilder with optional fragment registry.

        Args:
            fragment_registry: Optional registry for resolving <include> fragments.
        """
        self.fragment_registry = fragment_registry
        self.default_namespace = (
            str(default_namespace).strip() if default_namespace else None
        )

    def parse(self, xml_string: str) -> SqlNode:
        """Parse XML string into SqlNode tree.

        Args:
            xml_string: The XML string to parse.

        Returns:
            SqlNode tree representing the parsed XML.

        Raises:
            xml.etree.ElementTree.ParseError: If XML is malformed.
        """
        # Wrap in root element if needed
        wrapped_xml = f"<root>{xml_string}</root>"
        root = ET.fromstring(wrapped_xml)

        # Parse all children of the root
        contents = self._parse_children(root)

        # Return MixedSqlNode containing all parsed nodes
        return MixedSqlNode(contents)

    def parse_dynamic_tags(self, element: ET.Element) -> SqlNode:
        """Parse an XML element into a SqlNode.

        This method dispatches to specific parsing methods based on the
        element's tag name using the strategy mapping.

        Args:
            element: The XML element to parse.

        Returns:
            SqlNode representing the element.
        """
        tag = element.tag

        # Dispatch based on strategy mapping
        handler_name = self.NODE_HANDLER_MAP.get(tag)
        if handler_name:
            handler = getattr(self, handler_name)
            return handler(element)

        # Unknown tag, parse as mixed content
        contents = self._parse_children(element)
        return MixedSqlNode(contents)

    def _parse_children(self, element: ET.Element) -> list[SqlNode]:
        """Parse all children of an element (text nodes and sub-elements).

        Args:
            element: The parent XML element.

        Returns:
            List of SqlNode instances representing children.
        """
        contents: list[SqlNode] = []

        # Handle leading text (text before first child element)
        if element.text and element.text.strip():
            text_node = self._create_text_node(element.text)
            if text_node:
                contents.append(text_node)

        # Process child elements
        for child in element:
            # Parse child element
            child_node = self.parse_dynamic_tags(child)
            contents.append(child_node)

            # Handle trailing text (tail after child element)
            if child.tail and child.tail.strip():
                tail_node = self._create_text_node(child.tail)
                if tail_node:
                    contents.append(tail_node)

        return contents

    def _create_text_node(self, text: str) -> SqlNode | None:
        """Create appropriate text node based on content.

        Creates TextSqlNode if text contains ${...} placeholders,
        otherwise creates StaticTextSqlNode.

        Args:
            text: The text content.

        Returns:
            SqlNode for the text, or None if text is empty/whitespace only.
        """
        # Preserve token boundaries between sibling fragments. Fully stripping here
        # can collapse "... 1=1" and "AND ..." into "1=1AND ...".
        if not text or not text.strip():
            return None

        text = re.sub(r"\s+", " ", text)

        # Check for ${...} placeholders
        if self._PLACEHOLDER_PATTERN.search(text):
            return TextSqlNode(text)
        else:
            return StaticTextSqlNode(text)

    def _handle_if_node(self, element: ET.Element) -> SqlNode:
        """Parse <if test="..."> element.

        Args:
            element: The <if> XML element.

        Returns:
            IfSqlNode representing the conditional.
        """
        test = element.get("test", "")
        contents = self._parse_children(element)
        return IfSqlNode(test, MixedSqlNode(contents))

    def _handle_choose_node(self, element: ET.Element) -> SqlNode:
        """Parse <choose> element with <when> and <otherwise> children.

        Args:
            element: The <choose> XML element.

        Returns:
            ChooseSqlNode representing the choice.
        """
        when_nodes: list[WhenSqlNode] = []
        otherwise_node: OtherwiseSqlNode | None = None

        for child in element:
            if child.tag == "when":
                when_node = self._handle_when_node(child)
                when_nodes.append(when_node)
            elif child.tag == "otherwise":
                otherwise_node = self._handle_otherwise_node(child)

        return ChooseSqlNode(when_nodes, otherwise_node)

    def _handle_when_node(self, element: ET.Element) -> WhenSqlNode:
        """Parse <when test="..."> element.

        Args:
            element: The <when> XML element.

        Returns:
            WhenSqlNode representing the branch.
        """
        test = element.get("test", "")
        contents = self._parse_children(element)
        return WhenSqlNode(test, MixedSqlNode(contents))

    def _handle_otherwise_node(self, element: ET.Element) -> OtherwiseSqlNode:
        """Parse <otherwise> element.

        Args:
            element: The <otherwise> XML element.

        Returns:
            OtherwiseSqlNode representing the default branch.
        """
        contents = self._parse_children(element)
        return OtherwiseSqlNode(MixedSqlNode(contents))

    def _handle_where_node(self, element: ET.Element) -> SqlNode:
        """Parse <where> element.

        Args:
            element: The <where> XML element.

        Returns:
            WhereSqlNode representing the WHERE clause.
        """
        contents = self._parse_children(element)
        return WhereSqlNode(MixedSqlNode(contents))

    def _handle_set_node(self, element: ET.Element) -> SqlNode:
        """Parse <set> element.

        Args:
            element: The <set> XML element.

        Returns:
            SetSqlNode representing the SET clause.
        """
        contents = self._parse_children(element)
        return SetSqlNode(MixedSqlNode(contents))

    def _handle_trim_node(self, element: ET.Element) -> SqlNode:
        """Parse <trim> element with prefix/suffix attributes.

        Args:
            element: The <trim> XML element.

        Returns:
            TrimSqlNode representing the trim operation.
        """
        prefix = element.get("prefix", "")
        suffix = element.get("suffix", "")
        prefixOverrides = element.get("prefixOverrides", "")
        suffixOverrides = element.get("suffixOverrides", "")

        # Parse override lists (pipe-separated)
        # Note: preserve values as-is, including spaces (MyBatis behavior)
        prefix_overrides_list = [s for s in prefixOverrides.split("|") if s]
        suffix_overrides_list = [s for s in suffixOverrides.split("|") if s]

        contents = self._parse_children(element)
        return TrimSqlNode(
            MixedSqlNode(contents),
            prefix=prefix,
            suffix=suffix,
            prefix_overrides=prefix_overrides_list,
            suffix_overrides=suffix_overrides_list,
        )

    def _handle_foreach_node(self, element: ET.Element) -> SqlNode:
        """Parse <foreach> element for collection iteration.

        Args:
            element: The <foreach> XML element.

        Returns:
            ForEachSqlNode representing the iteration.
        """
        collection = element.get("collection", "")
        item = element.get("item", "")
        index = element.get("index", "")
        open_str = element.get("open", "")
        close_str = element.get("close", "")
        separator = element.get("separator", "")

        contents = self._parse_children(element)
        return ForEachSqlNode(
            collection=collection,
            item=item,
            index=index,
            open=open_str,
            close=close_str,
            separator=separator,
            contents=MixedSqlNode(contents) if contents else None,
        )

    def _handle_include_node(self, element: ET.Element) -> SqlNode:
        """Parse <include refid="..."> element.

        Args:
            element: The <include> XML element.

        Returns:
            IncludeSqlNode referencing the fragment.
        """
        refid = element.get("refid", "")
        if self.default_namespace and refid and "." not in refid:
            refid = f"{self.default_namespace}.{refid}"
        return IncludeSqlNode(refid, self.fragment_registry)

    def _handle_bind_node(self, element: ET.Element) -> SqlNode:
        """Parse <bind name="..." value="..."/> element.

        Args:
            element: The <bind> XML element.

        Returns:
            VarDeclSqlNode representing the variable declaration.
        """
        name = element.get("name", "")
        value = element.get("value", "")
        return VarDeclSqlNode(name, value)
