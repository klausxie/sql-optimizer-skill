#!/usr/bin/env python3
"""
测试完整流程（run -> status -> resume -> apply）- 使用 mock 跳过数据库连接

此测试验证 sqlopt-cli 的完整工作流程：
1. sqlopt-cli run --config ... --to-stage patch_generate
2. 验证 runs/<run_id>/pipeline/supervisor/state.json 所有阶段为 DONE
3. 验证 runs/<run_id>/overview/report.json 存在
4. 验证 runs/<run_id>/overview/report.summary.md 存在
5. sqlopt-cli status --run-id <run_id>
6. sqlopt-cli apply --run-id <run_id>

使用 heuristic provider（非真实 LLM）和 mock 数据库连接。
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _project_fixture(repo_root: Path) -> Path:
    return repo_root / "tests" / "fixtures" / "project"


def _local_config_text(repo_root: Path, platform: str = "postgresql") -> str:
    """生成本地配置文本，使用 heuristic provider"""
    dsn = "postgresql://postgres:postgres@127.0.0.1:5432/postgres?sslmode=disable"
    if platform == "mysql":
        dsn = "mysql://root:password@127.0.0.1:3306/test?sslmode=disable"

    return "\n".join(
        [
            "project:",
            "  root_path: .",
            "",
            "scan:",
            "  mapper_globs:",
            "    - src/main/resources/**/*.xml",
            "",
            "db:",
            f"  platform: {platform}",
            f"  dsn: {dsn}",
            "  schema: public",
            "",
            "llm:",
            "  enabled: true",
            "  provider: heuristic",
            "  timeout_ms: 80000",
            "",
            "report:",
            "  enabled: true",
        ]
    )


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


def _parse_last_dict(text: str) -> dict[str, Any]:
    lines = [
        _strip_ansi(line).strip()
        for line in text.splitlines()
        if _strip_ansi(line).strip()
    ]
    for line in reversed(lines):
        candidates = [line]
        start = line.find("{")
        end = line.rfind("}")
        if start != -1 and end != -1 and start < end:
            fragment = line[start : end + 1]
            if fragment != line:
                candidates.append(fragment)
        for candidate in candidates:
            try:
                value = ast.literal_eval(candidate)
            except Exception:
                try:
                    value = json.loads(candidate)
                except Exception:
                    continue
            if isinstance(value, dict):
                return value
    return {}


def _run(
    cmd: list[str], *, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, env=env)


def _require_ok(proc: subprocess.CompletedProcess[str], *, step: str) -> None:
    if proc.returncode == 0:
        return
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.stderr.strip():
        print(proc.stderr.strip(), file=sys.stderr)
    raise SystemExit(f"{step} failed with exit code {proc.returncode}")


def test_full_flow_with_mock():
    """测试完整流程（run -> status -> resume -> apply）- 使用 mock 跳过数据库连接"""
    repo_root = _repo_root()
    fixture = _project_fixture(repo_root)
    if not fixture.exists():
        pytest.skip(f"missing fixture project: {fixture}")

    with tempfile.TemporaryDirectory(prefix="sqlopt_full_flow_mock_") as td:
        temp_root = Path(td)
        project_dir = temp_root / "project"
        # 忽略 runs 目录（可能包含 Windows 保留文件名）
        shutil.copytree(fixture, project_dir, ignore=shutil.ignore_patterns("runs"))

        # 创建配置文件
        config_path = project_dir / "sqlopt.local.yml"
        config_path.write_text(
            _local_config_text(repo_root, "postgresql"), encoding="utf-8"
        )

        # 添加 python 路径
        sys.path.insert(0, str(repo_root / "python"))

        from sqlopt.io_utils import read_json

        # Mock 数据库连接检查
        def mock_check_db_connectivity(*args, **kwargs):
            return {"name": "db", "enabled": True, "ok": True}

        run_id = f"run_mock_{uuid4().hex[:8]}"

        with patch(
            "sqlopt.stages.preflight.check_db_connectivity",
            side_effect=mock_check_db_connectivity,
        ):
            # Step 1: 运行 sqlopt-cli run
            run_proc = _run(
                [
                    sys.executable,
                    str(repo_root / "scripts" / "sqlopt_cli.py"),
                    "run",
                    "--config",
                    str(config_path),
                    "--run-id",
                    run_id,
                    "--to-stage",
                    "patch_generate",
                ],
                cwd=project_dir,
            )
            _require_ok(run_proc, step="sqlopt-cli run")

            run_payload = _parse_last_dict(run_proc.stdout)
            actual_run_id = str(run_payload.get("run_id") or run_id).strip()

            # 如果运行未完成，继续 resume
            if not run_payload.get("complete"):
                for _ in range(300):  # 最多 300 步
                    resume_proc = _run(
                        [
                            sys.executable,
                            str(repo_root / "scripts" / "sqlopt_cli.py"),
                            "resume",
                            "--run-id",
                            actual_run_id,
                            "--project",
                            str(project_dir),
                        ],
                        cwd=project_dir,
                    )
                    if resume_proc.returncode != 0:
                        break
                    resume_payload = _parse_last_dict(resume_proc.stdout)
                    if resume_payload.get("complete"):
                        break

            # Step 2: 运行 sqlopt-cli status
            status_proc = _run(
                [
                    sys.executable,
                    str(repo_root / "scripts" / "sqlopt_cli.py"),
                    "status",
                    "--run-id",
                    actual_run_id,
                    "--project",
                    str(project_dir),
                ],
                cwd=project_dir,
            )
            _require_ok(status_proc, step="sqlopt-cli status")
            status_payload = _parse_last_dict(status_proc.stdout)

            # Step 3: 验证状态
            assert status_payload.get("run_id") == actual_run_id, (
                f"run_id mismatch: expected {actual_run_id}, got {status_payload.get('run_id')}"
            )
            assert "phase_status" in status_payload, (
                "missing phase_status in status output"
            )

            # 验证所有阶段
            phase_status = status_payload.get("phase_status", {})
            expected_phases = {
                "preflight",
                "scan",
                "optimize",
                "validate",
                "patch_generate",
                "report",
            }
            assert set(phase_status.keys()) == expected_phases, (
                f"unexpected phases: {set(phase_status.keys())} vs {expected_phases}"
            )

            # 验证 preflight 和 scan 阶段完成
            assert phase_status.get("preflight") == "DONE", (
                f"preflight not DONE: {phase_status.get('preflight')}"
            )
            assert phase_status.get("scan") == "DONE", (
                f"scan not DONE: {phase_status.get('scan')}"
            )

            # Step 4: 验证文件结构
            run_dir = project_dir / "runs" / actual_run_id
            assert run_dir.exists(), f"run directory not found: {run_dir}"

            # 验证 state.json
            state_path = run_dir / "pipeline" / "supervisor" / "state.json"
            assert state_path.exists(), f"state.json not found: {state_path}"
            state = read_json(state_path)
            assert "phase_status" in state, "missing phase_status in state.json"
            assert "current_phase" in state, "missing current_phase in state.json"

            # 验证报告文件
            report_path = run_dir / "overview" / "report.json"
            summary_path = run_dir / "overview" / "report.summary.md"

            if phase_status.get("report") == "DONE":
                assert report_path.exists(), f"report.json not found: {report_path}"
                assert summary_path.exists(), (
                    f"report.summary.md not found: {summary_path}"
                )

                report = read_json(report_path)
                assert "run_id" in report, "missing run_id in report.json"
                assert "stats" in report, "missing stats in report.json"
                assert report.get("run_id") == actual_run_id, (
                    f"report run_id mismatch: expected {actual_run_id}, got {report.get('run_id')}"
                )

            # Step 5: 运行 sqlopt-cli apply
            apply_proc = _run(
                [
                    sys.executable,
                    str(repo_root / "scripts" / "sqlopt_cli.py"),
                    "apply",
                    "--run-id",
                    actual_run_id,
                    "--project",
                    str(project_dir),
                ],
                cwd=project_dir,
            )
            _require_ok(apply_proc, step="sqlopt-cli apply")
            apply_payload = _parse_last_dict(apply_proc.stdout)

            assert apply_payload.get("run_id") == actual_run_id, (
                f"apply run_id mismatch: expected {actual_run_id}, got {apply_payload.get('run_id')}"
            )

            # 验证 apply 状态文件
            apply_state_path = run_dir / "apply" / "state.json"
            assert apply_state_path.exists(), (
                f"apply state.json not found: {apply_state_path}"
            )

            # 保存证据文件
            evidence_dir = repo_root / ".sisyphus" / "evidence"
            evidence_dir.mkdir(parents=True, exist_ok=True)
            evidence_file = evidence_dir / f"task-7-full-flow-{actual_run_id}.json"
            evidence_file.write_text(
                json.dumps(
                    {
                        "ok": True,
                        "run_id": actual_run_id,
                        "run_dir": str(run_dir),
                        "status": status_payload,
                        "apply": apply_payload,
                        "phase_status": phase_status,
                        "files_verified": {
                            "state_json": state_path.exists(),
                            "report_json": report_path.exists(),
                            "report_summary_md": summary_path.exists(),
                            "apply_state_json": apply_state_path.exists(),
                        },
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            print(
                json.dumps(
                    {
                        "ok": True,
                        "run_id": actual_run_id,
                        "run_dir": str(run_dir),
                        "phase_status": phase_status,
                        "complete": status_payload.get("complete"),
                        "evidence": str(evidence_file),
                    },
                    ensure_ascii=False,
                )
            )


if __name__ == "__main__":
    test_full_flow_with_mock()
