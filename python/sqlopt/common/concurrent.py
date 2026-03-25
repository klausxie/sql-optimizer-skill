from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar, Any
import time

T = TypeVar("T")
R = TypeVar("R")


@dataclass
class TaskResult(Generic[T]):
    item: Any
    success: bool
    result: Any
    error: str | None
    elapsed_ms: float


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
        self._executor = ThreadPoolExecutor(max_workers=self.options.max_workers)
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

        results: list[TaskResult[T]] = []
        future_to_item: dict[Future, T] = {}

        for item in items:
            future = self._executor.submit(func, item)
            future_to_item[future] = item

        completed = 0
        total = len(items)

        for future in as_completed(future_to_item):
            item = future_to_item[future]
            start_time = time.perf_counter()

            try:
                result = future.result(timeout=self.options.timeout_per_task)
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                results.append(TaskResult(item=item, success=True, result=result, error=None, elapsed_ms=elapsed_ms))
            except Exception as e:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                results.append(TaskResult(item=item, success=False, result=None, error=str(e), elapsed_ms=elapsed_ms))

            completed += 1
            if progress_callback:
                progress_callback(completed, total)

        return results
