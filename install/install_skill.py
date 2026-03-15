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
    raise SystemExit(
        "cannot locate python runtime (expected ./python or ./runtime/python)"
    )


_bootstrap()

from sqlopt.install_support import (  # noqa: E402
    SKILL_NAME,
    commands_dir,
    find_skill_source,
    opencode_home,
    project_skill_dir,
    replace_template_var,
    run_cmd,
    runtime_base,
    safe_rmtree,
    skill_dir,
    venv_python,
    write_cli_wrapper,
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Install SQL Optimizer skill")
    mode_group = p.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--global",
        dest="global_install",
        action="store_true",
        help="Install to global skill directory (~/.opencode/skills/sql-optimizer/) [default]",
    )
    mode_group.add_argument(
        "--project",
        default=None,
        help="Install to project-specific directory (<project>/.sqlopt/)",
    )
    p.add_argument(
        "--force", action="store_true", help="Force overwrite existing installation"
    )
    return p.parse_args()


def _copy_runtime(root_dir: Path, target_skill: Path) -> None:
    target_runtime = target_skill / "runtime"
    target_runtime.mkdir(parents=True, exist_ok=True)
    base = runtime_base(root_dir)
    for name in ["python", "scripts", "contracts"]:
        src = base / name
        if not src.exists():
            raise SystemExit(f"missing runtime folder: {src}")
        shutil.copytree(src, target_runtime / name, dirs_exist_ok=True)
    pyproject = base / "pyproject.toml"
    if pyproject.exists():
        shutil.copy2(pyproject, target_runtime / "pyproject.toml")
    install_dir = target_runtime / "install"
    install_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        root_dir / "install" / "requirements.txt", install_dir / "requirements.txt"
    )


def _get_python_command(target_skill: Path) -> str:
    """Get the Python command path for the target skill's venv."""
    if sys.platform.startswith("win"):
        return str(target_skill / "runtime" / ".venv" / "Scripts" / "python.exe")
    else:
        return str(target_skill / "runtime" / ".venv" / "bin" / "python")


def _get_cli_command(target_skill: Path) -> str:
    """Get the sqlopt-cli command string for the target skill."""
    cli_wrapper = (
        target_skill
        / "bin"
        / ("sqlopt-cli.cmd" if sys.platform.startswith("win") else "sqlopt-cli")
    )
    if cli_wrapper.exists():
        return str(cli_wrapper)
    # Fallback to direct python script invocation
    py = _get_python_command(target_skill)
    script = target_skill / "runtime" / "scripts" / "sqlopt_cli.py"
    return f"{py} {script}"


def _write_slash_commands(target_skill: Path, commands_dir: Path) -> None:
    """Generate OpenCode slash command documentation files for phase capabilities."""

    cli_cmd = _get_cli_command(target_skill)

    commands = [
        {
            "name": "sql-scan",
            "description": "扫描 MyBatis XML 文件",
            "argument_hint": "config=./sqlopt.yml project=.",
            "full_description": "扫描 MyBatis XML 映射文件，识别其中的 SQL 语句，为后续优化做准备。",
            "parameters": [
                {
                    "name": "config",
                    "required": False,
                    "default": "./sqlopt.yml",
                    "description": "配置文件路径",
                },
                {
                    "name": "project",
                    "required": False,
                    "default": ".",
                    "description": "项目根目录路径",
                },
            ],
            "examples": [
                f"{cli_cmd} run --to-stage scan --config ./sqlopt.yml --project .",
                f"{cli_cmd} run --to-stage scan --config ./sqlopt.yml",
            ],
        },
        {
            "name": "sql-optimize",
            "description": "优化 SQL 语句",
            "argument_hint": "config=./sqlopt.yml project=.",
            "full_description": "使用 LLM 分析扫描到的 SQL 语句，生成优化建议。",
            "parameters": [
                {
                    "name": "config",
                    "required": False,
                    "default": "./sqlopt.yml",
                    "description": "配置文件路径",
                },
                {
                    "name": "project",
                    "required": False,
                    "default": ".",
                    "description": "项目根目录路径",
                },
            ],
            "examples": [
                f"{cli_cmd} run --to-stage optimize --config ./sqlopt.yml --project .",
                f"{cli_cmd} run --to-stage optimize --config ./sqlopt.yml",
            ],
        },
        {
            "name": "sql-validate",
            "description": "验证优化效果",
            "argument_hint": "config=./sqlopt.yml project=.",
            "full_description": "在目标数据库上验证优化建议的实际效果，包括性能对比和结果一致性检查。",
            "parameters": [
                {
                    "name": "config",
                    "required": False,
                    "default": "./sqlopt.yml",
                    "description": "配置文件路径",
                },
                {
                    "name": "project",
                    "required": False,
                    "default": ".",
                    "description": "项目根目录路径",
                },
            ],
            "examples": [
                f"{cli_cmd} run --to-stage validate --config ./sqlopt.yml --project .",
                f"{cli_cmd} run --to-stage validate --config ./sqlopt.yml",
            ],
        },
        {
            "name": "sql-patch",
            "description": "生成 XML 补丁",
            "argument_hint": "config=./sqlopt.yml project=.",
            "full_description": "根据验证通过的优化建议，生成可应用的 MyBatis XML 补丁文件。",
            "parameters": [
                {
                    "name": "config",
                    "required": False,
                    "default": "./sqlopt.yml",
                    "description": "配置文件路径",
                },
                {
                    "name": "project",
                    "required": False,
                    "default": ".",
                    "description": "项目根目录路径",
                },
            ],
            "examples": [
                f"{cli_cmd} run --to-stage patch_generate --config ./sqlopt.yml --project .",
                f"{cli_cmd} run --to-stage patch_generate --config ./sqlopt.yml",
            ],
        },
        {
            "name": "sql-report",
            "description": "查看优化报告",
            "argument_hint": "config=./sqlopt.yml project=.",
            "full_description": "生成或查看完整的 SQL 优化报告，包括扫描结果、优化建议、验证数据和补丁信息。",
            "parameters": [
                {
                    "name": "config",
                    "required": False,
                    "default": "./sqlopt.yml",
                    "description": "配置文件路径",
                },
                {
                    "name": "project",
                    "required": False,
                    "default": ".",
                    "description": "项目根目录路径",
                },
            ],
            "examples": [
                f"{cli_cmd} run --to-stage report --config ./sqlopt.yml --project .",
                f"{cli_cmd} run --to-stage report --config ./sqlopt.yml",
            ],
        },
    ]

    commands_dir.mkdir(parents=True, exist_ok=True)

    for cmd in commands:
        content = f"""---
description: {cmd["description"]}
argument-hint: {cmd["argument_hint"]}
---

## 描述

{cmd["full_description"]}

## 参数

"""
        for param in cmd["parameters"]:
            name = param["name"]
            required = param.get("required", True)
            default = param.get("default")
            desc = param.get("description", "")

            if required:
                content += f"- `{name}` **(必需)**: {desc}\n"
            else:
                if default:
                    content += f"- `{name}` (可选，默认: `{default}`): {desc}\n"
                else:
                    content += f"- `{name}` (可选): {desc}\n"
        content += "\n## 示例\n\n"
        for example in cmd["examples"]:
            content += f"```bash\n{example}\n```\n\n"

        output_file = commands_dir / f"{cmd['name']}.md"
        output_file.write_text(content, encoding="utf-8")


def _create_project_config(
    root_dir: Path, target_skill: Path, project_dir: Path
) -> None:
    template = root_dir / "templates" / "sqlopt.example.yml"
    config_path = project_dir / "sqlopt.yml"
    if not template.exists() or config_path.exists():
        return
    shutil.copy2(template, config_path)
    print(f"created project config: {config_path}")


def main() -> None:
    args = _parse_args()
    script_dir = Path(__file__).resolve().parent
    root_dir = script_dir.parent
    source_skill = find_skill_source(root_dir)

    # Determine installation mode
    if args.project:
        # Project-level installation: <project>/.opencode/skills/sql-optimizer/
        project_dir = Path(args.project).resolve()
        target_skill = project_skill_dir(project_dir)
        target_skill.parent.mkdir(parents=True, exist_ok=True)
    else:
        # Global installation: ~/.config/opencode/skills/sql-optimizer/
        project_dir = Path.cwd()
        target_skill = skill_dir()
        target_skill.parent.mkdir(parents=True, exist_ok=True)

    if target_skill.exists():
        if args.force:
            safe_rmtree(target_skill)
        else:
            backup = (
                target_skill.parent
                / f"{SKILL_NAME}.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            target_skill.rename(backup)
            print(f"existing skill moved to: {backup}")

    target_skill.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_skill, target_skill, dirs_exist_ok=True)
    _copy_runtime(root_dir, target_skill)

    runtime_dir = target_skill / "runtime"
    run_cmd([sys.executable, "-m", "venv", str(runtime_dir / ".venv")])
    py = venv_python(runtime_dir)
    run_cmd([str(py), "-m", "pip", "install", "--upgrade", "pip"], quiet=True)
    run_cmd(
        [
            str(py),
            "-m",
            "pip",
            "install",
            "-r",
            str(runtime_dir / "install" / "requirements.txt"),
        ],
        quiet=True,
    )

    wrapper = write_cli_wrapper(target_skill)
    # 生成斜杠命令文档
    slash_commands_dir = target_skill.parent.parent / "commands"
    _write_slash_commands(target_skill, slash_commands_dir)
    _create_project_config(root_dir, target_skill, project_dir)

    print(f"installed skill: {SKILL_NAME}")
    print(f"skill dir: {target_skill}")
    print(f"project dir: {project_dir}")
    print(f"install mode: {'project-level' if args.project else 'global'}")
    if sys.platform.startswith("win"):
        print(
            f"next: python {root_dir / 'install' / 'doctor.py'} --project {project_dir}"
        )
        print(f"cli: {wrapper}")
    else:
        print(
            f"next: bash {root_dir / 'install' / 'doctor.sh'} --project {project_dir}"
        )


if __name__ == "__main__":
    main()
