"""Tests for concurrent execution helpers."""

from __future__ import annotations

import threading
import time

from sqlopt.common.concurrent import BatchOptions, ConcurrentExecutor


def test_concurrent_executor_preserves_input_order_and_respects_limit() -> None:
    counters = {
        "active": 0,
        "max_active": 0,
    }
    lock = threading.Lock()

    def work(item: int) -> int:
        with lock:
            counters["active"] += 1
            counters["max_active"] = max(counters["max_active"], counters["active"])
        time.sleep(0.02)
        with lock:
            counters["active"] -= 1
        return item * 2

    options = BatchOptions(max_workers=8, max_concurrent=2, batch_size=3, timeout_per_task=5)
    with ConcurrentExecutor(options) as executor:
        results = executor.map(work, [1, 2, 3, 4, 5])

    assert [result.result for result in results] == [2, 4, 6, 8, 10]
    assert counters["max_active"] <= 2


def test_concurrent_executor_retries_failed_tasks() -> None:
    attempts: dict[int, int] = {}

    def flaky(item: int) -> int:
        attempts[item] = attempts.get(item, 0) + 1
        if attempts[item] < 2:
            raise RuntimeError("temporary failure")
        return item + 1

    options = BatchOptions(
        max_workers=2,
        max_concurrent=2,
        batch_size=2,
        timeout_per_task=5,
        retry_count=1,
        retry_delay=0,
    )
    with ConcurrentExecutor(options) as executor:
        results = executor.map(flaky, [1, 2])

    assert [result.success for result in results] == [True, True]
    assert [result.attempts for result in results] == [2, 2]
    assert [result.result for result in results] == [2, 3]


def test_concurrent_executor_marks_timeout_like_completion_as_failure() -> None:
    def slow(item: int) -> int:
        time.sleep(0.05)
        return item

    options = BatchOptions(
        max_workers=1,
        max_concurrent=1,
        batch_size=1,
        timeout_per_task=0.01,
        retry_count=0,
        retry_delay=0,
    )
    with ConcurrentExecutor(options) as executor:
        results = executor.map(slow, [1])

    assert len(results) == 1
    assert results[0].success is False
    assert "timeout" in (results[0].error or "")
