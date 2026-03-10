from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from .application import config_service, run_index, run_service, workflow_engine
from .application.run_resolution import resolve_run_id
from .error_messages import format_error_message
from .errors import ConfigError, StageError
from .progress import get_progress_reporter, init_progress_reporter

STAGE_ORDER = workflow_engine.STAGE_ORDER


def _repo_root() -> Path:
    return Path.cwd().resolve()


def _run_label(run_id: str | None) -> str:
    value = str(run_id or "").strip()
    return value if value else "latest"


def _resolve_requested_run_id(requested_run_id: str | None, project: str | Path | None = None) -> str:
    # Keep explicit run_id passthrough for backward compatibility; only auto-resolve when omitted.
    if str(requested_run_id or "").strip():
        return str(requested_run_id)
    resolved_run_id, _ = resolve_run_id(None, project=project, repo_root=_repo_root())
    return resolved_run_id


def _resolve_run_dir(run_id: str) -> Path:
    """Compatibility wrapper for run directory resolution."""
    return run_index.resolve_run_dir(run_id, repo_root_fn=_repo_root)


def _interrupt_payload(run_id: str | None, *, next_action: str | None = None) -> dict[str, Any]:
    return run_service.build_interrupt_payload(_run_label(run_id), next_action=next_action)


def _validate_budget_args(args: argparse.Namespace) -> None:
    if int(getattr(args, "max_steps", 0)) < 0:
        raise ValueError("max_steps must be >= 0")
    if int(getattr(args, "max_seconds", 0)) < 0:
        raise ValueError("max_seconds must be >= 0")


def _run_phase_action(config: dict[str, Any], phase: str, fn: Callable[[], object]) -> tuple[object, int]:
    """Compatibility wrapper used by legacy tests and integrations."""
    return workflow_engine.run_phase_action(config, phase, fn)


def _finalize_report_if_enabled(
    run_dir: Path,
    config: dict[str, Any],
    validator: Any,
    state: dict[str, Any],
    *,
    final_meta_status: str,
) -> bool:
    """Compatibility wrapper that delegates report finalization to application layer."""
    return workflow_engine.finalize_report_if_enabled(
        run_dir,
        config,
        validator,
        state,
        final_meta_status=final_meta_status,
        run_phase_action_fn=_run_phase_action,
    )


def _advance_one_step(run_dir: Path, config: dict[str, Any], to_stage: str, validator: Any) -> dict[str, Any]:
    """Compatibility wrapper around workflow_engine.advance_one_step."""
    return workflow_engine.advance_one_step(
        run_dir,
        config,
        to_stage,
        validator,
        run_phase_action_fn=_run_phase_action,
        finalize_report_if_enabled_fn=_finalize_report_if_enabled,
        finalize_without_report_fn=workflow_engine.finalize_without_report,
    )


def _advance_until_complete(
    run_id: str,
    initial_result: dict[str, Any],
    *,
    step_fn: Callable[[], dict[str, Any]],
    max_steps: int,
    max_seconds: int,
) -> tuple[dict[str, Any], int, str]:
    """Advance the run until completion or budget exhaustion.

    max_steps=0 and max_seconds=0 mean unbounded.
    """
    outcome = run_service.advance_run_until_complete(
        run_id,
        initial_result,
        step_fn=step_fn,
        max_steps=max_steps,
        max_seconds=max_seconds,
    )
    return outcome.result, outcome.steps_executed, outcome.reason


def cmd_run(args: argparse.Namespace) -> None:
    config_path = Path(args.config).resolve()
    if not config_path.exists():
        error_info = format_error_message("CONFIG_NOT_FOUND", f"Config file not found: {config_path}")
        fallback_run_id = args.run_id or "<pending>"
        print({"run_id": fallback_run_id, "error": error_info})
        raise SystemExit(2)

    repo_root = _repo_root()
    run_id: str | None = None
    requested_run_id = str(args.run_id).strip() if str(args.run_id or "").strip() else f"run_{uuid4().hex[:12]}"
    try:
        _validate_budget_args(args)
        get_progress_reporter().report_info(f"run_id={requested_run_id}")
        run_id, initial_result = run_service.start_run(config_path, args.to_stage, requested_run_id, repo_root=repo_root)
        outcome = run_service.advance_run_until_complete(
            run_id,
            initial_result,
            step_fn=lambda: run_service.resume_run(run_id, repo_root=repo_root),
            max_steps=int(args.max_steps),
            max_seconds=int(args.max_seconds),
        )
        print(run_service.build_progress_payload(run_id, outcome))
    except ValueError as exc:
        error_info = format_error_message("CONFIG_INVALID", str(exc))
        fallback_run_id = run_id or requested_run_id or "<pending>"
        print({"run_id": fallback_run_id, "error": error_info})
        raise SystemExit(2)
    except FileNotFoundError:
        reason_code = "RUN_NOT_FOUND" if run_id else "CONFIG_NOT_FOUND"
        message = f"run_id not found in run index: {run_id}" if run_id else f"Config file not found: {config_path}"
        error_info = format_error_message(reason_code, message)
        fallback_run_id = run_id or requested_run_id or "<pending>"
        print({"run_id": fallback_run_id, "error": error_info})
        raise SystemExit(2)
    except ConfigError as exc:
        error_info = format_error_message("CONFIG_INVALID", str(exc))
        fallback_run_id = run_id or requested_run_id or "<pending>"
        print({"run_id": fallback_run_id, "error": error_info})
        raise SystemExit(2)
    except StageError as exc:
        error_info = format_error_message(exc.reason_code or "UNKNOWN_ERROR", str(exc))
        fallback_run_id = run_id or requested_run_id or "<pending>"
        print({"run_id": fallback_run_id, "error": error_info})
        raise SystemExit(2)
    except KeyboardInterrupt:
        target_run_id = run_id or requested_run_id or "<pending>"
        next_action = f"sqlopt-cli resume --run-id {target_run_id}" if target_run_id not in {"<pending>", "latest"} else None
        print(_interrupt_payload(target_run_id, next_action=next_action))
        raise SystemExit(130)


def cmd_resume(args: argparse.Namespace) -> None:
    resolved_run_id: str | None = None
    try:
        _validate_budget_args(args)
        resolved_run_id = _resolve_requested_run_id(getattr(args, "run_id", None), getattr(args, "project", "."))
        get_progress_reporter().report_info(f"run_id={resolved_run_id}")
        initial_result = run_service.resume_run(resolved_run_id, repo_root=_repo_root())
        outcome = run_service.advance_run_until_complete(
            resolved_run_id,
            initial_result,
            step_fn=lambda: run_service.resume_run(resolved_run_id or "", repo_root=_repo_root()),
            max_steps=int(args.max_steps),
            max_seconds=int(args.max_seconds),
        )
        print(run_service.build_progress_payload(resolved_run_id, outcome))
    except ValueError as exc:
        error_info = format_error_message("CONFIG_INVALID", str(exc))
        print({"run_id": _run_label(getattr(args, "run_id", None)), "error": error_info})
        raise SystemExit(2)
    except FileNotFoundError:
        error_info = format_error_message("RUN_NOT_FOUND", "run_id not found in run index")
        print({"run_id": _run_label(resolved_run_id or getattr(args, "run_id", None)), "error": error_info})
        raise SystemExit(2)
    except StageError as exc:
        error_info = format_error_message(exc.reason_code or "UNKNOWN_ERROR", str(exc))
        print({"run_id": _run_label(resolved_run_id or getattr(args, "run_id", None)), "error": error_info})
        raise SystemExit(2)
    except KeyboardInterrupt:
        target_run_id = resolved_run_id or getattr(args, "run_id", None)
        next_action = f"sqlopt-cli resume --run-id {target_run_id}" if target_run_id else None
        print(_interrupt_payload(target_run_id, next_action=next_action))
        raise SystemExit(130)


def cmd_status(args: argparse.Namespace) -> None:
    resolved_run_id: str | None = None
    try:
        resolved_run_id = _resolve_requested_run_id(getattr(args, "run_id", None), getattr(args, "project", "."))
        print(run_service.get_status(resolved_run_id, repo_root=_repo_root()))
    except FileNotFoundError:
        error_info = format_error_message("RUN_NOT_FOUND", "run_id not found in run index")
        print({"run_id": _run_label(resolved_run_id or getattr(args, "run_id", None)), "error": error_info})
        raise SystemExit(2)


def cmd_validate_config(args: argparse.Namespace) -> None:
    config_path = Path(args.config).resolve()

    if not config_path.exists():
        error_info = format_error_message("CONFIG_NOT_FOUND", f"Config file not found: {config_path}")
        print({"error": error_info})
        raise SystemExit(2)

    try:
        results = config_service.validate_config(config_path)
        print(results)
        raise SystemExit(0 if results["valid"] else 1)

    except Exception as exc:
        error_info = format_error_message("CONFIG_INVALID", str(exc))
        print({"error": error_info})
        raise SystemExit(2)


def cmd_apply(args: argparse.Namespace) -> None:
    resolved_run_id: str | None = None
    try:
        resolved_run_id = _resolve_requested_run_id(getattr(args, "run_id", None), getattr(args, "project", "."))
        print(run_service.apply_run(resolved_run_id, repo_root=_repo_root()))
    except FileNotFoundError:
        error_info = format_error_message("RUN_NOT_FOUND", "run_id not found in run index")
        print({"run_id": _run_label(resolved_run_id or getattr(args, "run_id", None)), "error": error_info})
        raise SystemExit(2)


def build_parser() -> argparse.ArgumentParser:
    top_epilog = (
        "快速工作流:\n"
        "  1) sqlopt-cli run --config sqlopt.yml\n"
        "  2) sqlopt-cli status\n"
        "  3) sqlopt-cli resume\n"
        "  4) sqlopt-cli apply\n"
        "\n"
        "默认行为:\n"
        "  - run: 默认 --config sqlopt.yml，max-steps/max-seconds=0 表示持续运行到完成\n"
        "  - status/resume/apply: 省略 --run-id 时自动选择最新 run（可用 --project 指定项目目录）\n"
        "\n"
        "更多信息请参阅：https://github.com/your-org/sql-optimizer/docs"
    )
    p = argparse.ArgumentParser(
        prog="sqlopt",
        description=(
            "SQL Optimizer CLI - 分析和优化 MyBatis SQL 语句\n"
            "覆盖 run / resume / status / apply 全流程。"
        ),
        epilog=top_epilog,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="抑制进度消息（仅输出 JSON 结果）",
    )
    sub = p.add_subparsers(dest="cmd", required=True, help="可用命令")

    p_run = sub.add_parser(
        "run",
        help="开始新的优化运行",
        description=(
            "启动新的优化运行。\n"
            "默认会自动持续推进，直到 complete=true。"
        ),
        epilog=(
            "示例:\n"
            "  sqlopt-cli run\n"
            "  sqlopt-cli run --config sqlopt.yml --run-id run_demo_001\n"
            "  sqlopt-cli run --to-stage report --run-id <run-id>\n"
            "  sqlopt-cli run --max-steps 3 --max-seconds 60"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p_run.add_argument(
        "--config",
        default="sqlopt.yml",
        help="sqlopt.yml 配置文件路径（默认：./sqlopt.yml）",
    )
    p_run.add_argument(
        "--run-id",
        help="运行 ID（默认自动生成；若指定且已存在，则继续该 run）",
    )
    p_run.add_argument(
        "--to-stage",
        default="patch_generate",
        choices=STAGE_ORDER,
        help="目标运行阶段（默认：patch_generate）。可用阶段：" + ", ".join(STAGE_ORDER),
    )
    p_run.add_argument(
        "--max-steps",
        type=int,
        default=0,
        help="最多推进步骤数（默认：0，不限制，直到完成）",
    )
    p_run.add_argument(
        "--max-seconds",
        type=int,
        default=0,
        help="最多运行秒数（默认：0，不限制，直到完成）",
    )
    p_run.set_defaults(func=cmd_run)

    p_resume = sub.add_parser(
        "resume",
        help="恢复现有运行",
        description=(
            "从中断处恢复运行。\n"
            "默认会持续推进，直到 complete=true。"
        ),
        epilog=(
            "示例:\n"
            "  sqlopt-cli resume\n"
            "  sqlopt-cli resume --run-id <run-id>\n"
            "  sqlopt-cli resume --project /path/to/project --max-steps 1"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p_resume.add_argument(
        "--run-id",
        help="要恢复的运行 ID（默认：自动选择最新运行）",
    )
    p_resume.add_argument(
        "--project",
        default=".",
        help="项目目录，用于在省略 --run-id 时解析最新运行（默认：当前目录）",
    )
    p_resume.add_argument(
        "--max-steps",
        type=int,
        default=0,
        help="最多推进步骤数（默认：0，不限制，直到完成）",
    )
    p_resume.add_argument(
        "--max-seconds",
        type=int,
        default=0,
        help="最多运行秒数（默认：0，不限制，直到完成）",
    )
    p_resume.set_defaults(func=cmd_resume)

    p_status = sub.add_parser(
        "status",
        help="检查运行状态",
        description="显示运行状态、当前阶段、下一步动作（next_action）与完成度。",
        epilog=(
            "示例:\n"
            "  sqlopt-cli status\n"
            "  sqlopt-cli status --run-id <run-id>\n"
            "  sqlopt-cli status --project /path/to/project"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p_status.add_argument(
        "--run-id",
        help="要检查状态的运行 ID（默认：自动选择最新运行）",
    )
    p_status.add_argument(
        "--project",
        default=".",
        help="项目目录，用于在省略 --run-id 时解析最新运行（默认：当前目录）",
    )
    p_status.set_defaults(func=cmd_status)

    p_apply = sub.add_parser(
        "apply",
        help="应用生成的补丁",
        description="应用补丁结果到项目（受 apply mode 控制，如 PATCH_ONLY / APPLY_IN_PLACE）。",
        epilog=(
            "示例:\n"
            "  sqlopt-cli apply\n"
            "  sqlopt-cli apply --run-id <run-id>\n"
            "  sqlopt-cli apply --project /path/to/project"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p_apply.add_argument(
        "--run-id",
        help="要应用其补丁的运行 ID（默认：自动选择最新运行）",
    )
    p_apply.add_argument(
        "--project",
        default=".",
        help="项目目录，用于在省略 --run-id 时解析最新运行（默认：当前目录）",
    )
    p_apply.set_defaults(func=cmd_apply)

    p_validate = sub.add_parser(
        "validate-config",
        help="验证配置文件",
        description=(
            "验证配置文件是否有效且完整。\n"
            "退出码：0=合法，1=不合法，2=执行异常。"
        ),
        epilog=(
            "示例:\n"
            "  sqlopt-cli validate-config --config sqlopt.yml\n"
            "  sqlopt-cli validate-config --config /abs/path/sqlopt.yml"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p_validate.add_argument(
        "--config",
        required=True,
        help="要验证的 sqlopt.yml 配置文件路径",
    )
    p_validate.set_defaults(func=cmd_validate_config)

    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    init_progress_reporter(enabled=not getattr(args, "quiet", False))
    try:
        args.func(args)
    except KeyboardInterrupt:
        print({"interrupted": True, "message": "Interrupted by user (Ctrl+C)"})
        raise SystemExit(130)
