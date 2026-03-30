from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlopt.platforms.postgresql import compare


class ComparePrepareTest(unittest.TestCase):
    def test_compare_plan_returns_prepare_failed_when_sql_becomes_empty(self) -> None:
        cfg = {"db": {"dsn": "postgresql://dummy"}, "validate": {"plan_compare_enabled": True}}
        with tempfile.TemporaryDirectory(prefix="sqlopt_cmp_prepare_") as td:
            with patch("sqlopt.platforms.postgresql.compare._get_sql_connect", return_value=(object(), "psycopg2")):
                out = compare.compare_plan(cfg, "SELECT 1", "<if test='x'></if>", Path(td))
        self.assertFalse(out["checked"])
        self.assertEqual(out.get("reasonCategory"), "SQL_PREPARE_FAILED")

    def test_compare_semantics_returns_prepare_failed_when_sql_becomes_empty(self) -> None:
        cfg = {"db": {"dsn": "postgresql://dummy"}, "validate": {"allow_db_unreachable_fallback": True}}
        with tempfile.TemporaryDirectory(prefix="sqlopt_cmp_prepare_") as td:
            with patch("sqlopt.platforms.postgresql.compare._get_sql_connect", return_value=(object(), "psycopg2")):
                out = compare.compare_semantics(cfg, "SELECT 1", "<if test='x'></if>", Path(td))
        self.assertFalse(out["checked"])
        self.assertEqual(out.get("reasonCategory"), "SQL_PREPARE_FAILED")
        self.assertEqual((out.get("rowCount") or {}).get("status"), "SKIPPED")


if __name__ == "__main__":
    unittest.main()
