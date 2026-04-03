from __future__ import annotations

import unittest

from sqlopt.application.run_selection import filter_units_by_sql_keys


class RunSelectionCompatibilityTest(unittest.TestCase):
    def test_filter_units_by_sql_keys_accepts_legacy_default_variant_suffix(self) -> None:
        units = [
            {
                "sqlKey": "demo.user.advanced.listUsersFilteredAliased",
                "statementKey": "demo.user.advanced.listUsersFilteredAliased",
            }
        ]

        selected, missing = filter_units_by_sql_keys(units, ["demo.user.advanced.listUsersFilteredAliased#v17"])

        self.assertEqual(selected, units)
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
