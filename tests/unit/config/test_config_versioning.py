from __future__ import annotations

import unittest

from sqlopt.configuration.versioning import apply_config_version_migration
from sqlopt.errors import ConfigError


class ConfigVersioningTest(unittest.TestCase):
    def test_apply_config_version_migration_normalizes_alias(self) -> None:
        cfg = apply_config_version_migration({"config_version": "1.0", "project": {}})
        self.assertEqual(cfg["config_version"], "v1")

    def test_apply_config_version_migration_rejects_unknown(self) -> None:
        with self.assertRaises(ConfigError):
            apply_config_version_migration({"config_version": "v2"})


if __name__ == "__main__":
    unittest.main()

