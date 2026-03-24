from __future__ import annotations

from typing import TYPE_CHECKING

from sqlopt.stages.branching.fragment_registry import FragmentRegistry
from sqlopt.stages.branching.sql_node import SqlNode
from sqlopt.stages.branching.xml_script_builder import XMLScriptBuilder

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
        xml_string: str,
        fragments: FragmentRegistry | None = None,
        default_namespace: str | None = None,
    ) -> SqlNode:
        """Create SqlNode from XML string.

        Args:
            xml_string: The XML string representing MyBatis dynamic SQL.
            fragments: Optional FragmentRegistry for resolving <include> tags.
            default_namespace: Optional namespace for resolving local include refids.

        Returns:
            SqlNode tree representing the parsed XML.
        """
        builder = XMLScriptBuilder(
            fragment_registry=fragments,
            default_namespace=default_namespace,
        )
        return builder.parse(xml_string)
