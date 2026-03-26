from __future__ import annotations

import math
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")
R = TypeVar("R")


@dataclass
class TaskResult(Generic[T]):
    item: Any
    success: bool
    result: Any
    error: str | None
    elapsed_ms: float
    attempts: int = 1


@dataclass
class BatchOptions:
    max_workers: int = 4
    max_concurrent: int = 4
    batch_size: int = 50
    timeout_per_task: int = 120
    retry_count: int = 3
    retry_delay: float = 1.0


class ConcurrentExecutor(Generic[T, R]):
    def __init__(self, options: BatchOptions | None = None):
        self.options = options or BatchOptions()
        self._executor: ThreadPoolExecutor | None = None

    def __enter__(self):
        worker_limit = max(
            1,
            min(
                self.options.max_workers,
                self.options.max_concurrent,
                self.options.batch_size,
            ),
        )
        self._executor = ThreadPoolExecutor(max_workers=worker_limit)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._executor:
            self._executor.shutdown(wait=True)
        return False

    def map(
        self, func: Callable[[T], R], items: list[T], progress_callback: Callable[[int, int], None] | None = None
    ) -> list[TaskResult[T]]:
        if not self._executor:
            raise RuntimeError("ConcurrentExecutor must be used as context manager")
        if not items:
            return []

        total = len(items)
        results_by_index: list[TaskResult[T] | None] = [None] * total
        completed = 0

        batch_size = max(1, self.options.batch_size)
        pending_limit = max(
            1,
            min(
                self.options.max_concurrent,
                self.options.max_workers,
                batch_size,
            ),
        )

        for batch_start in range(0, total, batch_size):
            batch_items = items[batch_start : batch_start + batch_size]
            next_batch_index = 0
            pending: dict[Future[TaskResult[T]], int] = {}

            while next_batch_index < len(batch_items) or pending:
                while next_batch_index < len(batch_items) and len(pending) < pending_limit:
                    global_index = batch_start + next_batch_index
                    item = batch_items[next_batch_index]
                    future = self._executor.submit(self._execute_task, func, item)
                    pending[future] = global_index
                    next_batch_index += 1

                done, _not_done = wait(tuple(pending.keys()), return_when=FIRST_COMPLETED)
                for future in done:
                    result_index = pending.pop(future)
                    results_by_index[result_index] = future.result()
                    completed += 1
                    if progress_callback:
                        progress_callback(completed, total)

        return [result for result in results_by_index if result is not None]

    def _execute_task(self, func: Callable[[T], R], item: T) -> TaskResult[T]:
        timeout_seconds = max(float(self.options.timeout_per_task), 0.0)
        attempts_allowed = max(1, self.options.retry_count + 1)
        last_error: str | None = None
        last_elapsed_ms = 0.0

        for attempt in range(1, attempts_allowed + 1):
            started_at = time.perf_counter()
            try:
                result = func(item)
                last_elapsed_ms = (time.perf_counter() - started_at) * 1000.0
                if timeout_seconds > 0 and last_elapsed_ms > timeout_seconds * 1000.0:
                    last_error = self._format_timeout_error(timeout_seconds, last_elapsed_ms)
                else:
                    return TaskResult(
                        item=item,
                        success=True,
                        result=result,
                        error=None,
                        elapsed_ms=last_elapsed_ms,
                        attempts=attempt,
                    )
            except Exception as exc:  # noqa: BLE001
                last_elapsed_ms = (time.perf_counter() - started_at) * 1000.0
                last_error = str(exc)

            if attempt < attempts_allowed:
                delay_seconds = self._retry_delay_for_attempt(attempt)
                if delay_seconds > 0:
                    time.sleep(delay_seconds)

        return TaskResult(
            item=item,
            success=False,
            result=None,
            error=last_error,
            elapsed_ms=last_elapsed_ms,
            attempts=attempts_allowed,
        )

    def _retry_delay_for_attempt(self, attempt: int) -> float:
        base_delay = max(float(self.options.retry_delay), 0.0)
        if base_delay == 0:
            return 0.0
        return base_delay * math.pow(2, attempt - 1)

    def _format_timeout_error(self, timeout_seconds: float, elapsed_ms: float) -> str:
        timeout_label = (
            f"{int(timeout_seconds)}s"
            if float(timeout_seconds).is_integer()
            else f"{timeout_seconds:.3f}s"
        )
        return f"task exceeded timeout {timeout_label} (elapsed={elapsed_ms:.1f}ms)"
