#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

STAGE_ORDER = ["preflight", "scan", "optimize", "validate", "patch_generate", "report"]


@dataclass
class CliResult:
    rc: int
    payload: dict[str, Any] | None
    stdout: str
    stderr: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _cli_env(repo_root: Path) -> dict[str, str]:
    env = dict(os.environ)
    py = str((repo_root / "python").resolve())
    prev = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{py}{os.pathsep}{prev}" if prev else py
    return env


def _parse_payload(stdout: str) -> dict[str, Any] | None:
    lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
    for line in reversed(lines):
        try:
            value = ast.literal_eval(line)
            if isinstance(value, dict):
                return value
        except Exception:
            pass
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                return value
        except Exception:
            pass
    return None


def _run_cli(repo_root: Path, *args: str) -> CliResult:
    proc = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "sqlopt_cli.py"), *args],
        capture_output=True,
        text=True,
        env=_cli_env(repo_root),
    )
    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    payload = _parse_payload(stdout)
    return CliResult(rc=proc.returncode, payload=payload, stdout=stdout, stderr=stderr)


def _error(reason_code: str, message: str, *, run_id: str | None = None, details: dict[str, Any] | None = None) -> None:
    out: dict[str, Any] = {
        "complete": False,
        "error": {"reason_code": reason_code, "message": message},
    }
    if run_id:
        out["run_id"] = run_id
    if details:
        out["details"] = details
    print(out)


def _continue_cmd(config: Path, to_stage: str, run_id: str, max_steps: int, max_seconds: int) -> str:
    return " ".join(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--config",
            str(config),
            "--to-stage",
            to_stage,
            "--run-id",
            run_id,
            "--max-steps",
            str(max_steps),
            "--max-seconds",
            str(max_seconds),
        ]
    )


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="sqlopt.yml")
    p.add_argument("--to-stage", default="patch_generate", choices=STAGE_ORDER)
    p.add_argument("--run-id")
    p.add_argument("--max-steps", type=int, default=200)
    p.add_argument("--max-seconds", type=int, default=95)
    return p


def main() -> None:
    args = _build_parser().parse_args()
    if args.max_steps <= 0:
        _error("INVALID_ARGUMENT", "max_steps must be > 0")
        raise SystemExit(2)
    if args.max_seconds <= 0:
        _error("INVALID_ARGUMENT", "max_seconds must be > 0")
        raise SystemExit(2)

    config_path = Path(args.config).resolve()
    if not config_path.exists():
        _error(
            "CONFIG_NOT_FOUND",
            "config not found (default is ./sqlopt.yml)",
            details={"config": str(config_path)},
        )
        raise SystemExit(2)

    repo_root = _repo_root()
    run_cmd = ["run", "--config", str(config_path), "--to-stage", args.to_stage]
    if args.run_id:
        run_cmd.extend(["--run-id", args.run_id])

    started = time.monotonic()
    step_calls = 0

    run_result = _run_cli(repo_root, *run_cmd)
    if run_result.stdout:
        print(run_result.stdout)
    run_payload = run_result.payload or {}
    run_id = str(run_payload.get("run_id") or args.run_id or "").strip()
    if not run_id:
        _error("RUN_ID_MISSING", "run command returned no run_id", details={"stdout": run_result.stdout})
        raise SystemExit(2)

    if run_result.rc != 0 or "error" in run_payload:
        err = run_payload.get("error", {}) if isinstance(run_payload, dict) else {}
        _error(
            str(err.get("reason_code") or "RUN_FAILED"),
            str(err.get("message") or "run command failed"),
            run_id=run_id,
            details={"next_recovery": f"python scripts/sqlopt_cli.py resume --run-id {run_id}"},
        )
        raise SystemExit(2)

    step_calls += 1
    deadline = started + args.max_seconds

    while True:
        status_result = _run_cli(repo_root, "status", "--run-id", run_id)
        status_payload = status_result.payload or {}
        if status_result.stdout:
            print(status_result.stdout)

        if status_result.rc != 0 or "error" in status_payload:
            err = status_payload.get("error", {}) if isinstance(status_payload, dict) else {}
            _error(
                str(err.get("reason_code") or "STATUS_FAILED"),
                str(err.get("message") or "status command failed"),
                run_id=run_id,
                details={"next_recovery": f"python scripts/sqlopt_cli.py status --run-id {run_id}"},
            )
            raise SystemExit(2)

        if bool(status_payload.get("complete", False)):
            print(
                {
                    "run_id": run_id,
                    "complete": True,
                    "reason": "completed",
                    "steps_executed": step_calls,
                    "current_phase": status_payload.get("current_phase"),
                    "remaining_statements": status_payload.get("remaining_statements"),
                }
            )
            return

        if str(status_payload.get("run_status", "")).upper() == "FAILED":
            _error(
                str(status_payload.get("last_reason_code") or "RUN_FAILED"),
                "run entered FAILED state",
                run_id=run_id,
                details={"next_recovery": f"python scripts/sqlopt_cli.py resume --run-id {run_id}"},
            )
            raise SystemExit(2)

        if step_calls >= args.max_steps:
            print(
                {
                    "run_id": run_id,
                    "complete": False,
                    "reason": "step_budget_exhausted",
                    "steps_executed": step_calls,
                    "next_action": _continue_cmd(config_path, args.to_stage, run_id, args.max_steps, args.max_seconds),
                }
            )
            return

        if time.monotonic() >= deadline:
            print(
                {
                    "run_id": run_id,
                    "complete": False,
                    "reason": "time_budget_exhausted",
                    "steps_executed": step_calls,
                    "next_action": _continue_cmd(config_path, args.to_stage, run_id, args.max_steps, args.max_seconds),
                }
            )
            return

        resume_result = _run_cli(repo_root, "resume", "--run-id", run_id)
        resume_payload = resume_result.payload or {}
        if resume_result.stdout:
            print(resume_result.stdout)

        if resume_result.rc != 0 or "error" in resume_payload:
            err = resume_payload.get("error", {}) if isinstance(resume_payload, dict) else {}
            _error(
                str(err.get("reason_code") or "RESUME_FAILED"),
                str(err.get("message") or "resume command failed"),
                run_id=run_id,
                details={"next_recovery": f"python scripts/sqlopt_cli.py resume --run-id {run_id}"},
            )
            raise SystemExit(2)

        step_calls += 1


if __name__ == "__main__":
    main()
