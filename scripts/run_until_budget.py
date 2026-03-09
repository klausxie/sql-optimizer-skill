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


@dataclass(frozen=True)
class NextInvocation:
    mode: str
    cli_args: list[str]
    recovery_cmd: str
    error_reason: str


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


def _error(
    reason_code: str,
    message: str,
    *,
    run_id: str | None = None,
    details: dict[str, Any] | None = None,
    next_mode: str | None = None,
    retryable: bool = False,
) -> None:
    out: dict[str, Any] = {
        "complete": False,
        "retryable": retryable,
        "error": {"reason_code": reason_code, "message": message},
    }
    if run_id:
        out["run_id"] = run_id
    if next_mode:
        out["next_mode"] = next_mode
    if details:
        out["details"] = details
    print(out)


def _continue_cmd(
    config: Path,
    to_stage: str,
    run_id: str,
    max_steps: int,
    max_seconds: int,
    *,
    next_stage: str | None = None,
) -> str:
    target_stage = next_stage or to_stage
    return " ".join(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--config",
            str(config),
            "--to-stage",
            target_stage,
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
    p.add_argument("--max-steps", type=int, default=0)  # 0 表示不限制
    p.add_argument("--max-seconds", type=int, default=0)  # 0 表示不限制
    return p


def _next_invocation(config_path: Path, run_id: str, status_payload: dict[str, Any]) -> NextInvocation:
    next_action = str(status_payload.get("next_action") or "resume")
    if next_action == "report-rebuild":
        recovery_cmd = (
            f"python scripts/sqlopt_cli.py run --config {config_path} --to-stage report --run-id {run_id} --max-steps 1"
        )
        return NextInvocation(
            mode="report-rebuild",
            cli_args=[
                "run",
                "--config",
                str(config_path),
                "--to-stage",
                "report",
                "--run-id",
                run_id,
                "--max-steps",
                "1",
            ],
            recovery_cmd=recovery_cmd,
            error_reason="REPORT_REBUILD_FAILED",
        )
    if next_action in {"resume", ""}:
        recovery_cmd = f"python scripts/sqlopt_cli.py resume --run-id {run_id} --max-steps 1"
        return NextInvocation(
            mode="resume",
            cli_args=["resume", "--run-id", run_id, "--max-steps", "1"],
            recovery_cmd=recovery_cmd,
            error_reason="RESUME_FAILED",
        )
    raise ValueError(f"unsupported next_action: {next_action}")


def main() -> None:
    args = _build_parser().parse_args()
    # max_steps=0 表示不限制步数, max_seconds=0 表示不限制时间
    if args.max_steps < 0:
        _error("INVALID_ARGUMENT", "max_steps must be >= 0")
        raise SystemExit(2)
    if args.max_seconds < 0:
        _error("INVALID_ARGUMENT", "max_seconds must be >= 0")
        raise SystemExit(2)

    config_path = Path(args.config).resolve()
    if not config_path.exists():
        _error(
            "CONFIG_NOT_FOUND",
            "config not found (default is ./sqlopt.yml)",
            details={"config": str(config_path)},
            retryable=False,
        )
        raise SystemExit(2)

    repo_root = _repo_root()
    run_cmd = ["run", "--config", str(config_path), "--to-stage", args.to_stage, "--max-steps", "1"]
    if args.run_id:
        run_cmd.extend(["--run-id", args.run_id])

    started = time.monotonic()
    step_calls = 0
    completion_mode = "pipeline"

    run_result = _run_cli(repo_root, *run_cmd)
    if run_result.stdout:
        print(run_result.stdout)
    run_payload = run_result.payload or {}
    run_id = str(run_payload.get("run_id") or args.run_id or "").strip()
    if not run_id:
        _error("RUN_ID_MISSING", "run command returned no run_id", details={"stdout": run_result.stdout}, retryable=False)
        raise SystemExit(2)

    if run_result.rc != 0 or "error" in run_payload:
        err = run_payload.get("error", {}) if isinstance(run_payload, dict) else {}
        _error(
            str(err.get("reason_code") or "RUN_FAILED"),
            str(err.get("message") or "run command failed"),
            run_id=run_id,
            details={"next_recovery": f"python scripts/sqlopt_cli.py resume --run-id {run_id}"},
            retryable=True,
        )
        raise SystemExit(2)

    step_calls += 1
    # 0 表示不限制时间
    deadline = started + args.max_seconds if args.max_seconds > 0 else float("inf")

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
                retryable=True,
            )
            raise SystemExit(2)

        if bool(status_payload.get("complete", False)):
            print(
                {
                    "run_id": run_id,
                    "complete": True,
                    "reason": "completed",
                    "completion_mode": completion_mode,
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
                retryable=True,
            )
            raise SystemExit(2)

        budget_next_mode = "report-rebuild" if str(status_payload.get("next_action") or "") == "report-rebuild" else "resume"
        budget_next_stage = "report" if budget_next_mode == "report-rebuild" else args.to_stage

        # 0 表示不限制步数
        if args.max_steps > 0 and step_calls >= args.max_steps:
            print(
                {
                    "run_id": run_id,
                    "complete": False,
                    "retryable": True,
                    "reason": "step_budget_exhausted",
                    "steps_executed": step_calls,
                    "next_mode": budget_next_mode,
                    "next_action": _continue_cmd(
                        config_path,
                        args.to_stage,
                        run_id,
                        args.max_steps,
                        args.max_seconds,
                        next_stage=budget_next_stage,
                    ),
                }
            )
            return

        if time.monotonic() >= deadline:
            print(
                {
                    "run_id": run_id,
                    "complete": False,
                    "retryable": True,
                    "reason": "time_budget_exhausted",
                    "steps_executed": step_calls,
                    "next_mode": budget_next_mode,
                    "next_action": _continue_cmd(
                        config_path,
                        args.to_stage,
                        run_id,
                        args.max_steps,
                        args.max_seconds,
                        next_stage=budget_next_stage,
                    ),
                }
            )
            return

        try:
            next_invocation = _next_invocation(config_path, run_id, status_payload)
        except ValueError as exc:
            _error("INVALID_STATUS", str(exc), run_id=run_id, retryable=False)
            raise SystemExit(2)
        completion_mode = next_invocation.mode if next_invocation.mode == "report-rebuild" else completion_mode

        step_result = _run_cli(repo_root, *next_invocation.cli_args)
        step_payload = step_result.payload or {}
        if step_result.stdout:
            print(step_result.stdout)

        if step_result.rc != 0 or "error" in step_payload:
            err = step_payload.get("error", {}) if isinstance(step_payload, dict) else {}
            _error(
                str(err.get("reason_code") or next_invocation.error_reason),
                str(err.get("message") or "follow-up command failed"),
                run_id=run_id,
                details={"next_recovery": next_invocation.recovery_cmd},
                next_mode=next_invocation.mode,
                retryable=True,
            )
            raise SystemExit(2)

        step_calls += 1


if __name__ == "__main__":
    main()
