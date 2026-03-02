from __future__ import annotations

import signal
import time
from dataclasses import dataclass
from typing import Any

from .errors import StageError


@dataclass
class StageContext:
    repo_root: str
    run_id: str
    run_dir: str
    config: dict[str, Any]


@dataclass
class StageResult:
    phase: str
    status: str
    processed_sql_key: str | None = None
    complete: bool = True


class _TimeoutError(Exception):
    pass


def _timeout_handler(_signum: int, _frame: Any) -> None:
    raise _TimeoutError("stage execution timed out")


HAS_POSIX_ALARM = all(
    hasattr(signal, name)
    for name in (
        "SIGALRM",
        "setitimer",
        "ITIMER_REAL",
    )
)


def execute_with_retry(
    phase: str,
    fn: Any,
    *,
    timeout_ms: int,
    retry_max: int,
    retry_backoff_ms: int,
) -> tuple[Any, int]:
    attempts = 0
    while True:
        attempts += 1
        old = None
        if HAS_POSIX_ALARM:
            old = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.setitimer(signal.ITIMER_REAL, max(timeout_ms, 1) / 1000.0)
        try:
            result = fn()
            return result, attempts
        except _TimeoutError as exc:
            if attempts > retry_max:
                raise StageError(f"{phase} timed out", reason_code="RUNTIME_STAGE_TIMEOUT") from exc
            time.sleep(max(retry_backoff_ms, 0) / 1000.0)
        except StageError:
            if attempts > retry_max:
                raise
            time.sleep(max(retry_backoff_ms, 0) / 1000.0)
        except Exception as exc:
            if attempts > retry_max:
                raise StageError(f"{phase} failed: {exc}", reason_code="RUNTIME_RETRY_EXHAUSTED") from exc
            time.sleep(max(retry_backoff_ms, 0) / 1000.0)
        finally:
            if HAS_POSIX_ALARM and old is not None:
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, old)
