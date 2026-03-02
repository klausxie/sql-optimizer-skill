from __future__ import annotations

import locale
import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def decode_bytes(raw: bytes | None) -> str:
    data = raw or b""
    if not data:
        return ""
    candidates = ["utf-8", locale.getpreferredencoding(False), "gb18030"]
    seen: set[str] = set()
    for enc in candidates:
        if not enc or enc in seen:
            continue
        seen.add(enc)
        try:
            return data.decode(enc, errors="strict")
        except Exception:
            continue
    return data.decode("utf-8", errors="replace")


def run_capture_text(
    cmd: list[str],
    *,
    timeout_s: float | None = None,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
) -> CommandResult:
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=False,
        timeout=timeout_s,
        env=env,
        cwd=cwd,
    )
    return CommandResult(
        returncode=int(proc.returncode),
        stdout=decode_bytes(proc.stdout if isinstance(proc.stdout, bytes) else None),
        stderr=decode_bytes(proc.stderr if isinstance(proc.stderr, bytes) else None),
    )
