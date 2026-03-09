#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def _bootstrap() -> None:
    script_dir = Path(__file__).resolve().parent
    root_dir = script_dir.parent
    candidates = [root_dir / "python", root_dir / "runtime" / "python"]
    for path in candidates:
        if path.exists():
            sys.path.insert(0, str(path))
            return
    raise SystemExit("cannot locate python runtime (expected ./python or ./runtime/python)")


_bootstrap()

from sqlopt.install_support import (  # noqa: E402
    SKILL_NAME,
    cli_run_command,
    commands_dir,
    find_skill_source,
    is_windows,
    normalize_jar_path_for_yaml,
    opencode_home,
    replace_template_var,
    run_cmd,
    runtime_base,
    safe_rmtree,
    skill_dir,
    venv_python,
    write_cli_wrapper,
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--project", default=".")
    p.add_argument("--force", action="store_true")
    p.add_argument("--verify", action="store_true", help="verify installed CLI and PATH only")
    p.add_argument("--no-auto-path", action="store_true", help="skip automatic PATH update during install")
    return p.parse_args()


def _cli_wrapper_path(target_skill: Path) -> Path:
    return target_skill / "bin" / ("sqlopt-cli.cmd" if is_windows() else "sqlopt-cli")


def _normalize_path_text(raw_path: str, *, windows: bool) -> str:
    clean = raw_path.strip().strip("\"").strip("'")
    if not clean:
        return ""
    normalized = os.path.normpath(clean)
    if windows:
        normalized = normalized.lower()
    return normalized.rstrip("\\/")


def _is_dir_on_path(target_dir: Path, env_path: str | None = None) -> bool:
    windows = is_windows()
    path_value = env_path if env_path is not None else os.environ.get("PATH", "")
    target_norm = _normalize_path_text(str(target_dir), windows=windows)
    if not target_norm:
        return False
    separator = ";" if windows else os.pathsep
    for entry in path_value.split(separator):
        if _normalize_path_text(entry, windows=windows) == target_norm:
            return True
    return False


def _prepend_path_entry(path_value: str, entry: Path, *, windows: bool) -> str:
    separator = ";" if windows else os.pathsep
    entries = [item for item in path_value.split(separator) if item.strip()]
    entry_text = str(entry)
    target_norm = _normalize_path_text(entry_text, windows=windows)
    for item in entries:
        if _normalize_path_text(item, windows=windows) == target_norm:
            return separator.join(entries)
    return separator.join([entry_text, *entries]).strip(separator)


def _choose_shell_rc_file(home: Path, shell: str) -> Path:
    shell_name = Path(shell).name.lower()
    if "zsh" in shell_name:
        return home / ".zshrc"
    if "bash" in shell_name:
        return home / ".bashrc"
    zsh_rc = home / ".zshrc"
    if zsh_rc.exists():
        return zsh_rc
    return home / ".bashrc"


def _auto_add_path_windows(bin_dir: Path) -> tuple[bool, str]:
    try:
        import winreg  # type: ignore
    except Exception as exc:
        return False, f"winreg unavailable: {exc}"

    key = None
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            "Environment",
            0,
            winreg.KEY_READ | winreg.KEY_WRITE,
        )
        try:
            current_user_path, _ = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current_user_path = ""

        updated_user_path = _prepend_path_entry(str(current_user_path or ""), bin_dir, windows=True)
        if updated_user_path != str(current_user_path or ""):
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, updated_user_path)

        current_process = os.environ.get("PATH", "")
        os.environ["PATH"] = _prepend_path_entry(current_process, bin_dir, windows=True)
        return True, "updated user PATH in registry"
    except Exception as exc:
        return False, str(exc)
    finally:
        if key is not None:
            winreg.CloseKey(key)


def _auto_add_path_unix(bin_dir: Path) -> tuple[bool, str]:
    home = Path.home()
    rc_file = _choose_shell_rc_file(home, os.environ.get("SHELL", ""))
    entry_text = str(bin_dir)
    export_line = f'export PATH="{entry_text}:$PATH"'
    try:
        existing = rc_file.read_text(encoding="utf-8") if rc_file.exists() else ""
        if entry_text not in existing:
            prefix = "" if existing.endswith("\n") or not existing else "\n"
            block = (
                f"{prefix}# sql-optimizer skill\n"
                f"{export_line}\n"
            )
            rc_file.parent.mkdir(parents=True, exist_ok=True)
            with rc_file.open("a", encoding="utf-8") as fh:
                fh.write(block)

        current_process = os.environ.get("PATH", "")
        os.environ["PATH"] = _prepend_path_entry(current_process, bin_dir, windows=False)
        return True, f"updated {rc_file}"
    except Exception as exc:
        return False, str(exc)


def _auto_add_path(bin_dir: Path) -> tuple[bool, str]:
    if is_windows():
        return _auto_add_path_windows(bin_dir)
    return _auto_add_path_unix(bin_dir)


def _print_path_hint(bin_dir: Path, *, auto_add: bool) -> bool:
    print(f"path entry: {bin_dir}")
    if _is_dir_on_path(bin_dir):
        print(f"path: ok ({bin_dir})")
        return True

    print(f"path: missing ({bin_dir})")
    if auto_add:
        ok, detail = _auto_add_path(bin_dir)
        if ok:
            print(f"path auto: ok ({detail})")
        else:
            print(f"path auto: failed ({detail})")
        if _is_dir_on_path(bin_dir):
            print(f"path: ok ({bin_dir})")
            return True

    if is_windows():
        escaped = str(bin_dir).replace("'", "''")
        print("add to PATH parameter:")
        print(f"  {bin_dir}")
        print("add to PATH (PowerShell current session):")
        print(f"  $env:Path = \"{bin_dir};$env:Path\"")
        print("add to PATH (PowerShell persistent, new terminals):")
        print("  $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')")
        print(f"  [Environment]::SetEnvironmentVariable('Path', '{escaped};' + $userPath, 'User')")
        print("then reopen PowerShell")
        print("cmd current session:")
        print(f"  set PATH={bin_dir};%PATH%")
        return False

    shell = os.environ.get("SHELL", "")
    rc_file = "~/.zshrc" if shell.endswith("zsh") else "~/.bashrc"
    print("add to PATH parameter:")
    print(f"  {bin_dir}")
    print(f"add to PATH ({rc_file}):")
    print(f"  echo 'export PATH=\"{bin_dir}:$PATH\"' >> {rc_file}")
    print(f"  source {rc_file}")
    return False


def _run_cli_self_check(wrapper: Path) -> tuple[bool, str]:
    if not wrapper.exists():
        return False, f"wrapper missing: {wrapper}"
    cmd = cli_run_command(wrapper, "--help")
    try:
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=20)
    except (FileNotFoundError, OSError) as exc:
        return False, f"runtime missing: {exc}"
    except subprocess.TimeoutExpired:
        return False, "self-check timeout (>20s)"
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip() or f"exit code {proc.returncode}"
        return False, detail
    first_line = next((line.strip() for line in (proc.stdout or "").splitlines() if line.strip()), "ok")
    return True, first_line


def _verify_installed_cli(target_skill: Path) -> int:
    wrapper = _cli_wrapper_path(target_skill)
    print(f"verify skill: {target_skill}")
    print(f"verify cli: {wrapper}")
    path_ok = _print_path_hint(wrapper.parent, auto_add=False)
    cli_ok, detail = _run_cli_self_check(wrapper)
    if cli_ok:
        print(f"self-check: ok ({detail})")
    else:
        print(f"self-check: failed ({detail})")
    if path_ok and cli_ok:
        print("verify result: OK (global command available)")
        return 0
    if cli_ok:
        print("verify result: PARTIAL (runtime ok, PATH missing)")
        return 1
    print("verify result: FAILED")
    return 1


def _copy_runtime(root_dir: Path, target_skill: Path) -> None:
    target_runtime = target_skill / "runtime"
    target_runtime.mkdir(parents=True, exist_ok=True)
    base = runtime_base(root_dir)
    for name in ["python", "scripts", "contracts", "java"]:
        src = base / name
        if not src.exists():
            raise SystemExit(f"missing runtime folder: {src}")
        shutil.copytree(src, target_runtime / name, dirs_exist_ok=True)
    pyproject = base / "pyproject.toml"
    if pyproject.exists():
        shutil.copy2(pyproject, target_runtime / "pyproject.toml")
    install_dir = target_runtime / "install"
    install_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root_dir / "install" / "requirements.txt", install_dir / "requirements.txt")


def _get_python_command(target_skill: Path) -> str:
    """Get the Python command path for the target skill's venv."""
    if sys.platform.startswith("win"):
        return str(target_skill / 'runtime' / '.venv' / 'Scripts' / 'python.exe')
    else:
        return str(target_skill / 'runtime' / '.venv' / 'bin' / 'python')


def _generate_command_doc(
    description: str,
    exec_command: str,
    *,
    usage_hint: str | None = None,
    examples: list[str] | None = None,
) -> str:
    """Generate markdown template for an OpenCode command.

    The template is written as explicit tool instructions so the model executes
    the command directly instead of asking follow-up questions.
    """
    lines = [
        "---",
        f"description: {description}",
        "---",
        "",
        "# 执行指令",
        "",
        "你是命令执行器。遵循以下规则：",
        "",
        "1. **立即执行**：不要调用 skill 工具，不要读取/修改文件，不要先提问",
        "2. **单次调用**：你必须立刻调用一次 bash 工具，且只调用这一次。",
        "3. **参数处理**：当使用 `$ARGUMENTS` 时，必须按原样直接拼接，不要整体加引号。",
        "",
        "## 执行命令",
        "",
        "- 当 `$ARGUMENTS` 为空时，执行：",
        f"  `{exec_command}`",
        "",
        "- 当 `$ARGUMENTS` 非空时，执行：",
        f"  `{exec_command} $ARGUMENTS`",
        "",
        "## 输出规则",
        "",
        "命令结束后，仅返回 bash 的原始输出。",
    ]
    if usage_hint:
        lines.extend([
            "",
            "## 常用参数",
            "",
            f"{usage_hint}",
        ])
    if examples:
        lines.extend([
            "",
            "## 使用示例",
            "",
        ])
        for example in examples:
            lines.append(f"- {example}")
    lines.append("")
    return "\n".join(lines)


def _retire_legacy_skill_backups(skills_root: Path) -> int:
    """Disable legacy backup skills under ~/.opencode/skills.

    OpenCode scans folders under ~/.opencode/skills and treats each SKILL.md as
    an active skill. Historical backup folders like `sql-optimizer.bak.*` may
    shadow the latest version and cause command routing to stale instructions.
    We keep backup files but disable skill discovery by renaming SKILL.md.
    """
    retired = 0
    for backup in sorted(skills_root.glob(f"{SKILL_NAME}.bak.*")):
        if not backup.is_dir():
            continue
        marker = backup / "SKILL.md"
        if not marker.exists():
            continue
        disabled = backup / "SKILL.md.disabled"
        if disabled.exists():
            disabled.unlink()
        marker.rename(disabled)
        retired += 1
    return retired


def _write_commands(target_skill: Path) -> None:
    """Generate OpenCode command documentation files.

    This function creates markdown files for each SQL Optimizer command
    that can be invoked through OpenCode. The commands are defined in a
    data-driven way to reduce duplication and improve maintainability.
    """
    cmd_dir = commands_dir()
    cmd_dir.mkdir(parents=True, exist_ok=True)

    # Get paths
    py_cmd = _get_python_command(target_skill)
    run_budget_script = str(target_skill / 'runtime' / 'scripts' / 'run_until_budget.py')
    resolved_id_script = str(target_skill / 'runtime' / 'scripts' / 'run_with_resolved_id.py')

    # Define all commands in a structured way
    commands = [
        {
            "name": "sql-optimizer-run",
            "description": "为项目执行一次 SQL 优化时间片（单次调用不保证跑完）",
            "exec_command": f"{py_cmd} {run_budget_script}",
            "usage_hint": "--config ./sqlopt.yml --to-stage patch_generate --run-id run_xxx --max-steps 200 --max-seconds 95",
            "examples": [
                "开始运行直到完成：--config ./sqlopt.yml",
                "继续指定运行直到完成：--config ./sqlopt.yml --run-id run_xxx",
            ],
        },
        {
            "name": "sql-optimizer-status",
            "description": "查询优化运行状态和进度（省略 run-id 时使用最近一次运行）",
            "exec_command": f"{py_cmd} {resolved_id_script} status",
            "usage_hint": "--project . [--run-id run_xxx]",
            "examples": [
                "查看最近运行：--project .",
                "查看指定运行：--project . --run-id run_xxx",
            ],
        },
        {
            "name": "sql-optimizer-resume",
            "description": "继续执行未完成的优化运行直到完成或失败（省略 run-id 时使用最近一次运行）",
            "exec_command": f"{py_cmd} {run_budget_script}",
            "usage_hint": "--config ./sqlopt.yml [--run-id run_xxx] --max-seconds 95",
            "examples": [
                "继续最近运行直到完成：--config ./sqlopt.yml",
                "继续指定运行直到完成：--config ./sqlopt.yml --run-id run_xxx",
            ],
        },
        {
            "name": "sql-optimizer-apply",
            "description": "应用生成的 SQL 优化补丁到项目文件（省略 run-id 时使用最近一次运行）",
            "exec_command": f"{py_cmd} {resolved_id_script} apply",
            "usage_hint": "--project . [--run-id run_xxx] [--mode APPLY_IN_PLACE]",
            "examples": [
                "应用最近运行的补丁：--project .",
                "应用指定运行的补丁：--project . --run-id run_xxx",
                "直接修改文件：--project . --mode APPLY_IN_PLACE",
            ],
        },
        {
            "name": "sql-optimizer-report",
            "description": "生成或查看优化运行的详细报告",
            "exec_command": f"{py_cmd} {resolved_id_script} report",
            "usage_hint": "--project . [--run-id run_xxx] [--format markdown]",
            "examples": [
                "查看最近报告：--project .",
                "生成 JSON 报告：--project . --format json",
            ],
        },
    ]

    # Generate and write documentation for each command
    for cmd in commands:
        doc_content = _generate_command_doc(
            description=cmd["description"],
            exec_command=str(cmd["exec_command"]).strip(),
            usage_hint=str(cmd.get("usage_hint") or "").strip() or None,
            examples=cmd.get("examples"),
        )
        output_file = cmd_dir / f"{cmd['name']}.md"
        output_file.write_text(doc_content, encoding="utf-8")

    # Cleanup legacy command docs that are no longer supported.
    (cmd_dir / "sql-optimizer-verify.md").unlink(missing_ok=True)


def _create_project_config(root_dir: Path, target_skill: Path, project_dir: Path) -> None:
    template = root_dir / "templates" / "sqlopt.example.yml"
    config_path = project_dir / "sqlopt.yml"
    if not template.exists() or config_path.exists():
        return
    scanner_jar = normalize_jar_path_for_yaml(target_skill / "runtime" / "java" / "scan-agent" / "target" / "scan-agent-1.0.0.jar")
    text = template.read_text(encoding="utf-8")
    config_path.write_text(replace_template_var(text, "__SCANNER_JAR__", scanner_jar), encoding="utf-8")
    print(f"created project config: {config_path}")


def main() -> None:
    args = _parse_args()
    script_dir = Path(__file__).resolve().parent
    root_dir = script_dir.parent
    project_dir = Path(args.project).resolve()
    target_skill = skill_dir()
    skills_root = target_skill.parent

    if args.verify:
        raise SystemExit(_verify_installed_cli(target_skill))

    source_skill = find_skill_source(root_dir)

    opencode_home().mkdir(parents=True, exist_ok=True)
    skills_root.mkdir(parents=True, exist_ok=True)

    if target_skill.exists():
        if args.force:
            safe_rmtree(target_skill)
        else:
            backup_root = opencode_home() / "skill_backups" / SKILL_NAME
            backup_root.mkdir(parents=True, exist_ok=True)
            backup = backup_root / datetime.now().strftime('%Y%m%d_%H%M%S')
            target_skill.rename(backup)
            print(f"existing skill moved to: {backup}")

    retired_count = _retire_legacy_skill_backups(skills_root)
    if retired_count:
        print(f"disabled {retired_count} legacy backup skill marker(s)")

    target_skill.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_skill, target_skill, dirs_exist_ok=True)
    _copy_runtime(root_dir, target_skill)

    runtime_dir = target_skill / "runtime"
    run_cmd([sys.executable, "-m", "venv", str(runtime_dir / ".venv")])
    py = venv_python(runtime_dir)
    run_cmd([str(py), "-m", "pip", "install", "--upgrade", "pip"], quiet=True)
    run_cmd([str(py), "-m", "pip", "install", "-r", str(runtime_dir / "install" / "requirements.txt")], quiet=True)

    wrapper = write_cli_wrapper(target_skill)
    _write_commands(target_skill)
    _create_project_config(root_dir, target_skill, project_dir)

    print(f"installed skill: {SKILL_NAME}")
    print(f"skill dir: {target_skill}")
    print(f"project dir: {project_dir}")
    if sys.platform.startswith("win"):
        print(f"next: python {root_dir / 'install' / 'doctor.py'} --project {project_dir}")
    else:
        print(f"next: bash {root_dir / 'install' / 'doctor.sh'} --project {project_dir}")

    print(f"cli: {wrapper}")
    path_ok = _print_path_hint(wrapper.parent, auto_add=not args.no_auto_path)
    cli_ok, detail = _run_cli_self_check(wrapper)
    if cli_ok:
        print(f"self-check: ok ({detail})")
    else:
        print(f"self-check: failed ({detail})")
    if path_ok:
        print("direct command: sqlopt-cli --help")
    else:
        print("direct command: pending PATH update")


if __name__ == "__main__":
    main()
