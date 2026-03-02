from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlopt.errors import StageError
from sqlopt.platforms import dispatch
from sqlopt.platforms.base import FunctionPlatformAdapter, PlatformCapabilities


class PlatformDispatchTest(unittest.TestCase):
    def test_dispatch_exposes_platform_adapter_capability(self) -> None:
        cfg = {"db": {"platform": "postgresql"}}
        adapter = dispatch.get_platform_adapter(cfg)
        self.assertEqual(adapter.name, "postgresql")
        self.assertIsInstance(adapter, FunctionPlatformAdapter)
        self.assertTrue(adapter.capabilities.supports_connectivity_check)
        self.assertTrue(adapter.capabilities.supports_plan_compare)
        self.assertTrue(adapter.capabilities.supports_semantic_compare)

    def test_dispatch_exposes_platform_capabilities_helper(self) -> None:
        cfg = {"db": {"platform": "postgresql"}}
        capabilities = dispatch.get_platform_capabilities(cfg)
        self.assertIsInstance(capabilities, PlatformCapabilities)
        self.assertTrue(capabilities.supports_sql_evidence)

    def test_dispatch_routes_to_postgresql_adapter(self) -> None:
        cfg = {"db": {"platform": "postgresql"}}
        with patch("sqlopt.platforms.postgresql.adapter.collect_sql_evidence", return_value=({"ok": True}, {"s": 1})) as m:
            e, p = dispatch.collect_sql_evidence(cfg, "SELECT 1")
            self.assertTrue(e["ok"])
            self.assertEqual(p["s"], 1)
            m.assert_called_once()

    def test_dispatch_compare_methods(self) -> None:
        cfg = {"db": {"platform": "postgresql"}}
        with tempfile.TemporaryDirectory(prefix="sqlopt_dispatch_") as td:
            d = Path(td)
            with patch("sqlopt.platforms.postgresql.adapter.compare_plan", return_value={"checked": True}) as m1:
                out1 = dispatch.compare_plan(cfg, "SELECT 1", "SELECT 1", d)
                self.assertTrue(out1["checked"])
                m1.assert_called_once()
            with patch("sqlopt.platforms.postgresql.adapter.compare_semantics", return_value={"checked": True}) as m2:
                out2 = dispatch.compare_semantics(cfg, "SELECT 1", "SELECT 1", d)
                self.assertTrue(out2["checked"])
                m2.assert_called_once()

    def test_dispatch_rejects_unsupported_platform(self) -> None:
        with self.assertRaises(StageError) as cm:
            dispatch.collect_sql_evidence({"db": {"platform": "mysql"}}, "SELECT 1")
        self.assertEqual(cm.exception.reason_code, "UNSUPPORTED_PLATFORM")


if __name__ == "__main__":
    unittest.main()
