"""Unit tests for baseline EXPLAIN parsing functionality."""

from __future__ import annotations

import unittest

from sqlopt.stages.baseline.baseline_collector import (
    ExplainPlan,
    ExplainParseResult,
    _parse_postgresql_explain_json,
    _parse_mysql_explain_json,
)


class TestPostgreSQLExplainParser(unittest.TestCase):
    """Tests for PostgreSQL EXPLAIN JSON parser."""

    def test_parse_simple_seq_scan(self) -> None:
        """Test parsing a simple sequential scan plan."""
        explain_result = [
            {
                "Plan": {
                    "Node Type": "Seq Scan",
                    "Relation Name": "users",
                    "Alias": "users",
                    "Startup Cost": 0.00,
                    "Total Cost": 1234.56,
                    "Plan Rows": 10000,
                    "Plan Width": 100,
                    "Actual Startup Time": 0.012,
                    "Actual Total Time": 5.678,
                    "Actual Rows": 9500,
                    "Actual Loops": 1,
                },
                "Planning Time": 0.123,
                "Triggers": [],
                "Execution Time": 5.789,
            }
        ]

        result = _parse_postgresql_explain_json(explain_result)

        self.assertIsInstance(result, ExplainParseResult)
        self.assertIsInstance(result.plan, ExplainPlan)

        plan = result.plan
        self.assertEqual(plan.scan_type, "FULL_TABLE_SCAN")
        self.assertEqual(plan.estimated_cost, 1234.56)
        self.assertEqual(plan.estimated_rows, 10000)
        self.assertEqual(plan.actual_rows, 9500)
        self.assertEqual(plan.actual_loops, 1)
        self.assertEqual(plan.actual_startup_time_ms, 0.012)
        self.assertEqual(plan.actual_total_time_ms, 5.678)
        self.assertIn("users", plan.plan_text)

    def test_parse_index_scan(self) -> None:
        """Test parsing an index scan plan."""
        explain_result = [
            {
                "Plan": {
                    "Node Type": "Index Scan",
                    "Relation Name": "orders",
                    "Alias": "o",
                    "Index Name": "idx_order_date",
                    "Startup Cost": 0.43,
                    "Total Cost": 8.45,
                    "Plan Rows": 1,
                    "Plan Width": 200,
                    "Actual Startup Time": 0.025,
                    "Actual Total Time": 0.027,
                    "Actual Rows": 1,
                    "Actual Loops": 1,
                    "Index Cond": "(order_date = '2024-01-01'::date)",
                },
                "Planning Time": 0.050,
                "Execution Time": 0.060,
            }
        ]

        result = _parse_postgresql_explain_json(explain_result)
        plan = result.plan

        self.assertEqual(plan.scan_type, "INDEX_SCAN")
        self.assertEqual(plan.index_name, "idx_order_date")
        self.assertEqual(plan.estimated_cost, 8.45)
        self.assertEqual(plan.estimated_rows, 1)
        self.assertEqual(plan.actual_rows, 1)

    def test_parse_index_only_scan(self) -> None:
        """Test parsing an index-only scan plan."""
        explain_result = [
            {
                "Plan": {
                    "Node Type": "Index Only Scan",
                    "Relation Name": "products",
                    "Index Name": "idx_product_sku",
                    "Total Cost": 5.00,
                    "Plan Rows": 50,
                }
            }
        ]

        result = _parse_postgresql_explain_json(explain_result)
        plan = result.plan

        self.assertEqual(plan.scan_type, "INDEX_ONLY_SCAN")
        self.assertEqual(plan.index_name, "idx_product_sku")

    def test_parse_nested_loop_join(self) -> None:
        """Test parsing a nested loop join plan."""
        explain_result = [
            {
                "Plan": {
                    "Node Type": "Nested Loop",
                    "Total Cost": 100.00,
                    "Plan Rows": 100,
                    "Plans": [
                        {
                            "Node Type": "Seq Scan",
                            "Relation Name": "users",
                        },
                        {
                            "Node Type": "Index Scan",
                            "Relation Name": "orders",
                        },
                    ],
                }
            }
        ]

        result = _parse_postgresql_explain_json(explain_result)
        plan = result.plan

        self.assertEqual(plan.scan_type, "NESTED_LOOP")
        self.assertEqual(plan.estimated_rows, 100)

    def test_parse_with_buffer_stats(self) -> None:
        """Test parsing plan with buffer statistics."""
        explain_result = [
            {
                "Plan": {
                    "Node Type": "Seq Scan",
                    "Relation Name": "large_table",
                    "Total Cost": 5000.00,
                    "Plan Rows": 500000,
                    "Shared Read Blocks": 1000,
                    "Shared Hit Blocks": 500,
                    "Shared Dirtied Blocks": 10,
                    "Shared Written Blocks": 5,
                }
            }
        ]

        result = _parse_postgresql_explain_json(explain_result)
        plan = result.plan

        self.assertEqual(plan.shared_read_blocks, 1000)
        self.assertEqual(plan.shared_hit_blocks, 500)
        self.assertEqual(plan.shared_dirtied_blocks, 10)
        self.assertEqual(plan.shared_written_blocks, 5)

    def test_parse_empty_result(self) -> None:
        """Test parsing empty or invalid result."""
        result = _parse_postgresql_explain_json([])

        self.assertEqual(result.plan.scan_type, "UNKNOWN")
        self.assertIn("Empty or invalid", result.warnings[0])

    def test_warning_for_row_estimate_mismatch(self) -> None:
        """Test warning generation for large row estimate mismatches."""
        explain_result = [
            {
                "Plan": {
                    "Node Type": "Seq Scan",
                    "Plan Rows": 100,
                    "Actual Rows": 50000,  # 500x more than estimated
                }
            }
        ]

        result = _parse_postgresql_explain_json(explain_result)

        self.assertTrue(any("much larger than estimated" in w for w in result.warnings))


class TestMySQLExplainParser(unittest.TestCase):
    """Tests for MySQL EXPLAIN JSON parser."""

    def test_parse_simple_query(self) -> None:
        """Test parsing a simple query plan."""
        explain_result = {
            "query_block": {
                "select_id": 1,
                "cost_info": {"query_cost": "1234.56"},
                "table": {
                    "table_name": "users",
                    "access_type": "ALL",
                    "rows_examined_per_scan": 10000,
                    "rows_produced_per_join": 10000,
                    "filtered": "100.00",
                    "cost_info": {
                        "read_cost": "1000.00",
                        "eval_cost": "2000.00",
                    },
                },
            }
        }

        result = _parse_mysql_explain_json(explain_result)

        self.assertIsInstance(result, ExplainParseResult)
        self.assertIsInstance(result.plan, ExplainPlan)

        plan = result.plan
        self.assertEqual(plan.scan_type, "FULL_TABLE_SCAN")
        self.assertEqual(plan.query_cost, 1234.56)
        self.assertEqual(plan.estimated_rows, 10000)

    def test_parse_index_ref_scan(self) -> None:
        """Test parsing an index ref scan."""
        explain_result = {
            "query_block": {
                "select_id": 1,
                "cost_info": {"query_cost": "10.50"},
                "table": {
                    "table_name": "orders",
                    "access_type": "ref",
                    "possible_keys": ["idx_user_id", "idx_order_date"],
                    "key": "idx_user_id",
                    "used_key_parts": ["user_id"],
                    "key_length": "8",
                    "ref": ["const"],
                    "rows_examined_per_scan": 50,
                    "rows_produced_per_join": 50,
                    "filtered": "100.00",
                },
            }
        }

        result = _parse_mysql_explain_json(explain_result)
        plan = result.plan

        self.assertEqual(plan.scan_type, "INDEX_REF")
        self.assertEqual(plan.index_name, "idx_user_id")
        self.assertEqual(plan.estimated_rows, 50)

    def test_parse_range_scan(self) -> None:
        """Test parsing a range scan."""
        explain_result = {
            "query_block": {
                "select_id": 1,
                "table": {
                    "table_name": "products",
                    "access_type": "range",
                    "key": "idx_price",
                    "rows_examined_per_scan": 100,
                },
            }
        }

        result = _parse_mysql_explain_json(explain_result)
        plan = result.plan

        self.assertEqual(plan.scan_type, "INDEX_RANGE_SCAN")
        self.assertEqual(plan.index_name, "idx_price")

    def test_parse_const_access(self) -> None:
        """Test parsing const access type (primary key lookup)."""
        explain_result = {
            "query_block": {
                "select_id": 1,
                "table": {
                    "table_name": "users",
                    "access_type": "const",
                    "key": "PRIMARY",
                    "rows_examined_per_scan": 1,
                },
            }
        }

        result = _parse_mysql_explain_json(explain_result)
        plan = result.plan

        self.assertEqual(plan.scan_type, "CONST")
        self.assertEqual(plan.index_name, "PRIMARY")

    def test_parse_with_analyze_metrics(self) -> None:
        """Test parsing EXPLAIN ANALYZE output (MySQL 8.0.18+)."""
        explain_result = {
            "query_block": {
                "select_id": 1,
                "table": {
                    "table_name": "orders",
                    "access_type": "ALL",
                    "rows_examined_per_scan": 1000,
                    "analyze": {
                        "r_rows": 950.0,
                        "r_total_time_ms": 15.5,
                    },
                },
            }
        }

        result = _parse_mysql_explain_json(explain_result)
        plan = result.plan

        self.assertEqual(plan.actual_rows, 950)
        self.assertEqual(plan.actual_total_time_ms, 15.5)

    def test_parse_with_used_columns(self) -> None:
        """Test parsing with used columns info."""
        explain_result = {
            "query_block": {
                "select_id": 1,
                "table": {
                    "table_name": "users",
                    "access_type": "ALL",
                    "used_columns": ["id", "name", "email"],
                    "attached_condition": "(`db`.`users`.`status` = 'active')",
                },
            }
        }

        result = _parse_mysql_explain_json(explain_result)
        plan = result.plan

        self.assertEqual(plan.used_columns, ["id", "name", "email"])
        self.assertEqual(plan.filter_condition, "(`db`.`users`.`status` = 'active')")

    def test_warning_for_full_table_scan(self) -> None:
        """Test warning generation for full table scans."""
        explain_result = {
            "query_block": {
                "select_id": 1,
                "table": {
                    "table_name": "large_table",
                    "access_type": "ALL",
                    "possible_keys": ["idx_status"],
                },
            }
        }

        result = _parse_mysql_explain_json(explain_result)

        self.assertTrue(any("Full table scan" in w for w in result.warnings))
        self.assertTrue(any("Possible keys not used" in w for w in result.warnings))

    def test_parse_empty_result(self) -> None:
        """Test parsing empty or invalid result."""
        result = _parse_mysql_explain_json({})

        self.assertEqual(result.plan.scan_type, "UNKNOWN")
        self.assertIn("Empty or invalid", result.warnings[0])

    def test_parse_nested_table_structure(self) -> None:
        """Test parsing nested table structure (e.g., subqueries)."""
        explain_result = {
            "query_block": {
                "select_id": 1,
                "cost_info": {"query_cost": "50.00"},
                "nested_loop": [
                    {
                        "table": {
                            "table_name": "users",
                            "access_type": "ALL",
                            "rows_examined_per_scan": 100,
                        }
                    }
                ],
            }
        }

        result = _parse_mysql_explain_json(explain_result)
        plan = result.plan

        self.assertEqual(plan.scan_type, "FULL_TABLE_SCAN")
        self.assertEqual(plan.estimated_rows, 100)


class TestExplainPlanDataClass(unittest.TestCase):
    """Tests for ExplainPlan dataclass."""

    def test_default_values(self) -> None:
        """Test default values for ExplainPlan."""
        plan = ExplainPlan(plan_text="test")

        self.assertEqual(plan.plan_text, "test")
        self.assertEqual(plan.scan_type, "UNKNOWN")
        self.assertIsNone(plan.estimated_cost)
        self.assertIsNone(plan.estimated_rows)
        self.assertIsNone(plan.actual_rows)
        self.assertIsNone(plan.index_name)

    def test_full_initialization(self) -> None:
        """Test full initialization of ExplainPlan."""
        plan = ExplainPlan(
            plan_text="SELECT * FROM users",
            estimated_cost=123.45,
            estimated_rows=1000,
            scan_type="INDEX_SCAN",
            actual_rows=950,
            actual_loops=1,
            actual_total_time_ms=5.5,
            index_name="idx_user_id",
            filter_condition="status = 'active'",
            shared_read_blocks=100,
            shared_hit_blocks=50,
            query_cost=123.45,
            used_columns=["id", "name"],
        )

        self.assertEqual(plan.estimated_cost, 123.45)
        self.assertEqual(plan.estimated_rows, 1000)
        self.assertEqual(plan.scan_type, "INDEX_SCAN")
        self.assertEqual(plan.actual_rows, 950)
        self.assertEqual(plan.index_name, "idx_user_id")
        self.assertEqual(plan.shared_read_blocks, 100)
        self.assertEqual(plan.query_cost, 123.45)
        self.assertEqual(plan.used_columns, ["id", "name"])


if __name__ == "__main__":
    unittest.main()
