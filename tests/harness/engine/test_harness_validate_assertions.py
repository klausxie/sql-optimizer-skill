from __future__ import annotations

import unittest

from sqlopt.devtools.harness.assertions import assert_validate_matrix_matches_scenarios
from sqlopt.devtools.harness.runtime import run_fixture_validate_harness


class HarnessValidateAssertionsTest(unittest.TestCase):
    def test_validate_assertions_accept_current_fixture_validate_harness(self) -> None:
        scenarios, _proposals, _acceptance_rows, _units_by_key, acceptance_by_key, _fragment_catalog = (
            run_fixture_validate_harness()
        )
        assert_validate_matrix_matches_scenarios(scenarios, acceptance_by_key)


if __name__ == "__main__":
    unittest.main()
