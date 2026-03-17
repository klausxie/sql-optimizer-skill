"""诊断前检查模块 - 在诊断阶段开始前检查配置和询问用户策略。

本模块提供以下功能：
1. 检查 db.dsn 是否有占位符
2. 检查数据库可达性
3. 提供策略选项供用户选择
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..platforms.dispatch import check_db_connectivity
from ..application.config_service import dsn_contains_placeholders, _mask_dsn

# 分支生成策略选项
BRANCH_STRATEGY_OPTIONS = [
    {
        "id": "all_combinations",
        "name": "AllCombinations",
        "description": "生成所有 2^n 组合，覆盖全面",
        "example": "3 个条件 → 8 个分支",
    },
    {
        "id": "pairwise",
        "name": "Pairwise",
        "description": "生成 n 个分支，快速验证",
        "example": "3 个条件 → 3 个分支",
    },
    {
        "id": "boundary",
        "name": "Boundary",
        "description": "生成边界测试用例",
        "example": "3 个条件 → 2 个分支",
    },
]

# 数据库验证策略选项
DB_STRATEGY_OPTIONS = [
    {
        "id": "full",
        "name": "完整验证",
        "description": "需要数据库可达，真实执行 SQL 验证优化效果",
        "requires_db": True,
    },
    {
        "id": "degraded",
        "name": "降级验证",
        "description": "不需要数据库，仅静态分析 + LLM 推测",
        "requires_db": False,
    },
]


def check_dsn_placeholders(config: dict[str, Any]) -> tuple[bool, str | None]:
    """检查 DSN 是否包含占位符。

    Args:
        config: 配置字典

    Returns:
        (has_placeholders, masked_dsn)
    """
    db_cfg = config.get("db") or {}
    dsn = str(db_cfg.get("dsn") or "").strip()
    has_placeholders = dsn_contains_placeholders(dsn)
    masked = _mask_dsn(dsn) if dsn else None
    return has_placeholders, masked


def check_db_reachable(config: dict[str, Any]) -> tuple[bool, str | None]:
    """检查数据库是否可达。

    Args:
        config: 配置字典

    Returns:
        (is_reachable, error_message)
    """
    try:
        result = check_db_connectivity(config)
        ok = bool(result.get("ok", False))
        error = result.get("error") if not ok else None
        return ok, error
    except Exception as e:
        return False, str(e)


def build_strategy_prompt(
    db_configured: bool,
    db_reachable: bool,
    conditions_count: int | None = None,
) -> str:
    """构建策略选择的提示信息。

    Args:
        db_configured: DSN 是否已配置（无占位符）
        db_reachable: 数据库是否可达
        conditions_count: 条件数量（用于分支策略提示）

    Returns:
        格式化的提示字符串
    """
    lines = [
        "=" * 50,
        "诊断配置检查",
        "=" * 50,
        "",
    ]

    # 数据库配置状态
    lines.append("【数据库配置】")
    if db_configured:
        lines.append("  状态: ✅ 已配置")
    else:
        lines.append("  状态: ❌ 存在占位符，请先完善配置")
    lines.append("")

    if db_configured:
        lines.append("【数据库可达性】")
        if db_reachable:
            lines.append("  状态: ✅ 数据库可达")
        else:
            lines.append("  状态: ⚠️ 数据库不可达")
        lines.append("")

    # 数据库验证策略选项
    lines.append("【数据库验证策略】")
    for opt in DB_STRATEGY_OPTIONS:
        lines.append(f"  [{opt['id']}] {opt['name']} - {opt['description']}")
    lines.append("")

    # 分支生成策略选项
    lines.append("【分支生成策略】")
    if conditions_count is not None and conditions_count > 0:
        lines.append(f"  (当前条件数: {conditions_count} 个)")
    for opt in BRANCH_STRATEGY_OPTIONS:
        lines.append(
            f"  [{opt['id']}] {opt['name']} - {opt['description']} ({opt['example']})"
        )
    lines.append("")

    lines.append("=" * 50)
    lines.append("请输入选项 (如: full pairwise 或 degraded boundary)")
    lines.append("格式: <数据库策略> <分支策略>")
    lines.append("=" * 50)

    return "\n".join(lines)


def parse_strategy_choice(user_input: str) -> tuple[str, str] | None:
    """解析用户输入的策略选择。

    Args:
        user_input: 用户输入，如 "full pairwise" 或 "degraded boundary"

    Returns:
        (db_strategy, branch_strategy) 或 None 如果无效
    """
    parts = user_input.strip().lower().split()
    if len(parts) != 2:
        return None

    db_choice, branch_choice = parts

    # 验证数据库策略
    db_valid = any(opt["id"] == db_choice for opt in DB_STRATEGY_OPTIONS)
    # 验证分支策略
    branch_valid = any(opt["id"] == branch_choice for opt in BRANCH_STRATEGY_OPTIONS)

    if db_valid and branch_valid:
        return db_choice, branch_choice

    return None


def get_strategy_from_config(config: dict[str, Any]) -> tuple[str, str]:
    """从配置中获取策略设置。

    Args:
        config: 配置字典

    Returns:
        (db_strategy, branch_strategy)
    """
    # 数据库验证策略
    validate_cfg = config.get("validate") or {}
    db_strategy = (
        "full"
        if validate_cfg.get("allow_db_unreachable_fallback", False) is False
        else "degraded"
    )

    # 分支生成策略
    branch_cfg = config.get("branch") or {}
    branch_strategy_map = {
        "all_combinations": "all_combinations",
        "pairwise": "pairwise",
        "boundary": "boundary",
        "auto": "pairwise",  # auto 默认用 pairwise
    }
    branch_strategy = branch_strategy_map.get(
        branch_cfg.get("strategy", "auto"), "pairwise"
    )

    return db_strategy, branch_strategy


def check_and_prepare(
    config: dict[str, Any],
    conditions_count: int | None = None,
) -> dict[str, Any]:
    """执行诊断前检查并准备策略配置。

    这个函数会：
    1. 检查 DSN 是否有占位符
    2. 检查数据库可达性
    3. 从配置中获取当前策略设置
    4. 返回检查结果和策略信息，供上层调用者（如 Skill）使用

    Args:
        config: 配置字典
        conditions_count: 条件数量（可选）

    Returns:
        {
            "db_configured": bool,
            "db_reachable": bool,
            "db_strategy": str,  # "full" or "degraded"
            "branch_strategy": str,  # "all_combinations" / "pairwise" / "boundary"
            "needs_user_choice": bool,  # 是否需要用户选择策略
            "prompt": str,  # 格式化的提示信息
        }
    """
    # 检查 DSN 占位符
    has_placeholders, masked_dsn = check_dsn_placeholders(config)
    db_configured = not has_placeholders

    # 检查数据库可达性
    db_reachable = False
    error_msg = None
    if db_configured:
        db_reachable, error_msg = check_db_reachable(config)

    # 从配置获取当前策略
    db_strategy, branch_strategy = get_strategy_from_config(config)

    # 构建提示信息
    prompt = build_strategy_prompt(
        db_configured=db_configured,
        db_reachable=db_reachable,
        conditions_count=conditions_count,
    )

    needs_user_choice = True

    return {
        "db_configured": db_configured,
        "db_reachable": db_reachable,
        "db_strategy": db_strategy,
        "branch_strategy": branch_strategy,
        "needs_user_choice": needs_user_choice,
        "prompt": prompt,
        "error_message": error_msg,
        "masked_dsn": masked_dsn,
    }


def apply_strategy_choice(
    config: dict[str, Any],
    db_strategy: str,
    branch_strategy: str,
) -> dict[str, Any]:
    """应用用户选择的策略到配置中。

    Args:
        config: 原始配置字典
        db_strategy: 数据库策略 ("full" 或 "degraded")
        branch_strategy: 分支策略

    Returns:
        更新后的配置字典（深拷贝）
    """
    import copy

    config = copy.deepcopy(config)

    # 更新数据库验证策略
    if "validate" not in config:
        config["validate"] = {}
    config["validate"]["allow_db_unreachable_fallback"] = db_strategy == "degraded"

    # 更新分支生成策略
    if "branch" not in config:
        config["branch"] = {}
    config["branch"]["strategy"] = branch_strategy

    return config
