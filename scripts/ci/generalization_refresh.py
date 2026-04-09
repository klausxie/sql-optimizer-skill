#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from sqlopt.devtools.sample_project_family_scopes import GENERALIZATION_BATCH_SCOPE_SQL_KEYS  # noqa: E402

RUN_SAMPLE_PROJECT_SCRIPT = ROOT / "scripts" / "run_sample_project.py"
DEFAULT_LLM_CASSETTE_ROOT = ROOT / "tests" / "fixtures" / "llm_cassettes"
GENERALIZATION_BATCH_NAMES = tuple(GENERALIZATION_BATCH_SCOPE_SQL_KEYS)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the generalization baseline runs for the sample project.")
    parser.add_argument(
        "--batch",
        action="append",
        choices=GENERALIZATION_BATCH_NAMES,
        default=[],
        help="Generalization batch name to rerun. Defaults to all configured batches.",
    )
    parser.add_argument(
        "--max-seconds",
        type=int,
        default=480,
        help="Per-batch execution limit passed to run_sample_project.py.",
    )
    parser.add_argument(
        "--llm-mode",
        default="replay",
        choices=("live", "record", "replay"),
        help="Override llm.mode for run_sample_project.py (default: replay).",
    )
    parser.add_argument(
        "--llm-cassette-root",
        default=str(DEFAULT_LLM_CASSETTE_ROOT),
        help="Override llm.cassette_root for run_sample_project.py.",
    )
    llm_replay_group = parser.add_mutually_exclusive_group()
    llm_replay_group.add_argument(
        "--llm-replay-strict",
        dest="llm_replay_strict",
        action="store_true",
        help="Fail on replay misses instead of falling back.",
    )
    llm_replay_group.add_argument(
        "--no-llm-replay-strict",
        dest="llm_replay_strict",
        action="store_false",
        help="Allow replay misses to be handled by the caller.",
    )
    parser.set_defaults(llm_replay_strict=True)
    parser.add_argument(
        "--llm-provider",
        help="Optional llm.provider override forwarded to run_sample_project.py.",
    )
    parser.add_argument(
        "--llm-model",
        help="Optional llm.model override forwarded to run_sample_project.py.",
    )
    return parser.parse_args()


def _selected_batches(selected: list[str]) -> list[str]:
    batches = list(selected) if selected else list(GENERALIZATION_BATCH_NAMES)
    unknown = [batch for batch in batches if batch not in GENERALIZATION_BATCH_SCOPE_SQL_KEYS]
    if unknown:
        raise ValueError(f"unknown generalization batch(es): {', '.join(sorted(unknown))}")
    return batches


def _extract_run_id(stdout: str) -> str:
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            payload = ast.literal_eval(line)
        except (SyntaxError, ValueError):
            continue
        if isinstance(payload, dict):
            run_id = payload.get("run_id")
            if isinstance(run_id, str) and run_id.strip():
                return run_id.strip()
    raise RuntimeError("could not parse run_id from sample project output")


def _llm_overlay_args(
    *,
    llm_mode: str,
    llm_cassette_root: str,
    llm_replay_strict: bool,
    llm_provider: str | None = None,
    llm_model: str | None = None,
) -> list[str]:
    args = [
        "--llm-mode",
        llm_mode,
        "--llm-cassette-root",
        str(Path(llm_cassette_root).resolve()),
    ]
    if llm_replay_strict:
        args.append("--llm-replay-strict")
    else:
        args.append("--no-llm-replay-strict")
    if llm_provider:
        args.extend(["--llm-provider", llm_provider])
    if llm_model:
        args.extend(["--llm-model", llm_model])
    return args


def _run_batch(
    batch_name: str,
    *,
    max_seconds: int,
    llm_mode: str = "replay",
    llm_cassette_root: str = str(DEFAULT_LLM_CASSETTE_ROOT),
    llm_replay_strict: bool = True,
    llm_provider: str | None = None,
    llm_model: str | None = None,
) -> str:
    proc = subprocess.run(
        [
            sys.executable,
            str(RUN_SAMPLE_PROJECT_SCRIPT),
            "--scope",
            batch_name,
            *_llm_overlay_args(
                llm_mode=llm_mode,
                llm_cassette_root=llm_cassette_root,
                llm_replay_strict=llm_replay_strict,
                llm_provider=llm_provider,
                llm_model=llm_model,
            ),
            "--max-steps",
            "0",
            "--max-seconds",
            str(max_seconds),
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        message_parts = [f"refresh batch failed: {batch_name} (exit={proc.returncode})"]
        if proc.stdout.strip():
            message_parts.append(f"stdout:\n{proc.stdout.strip()}")
        if proc.stderr.strip():
            message_parts.append(f"stderr:\n{proc.stderr.strip()}")
        raise RuntimeError("\n\n".join(message_parts))
    return _extract_run_id(proc.stdout)


def main() -> None:
    args = _parse_args()
    batches = _selected_batches(list(args.batch or []))
    payload = {"batches": {}}
    for batch_name in batches:
        payload["batches"][batch_name] = _run_batch(
            batch_name,
            max_seconds=int(args.max_seconds),
            llm_mode=args.llm_mode,
            llm_cassette_root=args.llm_cassette_root,
            llm_replay_strict=bool(args.llm_replay_strict),
            llm_provider=args.llm_provider,
            llm_model=args.llm_model,
        )
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
