#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _env(repo_root: Path) -> dict[str, str]:
    env = dict(os.environ)
    py = str((repo_root / "python").resolve())
    prev = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{py}{os.pathsep}{prev}" if prev else py
    return env


def _parse_dict_payload(text: str) -> dict:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for line in reversed(lines):
        try:
            val = ast.literal_eval(line)
            if isinstance(val, dict):
                return val
        except Exception:
            pass
        try:
            val = json.loads(line)
            if isinstance(val, dict):
                return val
        except Exception:
            pass
    return {}


def _resolve_run(repo_root: Path, run_id: str | None, project: str) -> tuple[str, Path]:
    cmd = [sys.executable, str(repo_root / "scripts" / "resolve_run_id.py")]
    if run_id:
        cmd.extend(["--run-id", run_id])
    cmd.extend(["--project", project, "--print-run-dir"])
    proc = subprocess.run(cmd, capture_output=True, text=True, env=_env(repo_root))
    if proc.returncode != 0:
        if proc.stdout.strip():
            print(proc.stdout.strip())
        if proc.stderr.strip():
            print(proc.stderr.strip(), file=sys.stderr)
        raise SystemExit(proc.returncode)
    payload = _parse_dict_payload(proc.stdout)
    rid = str(payload.get("run_id", "")).strip()
    run_dir = Path(str(payload.get("run_dir", ""))).resolve()
    if not rid or not str(run_dir):
        print({"error": {"reason_code": "RUN_RESOLVE_FAILED", "message": "failed to parse resolved run metadata"}})
        raise SystemExit(2)
    return rid, run_dir


def _ensure_cli_index(repo_root: Path, run_id: str, run_dir: Path) -> None:
    index_path = repo_root / ".sqlopt-run-index.json"
    data: dict[str, dict] = {}
    if index_path.exists():
        try:
            raw = json.loads(index_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data = raw
        except Exception:
            data = {}
    data[run_id] = {"run_dir": str(run_dir)}
    index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["status", "resume", "apply"])
    p.add_argument("--run-id")
    p.add_argument("--project", default=".")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    repo_root = _repo_root()
    rid, run_dir = _resolve_run(repo_root, args.run_id, args.project)
    _ensure_cli_index(repo_root, rid, run_dir)
    cmd = [sys.executable, str(repo_root / "scripts" / "sqlopt_cli.py"), args.command, "--run-id", rid]
    proc = subprocess.run(cmd, env=_env(repo_root), text=True)
    raise SystemExit(proc.returncode)


if __name__ == "__main__":
    main()
