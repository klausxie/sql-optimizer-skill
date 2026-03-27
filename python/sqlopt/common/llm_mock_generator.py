"""LLM providers for SQL optimization.

This module provides LLM implementations for generating optimization proposals
and performance baselines for SQL queries.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class LLMProviderBase(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate_optimization(self, sql: str, description: str = "") -> str:
        """Generate optimization proposal for SQL.

        Args:
            sql: Original SQL query
            description: Description of desired optimization

        Returns:
            JSON string matching OptimizationProposal schema
        """

    @abstractmethod
    def generate_baseline(self, sql: str, platform: str = "postgresql") -> dict[str, Any]:
        """Generate baseline performance data for SQL.

        Args:
            sql: SQL query to analyze
            platform: Database platform (postgresql, mysql, etc.)

        Returns:
            Dict matching PerformanceBaseline schema
        """

    @abstractmethod
    def generate_risks(self, sql: str) -> list[dict[str, Any]]:
        """Generate risks for SQL.

        Args:
            sql: SQL query to analyze

        Returns:
            List of dicts matching Risk schema
        """


class MockLLMProvider(LLMProviderBase):
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


class OpenAILLMProvider(LLMProviderBase):
    """OpenAI LLM provider for SQL optimization.

    Uses real database EXPLAIN for baseline generation and OpenAI API
    for optimization proposal generation.

    Example:
        >>> provider = OpenAILLMProvider(
        ...     db_connector=PostgreSQLConnector(host="localhost", dbname="test"),
        ...     api_key="sk-..."
        ... )
        >>> baseline = provider.generate_baseline("SELECT * FROM users", "postgresql")
        >>> proposal_json = provider.generate_optimization("SELECT * FROM users", "Add index hint")
    """

    def __init__(
        self,
        db_connector: Any = None,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
    ) -> None:
        """Initialize OpenAI LLM provider.

        Args:
            db_connector: Database connector for EXPLAIN plans (DBConnector instance)
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: OpenAI model to use
        """
        self.db_connector = db_connector
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import openai
            except ImportError:
                raise ImportError(
                    "openai package is required for OpenAILLMProvider but not installed. "
                    "Install with: pip install openai"
                )
            if not self.api_key:
                raise ValueError(
                    "OpenAI API key not provided. Set OPENAI_API_KEY environment variable "
                    "or pass api_key to constructor."
                )
            self._client = openai.OpenAI(api_key=self.api_key)
        return self._client

    def generate_optimization(self, sql: str, description: str = "") -> str:
        prompt = self._build_optimization_prompt(sql, description)
        response = self._get_client().chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a SQL optimization expert. Return ONLY valid JSON with no markdown formatting.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        return self._parse_optimization_response(content, sql)

    def _build_optimization_prompt(self, sql: str, description: str) -> str:
        return f"""Analyze this SQL query and suggest an optimized version.

Original SQL:
{sql}

{"Optimization hint: " + description if description else ""}

Return a JSON object with these fields:
- sql_unit_id: a short unique identifier
- path_id: a path identifier
- optimized_sql: the optimized SQL query
- rationale: explanation of why this optimization helps
- confidence: confidence score between 0.0 and 1.0

Example output:
{{"sql_unit_id": "unit_abc123", "path_id": "path_xyz", "optimized_sql": "SELECT id, name FROM users WHERE id = 1", "rationale": "Selected only needed columns", "confidence": 0.95}}"""

    def _parse_optimization_response(self, content: str, original_sql: str) -> str:
        try:
            data = json.loads(content)
            return json.dumps(
                {
                    "sql_unit_id": data.get(
                        "sql_unit_id",
                        f"unit_{hashlib.md5(original_sql.encode(), usedforsecurity=False).hexdigest()[:8]}",
                    ),
                    "path_id": data.get(
                        "path_id",
                        f"path_{hashlib.md5(original_sql.encode(), usedforsecurity=False).hexdigest()[:8]}",
                    ),
                    "original_sql": original_sql,
                    "optimized_sql": data.get("optimized_sql", original_sql),
                    "rationale": data.get("rationale", "LLM optimization"),
                    "confidence": data.get("confidence", 0.8),
                }
            )
        except json.JSONDecodeError:
            return json.dumps(
                {
                    "sql_unit_id": f"unit_{hashlib.md5(original_sql.encode(), usedforsecurity=False).hexdigest()[:8]}",
                    "path_id": f"path_{hashlib.md5(original_sql.encode(), usedforsecurity=False).hexdigest()[:8]}",
                    "original_sql": original_sql,
                    "optimized_sql": original_sql,
                    "rationale": "Failed to parse LLM response",
                    "confidence": 0.0,
                }
            )

    def generate_baseline(self, sql: str, platform: str = "postgresql") -> dict[str, Any]:
        _ = platform  # Platform is determined from db_connector configuration
        if self.db_connector is None:
            raise ValueError("DBConnector required for baseline generation")
        explain_plan = self.db_connector.execute_explain(sql)
        estimated_cost = self._estimate_cost_from_plan(explain_plan)
        return {
            "sql_unit_id": f"unit_{hashlib.md5(sql.encode(), usedforsecurity=False).hexdigest()[:8]}",
            "path_id": f"path_{hashlib.md5(sql.encode(), usedforsecurity=False).hexdigest()[:8]}",
            "plan": explain_plan,
            "estimated_cost": estimated_cost,
            "actual_time_ms": None,
        }

    def _estimate_cost_from_plan(self, plan: dict[str, Any]) -> float:
        if not plan:
            return 100.0
        if "Plan" in plan:
            total_cost = plan["Plan"].get("Total Cost", 100.0)
            return float(total_cost) if total_cost is not None else 100.0
        if "cost" in plan:
            return float(plan["cost"])
        return 100.0

    def generate_risks(self, sql: str) -> list[dict[str, Any]]:
        prompt = f"""Analyze this SQL query for potential risks:

{sql}

Return a JSON array of risk objects with fields:
- sql_unit_id: a short unique identifier
- risk_type: uppercase risk type (e.g., SELECT_STAR, MISSING_WHERE)
- severity: HIGH, MEDIUM, or LOW
- message: description of the risk

Example: [{{"sql_unit_id": "u1", "risk_type": "SELECT_STAR", "severity": "MEDIUM", "message": "Avoid SELECT *"}}]"""
        response = self._get_client().chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a SQL security expert. Return ONLY valid JSON array.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "[]"
        try:
            risks_raw = json.loads(content)
            if isinstance(risks_raw, dict) and "risks" in risks_raw:
                risks_raw = risks_raw["risks"]
            if not isinstance(risks_raw, list):
                risks_raw = [risks_raw]
            risks: list[dict[str, Any]] = [r for r in risks_raw if isinstance(r, dict)]
            sql_unit_id = f"unit_{hashlib.md5(sql.encode(), usedforsecurity=False).hexdigest()[:8]}"
            for r in risks:
                r.setdefault("sql_unit_id", sql_unit_id)
            return risks
        except json.JSONDecodeError:
            return [
                {
                    "sql_unit_id": f"unit_{hashlib.md5(sql.encode(), usedforsecurity=False).hexdigest()[:8]}",
                    "risk_type": "PARSE_ERROR",
                    "severity": "LOW",
                    "message": "Failed to parse LLM risk analysis",
                }
            ]


class OpenCodeRunLLMProvider(LLMProviderBase):
    """OpenCode run-based LLM provider for SQL optimization.

    Uses the `opencode run` command to leverage LLM capabilities for generating
    optimization proposals. Falls back to MockLLMProvider for baseline generation
    if database connector is not available.

    Example:
        >>> provider = OpenCodeRunLLMProvider(
        ...     db_connector=PostgreSQLConnector(host="localhost", dbname="test")
        ... )
        >>> baseline = provider.generate_baseline("SELECT * FROM users", "postgresql")
        >>> proposal_json = provider.generate_optimization("SELECT * FROM users", "Add index hint")
    """

    def __init__(
        self,
        db_connector: Any = None,
        model: str | None = None,
    ) -> None:
        """Initialize OpenCodeRun LLM provider.

        Args:
            db_connector: Database connector for EXPLAIN plans (DBConnector instance)
            model: Model to use in provider/model format. If None, uses user's opencode default.
        """
        self.db_connector = db_connector
        self.model = model
        self._mock = MockLLMProvider()

    def generate_optimization(self, sql: str, description: str = "") -> str:
        prompt = self._build_optimization_prompt(sql, description)
        json_output = self._call_opencode(prompt)
        return self._parse_response(json_output, sql)

    def _build_optimization_prompt(self, sql: str, description: str) -> str:
        return f"""Analyze this SQL query and suggest an optimized version.

Original SQL:
{sql}

{"Optimization hint: " + description if description else ""}

Return a JSON object with these fields:
- sql_unit_id: a short unique identifier
- path_id: a path identifier
- optimized_sql: the optimized SQL query
- rationale: explanation of why this optimization helps
- confidence: confidence score between 0.0 and 1.0

Example output:
{{"sql_unit_id": "unit_abc123", "path_id": "path_xyz", "optimized_sql": "SELECT id, name FROM users WHERE id = 1", "rationale": "Selected only needed columns", "confidence": 0.95}}"""

    def _is_windows(self) -> bool:
        """Check if running on Windows."""
        return sys.platform == "win32" or os.name == "nt"

    def _get_opencode_cmd(self) -> list[str]:
        """Get the command to run opencode CLI.

        On Windows, .CMD batch files don't work well with subprocess.run()
        without shell=True. Instead, we call node directly with the opencode script.
        """
        if self._is_windows():
            # On Windows, find node and the opencode script
            node_path = shutil.which("node")
            if not node_path:
                raise RuntimeError("node command not found")
            opencode_path = shutil.which("opencode")
            if not opencode_path:
                raise RuntimeError("opencode command not found")
            # opencode is a .CMD file that ultimately runs: node <script> <args>
            # We bypass the batch file and call node directly
            opencode_script = Path(opencode_path).parent / "node_modules" / "opencode-ai" / "bin" / "opencode"
            if not opencode_script.exists():
                # Fallback: use the original batch file approach
                return ["opencode"]
            return [node_path, str(opencode_script)]
        # On Unix, opencode is a shell script that works directly
        if not shutil.which("opencode"):
            raise RuntimeError("opencode command not found")
        return ["opencode"]

    def _call_opencode(self, prompt: str) -> str:
        import subprocess

        cmd = [
            *self._get_opencode_cmd(),
            "run",
            prompt,
            "--format",
            "json",
        ]
        if self.model:
            cmd.extend(["--model", self.model])
        try:
            result = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=120,
            )
            if result.returncode != 0:
                return f'{{"error": "opencode run failed: {result.stderr}"}}'
            return result.stdout
        except subprocess.TimeoutExpired:
            return '{"error": "opencode run timed out"}'
        except FileNotFoundError:
            return '{"error": "opencode command not found"}'

    def _parse_response(self, json_output: str, original_sql: str) -> str:
        # Find the LAST text event that contains JSON with optimized_sql
        # OpenCode returns multiple text events - we want the final one with the actual response
        text_events: list[str] = []
        for line in json_output.strip().split("\n"):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if data.get("type") == "text":
                    part = data.get("part", {})
                    text = part.get("text", "")
                    text_events.append(text)
            except json.JSONDecodeError:
                continue

        content = None
        # Search from the end to find the event with optimized_sql
        for text in reversed(text_events):
            if "optimized_sql" in text:
                # Extract JSON from code block
                if "```json" in text:
                    start = text.find("```json") + 7
                    end = text.rfind("```")
                    if end > start:
                        text = text[start:end]
                try:
                    candidate = json.loads(text.strip())
                    if isinstance(candidate, dict) and "optimized_sql" in candidate:
                        content = candidate
                        break
                except json.JSONDecodeError:
                    continue

        if content is None:
            return json.dumps(
                {
                    "sql_unit_id": f"unit_{hashlib.md5(original_sql.encode(), usedforsecurity=False).hexdigest()[:8]}",
                    "path_id": f"path_{hashlib.md5(original_sql.encode(), usedforsecurity=False).hexdigest()[:8]}",
                    "original_sql": original_sql,
                    "optimized_sql": original_sql,
                    "rationale": "No valid JSON content found in OpenCodeRun response",
                    "confidence": 0.0,
                }
            )
        if "error" in content:
            return json.dumps(
                {
                    "sql_unit_id": f"unit_{hashlib.md5(original_sql.encode(), usedforsecurity=False).hexdigest()[:8]}",
                    "path_id": f"path_{hashlib.md5(original_sql.encode(), usedforsecurity=False).hexdigest()[:8]}",
                    "original_sql": original_sql,
                    "optimized_sql": original_sql,
                    "rationale": f"OpenCodeRun error: {content['error']}",
                    "confidence": 0.0,
                }
            )
        return json.dumps(
            {
                "sql_unit_id": content.get(
                    "sql_unit_id",
                    f"unit_{hashlib.md5(original_sql.encode(), usedforsecurity=False).hexdigest()[:8]}",
                ),
                "path_id": content.get(
                    "path_id",
                    f"path_{hashlib.md5(original_sql.encode(), usedforsecurity=False).hexdigest()[:8]}",
                ),
                "original_sql": original_sql,
                "optimized_sql": content.get("optimized_sql", original_sql),
                "rationale": content.get("rationale", "OpenCodeRun optimization"),
                "confidence": content.get("confidence", 0.8),
            }
        )

    def generate_baseline(self, sql: str, platform: str = "postgresql") -> dict[str, Any]:
        if self.db_connector is None:
            return self._mock.generate_baseline(sql, platform)
        explain_plan = self.db_connector.execute_explain(sql)
        estimated_cost = self._estimate_cost_from_plan(explain_plan)
        return {
            "sql_unit_id": f"unit_{hashlib.md5(sql.encode(), usedforsecurity=False).hexdigest()[:8]}",
            "path_id": f"path_{hashlib.md5(sql.encode(), usedforsecurity=False).hexdigest()[:8]}",
            "plan": explain_plan,
            "estimated_cost": estimated_cost,
            "actual_time_ms": None,
        }

    def _estimate_cost_from_plan(self, plan: dict[str, Any]) -> float:
        if not plan:
            return 100.0
        if "Plan" in plan:
            total_cost = plan["Plan"].get("Total Cost", 100.0)
            return float(total_cost) if total_cost is not None else 100.0
        if "cost" in plan:
            return float(plan["cost"])
        return 100.0

    def generate_risks(self, sql: str) -> list[dict[str, Any]]:
        return self._mock.generate_risks(sql)
