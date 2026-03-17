#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sys
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


def _get_cli_command(target_skill: Path, project_dir: Path) -> str:
    """Get the sqlopt-cli command string for the target skill (relative path)."""
    cli_wrapper = (
        target_skill
        / "bin"
        / ("sqlopt-cli.cmd" if sys.platform.startswith("win") else "sqlopt-cli")
    )
    if cli_wrapper.exists():
        # Return relative path from project_dir
        try:
            return str(cli_wrapper.relative_to(project_dir))
        except ValueError:
            return str(cli_wrapper)
    # Fallback to direct python script invocation
    py = Path(_get_python_command(target_skill))
    script = target_skill / "runtime" / "scripts" / "sqlopt_cli.py"
    try:
        py_rel = str(py.relative_to(project_dir))
        script_rel = str(script.relative_to(project_dir))
    except ValueError:
        return f"{py} {script}"
    return f"{py_rel} {script_rel}"


def _write_slash_commands(
    target_skill: Path, commands_dir: Path, project_dir: Path
) -> None:
    """Generate OpenCode slash command documentation files for phase capabilities."""

    cli_cmd = _get_cli_command(target_skill, project_dir)

    commands = [
        {
            "name": "sql-diagnose",
            "description": "诊断 SQL 性能问题",
            "argument_hint": "<SQL关键字或文件>",
            "full_description": "一键诊断: 找到SQL位置 → 生成分支 → 真实执行(可选) → 生成诊断报告。当用户说'帮我诊断一下xxx'、'看看有什么性能问题'时使用此命令。",
            "parameters": [
                {
                    "name": "范围",
                    "required": True,
                    "description": "SQL ID、文件路径或关键字，如 listUsers、UserMapper.xml",
                },
                {
                    "name": "模式",
                    "required": False,
                    "default": "full",
                    "description": "quick(仅LLM推测) / full(真实执行，需要数据库)",
                },
            ],
            "examples": [
                f"{cli_cmd} run --to-stage diagnose --sql-key listUsers",
                f"{cli_cmd} run --to-stage diagnose --mapper-path UserMapper.xml",
            ],
        },
        {
            "name": "sql-optimize",
            "description": "生成优化建议",
            "argument_hint": "[run-id]",
            "full_description": "根据诊断结果，对问题分支生成 LLM 优化建议。当用户说'给个优化建议'、'如何优化这些慢SQL'时使用此命令。",
            "parameters": [
                {
                    "name": "run-id",
                    "required": False,
                    "default": None,
                    "description": "运行ID，不指定则使用最新",
                },
            ],
            "examples": [
                f"{cli_cmd} run --to-stage optimize",
            ],
        },
        {
            "name": "sql-validate",
            "description": "验证优化效果",
            "argument_hint": "[run-id]",
            "full_description": "真实执行优化后的 SQL，验证性能提升效果。当用户说'验证一下优化效果'、'看看性能提升了多少'时使用此命令。",
            "parameters": [
                {
                    "name": "run-id",
                    "required": False,
                    "default": None,
                    "description": "运行ID，不指定则使用最新",
                },
            ],
            "examples": [
                f"{cli_cmd} run --to-stage validate",
            ],
        },
        {
            "name": "sql-apply",
            "description": "应用补丁",
            "argument_hint": "[run-id]",
            "full_description": "应用验证通过的优化补丁到源码。当用户说'应用这些补丁'、'把这些修改应用到代码'时使用此命令。",
            "parameters": [
                {
                    "name": "run-id",
                    "required": False,
                    "default": None,
                    "description": "运行ID，不指定则使用最新",
                },
            ],
            "examples": [
                f"{cli_cmd} apply --run-id latest",
            ],
        },
        {
            "name": "sql-report",
            "description": "生成总结报告",
            "argument_hint": "[run-id]",
            "full_description": "汇总所有阶段的总结报告。当用户说'生成总结报告'、'给我一个完整的报告'时使用此命令。",
            "parameters": [
                {
                    "name": "run-id",
                    "required": False,
                    "default": None,
                    "description": "运行ID，不指定则使用最新",
                },
            ],
            "examples": [
                f"{cli_cmd} run --to-stage report",
            ],
        },
    ]

    commands_dir.mkdir(parents=True, exist_ok=True)

    # Clean up old format command files before generating new ones
    if commands_dir.exists():
        # Delete old format files (sql-optimizer-*.md)
        for old_file in commands_dir.glob("sql-optimizer-*.md"):
            print(f"Deleting old format file: {old_file.name}")
            old_file.unlink()
        # Delete same-name new format files to ensure clean overwrite
        for cmd in commands:
            new_file = commands_dir / f"{cmd['name']}.md"
            if new_file.exists():
                print(f"Deleting existing file: {new_file.name}")
                new_file.unlink()

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

        # 为 sql-scan 添加扫描策略
        if cmd["name"] == "sql-scan":
            content += """
## 扫描策略

### Maven 标准结构 (优先)

如果项目根目录有 `pom.xml`，自动使用以下搜索路径：

| 优先级 | 路径 | 说明 |
|--------|------|------|
| 1 | `src/main/resources/**/*.xml` | 标准 Maven 资源目录 |
| 2 | `src/main/resources/mapper/**/*.xml` | MyBatis mapper 子目录 |
| 3 | `**/*Mapper.xml` | 任意 Mapper 文件 |

### 自动排除

以下目录会被自动排除：
- `target/` - Maven 构建输出
- `.git/` - Git 目录
- `node_modules/` - Node.js 依赖

### SQL Key 选择

- 支持完整 `sqlKey`
- 支持 `namespace.statementId`
- 支持 `statementId`
- 支持 `statementId#vN`
- 如果一个方法名匹配多个 SQL，CLI 会返回候选 full key，而不是自动猜测

"""

        # 添加下一步建议
        next_steps = {
            "sql-diagnose": (
                "sql-optimize",
                "诊断完成后进入优化阶段",
            ),
            "sql-optimize": ("sql-validate", "优化建议生成后进入验证阶段"),
            "sql-validate": (
                "sql-apply",
                "验证通过后可应用补丁",
            ),
            "sql-apply": ("sql-report", "补丁应用后可生成总结报告"),
            "sql-report": (None, "流程已完成"),
        }

        content += "## 下一步建议\n\n"
        next_cmd, condition = next_steps.get(cmd["name"], (None, None))
        if next_cmd:
            cond_text = f" ({condition})" if condition else ""
            content += f"本阶段完成后 → 执行 `/{next_cmd}`{cond_text}\n"
        elif condition:
            # 没有下一步但有特殊消息
            content += f"{condition}\n"
        else:
            content += "流程已完成。\n"

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
        target_commands = project_dir / ".opencode" / "commands"
        target_skill.parent.mkdir(parents=True, exist_ok=True)
    else:
        # Global installation: ~/.config/opencode/skills/sql-optimizer/
        project_dir = Path.cwd()
        target_skill = skill_dir()
        target_commands = commands_dir()  # ~/.config/opencode/commands/
        target_skill.parent.mkdir(parents=True, exist_ok=True)

    if target_skill.exists():
        if args.force:
            safe_rmtree(target_skill)
        else:
            # 默认覆盖：直接删除旧版本
            safe_rmtree(target_skill)
            print(f"existing skill removed: {target_skill}")

    target_skill.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_skill, target_skill, dirs_exist_ok=True)
    _copy_runtime(root_dir, target_skill)

    runtime_dir = target_skill / "runtime"
    run_cmd([sys.executable, "-m", "venv", str(runtime_dir / ".venv")])
    py = venv_python(runtime_dir)

    # pip install 失败不中止，继续生成斜杠命令（不依赖这些包）
    try:
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
    except Exception as e:
        print(f"WARNING: pip install failed ({e}), continuing anyway...")

    wrapper = write_cli_wrapper(target_skill)
    # 生成斜杠命令文档
    _write_slash_commands(target_skill, target_commands, project_dir)
    _create_project_config(root_dir, target_skill, project_dir)

    print(f"installed skill: {SKILL_NAME}")
    print(f"skill dir: {target_skill}")
    print(f"commands dir: {target_commands}")
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
