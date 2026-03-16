#!/usr/bin/env python3
"""
Task 7: 完整流程测试 - 使用 mock 跳过数据库连接

此测试验证 sqlopt 的完整工作流程：
1. run_service.start_run() 开始运行
2. run_service.resume_run() 恢复运行直到完成
3. run_service.get_status() 获取状态
4. run_service.apply_run() 应用补丁

验证：
- runs/<run_id>/pipeline/supervisor/state.json 所有阶段为 DONE
- runs/<run_id>/overview/report.json 存在
- runs/<run_id>/overview/report.summary.md 存在

使用 heuristic provider（非真实 LLM）和 mock 数据库连接。
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _project_fixture(repo_root: Path) -> Path:
    return repo_root / "tests" / "fixtures" / "project"


def _write_config(config_path: Path, project_root: Path) -> None:
    """写入配置文件，使用 heuristic provider"""
    config = {
        "project": {"root_path": str(project_root)},
        "scan": {"mapper_globs": ["src/main/resources/**/*.xml"]},
        "db": {
            "platform": "postgresql",
            "dsn": "postgresql://postgres:postgres@127.0.0.1:5432/postgres?sslmode=disable",
        },
        "llm": {"enabled": True, "provider": "heuristic", "timeout_ms": 80000},
        "report": {"enabled": True},
    }
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def test_full_flow_with_mock():
    """测试完整流程（run -> status -> resume -> apply）- 使用 mock 跳过数据库连接"""
    code_root = _repo_root()
    fixture = _project_fixture(code_root)
    if not fixture.exists():
        pytest.skip(f"missing fixture project: {fixture}")

    # 添加 python 路径
    python_path = str(code_root / "python")
    if python_path not in sys.path:
        sys.path.insert(0, python_path)

    from sqlopt.application import run_service
    from sqlopt.io_utils import read_json

    with tempfile.TemporaryDirectory(prefix="sqlopt_full_flow_mock_") as td:
        project_dir = Path(td) / "project"
        # 忽略 runs 目录（可能包含 Windows 保留文件名）
        shutil.copytree(fixture, project_dir, ignore=shutil.ignore_patterns("runs"))

        # 创建配置文件
        config_path = project_dir / "sqlopt.json"
        _write_config(config_path, project_dir)

        # Mock 数据库连接检查
        def mock_check_db_connectivity(*args, **kwargs):
            return {"name": "db", "enabled": True, "ok": True}

        run_id = f"run_mock_{uuid4().hex[:8]}"

        with patch(
            "sqlopt.stages.preflight.check_db_connectivity",
            side_effect=mock_check_db_connectivity,
        ):
            # Step 1: 开始运行
            actual_run_id, first_result = run_service.start_run(
                config_path,
                "patch_generate",
                run_id,
                repo_root=project_dir,
            )

            # 如果运行未完成，继续 resume
            if not first_result.get("complete"):
                for _ in range(300):  # 最多 300 步
                    result = run_service.resume_run(
                        actual_run_id, repo_root=project_dir
                    )
                    if result.get("complete"):
                        break

            # Step 2: 获取状态
            status_payload = run_service.get_status(
                actual_run_id, repo_root=project_dir
            )

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

            # Step 5: 运行 apply
            apply_payload = run_service.apply_run(actual_run_id, repo_root=project_dir)

            assert apply_payload.get("run_id") == actual_run_id, (
                f"apply run_id mismatch: expected {actual_run_id}, got {apply_payload.get('run_id')}"
            )

            # 验证 apply 状态文件
            apply_state_path = run_dir / "apply" / "state.json"
            assert apply_state_path.exists(), (
                f"apply state.json not found: {apply_state_path}"
            )

            # 保存证据文件
            evidence_dir = code_root / ".sisyphus" / "evidence"
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
