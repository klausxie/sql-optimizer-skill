from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


SKILL_NAME = "sql-optimizer"


def home_dir() -> Path:
    raw = os.environ.get("HOME") or os.environ.get("USERPROFILE")
    if raw:
        return Path(raw).expanduser().resolve()
    return Path.home().resolve()


def opencode_home() -> Path:
    return home_dir() / ".opencode"


def is_windows() -> bool:
    return platform.system().lower().startswith("win")


def skill_dir() -> Path:
    return opencode_home() / "skills" / SKILL_NAME


def commands_dir() -> Path:
    return opencode_home() / "commands"


def runtime_python(root_dir: Path) -> Path:
    runtime_base = (root_dir / "runtime") if (root_dir / "runtime" / "python").exists() else root_dir
    return runtime_base / "python"


def find_skill_source(root_dir: Path) -> Path:
    candidate = root_dir / "skills" / SKILL_NAME
    if candidate.exists():
        return candidate
    fallback = root_dir / "skills"
    if fallback.exists() and (fallback / "SKILL.md").exists():
        return fallback
    raise FileNotFoundError(f"missing skill source under {root_dir / 'skills'}")


def runtime_base(root_dir: Path) -> Path:
    if (root_dir / "runtime" / "python").exists():
        return root_dir / "runtime"
    return root_dir


def venv_python(runtime_dir: Path) -> Path:
    if is_windows():
        return runtime_dir / ".venv" / "Scripts" / "python.exe"
    return runtime_dir / ".venv" / "bin" / "python"


def ensure_pythonpath_for_install_script(script_dir: Path) -> None:
    root_dir = script_dir.parent
    candidates = [root_dir / "python", root_dir / "runtime" / "python"]
    for path in candidates:
        if path.exists():
            sys.path.insert(0, str(path))
            return
    raise SystemExit("cannot locate python runtime (expected ./python or ./runtime/python)")


def run_cmd(cmd: list[str], *, quiet: bool = False) -> None:
    kwargs = {"check": True}
    if quiet:
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.DEVNULL
    subprocess.run(cmd, **kwargs)


def normalize_jar_path_for_yaml(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def replace_template_var(template_text: str, key: str, value: str) -> str:
    return template_text.replace(key, value)


def write_cli_wrapper(skill_root: Path) -> Path:
    bin_dir = skill_root / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    if is_windows():
        wrapper = bin_dir / "sqlopt-cli.cmd"
        wrapper.write_text(
            "\n".join(
                [
                    "@echo off",
                    "setlocal",
                    "set \"ROOT_DIR=%~dp0..\\runtime\"",
                    "set \"PYTHONPATH=%ROOT_DIR%\\python\"",
                    "\"%ROOT_DIR%\\.venv\\Scripts\\python.exe\" \"%ROOT_DIR%\\scripts\\sqlopt_cli.py\" %*",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return wrapper
    wrapper = bin_dir / "sqlopt-cli"
    wrapper.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                f"ROOT_DIR=\"{str((skill_root / 'runtime').resolve())}\"",
                "export PYTHONPATH=\"$ROOT_DIR/python\"",
                "exec \"$ROOT_DIR/.venv/bin/python\" \"$ROOT_DIR/scripts/sqlopt_cli.py\" \"$@\"",
                "",
            ]
        ),
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    return wrapper


def cli_run_command(wrapper: Path, *args: str) -> list[str]:
    if is_windows():
        return ["cmd", "/c", str(wrapper), *args]
    return [str(wrapper), *args]


def safe_rmtree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
