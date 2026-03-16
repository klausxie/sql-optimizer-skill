from __future__ import annotations

from typing import TYPE_CHECKING

from sqlopt.scripting.fragment_registry import FragmentRegistry
from sqlopt.scripting.sql_node import SqlNode
from sqlopt.scripting.xml_script_builder import XMLScriptBuilder

if TYPE_CHECKING:
    pass


class XMLLanguageDriver:
    """Language driver for MyBatis XML dynamic SQL.

    This is the entry point for parsing MyBatis XML templates into
    SqlNode trees. It provides a simplified interface for creating
    SqlSource from XML strings.
    """

    @staticmethod
    def create_sql_source(
        xml_string: str, fragments: FragmentRegistry | None = None
    ) -> SqlNode:
        """Create SqlNode from XML string.

        Args:
            xml_string: The XML string representing MyBatis dynamic SQL.
            fragments: Optional FragmentRegistry for resolving <include> tags.

        Returns:
            SqlNode tree representing the parsed XML.
        """
        builder = XMLScriptBuilder(fragment_registry=fragments)
        return builder.parse(xml_string)
