"""LLM 语义等价性检查

在 validate 阶段使用 LLM 判断原始 SQL 和改写 SQL 是否语义等价。
主要用于：
1. DB 验证失败时，提供额外的语义判断依据
2. 标记 DB 验证失败但 LLM 认为等价的案例，供人工审核
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LlmSemanticResult:
    """LLM 语义判断结果"""
    equivalent: bool  # 是否语义等价
    confidence: str  # "low", "medium", "high"
    reasoning: str  # 判断理由
    risk_flags: list[str]  # 风险标记


def build_semantic_check_prompt(
    original_sql: str,
    rewritten_sql: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构建语义等价性检查的 prompt

    Args:
        original_sql: 原始 SQL
        rewritten_sql: 改写后的 SQL
        context: 额外上下文（如表结构、执行结果等）

    Returns:
        用于 LLM 调用的 prompt 字典
    """
    context = context or {}

    return {
        "task": "sql_semantic_equivalence_check",
        "original_sql": original_sql,
        "rewritten_sql": rewritten_sql,
        "requiredContext": {
            "db_platform": context.get("db_platform", "unknown"),
            "tables_involved": context.get("tables", []),
            "db_result_comparison": context.get("db_result", {}),
        },
        "optionalContext": {
            "original_explain_plan": context.get("original_plan"),
            "rewritten_explain_plan": context.get("rewritten_plan"),
            "original_result_sample": context.get("original_result_sample"),
            "rewritten_result_sample": context.get("rewritten_result_sample"),
        },
        "judgment_criteria": {
            "must_preserve": [
                "结果集行数（在相同数据下）",
                "列的顺序和类型",
                "WHERE 条件的语义",
                "JOIN 的类型和条件",
                "聚合函数的逻辑",
            ],
            "acceptable_differences": [
                "列的别名变化",
                "表达式等价变形（如 a+b 与 b+a）",
                "查询顺序不同但结果相同（无 ORDER BY 时）",
            ],
            "unacceptable_differences": [
                "结果集行数不同",
                "列数或类型不同",
                "过滤条件改变",
                "JOIN 类型改变（如 INNER 变 LEFT）",
                "聚合逻辑改变",
            ],
        },
    }


def parse_llm_semantic_response(
    response_text: str,
    default_confidence: str = "low",
    original_sql: str = "",
    rewritten_sql: str = "",
) -> LlmSemanticResult:
    """解析 LLM 语义判断响应

    Args:
        response_text: LLM 返回的响应文本
        default_confidence: 默认置信度
        original_sql: 原始 SQL（用于风险检测）
        rewritten_sql: 改写 SQL（用于风险检测）

    Returns:
        LlmSemanticResult 对象
    """
    import re

    response_lower = response_text.lower()

    # 判断是否等价
    equivalent = False
    if any(kw in response_lower for kw in ["语义等价", "semantically equivalent", "语义相同", "equivalent"]):
        if "不等价" not in response_lower and "not equivalent" not in response_lower:
            equivalent = True

    # 提取置信度
    confidence = default_confidence
    if "high" in response_lower or "高置信度" in response_lower or "confidence: high" in response_lower:
        confidence = "high"
    elif "medium" in response_lower or "中置信度" in response_lower or "confidence: medium" in response_lower:
        confidence = "medium"
    elif "low" in response_lower or "低置信度" in response_lower or "confidence: low" in response_lower:
        confidence = "low"

    # 提取理由
    reasoning = response_text.strip()
    reasoning_match = re.search(r"(?:理由 | reasoning|原因|analysis)[:：]?\s*(.+)", response_text, re.IGNORECASE | re.DOTALL)
    if reasoning_match:
        reasoning = reasoning_match.group(1).strip()

    # 检测风险标记
    risk_flags: list[str] = []
    original_upper = original_sql.upper()
    rewritten_upper = rewritten_sql.upper()
    if "ORDER BY" in original_upper and "ORDER BY" not in rewritten_upper:
        risk_flags.append("ORDER_BY_REMOVED")
    if "LIMIT" in original_upper and "LIMIT" not in rewritten_upper:
        risk_flags.append("LIMIT_REMOVED")
    if "DISTINCT" in original_upper and "DISTINCT" not in rewritten_upper:
        risk_flags.append("DISTINCT_REMOVED")

    return LlmSemanticResult(
        equivalent=equivalent,
        confidence=confidence,
        reasoning=reasoning,
        risk_flags=risk_flags,
    )


def check_semantic_equivalence(
    original_sql: str,
    rewritten_sql: str,
    llm_cfg: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> LlmSemanticResult:
    """使用 LLM 判断两个 SQL 是否语义等价

    Args:
        original_sql: 原始 SQL
        rewritten_sql: 改写后的 SQL
        llm_cfg: LLM 配置
        context: 额外上下文

    Returns:
        LlmSemanticResult 对象
    """
    # 构建 prompt
    prompt = build_semantic_check_prompt(original_sql, rewritten_sql, context)

    # 调用 LLM
    # 注意：这里复用 provider 的基础设施，但不使用 candidate 生成逻辑
    from ...llm.provider import _run_opencode, _opencode_builtin_candidate
    from ...llm.retry_context import build_retry_prompt

    provider = llm_cfg.get("provider", "opencode_builtin")

    try:
        if provider == "opencode_run":
            # 使用 opencode_run 执行语义判断
            candidates, _ = _run_opencode(
                sql_key="semantic_check",
                prompt=prompt,
                llm_cfg=llm_cfg,
            )
            response_text = candidates[0].get("rewrittenSql", "") if candidates else ""
        else:
            # 使用内置模式（降级）
            # 对于语义检查，内置模式返回一个保守的响应
            response_text = "语义等价性需要外部 LLM 验证；内置模式无法执行深度语义分析"

        # 解析响应
        result = parse_llm_semantic_response(response_text, original_sql=original_sql, rewritten_sql=rewritten_sql)
        return result

    except Exception as exc:
        # LLM 调用失败，返回保守结果
        return LlmSemanticResult(
            equivalent=False,
            confidence="low",
            reasoning=f"LLM 调用失败：{str(exc)}",
            risk_flags=["LLM_UNAVAILABLE"],
        )


def integrate_llm_semantic_check(
    original_sql: str,
    rewritten_sql: str,
    db_equivalence_result: dict[str, Any],
    llm_cfg: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> tuple[bool, list[str], dict[str, Any]]:
    """集成 LLM 语义检查到 validate 阶段

    当 DB 语义验证失败时，使用 LLM 进行额外判断。
    如果 LLM 认为语义等价，标记为需要人工审核而非直接失败。

    Args:
        original_sql: 原始 SQL
        rewritten_sql: 改写后的 SQL
        db_equivalence_result: DB 语义验证结果
        llm_cfg: LLM 配置
        config: 配置字典

    Returns:
        (should_override_failure, warnings, llm_result_dict)
        - should_override_failure: 是否应该覆盖失败状态
        - warnings: 警告列表
        - llm_result_dict: LLM 结果字典
    """
    warnings: list[str] = []
    llm_result_dict: dict[str, Any] = {}

    # 检查配置是否启用
    validate_cfg = (config or {}).get("validate", {}) or {}
    llm_semantic_cfg = validate_cfg.get("llm_semantic_check", {})
    enabled = bool(llm_semantic_cfg.get("enabled", False))
    only_on_db_mismatch = bool(llm_semantic_cfg.get("only_on_db_mismatch", True))

    if not enabled:
        return False, warnings, llm_result_dict

    # 判断是否需要 LLM 检查
    row_status = (db_equivalence_result.get("rowCount") or {}).get("status")
    db_semantic_match = row_status == "MATCH"
    db_semantic_error = row_status == "ERROR"
    db_semantic_mismatch = row_status == "MISMATCH"

    # 如果 DB 验证通过，不需要 LLM 检查
    if db_semantic_match and only_on_db_mismatch:
        return False, warnings, llm_result_dict

    # 如果 DB 验证失败或错误，使用 LLM 检查
    if db_semantic_mismatch or db_semantic_error:
        context = {
            "db_platform": (config or {}).get("db", {}).get("platform", "unknown"),
            "db_result": db_equivalence_result,
        }

        llm_result = check_semantic_equivalence(
            original_sql=original_sql,
            rewritten_sql=rewritten_sql,
            llm_cfg=llm_cfg,
            context=context,
        )

        llm_result_dict = {
            "equivalent": llm_result.equivalent,
            "confidence": llm_result.confidence,
            "reasoning": llm_result.reasoning,
            "risk_flags": llm_result.risk_flags,
        }

        # 如果 LLM 认为语义等价但 DB 验证失败，标记警告
        if llm_result.equivalent and db_semantic_mismatch:
            warnings.append("VALIDATE_LLM_SEMANTIC_EQUIVALENT_BUT_DB_MISMATCH")
            # 高置信度时可以考虑覆盖失败状态
            if llm_result.confidence == "high":
                return True, warnings, llm_result_dict

        # 如果 DB 验证错误，LLM 提供额外信息
        if db_semantic_error:
            warnings.append("VALIDATE_LLM_SEMANTIC_CHECK_PROVIDES_REASONING")

    return False, warnings, llm_result_dict
