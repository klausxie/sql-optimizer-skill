"""V8 XML patch generator for MyBatis SQL optimization."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PatchResult:
    """Result of a patch generation operation."""

    sql_key: str
    original_sql: str
    patched_sql: str
    xml_fragment: str
    backup_needed: bool


class PatchGenerator:
    """Generates MyBatis XML patches for optimized SQL statements."""

    def generate_patch(self, sql_unit: dict, proposal: dict) -> str:
        """
        Generate XML fragment for an optimized SQL statement.

        Args:
            sql_unit: SQL unit containing namespace and statementId
            proposal: Optimization proposal with patched SQL

        Returns:
            XML fragment string
        """
        namespace = sql_unit.get("namespace", "unknown")
        statement_id = sql_unit.get("statementId", "unknown")
        original_sql = sql_unit.get("sql", "")
        patched_sql = proposal.get("patched_sql", proposal.get("sql", ""))
        result_type = sql_unit.get("resultType", "map")

        xml_content = f"""<!-- Original: {namespace}.{statement_id} -->
<select id="{statement_id}" resultType="{result_type}">
  <!-- Patched SQL -->
  {patched_sql}
</select>"""

        return xml_content

    def format_patch(self, xml_content: str) -> str:
        """
        Format XML content with proper indentation.

        Args:
            xml_content: Raw XML content

        Returns:
            Formatted XML string
        """
        lines = xml_content.split("\n")
        formatted_lines = []
        indent_level = 0

        for line in lines:
            stripped = line.strip()
            if not stripped:
                formatted_lines.append("")
                continue

            if stripped.startswith("</"):
                indent_level = max(0, indent_level - 1)

            formatted_lines.append("  " * indent_level + stripped)

            if (
                stripped.startswith("<")
                and not stripped.startswith("</")
                and not stripped.endswith("/>")
                and not stripped.startswith("<!--")
            ):
                if (
                    "</select>" not in stripped
                    and "</update>" not in stripped
                    and "</insert>" not in stripped
                    and "</delete>" not in stripped
                ):
                    indent_level += 1

        return "\n".join(formatted_lines)

    def create_patch_result(
        self,
        sql_unit: dict,
        proposal: dict,
        backup_needed: bool = True,
    ) -> PatchResult:
        """
        Create a complete patch result.

        Args:
            sql_unit: SQL unit dictionary
            proposal: Optimization proposal dictionary
            backup_needed: Whether backup is needed

        Returns:
            PatchResult instance
        """
        namespace = sql_unit.get("namespace", "unknown")
        statement_id = sql_unit.get("statementId", "unknown")
        original_sql = sql_unit.get("sql", "")
        patched_sql = proposal.get("patched_sql", proposal.get("sql", ""))

        xml_fragment = self.generate_patch(sql_unit, proposal)
        formatted_fragment = self.format_patch(xml_fragment)

        return PatchResult(
            sql_key=f"{namespace}.{statement_id}",
            original_sql=original_sql,
            patched_sql=patched_sql,
            xml_fragment=formatted_fragment,
            backup_needed=backup_needed,
        )
