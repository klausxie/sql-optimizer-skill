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
            "description": "扫描并识别潜在慢 SQL",
            "argument_hint": "范围=SQL ID或文件路径",
            "full_description": "扫描 MyBatis XML 文件，识别潜在的慢 SQL。只输出慢 SQL 列表，不做深度优化建议。",
            "parameters": [
                {
                    "name": "范围",
                    "required": False,
                    "default": None,
                    "description": "SQL ID、文件路径或配置文件，如 findUsers、UserMapper.xml、@sql-list.txt",
                },
            ],
            "examples": [
                f"{cli_cmd} run --to-stage scan --sql-key findUsers",
                f"{cli_cmd} run --to-stage scan --mapper-path UserMapper.xml",
            ],
            "interaction": "扫描完成后，Agent 必须提示用户：'是否执行这些 SQL 获取性能数据？'",
        },
        {
            "name": "sql-execute",
            "description": "执行 SQL 获取性能数据",
            "argument_hint": "config=./sqlopt.yml",
            "full_description": "在数据库上执行扫描发现的慢 SQL，收集实际执行时间、EXPLAIN 结果等性能数据。",
            "parameters": [
                {
                    "name": "config",
                    "required": False,
                    "default": "./sqlopt.yml",
                    "description": "配置文件路径（需包含数据库 DSN）",
                },
            ],
            "examples": [
                f"{cli_cmd} run --to-stage validate --config ./sqlopt.yml",
            ],
        },
        {
            "name": "sql-analyze",
            "description": "分析执行结果确认瓶颈",
            "argument_hint": "run-id=<运行ID>",
            "full_description": "分析执行结果，确认真正的慢 SQL 及其性能瓶颈（全表扫描、索引缺失、N+1问题等）。",
            "parameters": [
                {
                    "name": "run-id",
                    "required": False,
                    "default": None,
                    "description": "运行ID，不指定则使用最新",
                },
            ],
            "examples": [
                f"{cli_cmd} status --run-id latest",
            ],
        },
        {
            "name": "sql-optimize",
            "description": "生成优化建议",
            "argument_hint": "run-id=<运行ID>",
            "full_description": "根据分析结果生成针对性优化建议。简单场景用规则优化，复杂场景用 LLM 优化。",
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
            "name": "sql-apply",
            "description": "生成并应用 XML 补丁",
            "argument_hint": "run-id=<运行ID>",
            "full_description": "根据优化建议生成 MyBatis XML 补丁，用户确认后应用到项目。",
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

"""

        # 添加下一步建议
        next_steps = {
            "sql-scan": ("sql-execute", "⚠️ 必须提示用户确认执行"),
            "sql-execute": ("sql-analyze", None),
            "sql-analyze": ("sql-optimize", None),
            "sql-optimize": ("sql-apply", None),
            "sql-apply": (None, "流程完成"),
        }

        content += "## 下一步建议\n\n"
        next_cmd, condition = next_steps.get(cmd["name"], (None, None))
        if next_cmd:
            if condition and condition.startswith("⚠️"):
                # 特殊提示，需要单独显示
                content += f"{condition}\n\n"
                content += f"用户确认后 → 执行 `/{next_cmd}`\n"
            else:
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
    _write_slash_commands(target_skill, target_commands)
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
