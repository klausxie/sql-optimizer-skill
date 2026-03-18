from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

# Windows UTF-8 encoding fix
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass  # Fallback to default if reconfigure not available

from sqlopt.application import config_service, run_index, run_service
from sqlopt.application.run_resolution import resolve_run_id
from sqlopt.application import workflow_v8
from sqlopt.config import load_config
from sqlopt.error_messages import format_error_message
from sqlopt.errors import ConfigError, StageError
from sqlopt.progress import get_progress_reporter, init_progress_reporter
from sqlopt.run_paths import canonical_paths
from sqlopt.verification import read_verification_ledger, summarize_records

# V8 为默认引擎
STAGE_ORDER = workflow_v8.STAGE_ORDER


def _get_stage_order(use_v8: bool) -> list[str]:
    """根据引擎类型返回阶段顺序。"""
    return workflow_v8.STAGE_ORDER


def _repo_root() -> Path:
    return Path.cwd().resolve()


def _run_label(run_id: str | None) -> str:
    value = str(run_id or "").strip()
    return value if value else "latest"


def _resolve_requested_run_id(
    requested_run_id: str | None, project: str | Path | None = None
) -> str:
    # Keep explicit run_id passthrough for backward compatibility; only auto-resolve when omitted.
    if str(requested_run_id or "").strip():
        return str(requested_run_id)
    resolved_run_id, _ = resolve_run_id(None, project=project, repo_root=_repo_root())
    return resolved_run_id


def _resolve_run_dir(run_id: str) -> Path:
    """Compatibility wrapper for run directory resolution."""
    return run_index.resolve_run_dir(run_id, repo_root_fn=_repo_root)


def _interrupt_payload(
    run_id: str | None, *, next_action: str | None = None
) -> dict[str, Any]:
    return run_service.build_interrupt_payload(
        _run_label(run_id), next_action=next_action
    )


def _validate_budget_args(args: argparse.Namespace) -> None:
    if int(getattr(args, "max_steps", 0)) < 0:
        raise ValueError("max_steps must be >= 0")
    if int(getattr(args, "max_seconds", 0)) < 0:
        raise ValueError("max_seconds must be >= 0")


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
        error_info = format_error_message(
            "CONFIG_NOT_FOUND", f"Config file not found: {config_path}"
        )
        fallback_run_id = args.run_id or "<pending>"
        print({"run_id": fallback_run_id, "error": error_info})
        raise SystemExit(2)

    validation_result = config_service.validate_config(
        config_path, check_connectivity=True
    )
    if not validation_result.get("valid", False):
        error_info = format_error_message(
            "CONFIG_INVALID",
            f"Configuration validation failed: {validation_result.get('error', 'Unknown error')}",
        )
        fallback_run_id = args.run_id or "<pending>"
        print(
            {
                "run_id": fallback_run_id,
                "error": error_info,
                "validation_details": validation_result,
            }
        )
        raise SystemExit(2)

    use_v8 = getattr(args, "use_v8", True)
    repo_root = _repo_root()
    run_id: str | None = None
    requested_run_id = (
        str(args.run_id).strip()
        if str(args.run_id or "").strip()
        else f"run_{uuid4().hex[:12]}"
    )
    try:
        _validate_budget_args(args)
        get_progress_reporter().report_info(f"run_id={requested_run_id}")

        if use_v8:
            # V8 引擎路径
            config = load_config(config_path)
            from sqlopt.application.workflow_v8 import V8WorkflowEngine

            runs_root = Path(config["project"]["root_path"]).resolve() / "runs"
            run_dir = runs_root / requested_run_id
            run_dir.mkdir(parents=True, exist_ok=True)

            engine = workflow_v8.V8WorkflowEngine(config, run_id=requested_run_id)
            to_stage = getattr(args, "to_stage", "patch")
            result = engine.run(run_dir, to_stage=to_stage)

            print(
                {
                    "run_id": requested_run_id,
                    "engine": "v8",
                    "result": result,
                    "completed": engine.state.status == "completed",
                }
            )
        else:
            # 旧版引擎路径
            selection = {
                "mapper_paths": list(getattr(args, "mapper_path", None) or []),
                "sql_keys": list(getattr(args, "sql_key", None) or []),
            }
            run_id, initial_result = run_service.start_run(
                config_path,
                args.to_stage,
                requested_run_id,
                repo_root=repo_root,
                selection=selection,
            )
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
        message = (
            f"run_id not found in run index: {run_id}"
            if run_id
            else f"Config file not found: {config_path}"
        )
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
        next_action = (
            f"sqlopt-cli resume --run-id {target_run_id}"
            if target_run_id not in {"<pending>", "latest"}
            else None
        )
        print(_interrupt_payload(target_run_id, next_action=next_action))
        raise SystemExit(130)


def cmd_resume(args: argparse.Namespace) -> None:
    resolved_run_id: str | None = None
    try:
        _validate_budget_args(args)
        resolved_run_id = _resolve_requested_run_id(
            getattr(args, "run_id", None), getattr(args, "project", ".")
        )
        get_progress_reporter().report_info(f"run_id={resolved_run_id}")

        use_v8 = getattr(args, "use_v8", True)
        if use_v8:
            # V8 引擎路径
            run_dir = run_index.resolve_run_dir(
                resolved_run_id, repo_root_fn=_repo_root
            )
            paths = canonical_paths(run_dir)
            config = load_config(paths.config_resolved_path)

            engine = workflow_v8.V8WorkflowEngine(config, run_id=resolved_run_id)
            engine.load_state_from_repo()
            to_stage = getattr(args, "to_stage", "patch")
            result = engine.resume(run_dir, to_stage=to_stage)

            print(
                {
                    "run_id": resolved_run_id,
                    "engine": "v8",
                    "result": result,
                    "completed": engine.state.status == "completed",
                }
            )
        else:
            # 旧版引擎路径
            initial_result = run_service.resume_run(
                resolved_run_id, repo_root=_repo_root()
            )
            outcome = run_service.advance_run_until_complete(
                resolved_run_id,
                initial_result,
                step_fn=lambda: run_service.resume_run(
                    resolved_run_id or "", repo_root=_repo_root()
                ),
                max_steps=int(args.max_steps),
                max_seconds=int(args.max_seconds),
            )
            print(run_service.build_progress_payload(resolved_run_id, outcome))
    except ValueError as exc:
        error_info = format_error_message("CONFIG_INVALID", str(exc))
        print(
            {"run_id": _run_label(getattr(args, "run_id", None)), "error": error_info}
        )
        raise SystemExit(2)
    except FileNotFoundError:
        error_info = format_error_message(
            "RUN_NOT_FOUND", "run_id not found in run index"
        )
        print(
            {
                "run_id": _run_label(resolved_run_id or getattr(args, "run_id", None)),
                "error": error_info,
            }
        )
        raise SystemExit(2)
    except StageError as exc:
        error_info = format_error_message(exc.reason_code or "UNKNOWN_ERROR", str(exc))
        print(
            {
                "run_id": _run_label(resolved_run_id or getattr(args, "run_id", None)),
                "error": error_info,
            }
        )
        raise SystemExit(2)
    except KeyboardInterrupt:
        target_run_id = resolved_run_id or getattr(args, "run_id", None)
        next_action = (
            f"sqlopt-cli resume --run-id {target_run_id}" if target_run_id else None
        )
        print(_interrupt_payload(target_run_id, next_action=next_action))
        raise SystemExit(130)


def cmd_status(args: argparse.Namespace) -> None:
    resolved_run_id: str | None = None
    try:
        resolved_run_id = _resolve_requested_run_id(
            getattr(args, "run_id", None), getattr(args, "project", ".")
        )
        output_format = getattr(args, "format", "json")
        use_v8 = getattr(args, "use_v8", True)

        if use_v8:
            # V8 引擎路径
            run_dir = run_index.resolve_run_dir(
                resolved_run_id, repo_root_fn=_repo_root
            )
            paths = canonical_paths(run_dir)
            config = load_config(paths.config_resolved_path)

            engine = workflow_v8.V8WorkflowEngine(config, run_id=resolved_run_id)
            engine.load_state_from_repo()

            status_result = {
                "run_id": engine.state.run_id,
                "status": engine.state.status,
                "current_stage": engine.state.current_stage,
                "completed_stages": engine.state.completed_stages,
                "stage_results": engine.state.stage_results,
                "started_at": engine.state.started_at,
                "updated_at": engine.state.updated_at,
                "completed": engine.state.status == "completed",
            }

            if output_format == "summary":
                print(f"=== Run Status Summary (V8) ===")
                print(f"Run ID:    {engine.state.run_id}")
                print(
                    f"Status:    {engine.state.status} {'✓' if engine.state.status == 'completed' else '...'}"
                )
                print(f"Current:   {engine.state.current_stage or 'none'}")
                print(
                    f"Completed: {', '.join(engine.state.completed_stages) or 'none'}"
                )
            else:
                print(status_result)
        else:
            # 旧版引擎路径
            status_result = run_service.get_status(
                resolved_run_id, repo_root=_repo_root()
            )

            if output_format == "summary":
                run_id = status_result.get("run_id", resolved_run_id or "unknown")
                phase = status_result.get("phase", "unknown")
                status = status_result.get("status", "unknown")
                completed = status_result.get("completed", False)
                total_sql = status_result.get("total_sql", 0)
                completed_sql = status_result.get("completed_sql", 0)
                progress_pct = status_result.get("progress_percentage", 0.0)

                print(f"=== Run Status Summary ===")
                print(f"Run ID:    {run_id}")
                print(f"Status:    {status} {'✓' if completed else '...'}")
                print(f"Phase:     {phase}")
                print(
                    f"Progress:  {completed_sql}/{total_sql} SQL ({progress_pct:.1f}%)"
                )

                # Show next action if available
                next_action = status_result.get("next_action")
                if next_action:
                    print(f"Next:      {next_action}")

                # Show errors if any
                errors = status_result.get("errors", [])
                if errors:
                    print(f"Errors:    {len(errors)}")
                    for err in errors[:3]:  # Show first 3 errors
                        print(f"  - {err}")
            else:
                # JSON format (default)
                print(status_result)
    except FileNotFoundError:
        error_info = format_error_message(
            "RUN_NOT_FOUND", "run_id not found in run index"
        )
        print(
            {
                "run_id": _run_label(resolved_run_id or getattr(args, "run_id", None)),
                "error": error_info,
            }
        )
        raise SystemExit(2)


def cmd_validate_config(args: argparse.Namespace) -> None:
    config_path = Path(args.config).resolve()

    if not config_path.exists():
        error_info = format_error_message(
            "CONFIG_NOT_FOUND", f"Config file not found: {config_path}"
        )
        print({"error": error_info})
        raise SystemExit(2)

    try:
        results = config_service.validate_config(config_path, check_connectivity=True)
        print(results)
        raise SystemExit(0 if results["valid"] else 1)

    except Exception as exc:
        error_info = format_error_message("CONFIG_INVALID", str(exc))
        print({"error": error_info})
        raise SystemExit(2)


def cmd_apply(args: argparse.Namespace) -> None:
    resolved_run_id: str | None = None
    try:
        resolved_run_id = _resolve_requested_run_id(
            getattr(args, "run_id", None), getattr(args, "project", ".")
        )

        if not getattr(args, "force", False):
            run_dir = run_index.resolve_run_dir(
                resolved_run_id, repo_root_fn=_repo_root
            )
            from sqlopt.stages.patch.apply import _resolved_config

            try:
                cfg = _resolved_config(run_dir)
                apply_cfg = (
                    (cfg.get("apply", {}) or {}) if isinstance(cfg, dict) else {}
                )
                mode = str(apply_cfg.get("mode", "PATCH_ONLY")).strip().upper()

                if mode == "APPLY_IN_PLACE":
                    from sqlopt.stages.patch.apply import _collect_patch_files

                    patch_files = _collect_patch_files(run_dir)
                    if patch_files:
                        print(f"\n警告: 即将修改 {len(patch_files)} 个文件!")
                        print("将使用 git apply 命令应用补丁。")
                        response = input("\n确认应用补丁? (y/N): ")
                        if response.lower() not in ("y", "yes"):
                            print("已取消操作。")
                            return
            except Exception:
                pass

        print(run_service.apply_run(resolved_run_id, repo_root=_repo_root()))
    except FileNotFoundError:
        error_info = format_error_message(
            "RUN_NOT_FOUND", "run_id not found in run index"
        )
        print(
            {
                "run_id": _run_label(resolved_run_id or getattr(args, "run_id", None)),
                "error": error_info,
            }
        )
        raise SystemExit(2)


def cmd_verify(args: argparse.Namespace) -> None:
    """验证证据链，显示验证结果摘要。"""
    resolved_run_id: str | None = None
    try:
        resolved_run_id = _resolve_requested_run_id(
            getattr(args, "run_id", None), getattr(args, "project", ".")
        )
        run_dir = run_index.resolve_run_dir(resolved_run_id, repo_root_fn=_repo_root)
        paths = canonical_paths(run_dir)

        ledger_path = paths.verification_ledger_path
        if not ledger_path.exists():
            error_info = format_error_message(
                "VERIFICATION_NOT_FOUND",
                f"验证账本不存在: {ledger_path}",
            )
            print(
                {
                    "run_id": resolved_run_id,
                    "error": error_info,
                    "hint": "请先运行 sqlopt-cli run 完成优化流程",
                }
            )
            raise SystemExit(2)

        records = read_verification_ledger(run_dir)

        # Filter by sql_key if specified
        sql_key_filter = getattr(args, "sql_key", None)
        if sql_key_filter:
            records = [r for r in records if r.get("sql_key") == sql_key_filter]
            if not records:
                print(
                    {
                        "run_id": resolved_run_id,
                        "sql_key": sql_key_filter,
                        "error": f"未找到 sql_key={sql_key_filter} 的验证记录",
                    }
                )
                raise SystemExit(1)

        verbose = getattr(args, "verbose", False)

        if verbose:
            # 详细模式：输出完整记录
            result = {
                "run_id": resolved_run_id,
                "record_count": len(records),
                "records": records,
            }
        else:
            # 摘要模式
            # 获取 total_sql from plan.json
            total_sql = 0
            plan_path = paths.plan_path
            if plan_path.exists():
                import json

                try:
                    with open(plan_path, "r", encoding="utf-8") as f:
                        plan_data = json.load(f)
                        total_sql = len(plan_data.get("statements", []))
                except Exception:
                    pass

            summary = summarize_records(resolved_run_id, records, total_sql=total_sql)
            result = summary.to_contract()

        print(result)

    except FileNotFoundError:
        error_info = format_error_message(
            "RUN_NOT_FOUND", "run_id not found in run index"
        )
        print(
            {
                "run_id": _run_label(resolved_run_id or getattr(args, "run_id", None)),
                "error": error_info,
            }
        )
        raise SystemExit(2)


def build_parser() -> argparse.ArgumentParser:
    top_epilog = (
        "快速工作流:\n"
        "  1) sqlopt-cli validate-config --config sqlopt.yml\n"
        "  2) sqlopt-cli run --config sqlopt.yml\n"
        "  3) sqlopt-cli status\n"
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
        description=("启动新的优化运行。\n默认会自动持续推进，直到 complete=true。"),
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
        "--mapper-path",
        action="append",
        default=[],
        help="仅扫描指定 mapper 相对路径（可重复），相对于 project.root_path",
    )
    p_run.add_argument(
        "--sql-key",
        action="append",
        default=[],
        help="仅执行指定 SQL（可重复）。支持 full sqlKey、namespace.statementId、statementId、statementId#vN；若匹配多个会报出候选",
    )
    p_run.add_argument(
        "--run-id",
        help="运行 ID（默认自动生成；若指定且已存在，则继续该 run）",
    )
    # 合并 V8 和旧版阶段作为有效选项
    p_run.add_argument(
        "--to-stage",
        default="patch",
        choices=STAGE_ORDER,
        help="目标运行阶段（默认：patch）",
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
    p_run.add_argument(
        "--use-v8",
        type=lambda x: x.lower() not in ("false", "0", "no"),
        default=True,
        help="使用 V8 引擎（默认：True）。设为 false 使用旧版引擎",
    )
    p_run.set_defaults(func=cmd_run)

    p_resume = sub.add_parser(
        "resume",
        help="恢复现有运行",
        description=("从中断处恢复运行。\n默认会持续推进，直到 complete=true。"),
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
    p_resume.add_argument(
        "--use-v8",
        type=lambda x: x.lower() not in ("false", "0", "no"),
        default=True,
        help="使用 V8 引擎（默认：True）。设为 false 使用旧版引擎",
    )
    p_resume.add_argument(
        "--to-stage",
        default="patch",
        choices=STAGE_ORDER,
        help="目标运行阶段（默认：patch）",
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
    p_status.add_argument(
        "--format",
        choices=["json", "summary"],
        default="json",
        help="输出格式：json（默认）或 summary（人类可读摘要）",
    )
    p_status.add_argument(
        "--use-v8",
        type=lambda x: x.lower() not in ("false", "0", "no"),
        default=True,
        help="使用 V8 引擎（默认：True）。设为 false 使用旧版引擎",
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
    p_apply.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="强制应用补丁，无需确认（适用于 APPLY_IN_PLACE 模式）",
    )
    p_apply.set_defaults(func=cmd_apply)

    p_validate = sub.add_parser(
        "validate-config",
        help="验证配置文件",
        description=(
            "验证配置文件是否有效且完整。\n退出码：0=合法，1=不合法，2=执行异常。"
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

    p_verify = sub.add_parser(
        "verify",
        help="验证证据链",
        description="验证优化流程的证据链完整性，显示验证结果摘要。",
        epilog=(
            "示例:\n"
            "  sqlopt-cli verify\n"
            "  sqlopt-cli verify --run-id <run-id>\n"
            "  sqlopt-cli verify --run-id <run-id> --sql-key <sql-key>\n"
            "  sqlopt-cli verify --run-id <run-id> --verbose"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p_verify.add_argument(
        "--run-id",
        help="要验证的运行 ID（默认：自动选择最新运行）",
    )
    p_verify.add_argument(
        "--project",
        default=".",
        help="项目目录，用于在省略 --run-id 时解析最新运行（默认：当前目录）",
    )
    p_verify.add_argument(
        "--sql-key",
        help="仅验证指定 SQL 的证据链",
    )
    p_verify.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="显示详细验证记录",
    )
    p_verify.set_defaults(func=cmd_verify)

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
