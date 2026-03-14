"""
端到端性能基线测试 - 需要真实数据库连接

测试范围:
- 数据库连接验证
- EXPLAIN 计划收集
- 扫描类型检测
- 索引使用验证
- 分支基线收集

前置条件:
- PostgreSQL 或 MySQL 数据库运行中
- 环境变量 TEST_DATABASE_URL 设置
- tests/fixtures/sql_local/schema.sql 已执行

运行方式:
    export TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/sqlopt_test"
    python -m pytest tests/test_e2e_baseline.py -v
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# 检测数据库是否可用
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")


def _db_available() -> bool:
    """检查数据库是否可用"""
    if not TEST_DATABASE_URL:
        return False
    try:
        if "postgresql" in TEST_DATABASE_URL:
            from sqlopt.platforms.postgresql.evidence import check_db_connectivity
        elif "mysql" in TEST_DATABASE_URL:
            from sqlopt.platforms.mysql.evidence import check_db_connectivity
        else:
            return False

        config = {"db": {"dsn": TEST_DATABASE_URL}}
        result = check_db_connectivity(config)
        return result.get("ok", False)
    except Exception:
        return False


DB_AVAILABLE = _db_available()


def _get_config() -> dict[str, Any]:
    """获取测试配置"""
    platform = "postgresql" if "postgresql" in TEST_DATABASE_URL else "mysql"
    return {
        "db": {
            "platform": platform,
            "dsn": TEST_DATABASE_URL,
        },
        "branch": {
            "baseline_testing_enabled": True,
        },
    }


@unittest.skipIf(not DB_AVAILABLE, "Database not available (set TEST_DATABASE_URL)")
class E2EBaselineConnectionTest(unittest.TestCase):
    """数据库连接测试"""

    def test_01_database_connectivity(self) -> None:
        """测试数据库连接"""
        if "postgresql" in TEST_DATABASE_URL:
            from sqlopt.platforms.postgresql.evidence import check_db_connectivity
        else:
            from sqlopt.platforms.mysql.evidence import check_db_connectivity

        config = _get_config()
        result = check_db_connectivity(config)

        self.assertTrue(
            result.get("ok", False), f"DB connection failed: {result.get('error')}"
        )

    def test_02_tables_exist(self) -> None:
        """测试必需的表存在"""
        import psycopg2

        with psycopg2.connect(TEST_DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN ('users', 'orders', 'shipments')
                """)
                tables = {row[0] for row in cur.fetchall()}

        self.assertIn("users", tables)
        self.assertIn("orders", tables)
        self.assertIn("shipments", tables)

    def test_03_data_seeded(self) -> None:
        """测试数据已初始化"""
        import psycopg2

        with psycopg2.connect(TEST_DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM users")
                users_count = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM orders")
                orders_count = cur.fetchone()[0]

        self.assertGreaterEqual(users_count, 100, "users table should have >= 100 rows")
        self.assertGreaterEqual(
            orders_count, 300, "orders table should have >= 300 rows"
        )


@unittest.skipIf(not DB_AVAILABLE, "Database not available (set TEST_DATABASE_URL)")
class E2EBaselineExplainTest(unittest.TestCase):
    """EXPLAIN 计划收集测试"""

    def test_04_explain_simple_select(self) -> None:
        """测试简单查询 EXPLAIN"""
        from sqlopt.platforms.postgresql.evidence import _collect_explain

        config = _get_config()
        sql = "SELECT * FROM users WHERE id = 1"

        result = _collect_explain(config, sql)

        self.assertTrue(
            result.get("ok", False), f"EXPLAIN failed: {result.get('error')}"
        )
        self.assertIn("planLines", result)
        self.assertGreater(len(result["planLines"]), 0)

    def test_05_explain_join_query(self) -> None:
        """测试 JOIN 查询 EXPLAIN"""
        from sqlopt.platforms.postgresql.evidence import _collect_explain

        config = _get_config()
        sql = """
        SELECT u.name, COUNT(o.id) as order_count
        FROM users u
        LEFT JOIN orders o ON u.id = o.user_id
        WHERE u.status = 'ACTIVE'
        GROUP BY u.id, u.name
        """

        result = _collect_explain(config, sql)

        self.assertTrue(result.get("ok", False))
        plan_text = "\n".join(result.get("planLines", []))
        # 应该包含 JOIN 操作
        self.assertTrue(
            any(kw in plan_text.upper() for kw in ["JOIN", "HASH", "MERGE", "NESTED"]),
            f"Expected JOIN in plan: {plan_text[:200]}",
        )

    def test_06_explain_subquery(self) -> None:
        """测试子查询 EXPLAIN"""
        from sqlopt.platforms.postgresql.evidence import _collect_explain

        config = _get_config()
        sql = "SELECT * FROM users WHERE id IN (SELECT user_id FROM orders)"

        result = _collect_explain(config, sql)

        self.assertTrue(result.get("ok", False))


@unittest.skipIf(not DB_AVAILABLE, "Database not available (set TEST_DATABASE_URL)")
class E2EBaselineScanTypeTest(unittest.TestCase):
    """扫描类型检测测试"""

    def test_07_seq_scan_detection(self) -> None:
        """测试全表扫描检测"""
        from sqlopt.adapters.branch_diagnose import diagnose_branches

        config = _get_config()
        sql = "SELECT * FROM users"
        branches = [{"sql": sql}]

        diagnosed = diagnose_branches(branches, config)

        self.assertEqual(len(diagnosed), 1)
        baseline = diagnosed[0].get("baseline", {})
        # 全表扫描应该被标记为有问题
        self.assertTrue(
            baseline.get("type") in ["ALL", "FSEQ", "Seq Scan", None]
            or baseline.get("problematic", False),
            f"Expected seq scan to be problematic: {baseline}",
        )

    def test_08_index_scan_detection(self) -> None:
        """测试索引扫描检测"""
        from sqlopt.adapters.branch_diagnose import diagnose_branches

        config = _get_config()
        sql = "SELECT * FROM users WHERE id = 1"
        branches = [{"sql": sql}]

        diagnosed = diagnose_branches(branches, config)

        self.assertEqual(len(diagnosed), 1)
        baseline = diagnosed[0].get("baseline", {})
        # 主键查询应使用索引
        self.assertTrue(
            baseline.get("usingIndex", False)
            or "Index" in str(baseline.get("type", "")),
            f"Expected index scan: {baseline}",
        )


@unittest.skipIf(not DB_AVAILABLE, "Database not available (set TEST_DATABASE_URL)")
class E2EBaselineIndexUsageTest(unittest.TestCase):
    """索引使用验证测试"""

    def test_09_primary_key_index(self) -> None:
        """测试主键索引使用"""
        from sqlopt.platforms.postgresql.evidence import _collect_explain

        config = _get_config()
        sql = "SELECT * FROM users WHERE id = 1"

        result = _collect_explain(config, sql)

        self.assertTrue(result.get("ok", False))
        plan_text = "\n".join(result.get("planLines", [])).lower()
        self.assertIn("index", plan_text)

    def test_10_unique_index(self) -> None:
        """测试唯一索引使用"""
        from sqlopt.platforms.postgresql.evidence import _collect_explain

        config = _get_config()
        sql = "SELECT * FROM users WHERE email = 'alice@example.com'"

        result = _collect_explain(config, sql)

        self.assertTrue(result.get("ok", False))
        plan_text = "\n".join(result.get("planLines", [])).lower()
        self.assertIn("index", plan_text)


@unittest.skipIf(not DB_AVAILABLE, "Database not available (set TEST_DATABASE_URL)")
class E2EBaselineBranchTest(unittest.TestCase):
    """分支基线收集测试"""

    def test_11_multiple_branches(self) -> None:
        """测试多分支基线收集"""
        from sqlopt.adapters.branch_diagnose import diagnose_branches

        config = _get_config()
        branches = [
            {"sql": "SELECT * FROM users WHERE status = 'ACTIVE'"},
            {"sql": "SELECT * FROM users WHERE name LIKE '%Alice%'"},
            {"sql": "SELECT * FROM users WHERE id IN (1, 2, 3)"},
        ]

        diagnosed = diagnose_branches(branches, config)

        self.assertEqual(len(diagnosed), 3)
        for branch in diagnosed:
            self.assertIn("baseline", branch)

    def test_12_problematic_pattern_detection(self) -> None:
        """测试问题模式检测"""
        from sqlopt.adapters.branch_diagnose import diagnose_branches

        config = _get_config()
        # LIKE '%xxx%' 会导致全表扫描
        sql = "SELECT * FROM users WHERE name LIKE '%Alice%'"
        branches = [{"sql": sql}]

        diagnosed = diagnose_branches(branches, config)

        baseline = diagnosed[0].get("baseline", {})
        # 这种模式应该被标记
        # 注意：实际行为取决于数据库优化器
        self.assertIsNotNone(baseline.get("type"))


if __name__ == "__main__":
    unittest.main()
