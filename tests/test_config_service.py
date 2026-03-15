from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlopt.application import config_service
from sqlopt.errors import StageError
from sqlopt.errors import ConfigError


class ConfigServiceTest(unittest.TestCase):
    def test_validate_config_reports_successful_checks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_config_service_") as td:
            root = Path(td)
            mapper = root / "src" / "main" / "resources" / "demo" / "UserMapper.xml"
            mapper.parent.mkdir(parents=True, exist_ok=True)
            mapper.write_text("<mapper />", encoding="utf-8")
            config = root / "sqlopt.yml"
            config.write_text(
                "\n".join(
                    [
                        "project:",
                        "  root_path: .",
                        "scan:",
                        "  mapper_globs:",
                        "    - src/main/resources/**/*.xml",
                        "db:",
                        "  platform: postgresql",
                        "  dsn: postgresql://user:pass@localhost:5432/demo",
                        "llm:",
                        "  provider: heuristic",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            results = config_service.validate_config(config)

        self.assertTrue(results["valid"])
        checks = {row["field"]: row for row in results["checks"]}
        self.assertEqual(checks["project.root_path"]["status"], "ok")
        self.assertEqual(checks["db.platform"]["status"], "ok")
        self.assertEqual(checks["scan.mapper_globs"]["status"], "ok")

    def test_validate_config_accepts_mysql_platform(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_config_invalid_") as td:
            config = Path(td) / "sqlopt.yml"
            config.write_text(
                "\n".join(
                    [
                        "project:",
                        "  root_path: .",
                        "scan:",
                        "  mapper_globs:",
                        "    - src/main/resources/**/*.xml",
                        "db:",
                        "  platform: mysql",
                        "  dsn: mysql://user:pass@localhost:3306/demo",
                        "llm:",
                        "  provider: heuristic",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            results = config_service.validate_config(config)

        self.assertTrue(results["valid"])
        checks = {row["field"]: row for row in results["checks"]}
        self.assertEqual(checks["db.platform"]["status"], "ok")

    def test_validate_config_raises_on_invalid_platform(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_config_invalid_") as td:
            config = Path(td) / "sqlopt.yml"
            config.write_text(
                "\n".join(
                    [
                        "project:",
                        "  root_path: .",
                        "scan:",
                        "  mapper_globs:",
                        "    - src/main/resources/**/*.xml",
                        "db:",
                        "  platform: sqlite",
                        "  dsn: sqlite:///tmp/demo.db",
                        "llm:",
                        "  provider: heuristic",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(ConfigError):
                config_service.validate_config(config)

    def test_validate_config_marks_placeholder_dsn_invalid(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_config_placeholder_") as td:
            config = Path(td) / "sqlopt.yml"
            config.write_text(
                "\n".join(
                    [
                        "project:",
                        "  root_path: .",
                        "scan:",
                        "  mapper_globs:",
                        "    - src/main/resources/**/*.xml",
                        "db:",
                        "  platform: postgresql",
                        "  dsn: postgresql://<user>:<password>@127.0.0.1:5432/<database>?sslmode=disable",
                        "llm:",
                        "  provider: heuristic",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            results = config_service.validate_config(config)

        self.assertFalse(results["valid"])
        checks = {row["field"]: row for row in results["checks"]}
        self.assertEqual(checks["db.dsn"]["status"], "invalid")

    def test_validate_config_can_check_connectivity(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sqlopt_config_connectivity_") as td:
            config = Path(td) / "sqlopt.yml"
            config.write_text(
                "\n".join(
                    [
                        "project:",
                        "  root_path: .",
                        "scan:",
                        "  mapper_globs:",
                        "    - src/main/resources/**/*.xml",
                        "db:",
                        "  platform: mysql",
                        "  dsn: mysql://user:pass@127.0.0.1:3306/demo",
                        "llm:",
                        "  provider: heuristic",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch(
                "sqlopt.application.config_service.check_db_connectivity",
                return_value={"ok": False, "error": "Access denied", "reason_code": "PREFLIGHT_DB_UNREACHABLE"},
            ):
                results = config_service.validate_config(config, check_connectivity=True)

        self.assertFalse(results["valid"])
        checks = {row["field"]: row for row in results["checks"]}
        self.assertEqual(checks["db.connection"]["status"], "error")
        self.assertIn("Access denied", checks["db.connection"]["message"])

    def test_prepare_runtime_prerequisites_marks_db_unreachable_when_fallback_allowed(self) -> None:
        config = {
            "db": {"platform": "postgresql", "dsn": "postgresql://user:pass@127.0.0.1:5432/demo"},
            "validate": {"allow_db_unreachable_fallback": True},
        }

        with patch(
            "sqlopt.application.config_service.check_db_connectivity",
            return_value={"ok": False, "error": "connection refused", "reason_code": "PREFLIGHT_DB_UNREACHABLE"},
        ):
            result = config_service.prepare_runtime_prerequisites(config, to_stage="validate")

        self.assertTrue(result["requires_db"])
        self.assertFalse(result["db_reachable"])
        self.assertIn("connection refused", result["warning"])
        self.assertFalse(config["validate"]["db_reachable"])

    def test_prepare_runtime_prerequisites_rejects_placeholder_dsn_for_db_stage(self) -> None:
        config = {
            "db": {"platform": "postgresql", "dsn": "postgresql://<user>:<password>@127.0.0.1:5432/<database>?sslmode=disable"},
            "validate": {"allow_db_unreachable_fallback": True},
        }

        with self.assertRaises(StageError) as ctx:
            config_service.prepare_runtime_prerequisites(config, to_stage="report")

        self.assertEqual(ctx.exception.reason_code, "DB_CONNECTION_FAILED")
        self.assertIn("placeholders", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
