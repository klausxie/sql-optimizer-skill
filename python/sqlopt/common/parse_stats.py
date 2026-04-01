"""Shared data classes for parse stage reporting — unified data layer for SUMMARY.html.

All report generation functions consume ParseStageStats instead of computing independently.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import floor
from typing import Optional

from sqlopt.contracts.parse import ParseOutput, SQLUnitWithBranches

# ruff: noqa: RUF001, RUF003

# Strategy names and Chinese display names (shared constant)
STRATEGY_NAMES = {
    "all_combinations": "全组合（所有条件排列）",
    "each": "单测（每个条件单独测）",
    "boundary": "边界值（极值测试）",
    "ladder": "阶梯采样（智能加权）",
}

# Strategy explanations (shared constant, used in both T4 and T8)
STRATEGY_EXPLANATIONS = {
    "all_combinations": "全组合策略会生成所有条件的所有可能组合。当条件数较多时，分支数呈指数增长（2^n）。",
    "each": "单测策略每个条件单独为 true/false，分支数随条件数线性增长（n）。",
    "boundary": "边界值策略只生成极值情况（全 true / 全 false / 各一个 false 等），分支数最少（约 n+1）。",
    "ladder": "阶梯采样策略结合了高权重两两组合和边界覆盖，在覆盖率和分支数之间取得平衡。",
}


# 极值理论分支阈值 — 超过此值视为"分支爆炸"风险单元
OUTLIER_THEORETICAL_BRANCHES_THRESHOLD: int = 1_000_000


@dataclass
class PerUnitBranchStats:
    """Per-unit branch statistics with enhanced explainability fields."""

    sql_unit_id: str
    cond_count: int
    theoretical_branches: int
    actual_branches: int
    valid_branches: int
    error_branches: int
    coverage_pct: float
    # Branch type distribution: {"error": N, "baseline_only": N, "normal": N}
    branch_type_dist: dict[str, int]
    top_risk_flag: Optional[str]

    # --- 增强可解释性：理论分支推理过程 ---
    # 每行一个推理步骤，展示完整推导过程
    # Example: [
    #   "IF1: true分支(1) + false分支(1) = 2",
    #   "IF2: true分支(1) + false分支(1) = 2",
    #   "组合: 2 × 2 = 4 理论分支"
    # ]
    formula_steps: list[str]
    # 结论: "4 个理论分支（全组合）"
    formula_conclusion: str

    # --- 增强可解释性：策略行为解读 ---
    strategy_name: str  # "ladder"
    strategy_display: str  # "阶梯采样（智能加权）"
    strategy_actual: str  # "采样 5/8 分支"
    strategy_saved: str  # "节省 37.5%"
    strategy_meaning: str  # "覆盖率 62.5% = 每 10 个分支有 6 个被测试"
    strategy_whatif: str


@dataclass
class ParseStageStats:
    """Aggregated parse stage statistics — single source of truth for all reporting."""

    run_id: str
    duration_seconds: float
    total_units: int
    total_branches: int
    sum_theoretical: int  # sum of all units' theoretical_branches
    coverage_pct: float  # global: total_branches / sum_theoretical
    valid_branches: int
    invalid_branches: int
    error_branches: int
    failed_units: int
    strategy: str  # current strategy key
    max_branches: int
    # 全局分布
    cond_distribution: list[tuple[str, int]]  # [(condition, count), ...] Top 10
    risk_flag_distribution: list[tuple[str, int]]  # Top 15
    branch_type_distribution: dict[str, int]  # {"error": N, "baseline_only": N, "normal": N}
    high_risk_branches: int
    medium_risk_branches: int
    low_risk_branches: int
    per_unit: list[PerUnitBranchStats]

    # --- 极值分离统计 ---
    outlier_units: list[OutlierUnitStats]
    normal_sum_theoretical: int
    normal_total_branches: int
    normal_coverage_pct: float
    outlier_count: int
    normal_count: int


@dataclass
class OutlierUnitStats:
    """极值单元统计 — theoretical_branches 超过阈值的单元."""

    sql_unit_id: str
    cond_count: int
    theoretical_branches: int
    actual_branches: int
    coverage_pct: float
    reason: str


def build_parse_stage_stats(
    output: ParseOutput,
    total_branches: int,
    failed_units: int,
    duration_seconds: float,
    run_id: str,
) -> ParseStageStats:
    """Build ParseStageStats from ParseOutput — single data source for all reports.

    This function consolidates all statistical computation so that HTML and any future
    report formats consume the same pre-computed data.

    Args:
        output: ParseOutput from parse stage
        total_branches: Pre-computed total branch count
        failed_units: Number of units that failed to expand
        duration_seconds: Total execution time
        run_id: Run identifier

    Returns:
        ParseStageStats ready for report generation
    """
    units = output.sql_units_with_branches
    total_units = len(units)

    # Per-unit stats
    per_unit: list[PerUnitBranchStats] = []
    sum_theoretical = 0
    valid_branches = 0
    invalid_branches = 0
    error_branches = 0
    all_conditions: list[str] = []
    all_flags: list[str] = []
    high_risk = 0
    medium_risk = 0
    low_risk = 0
    branch_type_dist: dict[str, int] = {"error": 0, "baseline_only": 0, "normal": 0}
    # --- 极值分离统计 ---
    outlier_units: list[OutlierUnitStats] = []
    normal_sum_theoretical = 0
    normal_total_branches = 0
    medium_risk = 0
    low_risk = 0
    branch_type_dist: dict[str, int] = {"error": 0, "baseline_only": 0, "normal": 0}

    for u in units:
        # Count conditions from active_conditions across all branches
        unique_conds: set[str] = set()
        for b in u.branches:
            for c in b.active_conditions:
                unique_conds.add(c)
            all_conditions.extend(b.active_conditions)
        cond_count = len(unique_conds)

        # Branch counts
        unit_valid = sum(1 for b in u.branches if b.is_valid)
        unit_error = sum(1 for b in u.branches if b.branch_type == "error")
        unit_branch_types: dict[str, int] = {}
        for b in u.branches:
            bt = b.branch_type or "normal"
            unit_branch_types[bt] = unit_branch_types.get(bt, 0) + 1
            branch_type_dist[bt] = branch_type_dist.get(bt, 0) + 1

        # Risk levels
        unit_high = sum(1 for b in u.branches if getattr(b, "risk_level", None) == "HIGH")
        unit_medium = sum(1 for b in u.branches if getattr(b, "risk_level", None) == "MEDIUM")
        unit_low = sum(1 for b in u.branches if getattr(b, "risk_level", None) == "LOW")

        # Risk flags
        for b in u.branches:
            all_flags.extend(b.risk_flags)

        # Coverage
        theoretical = u.theoretical_branches if u.theoretical_branches > 0 else 1
        coverage_pct = len(u.branches) / theoretical * 100

        # --- 极值分离统计 ---
        if theoretical > OUTLIER_THEORETICAL_BRANCHES_THRESHOLD:
            if cond_count > 0:
                power = min(cond_count, 30)
                approx = 2**power
                reason = f"{cond_count}个IF条件 → 2^{cond_count} ≈ {approx:,} 理论分支"
            else:
                reason = f"理论分支 {theoretical:,} > {OUTLIER_THEORETICAL_BRANCHES_THRESHOLD:,} 阈值"

            outlier_units.append(
                OutlierUnitStats(
                    sql_unit_id=u.sql_unit_id,
                    cond_count=cond_count,
                    theoretical_branches=theoretical,
                    actual_branches=len(u.branches),
                    coverage_pct=len(u.branches) / theoretical * 100 if theoretical > 0 else 0,
                    reason=reason,
                )
            )
        else:
            normal_sum_theoretical += theoretical
            normal_total_branches += len(u.branches)

        # Top risk flag
        unit_flags = [f for b in u.branches for f in b.risk_flags]
        top_flag: Optional[str] = None
        if unit_flags:
            top_flag = Counter(unit_flags).most_common(1)[0][0]

        # --- Build formula_steps ---
        formula_steps = _build_formula_steps(u, cond_count)
        formula_conclusion = f"{theoretical} 个理论分支"

        # --- Build strategy explanation ---
        strategy_name = getattr(output, "strategy", None) or "unknown"
        strategy_display = STRATEGY_NAMES.get(strategy_name, strategy_name)
        strategy_actual, strategy_saved, strategy_meaning, strategy_whatif = _build_strategy_explanation(
            strategy_name, len(u.branches), theoretical, cond_count
        )

        per_unit.append(
            PerUnitBranchStats(
                sql_unit_id=u.sql_unit_id,
                cond_count=cond_count,
                theoretical_branches=theoretical,
                actual_branches=len(u.branches),
                valid_branches=unit_valid,
                error_branches=unit_error,
                coverage_pct=coverage_pct,
                branch_type_dist=unit_branch_types,
                top_risk_flag=top_flag,
                # Explainability
                formula_steps=formula_steps,
                formula_conclusion=formula_conclusion,
                strategy_name=strategy_name,
                strategy_display=strategy_display,
                strategy_actual=strategy_actual,
                strategy_saved=strategy_saved,
                strategy_meaning=strategy_meaning,
                strategy_whatif=strategy_whatif,
            )
        )

        sum_theoretical += theoretical
        valid_branches += unit_valid
        invalid_branches += len(u.branches) - unit_valid
        error_branches += unit_error
        high_risk += unit_high
        medium_risk += unit_medium
        low_risk += unit_low

    # Global coverage
    global_coverage = (total_branches / sum_theoretical * 100) if sum_theoretical > 0 else 0.0

    # --- 极值分离统计 ---
    normal_coverage_pct = normal_total_branches / normal_sum_theoretical * 100 if normal_sum_theoretical > 0 else 0.0
    outlier_count = len(outlier_units)
    normal_count = total_units - outlier_count

    # Condition distribution
    cond_counter = Counter(all_conditions)
    cond_distribution = cond_counter.most_common(10)

    # Risk flag distribution
    flag_counter = Counter(all_flags)
    risk_flag_distribution = flag_counter.most_common(15)

    return ParseStageStats(
        run_id=run_id,
        duration_seconds=duration_seconds,
        total_units=total_units,
        total_branches=total_branches,
        sum_theoretical=sum_theoretical,
        coverage_pct=global_coverage,
        valid_branches=valid_branches,
        invalid_branches=invalid_branches,
        error_branches=error_branches,
        failed_units=failed_units,
        strategy=getattr(output, "strategy", None) or "unknown",
        max_branches=getattr(output, "max_branches", 0) or 0,
        cond_distribution=cond_distribution,
        risk_flag_distribution=risk_flag_distribution,
        branch_type_distribution=branch_type_dist,
        high_risk_branches=high_risk,
        medium_risk_branches=medium_risk,
        low_risk_branches=low_risk,
        per_unit=per_unit,
        outlier_units=outlier_units,
        normal_sum_theoretical=normal_sum_theoretical,
        normal_total_branches=normal_total_branches,
        normal_coverage_pct=normal_coverage_pct,
        outlier_count=outlier_count,
        normal_count=normal_count,
    )


def _build_formula_steps(u: SQLUnitWithBranches, cond_count: int) -> list[str]:
    """Build step-by-step formula explanation for a SQL unit.

    Reads the actual branch structure to generate meaningful steps.
    Falls back to generic explanation based on cond_count.
    """
    steps: list[str] = []
    if_count = 0
    choose_count = 0
    foreach_count = 0

    # Analyze branch structure to determine node types
    for b in u.branches:
        if b.condition:
            cond = b.condition
            if "choose" in cond.lower() or "when" in cond.lower():
                choose_count += 1
            elif "foreach" in cond.lower():
                foreach_count += 1
            else:
                if_count += 1

    if if_count > 0:
        steps.append(f"IF节点: 每个IF产生 2 个分支 (true/false)，共 {if_count} 个IF")
    if choose_count > 0:
        steps.append(f"Choose节点: 互斥选择 {choose_count} 个when + 1 个default")
    if foreach_count > 0:
        steps.append(f"ForEach节点: 每个产生 3 个分支 (空/单项/多项)，共 {foreach_count} 个ForEach")

    if not steps:
        steps.append(f"共 {cond_count} 个条件")

    return steps


def _build_strategy_explanation(
    strategy: str,
    actual: int,
    theoretical: int,
    cond_count: int,
) -> tuple[str, str, str, str]:
    """Build human-readable strategy behavior explanation.

    Returns: (strategy_actual, strategy_saved, strategy_meaning, strategy_whatif)
    """
    if theoretical <= 0:
        theoretical = 1

    saved_pct = (theoretical - actual) / theoretical * 100 if theoretical > 0 else 0
    coverage_pct = actual / theoretical * 100 if theoretical > 0 else 0

    strategy_actual = f"采样 {actual}/{theoretical} 分支"
    strategy_saved = f"节省 {saved_pct:.1f}%" if saved_pct > 0 else "无节省"
    strategy_meaning = f"覆盖率 {coverage_pct:.1f}% = 每 10 个分支有 {floor(coverage_pct / 10)} 个被测试"

    if strategy == "all_combinations":
        strategy_whatif = "💡 当前已是全组合，覆盖率 100%"
    elif strategy == "each":
        strategy_whatif = f"💡 若需更完整覆盖，可切 all_combinations（需 {theoretical} 分支）"
    elif strategy == "boundary":
        strategy_whatif = f"💡 若需更多分支，可切 each 策略（需 {cond_count * 2} 分支）"
    elif strategy == "ladder":
        strategy_whatif = f"💡 若需更完整覆盖，可切 all_combinations（需 {theoretical} 分支）"
    else:
        strategy_whatif = ""

    return strategy_actual, strategy_saved, strategy_meaning, strategy_whatif
