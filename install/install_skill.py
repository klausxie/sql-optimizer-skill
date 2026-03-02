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
    argument_hint: str,
    command_template: str,
    parameters: list[dict] | None = None,
    examples: list[str] | None = None,
    notes: list[str] | None = None,
) -> str:
    """Generate markdown documentation for a single command.

    Args:
        description: Command description for the frontmatter
        argument_hint: Argument hint string for the frontmatter
        command_template: Full command template with placeholders
        parameters: Optional list of parameter definitions with name, required, default, description
        examples: Optional list of usage examples
        notes: Optional list of additional notes

    Returns:
        Markdown documentation string
    """
    lines = [
        "---",
        f"description: {description}",
        f"argument-hint: {argument_hint}",
        "---",
        "",
        "## 命令格式",
        "",
        f"`{command_template}`",
        "",
    ]

    if parameters:
        lines.extend([
            "## 参数说明",
            "",
        ])
        for param in parameters:
            name = param["name"]
            required = param.get("required", True)
            default = param.get("default")
            desc = param.get("description", "")

            if required:
                lines.append(f"- `{name}` **(必需)**: {desc}")
            else:
                if default:
                    lines.append(f"- `{name}` (可选，默认: `{default}`): {desc}")
                else:
                    lines.append(f"- `{name}` (可选): {desc}")
        lines.append("")

    if examples:
        lines.extend([
            "## 使用示例",
            "",
        ])
        for example in examples:
            lines.append(f"```bash")
            lines.append(example)
            lines.append("```")
            lines.append("")

    if notes:
        lines.extend([
            "## 注意事项",
            "",
        ])
        for note in notes:
            lines.append(f"- {note}")
        lines.append("")

    return "\n".join(lines)


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
            "argument_hint": "config=./sqlopt.yml to_stage=patch_generate run_id=RUN_ID max_steps=200 max_seconds=95",
            "script": run_budget_script,
            "args": "--config <config> --to-stage <to_stage> --run-id <run_id> --max-steps <max_steps> --max-seconds <max_seconds>",
            "parameters": [
                {"name": "config", "required": False, "default": "./sqlopt.yml", "description": "配置文件路径"},
                {"name": "to_stage", "required": False, "default": "patch_generate", "description": "目标阶段，可选值: preflight, scan, optimize, validate, patch_generate, report"},
                {"name": "run_id", "required": False, "default": "自动生成", "description": "运行 ID，省略时自动生成新的 run_id"},
                {"name": "max_steps", "required": False, "default": "200", "description": "最大执行步数"},
                {"name": "max_seconds", "required": False, "default": "95", "description": "最大执行时间（秒）"},
            ],
            "examples": [
                "# 最简单的用法（使用所有默认值）",
                f"{py_cmd} {run_budget_script}",
                "",
                "# 指定配置文件和目标阶段",
                f"{py_cmd} {run_budget_script} --config ./sqlopt.yml --to-stage patch_generate",
                "",
                "# 继续已有的运行",
                f"{py_cmd} {run_budget_script} --run-id run_abc123",
            ],
            "notes": [
                "单次调用约 95 秒，不保证完成所有 SQL 优化",
                "需要循环调用直到返回 complete=true",
                "返回 JSON 格式包含 run_id、complete、phase 等信息",
                "可选参数不传时使用默认值",
            ],
        },
        {
            "name": "sql-optimizer-status",
            "description": "查询 sql-optimizer 运行状态（省略 run_id 时默认使用最近一次）",
            "argument_hint": "run_id=RUN_ID project=.",
            "script": resolved_id_script,
            "args": "status --run-id <run_id> --project <project>",
            "parameters": [
                {"name": "project", "required": False, "default": ".", "description": "项目根目录路径"},
                {"name": "run_id", "required": False, "default": "最近一次运行", "description": "运行 ID，省略时自动使用最近一次运行"},
            ],
            "examples": [
                "# 最简单的用法（使用所有默认值）",
                f"{py_cmd} {resolved_id_script} status",
                "",
                "# 查询最近一次运行的状态",
                f"{py_cmd} {resolved_id_script} status --project .",
                "",
                "# 查询指定 run_id 的状态",
                f"{py_cmd} {resolved_id_script} status --run-id run_abc123",
            ],
            "notes": [
                "省略 run_id 时自动使用最近一次运行",
                "省略 project 时默认使用当前目录",
                "返回 JSON 格式包含 current_phase、remaining_statements、complete 等信息",
                "可选参数不传时使用默认值",
            ],
        },
        {
            "name": "sql-optimizer-resume",
            "description": "继续推进一次 sql-optimizer 运行（省略 run_id 时默认使用最近一次）",
            "argument_hint": "run_id=RUN_ID project=.",
            "script": resolved_id_script,
            "args": "resume --run-id <run_id> --project <project>",
            "parameters": [
                {"name": "project", "required": False, "default": ".", "description": "项目根目录路径"},
                {"name": "run_id", "required": False, "default": "最近一次运行", "description": "运行 ID，省略时自动使用最近一次运行"},
            ],
            "examples": [
                "# 最简单的用法（使用所有默认值）",
                f"{py_cmd} {resolved_id_script} resume",
                "",
                "# 继续最近一次运行",
                f"{py_cmd} {resolved_id_script} resume --project .",
                "",
                "# 继续指定 run_id 的运行",
                f"{py_cmd} {resolved_id_script} resume --run-id run_abc123",
            ],
            "notes": [
                "省略 run_id 时自动使用最近一次运行",
                "省略 project 时默认使用当前目录",
                "从上次中断的地方继续执行",
                "返回 JSON 格式包含执行结果",
                "可选参数不传时使用默认值",
            ],
        },
        {
            "name": "sql-optimizer-apply",
            "description": "对 sql-optimizer 运行执行 apply（省略 run_id 时默认使用最近一次）",
            "argument_hint": "run_id=RUN_ID project=.",
            "script": resolved_id_script,
            "args": "apply --run-id <run_id> --project <project>",
            "parameters": [
                {"name": "project", "required": False, "default": ".", "description": "项目根目录路径"},
                {"name": "run_id", "required": False, "default": "最近一次运行", "description": "运行 ID，省略时自动使用最近一次运行"},
            ],
            "examples": [
                "# 最简单的用法（使用所有默认值）",
                f"{py_cmd} {resolved_id_script} apply",
                "",
                "# 应用最近一次运行的补丁",
                f"{py_cmd} {resolved_id_script} apply --project .",
                "",
                "# 应用指定 run_id 的补丁",
                f"{py_cmd} {resolved_id_script} apply --run-id run_abc123",
            ],
            "notes": [
                "省略 run_id 时自动使用最近一次运行",
                "省略 project 时默认使用当前目录",
                "默认模式为 PATCH_ONLY（生成补丁文件，不修改源文件）",
                "如需直接修改源文件，在 sqlopt.yml 中设置 apply.mode: APPLY_IN_PLACE",
                "可选参数不传时使用默认值",
            ],
        },
    ]

    # Generate and write documentation for each command
    for cmd in commands:
        command_template = f"{py_cmd} {cmd['script']} {cmd['args']}"
        doc_content = _generate_command_doc(
            description=cmd["description"],
            argument_hint=cmd["argument_hint"],
            command_template=command_template,
            parameters=cmd.get("parameters"),
            examples=cmd.get("examples"),
            notes=cmd.get("notes"),
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
    opencode_home().mkdir(parents=True, exist_ok=True)
    (opencode_home() / "skills").mkdir(parents=True, exist_ok=True)

    if target_skill.exists():
        if args.force:
            safe_rmtree(target_skill)
        else:
            backup = target_skill.parent / f"{SKILL_NAME}.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            target_skill.rename(backup)
            print(f"existing skill moved to: {backup}")

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
