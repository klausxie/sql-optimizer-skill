"""Branch Generator Adapter for V9 Parse Stage.

Wraps the full branching module (stages/branching) to provide a simplified
interface that works with SQL unit dicts.

The adapter:
1. Parses templateSql into SqlNode using XMLScriptBuilder
2. Uses FragmentRegistry for cross-file include resolution
3. Generates branches using full BranchGenerator with proper SqlNode semantics
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from ..stages.branching import (
    BranchGenerator as FullBranchGenerator,
    FragmentRegistry,
    XMLScriptBuilder,
)


class BranchGenerator:
    """Adapter wrapping the full branching module for V9.

    This class provides the same interface as the original simplified
    BranchGenerator, Internally it uses the full BranchGenerator
    from stages/branching for proper SqlNode-based branch generation.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        fragment_registry: Optional[FragmentRegistry] = None,
    ):
        self.config = config or {}
        branch_cfg = self.config.get("branch", {})
        self.max_branches = branch_cfg.get("max_branches", 100)
        self.strategy = branch_cfg.get("strategy", "all_combinations")
        self._fragment_registry = fragment_registry

    def generate(self, sql_unit: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate branches from a SQL unit.

        Args:
            sql_unit: SQL unit dict with templateSql and sql fields.

        Returns:
            List of branch dicts with id, conditions, sql, type fields.
        """
        template_sql = sql_unit.get("templateSql", "")
        sql = sql_unit.get("sql", "")

        if not template_sql:
            return [
                {
                    "id": 1,
                    "conditions": [],
                    "sql": sql.strip() if sql else "",
                    "type": "static",
                }
            ]

        sql_node = self._parse_template(template_sql)
        if sql_node is None:
            return [
                {
                    "id": 1,
                    "conditions": [],
                    "sql": sql.strip() if sql else "",
                    "type": "static",
                }
            ]

        generator = FullBranchGenerator(
            strategy=self.strategy,
            max_branches=self.max_branches,
        )
        branches = generator.generate(sql_node)

        return [
            {
                "id": branch.get("branch_id", idx),
                "conditions": branch.get("active_conditions", []),
                "sql": branch.get("sql", ""),
                "type": "dynamic" if branch.get("active_conditions") else "static",
                "riskFlags": branch.get("risk_flags", []),
            }
            for idx, branch in enumerate(branches)
        ]

    def _parse_template(self, template_sql: str):
        """Parse template SQL into a SqlNode tree."""
        builder = XMLScriptBuilder(
            fragment_registry=self._fragment_registry,
            default_namespace=None,
        )
        try:
            return builder.parse(template_sql)
        except Exception:
            return None


def generate_branches(
    sql_unit: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
    fragment_registry: Optional[FragmentRegistry] = None,
) -> List[Dict[str, Any]]:
    """Entry point for branch generation."""
    generator = BranchGenerator(config, fragment_registry)
    return generator.generate(sql_unit)


DEFAULT_CONFIG = {
    "branch": {
        "strategy": "all_combinations",
        "max_branches": 100,
    }
}
