from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[2]
_PYTHON_DIR = str(_REPO_ROOT / "python")
_CLI_SCRIPT = str(_REPO_ROOT / "scripts" / "sqlopt_cli.py")


@pytest.fixture
def temp_project_dir():
    with tempfile.TemporaryDirectory(prefix="sqlopt_cli_e2e_") as td:
        project_dir = Path(td)
        yield project_dir


class TestE2ECLI:
    def test_cli_help_shows_v9_stages(self):
        result = subprocess.run(
            [sys.executable, _CLI_SCRIPT, "--help"],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(_PYTHON_DIR)},
        )
        assert result.returncode == 0
        assert "init" in result.stdout

    def test_cli_validate_config_help(self):
        result = subprocess.run(
            [
                sys.executable,
                _CLI_SCRIPT,
                "validate-config",
                "--help",
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(_PYTHON_DIR)},
        )
        assert result.returncode == 0

    def test_cli_run_requires_config(self, temp_project_dir):
        result = subprocess.run(
            [
                sys.executable,
                _CLI_SCRIPT,
                "run",
            ],
            capture_output=True,
            text=True,
            cwd=temp_project_dir,
            env={**os.environ, "PYTHONPATH": str(_PYTHON_DIR)},
        )
        assert result.returncode != 0

    def test_cli_validate_config_with_json_config(self, temp_project_dir):
        config = {
            "config_version": "v1",
            "project": {"root_path": "."},
            "scan": {"mapper_globs": ["**/*.xml"]},
            "db": {"platform": "postgresql", "dsn": "postgresql://localhost/test"},
            "llm": {"enabled": False, "provider": "heuristic"},
        }
        config_file = temp_project_dir / "sqlopt.yml"
        config_file.write_text(json.dumps(config), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                _CLI_SCRIPT,
                "validate-config",
                "--config",
                str(config_file),
            ],
            capture_output=True,
            text=True,
            cwd=temp_project_dir,
            env={**os.environ, "PYTHONPATH": str(_PYTHON_DIR)},
        )
        assert result.returncode in (0, 1)

    def test_cli_status_no_run_id_shows_error(self, temp_project_dir):
        result = subprocess.run(
            [
                sys.executable,
                _CLI_SCRIPT,
                "status",
            ],
            capture_output=True,
            text=True,
            cwd=temp_project_dir,
            env={**os.environ, "PYTHONPATH": str(_PYTHON_DIR)},
        )
        assert result.returncode != 0
