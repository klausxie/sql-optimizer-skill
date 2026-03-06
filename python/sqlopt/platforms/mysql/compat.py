from __future__ import annotations

from typing import Any

_UNSUPPORTED_MAX_EXECUTION_TIME_ERRNOS = {1064, 1193}


def _extract_errno(exc: Exception) -> int | None:
    errno = getattr(exc, "errno", None)
    if isinstance(errno, int):
        return errno

    args = getattr(exc, "args", ())
    if args and isinstance(args[0], int):
        return int(args[0])
    return None


def _is_unsupported_max_execution_time_error(exc: Exception) -> bool:
    errno = _extract_errno(exc)
    if errno in _UNSUPPORTED_MAX_EXECUTION_TIME_ERRNOS:
        return True

    text = str(exc).lower()
    if "max_execution_time" not in text:
        return False
    if "unknown system variable" in text:
        return True
    if "you have an error in your sql syntax" in text:
        return True
    return False


def set_timeout_best_effort(cur: Any, timeout_ms: int) -> bool:
    sql = f"SET SESSION MAX_EXECUTION_TIME = {max(1, int(timeout_ms))}"
    try:
        cur.execute(sql)
        return True
    except Exception as exc:
        if _is_unsupported_max_execution_time_error(exc):
            return False
        raise
