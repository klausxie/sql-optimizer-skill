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
            "full_description": "扫描 MyBatis XML 文件并确认当前选择范围。`--sql-key` 支持完整 sqlKey、namespace.statementId、statementId、statementId#vN；如果命中多个 SQL，会返回候选 full key。",
            "parameters": [
                {
                    "name": "范围",
                    "required": False,
                    "default": None,
                    "description": "SQL ID、完整 sqlKey、文件路径或配置文件，如 findUsers、demo.user.findUsers#v1、UserMapper.xml、@sql-list.txt",
                },
            ],
            "examples": [
                f"{cli_cmd} run --to-stage scan --sql-key findUsers",
                f"{cli_cmd} run --to-stage scan --mapper-path UserMapper.xml",
            ],
        },
        {
            "name": "sql-validate-config",
            "description": "验证配置与数据库连通性",
            "argument_hint": "config=./sqlopt.yml",
            "full_description": "检查 sqlopt.yml、mapper 匹配结果和数据库连通性。遇到占位符 DSN、认证失败或数据库不可达时，先修配置再继续 full run。",
            "parameters": [
                {
                    "name": "config",
                    "required": False,
                    "default": "./sqlopt.yml",
                    "description": "配置文件路径",
                },
            ],
            "examples": [
                f"{cli_cmd} validate-config --config ./sqlopt.yml",
            ],
        },
        {
            "name": "sql-execute",
            "description": "推进到 validate 阶段",
            "argument_hint": "config=./sqlopt.yml",
            "full_description": "继续推进当前 run 到 validate 阶段并尝试收集数据库验证证据。当前 CLI 没有 scan 之后的额外交互确认；调用此命令本身就表示继续。",
            "parameters": [
                {
                    "name": "config",
                    "required": False,
                    "default": "./sqlopt.yml",
                    "description": "配置文件路径（需已通过 validate-config）",
                },
            ],
            "examples": [
                f"{cli_cmd} run --to-stage validate --config ./sqlopt.yml",
            ],
        },
        {
            "name": "sql-status",
            "description": "查看运行状态与下一步",
            "argument_hint": "run-id=<运行ID>",
            "full_description": "查看当前 run 的 phase、next_action、剩余语句数，以及是否需要 report-rebuild。它是观察入口，不是独立计算阶段。",
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
            "full_description": "启动或继续到 optimize 阶段，用于先生成 rewrite 候选而不继续进入 validate/patch。",
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
            "description": "应用已生成的补丁",
            "argument_hint": "run-id=<运行ID>",
            "full_description": "应用已生成的 `.patch` 文件。默认 PATCH_ONLY 模式不会直接改源码；如果没有 patch 文件，输出会明确给出 skipped reason 汇总。",
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
            "sql-scan": (
                "sql-validate-config",
                "如果下一步要进入 validate/report，先确认数据库配置",
            ),
            "sql-validate-config": ("sql-execute", "配置通过后再推进到 validate"),
            "sql-execute": (
                "sql-status",
                "查看 next_action、report-rebuild 和 validate 结果",
            ),
            "sql-status": ("sql-apply", "仅当 patch 结果里存在 patchFiles"),
            "sql-optimize": ("sql-execute", "需要数据库验证时再继续"),
            "sql-apply": (None, "流程完成"),
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
