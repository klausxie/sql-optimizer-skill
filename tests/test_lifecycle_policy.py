from __future__ import annotations

import unittest

from sqlopt.application import lifecycle_policy


class LifecyclePolicyTest(unittest.TestCase):
    def test_advance_until_complete_returns_completed_outcome(self) -> None:
        calls: list[int] = []

        def step() -> dict[str, object]:
            calls.append(1)
            return {"complete": True, "phase": "patch"}

        outcome = lifecycle_policy.advance_until_complete(
            {"complete": False, "phase": "scan"},
            step_fn=step,
            max_steps=0,
            max_seconds=0,
            monotonic_fn=lambda: 0.0,
        )

        self.assertTrue(outcome.complete)
        self.assertFalse(outcome.retryable)
        self.assertEqual(outcome.reason, "completed")
        self.assertEqual(outcome.steps_executed, 2)
        self.assertEqual(outcome.result["phase"], "patch")
        self.assertEqual(len(calls), 1)

    def test_advance_until_complete_step_budget_exhausted_is_retryable(self) -> None:
        outcome = lifecycle_policy.advance_until_complete(
            {"complete": False, "phase": "scan"},
            step_fn=lambda: {"complete": True, "phase": "patch"},
            max_steps=1,
            max_seconds=0,
            monotonic_fn=lambda: 0.0,
        )

        self.assertFalse(outcome.complete)
        self.assertTrue(outcome.retryable)
        self.assertEqual(outcome.reason, "step_budget_exhausted")
        self.assertEqual(outcome.steps_executed, 1)

    def test_advance_until_complete_time_budget_exhausted_is_retryable(self) -> None:
        ticks = iter([0.0, 10.0])
        outcome = lifecycle_policy.advance_until_complete(
            {"complete": False, "phase": "scan"},
            step_fn=lambda: {"complete": True, "phase": "patch"},
            max_steps=0,
            max_seconds=1,
            monotonic_fn=lambda: next(ticks),
        )

        self.assertFalse(outcome.complete)
        self.assertTrue(outcome.retryable)
        self.assertEqual(outcome.reason, "time_budget_exhausted")
        self.assertEqual(outcome.steps_executed, 1)

    def test_build_progress_payload_is_compatible_for_completed_and_budget_paths(self) -> None:
        completed = lifecycle_policy.LifecycleOutcome(
            result={"complete": True, "phase": "patch"},
            steps_executed=2,
            reason="completed",
            complete=True,
            retryable=False,
        )
        payload = lifecycle_policy.build_progress_payload("run_done", completed)
        self.assertEqual(payload["run_id"], "run_done")
        self.assertTrue(payload["complete"])
        self.assertNotIn("reason", payload)
        self.assertNotIn("retryable", payload)

        budget = lifecycle_policy.LifecycleOutcome(
            result={"complete": False, "phase": "optimize"},
            steps_executed=1,
            reason="step_budget_exhausted",
            complete=False,
            retryable=True,
        )
        budget_payload = lifecycle_policy.build_progress_payload("run_demo", budget)
        self.assertEqual(budget_payload["reason"], "step_budget_exhausted")
        self.assertTrue(budget_payload["retryable"])

    def test_is_retryable_reason_helper(self) -> None:
        self.assertTrue(lifecycle_policy.is_retryable_reason("RUNTIME_RETRY_EXHAUSTED"))
        self.assertFalse(lifecycle_policy.is_retryable_reason("PREFLIGHT_CHECK_FAILED"))


if __name__ == "__main__":
    unittest.main()
