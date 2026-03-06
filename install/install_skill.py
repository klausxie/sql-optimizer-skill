#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
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
    commands_dir,
    find_skill_source,
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
    return p.parse_args()


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
        "2. **单次调用**：必须立刻调用一次 bash 工具，且只调用这一次",
        "3. **参数处理**：当使用 `$ARGUMENTS` 时，必须按原样直接拼接，不要整体加引号",
        "",
        "## 执行命令",
        "",
        "- 当 `$ARGUMENTS` 为空时：",
        f"  ```bash",
        f"  {exec_command}",
        f"  ```",
        "",
        "- 当 `$ARGUMENTS` 非空时：",
        f"  ```bash",
        f"  {exec_command} $ARGUMENTS",
        f"  ```",
        "",
        "## 输出规则",
        "",
        "命令结束后，仅返回 bash 的原始输出，不要添加额外说明。",
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
            "name": "sql-optimizer-verify",
            "description": "验证优化运行的数据契约和输出完整性",
            "exec_command": f"{py_cmd} {resolved_id_script} verify",
            "usage_hint": "--project . [--run-id run_xxx] [--phase validate]",
            "examples": [
                "验证最近运行：--project .",
                "验证指定阶段：--project . --phase validate",
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
    source_skill = find_skill_source(root_dir)
    target_skill = skill_dir()
    skills_root = target_skill.parent
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
        print(f"cli: {wrapper}")
    else:
        print(f"next: bash {root_dir / 'install' / 'doctor.sh'} --project {project_dir}")


if __name__ == "__main__":
    main()
