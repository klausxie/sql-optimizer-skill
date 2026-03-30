from __future__ import annotations

import unittest
from unittest.mock import patch

from sqlopt.llm.provider import generate_llm_candidates


class LlmStrictFailureTest(unittest.TestCase):
    def test_opencode_failure_does_not_fallback(self) -> None:
        with patch("sqlopt.llm.provider._run_opencode", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                generate_llm_candidates(
                    "k1",
                    "SELECT * FROM users",
                    {"enabled": True, "provider": "opencode_run", "strict_required": False},
                    prompt={"sqlKey": "k1"},
                )

    def test_non_opencode_provider_still_runs(self) -> None:
        candidates, trace = generate_llm_candidates(
            "k2",
            "SELECT * FROM users",
            {"enabled": True, "provider": "heuristic"},
        )
        self.assertEqual(len(candidates), 1)
        self.assertEqual(trace.get("degrade_reason"), None)


if __name__ == "__main__":
    unittest.main()

