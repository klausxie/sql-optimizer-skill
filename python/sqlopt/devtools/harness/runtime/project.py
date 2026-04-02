from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .models import HarnessProjectHandle

ROOT = Path(__file__).resolve().parents[5]
FIXTURES_ROOT = ROOT / "tests" / "fixtures"
FIXTURE_PROJECT_ROOT = FIXTURES_ROOT / "projects" / "sample_project"
FIXTURE_SCENARIOS_PATH = FIXTURES_ROOT / "scenarios" / "sample_project.json"
FIXTURE_CONFIG_DIR = FIXTURES_ROOT / "configs" / "sample_project"
FIXTURE_MOCK_DIR = FIXTURES_ROOT / "mocks" / "sample_project"
FIXTURE_SCAN_SAMPLES_DIR = FIXTURES_ROOT / "scan_samples"


def copy_fixture_project(destination_root: Path, *, name: str = "sample_project") -> Path:
    project_root = destination_root / name
    shutil.copytree(FIXTURE_PROJECT_ROOT, project_root)
    return project_root


def prepare_fixture_project(
    destination_root: Path,
    *,
    name: str = "sample_project",
    mutable: bool = True,
    init_git: bool = True,
) -> HarnessProjectHandle:
    root_path = copy_fixture_project(destination_root, name=name)
    if mutable and init_git:
        subprocess.run(
            ["git", "init"],
            cwd=root_path,
            check=True,
            capture_output=True,
            text=True,
        )
    return HarnessProjectHandle(
        name=name,
        root_path=root_path,
        mutable=mutable,
        fixture_root=FIXTURE_PROJECT_ROOT,
    )
