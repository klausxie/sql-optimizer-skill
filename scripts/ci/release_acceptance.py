#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _script_path(repo_root: Path, name: str) -> Path:
    return repo_root / "scripts" / "ci" / name


def _parse_last_dict(text: str) -> dict[str, Any]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in reversed(lines):
        try:
            value = ast.literal_eval(line)
        except Exception:
            try:
                value = json.loads(line)
            except Exception:
                continue
        if isinstance(value, dict):
            return value
    return {}


def _run_acceptance_step(repo_root: Path, script_name: str) -> dict[str, Any]:
    script = _script_path(repo_root, script_name)
    if not script.exists():
        raise SystemExit(f"missing acceptance script: {script}")
    proc = subprocess.run([sys.executable, str(script)], text=True, capture_output=True)
    if proc.returncode != 0:
        if proc.stdout.strip():
            print(proc.stdout.strip())
        if proc.stderr.strip():
            print(proc.stderr.strip(), file=sys.stderr)
        raise SystemExit(f"{script_name} failed with exit code {proc.returncode}")
    payload = _parse_last_dict(proc.stdout)
    if not payload:
        raise SystemExit(f"{script_name} produced no structured payload")
    if not bool(payload.get("ok", False)):
        raise SystemExit(f"{script_name} did not report ok=true")
    return payload


def main() -> None:
    repo_root = _repo_root()
    steps = [
        ("opencode_install_smoke", "opencode_smoke_acceptance.py"),
        ("degraded_runtime", "degraded_runtime_acceptance.py"),
        ("report_rebuild", "report_rebuild_acceptance.py"),
        ("verification_chain", "verification_chain_acceptance.py"),
    ]
    results: dict[str, Any] = {}
    for label, script_name in steps:
        results[label] = _run_acceptance_step(repo_root, script_name)
    print(json.dumps({"ok": True, "steps": results}, ensure_ascii=False))


if __name__ == "__main__":
    main()
