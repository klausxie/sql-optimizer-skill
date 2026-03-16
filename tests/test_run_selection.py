from __future__ import annotations

import unittest

from sqlopt.application.run_selection import filter_units_by_sql_keys


def _unit(sql_key: str, statement_id: str, variant_id: str) -> dict[str, str]:
    return {
        "sqlKey": sql_key,
        "statementId": statement_id,
        "variantId": variant_id,
    }


class RunSelectionTest(unittest.TestCase):
    def test_filter_units_accepts_statement_id_when_unique(self) -> None:
        units = [
            _unit("demo.user.findUsers#v1", "findUsers", "v1"),
            _unit("demo.order.findOrders#v1", "findOrders", "v1"),
        ]

        selected, missing, ambiguous = filter_units_by_sql_keys(units, ["findUsers"])

        self.assertEqual([row["sqlKey"] for row in selected], ["demo.user.findUsers#v1"])
        self.assertEqual(missing, [])
        self.assertEqual(ambiguous, {})

    def test_filter_units_accepts_statement_id_with_variant_suffix(self) -> None:
        units = [
            _unit("demo.user.findUsers#v1", "findUsers", "v1"),
            _unit("demo.user.findUsers#v2", "findUsers", "v2"),
        ]

        selected, missing, ambiguous = filter_units_by_sql_keys(units, ["findUsers#v2"])

        self.assertEqual([row["sqlKey"] for row in selected], ["demo.user.findUsers#v2"])
        self.assertEqual(missing, [])
        self.assertEqual(ambiguous, {})

    def test_filter_units_reports_ambiguous_statement_id(self) -> None:
        units = [
            _unit("demo.user.findUsers#v1", "findUsers", "v1"),
            _unit("demo.admin.findUsers#v1", "findUsers", "v1"),
        ]

        selected, missing, ambiguous = filter_units_by_sql_keys(units, ["findUsers"])

        self.assertEqual(selected, [])
        self.assertEqual(missing, [])
        self.assertEqual(
            ambiguous,
            {
                "findUsers": [
                    "demo.user.findUsers#v1",
                    "demo.admin.findUsers#v1",
                ]
            },
        )


if __name__ == "__main__":
    unittest.main()
