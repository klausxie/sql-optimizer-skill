from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlopt.application import config_service
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
                        "  java_scanner:",
                        "    jar_path: __SCANNER_JAR__",
                        "db:",
                        "  platform: postgresql",
                        "  dsn: postgresql://user:pass@localhost:5432/demo",
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
        self.assertEqual(checks["scan.java_scanner.jar_path"]["status"], "warning")

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
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(ConfigError):
                config_service.validate_config(config)


if __name__ == "__main__":
    unittest.main()
