from __future__ import annotations

import unittest

from sqlopt.utils import statement_key, statement_key_from_row


class SqlKeyUtilsTest(unittest.TestCase):
    def test_statement_key_keeps_plain_statement_identity(self) -> None:
        self.assertEqual(statement_key("demo.user.findUsers"), "demo.user.findUsers")

    def test_statement_key_strips_variant_suffix_when_present(self) -> None:
        self.assertEqual(statement_key("demo.user.findUsers#v2"), "demo.user.findUsers")

    def test_statement_key_from_row_prefers_explicit_statement_key(self) -> None:
        self.assertEqual(
            statement_key_from_row({"statementKey": "demo.user.findUsers", "sqlKey": "demo.user.findUsers#v9"}),
            "demo.user.findUsers",
        )


if __name__ == "__main__":
    unittest.main()
