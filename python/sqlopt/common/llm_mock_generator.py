"""Mock LLM provider for generating test data.

This module provides mock implementations of LLM responses for testing
the SQL optimizer without requiring actual LLM API calls.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


class MockLLMProvider:
    """Mock LLM provider for generating test data.

    Generates deterministic mock responses based on input SQL and
    optional descriptions. Useful for unit testing without LLM API calls.

    Example:
        >>> provider = MockLLMProvider()
        >>> result = provider.generate_optimization(
        ...     "SELECT * FROM users",
        ...     "Add index hint"
        ... )
        >>> data = json.loads(result)
        >>> "optimized_sql" in data
        True
    """

    def _generate_deterministic_id(self, sql: str, prefix: str = "") -> str:
        """Generate a deterministic ID based on SQL hash.

        Args:
            sql: SQL string to hash
            prefix: Optional prefix for the ID

        Returns:
            A deterministic ID string
        """
        hash_value = hashlib.md5(sql.encode(), usedforsecurity=False).hexdigest()[:8]
        return f"{prefix}{hash_value}" if prefix else hash_value

    def generate_optimization(self, sql: str, description: str = "") -> str:
        """Generate mock optimization proposal based on description.

        Args:
            sql: Original SQL query
            description: Description of desired optimization

        Returns:
            JSON string matching OptimizationProposal schema
        """
        sql_unit_id = f"unit_{self._generate_deterministic_id(sql, '')}"
        path_id = f"path_{self._generate_deterministic_id(sql + description, '')}"

        optimized_sql = self._generate_mock_optimized_sql(sql, description)
        rationale = self._generate_mock_rationale(description)
        confidence = 0.85 if description else 0.75

        proposal = {
            "sql_unit_id": sql_unit_id,
            "path_id": path_id,
            "original_sql": sql,
            "optimized_sql": optimized_sql,
            "rationale": rationale,
            "confidence": confidence,
        }

        return json.dumps(proposal)

    def _generate_mock_optimized_sql(self, sql: str, description: str) -> str:
        """Generate mock optimized SQL based on description hints.

        Args:
            sql: Original SQL query
            description: Description hint for optimization

        Returns:
            Mock optimized SQL string
        """
        desc_lower = description.lower() if description else ""

        if "index" in desc_lower:
            if "FROM" in sql.upper():
                return sql.replace("SELECT", "SELECT /*+ IndexScan(users) */", 1)
            return f"/*+ IndexScan */ {sql}"

        if "limit" in desc_lower:
            if "LIMIT" not in sql.upper():
                return f"{sql.rstrip(';')} LIMIT 100"
            return sql

        if "join" in desc_lower:
            return sql.replace("WHERE", "/*+ HashJoin */ WHERE", 1)

        return f"/* optimized */ {sql}"

    def _generate_mock_rationale(self, description: str) -> str:
        """Generate mock rationale based on description.

        Args:
            description: Description hint

        Returns:
            Mock rationale string
        """
        if not description:
            return "General query optimization applied"

        desc_lower = description.lower()

        if "index" in desc_lower:
            return "Index hint added to improve scan performance"
        if "limit" in desc_lower:
            return "LIMIT clause added to reduce result set size"
        if "join" in desc_lower:
            return "JOIN optimization hint added for better execution plan"

        return f"Applied optimization: {description}"

    def generate_baseline(self, sql: str, platform: str = "postgresql") -> dict[str, Any]:
        """Generate mock EXPLAIN baseline for SQL.

        Args:
            sql: SQL query to analyze
            platform: Database platform (postgresql, mysql, etc.)

        Returns:
            Dict matching PerformanceBaseline schema
        """
        sql_unit_id = f"unit_{self._generate_deterministic_id(sql, '')}"
        path_id = f"path_{self._generate_deterministic_id(sql, '')}"

        plan = self._generate_mock_explain_plan(sql, platform)
        estimated_cost = self._estimate_mock_cost(sql)

        return {
            "sql_unit_id": sql_unit_id,
            "path_id": path_id,
            "plan": plan,
            "estimated_cost": estimated_cost,
            "actual_time_ms": None,
        }

    def _generate_mock_explain_plan(self, sql: str, platform: str) -> dict[str, Any]:
        """Generate mock EXPLAIN plan based on SQL and platform.

        Args:
            sql: SQL query
            platform: Database platform

        Returns:
            Mock EXPLAIN plan as dict
        """
        sql_upper = sql.upper()

        has_join = "JOIN" in sql_upper
        has_where = "WHERE" in sql_upper
        has_group_by = "GROUP BY" in sql_upper
        has_order_by = "ORDER BY" in sql_upper

        if platform == "postgresql":
            return self._generate_postgres_plan(has_join, has_where, has_group_by, has_order_by)
        if platform == "mysql":
            return self._generate_mysql_plan(has_join, has_where, has_group_by, has_order_by)

        return {
            "type": "seq_scan",
            "relation": "table",
            "cost": 1.0,
        }

    def _generate_postgres_plan(
        self,
        has_join: bool,
        has_where: bool,
        has_group_by: bool,
        has_order_by: bool,
    ) -> dict[str, Any]:
        """Generate mock PostgreSQL EXPLAIN plan.

        Args:
            has_join: Whether SQL has JOIN
            has_where: Whether SQL has WHERE
            has_group_by: Whether SQL has GROUP BY
            has_order_by: Whether SQL has ORDER BY

        Returns:
            Mock PostgreSQL plan
        """
        node_type = "Seq Scan"
        if has_join:
            node_type = "Hash Join"

        plan = {
            "Plan": {
                "Node Type": node_type,
                "Relation Name": "users",
                "Alias": "users",
                "Startup Cost": 0.0,
                "Total Cost": 100.0,
                "Plan Rows": 1000,
                "Plan Width": 100,
            }
        }

        if has_join:
            plan["Plan"]["Plans"] = [
                {
                    "Node Type": "Seq Scan",
                    "Relation Name": "users",
                    "Startup Cost": 0.0,
                    "Total Cost": 50.0,
                    "Plan Rows": 500,
                    "Plan Width": 50,
                },
                {
                    "Node Type": "Index Scan",
                    "Relation Name": "orders",
                    "Startup Cost": 0.0,
                    "Total Cost": 50.0,
                    "Plan Rows": 500,
                    "Plan Width": 50,
                },
            ]

        if has_where:
            plan["Plan"]["Filter"] = "id > 0"

        if has_group_by:
            plan["Plan"]["Group Key"] = ["id"]

        if has_order_by:
            plan["Plan"]["Sort Key"] = ["id"]

        return plan

    def _generate_mysql_plan(
        self,
        has_join: bool,
        has_where: bool,
        has_group_by: bool,
        has_order_by: bool,
    ) -> dict[str, Any]:
        """Generate mock MySQL EXPLAIN plan.

        Args:
            has_join: Whether SQL has JOIN
            has_where: Whether SQL has WHERE
            has_group_by: Whether SQL has GROUP BY
            has_order_by: Whether SQL has ORDER BY

        Returns:
            Mock MySQL plan
        """
        plan = {
            "id": 1,
            "select_type": "SIMPLE",
            "table": "users",
            "type": "ALL",
            "possible_keys": None,
            "key": None,
            "key_len": None,
            "ref": None,
            "rows": 1000,
            "filtered": 100.0,
            "Extra": None,
        }

        if has_where:
            plan["Extra"] = "Using where"

        if has_join:
            plan["type"] = "ref"
            plan["possible_keys"] = "PRIMARY"

        if has_group_by:
            extra = plan.get("Extra") or ""
            plan["Extra"] = f"{extra}; Using temporary".strip("; ")

        if has_order_by:
            extra = plan.get("Extra") or ""
            plan["Extra"] = f"{extra}; Using filesort".strip("; ")

        return plan

    def _estimate_mock_cost(self, sql: str) -> float:
        """Estimate mock cost based on SQL complexity.

        Args:
            sql: SQL query

        Returns:
            Estimated cost value
        """
        base_cost = 10.0

        sql_upper = sql.upper()

        if "JOIN" in sql_upper:
            base_cost += 20.0
        if "WHERE" in sql_upper:
            base_cost += 5.0
        if "GROUP BY" in sql_upper:
            base_cost += 15.0
        if "ORDER BY" in sql_upper:
            base_cost += 10.0
        if "HAVING" in sql_upper:
            base_cost += 10.0
        if "DISTINCT" in sql_upper:
            base_cost += 8.0

        if "LIMIT" in sql_upper:
            base_cost *= 0.5

        return base_cost

    def generate_risks(self, sql: str) -> list[dict[str, Any]]:
        """Generate mock risks for SQL.

        Args:
            sql: SQL query to analyze

        Returns:
            List of dicts matching Risk schema
        """
        sql_unit_id = f"unit_{self._generate_deterministic_id(sql, '')}"
        risks: list[dict[str, Any]] = []

        sql_upper = sql.upper()

        # Check for common risk patterns
        if "SELECT *" in sql_upper or "SELECT  *" in sql_upper:
            risks.append(
                {
                    "sql_unit_id": sql_unit_id,
                    "risk_type": "SELECT_STAR",
                    "severity": "MEDIUM",
                    "message": "SELECT * retrieves all columns, consider specifying needed columns",
                }
            )

        if sql_upper.count("JOIN") > 3:
            risks.append(
                {
                    "sql_unit_id": sql_unit_id,
                    "risk_type": "TOO_MANY_JOINS",
                    "severity": "HIGH",
                    "message": "Query has more than 3 JOINs, consider restructuring",
                }
            )

        if "WHERE" not in sql_upper and "FROM" in sql_upper:
            risks.append(
                {
                    "sql_unit_id": sql_unit_id,
                    "risk_type": "MISSING_WHERE",
                    "severity": "HIGH",
                    "message": "Query lacks WHERE clause, may scan entire table",
                }
            )

        if "LIKE '%" in sql_upper:
            risks.append(
                {
                    "sql_unit_id": sql_unit_id,
                    "risk_type": "LEADING_WILDCARD",
                    "severity": "MEDIUM",
                    "message": "Leading wildcard in LIKE prevents index usage",
                }
            )

        if "OR" in sql_upper and "WHERE" in sql_upper:
            risks.append(
                {
                    "sql_unit_id": sql_unit_id,
                    "risk_type": "OR_CONDITION",
                    "severity": "LOW",
                    "message": "OR conditions may prevent optimal index usage",
                }
            )

        if not risks:
            risks.append(
                {
                    "sql_unit_id": sql_unit_id,
                    "risk_type": "INFO",
                    "severity": "LOW",
                    "message": "No significant risks detected in query",
                }
            )

        return risks
