"""规则引擎 ↔ LLM 双向反馈机制

收集 LLM 在优化过程中发现的问题，反馈给规则引擎用于持续改进。
主要用于：
1. 记录 LLM 发现但规则未覆盖的问题模式
2. 统计 LLM 与规则引擎的差异
3. 为规则优化提供数据依据
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..io_utils import append_jsonl


@dataclass
class LlmFeedbackRecord:
    """LLM 反馈记录"""
    sql_key: str
    run_id: str
    llm_detected_issues: list[dict[str, Any]]  # LLM 发现的问题
    triggered_rules: list[str]  # 触发的规则 ID 列表
    acceptance_status: str  # 最终接受状态
    llm_candidates_count: int = 0  # LLM 生成的候选数量
    valid_candidates_count: int = 0  # 有效候选数量
    validation_errors: list[dict[str, Any]] = field(default_factory=list)  # 验证错误
    metadata: dict[str, Any] = field(default_factory=dict)  # 额外元数据
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class LlmIssuePattern:
    """LLM 发现的问题模式"""
    pattern_type: str  # 问题类型
    description: str  # 问题描述
    frequency: int = 1  # 出现频率
    sample_sql_keys: list[str] = field(default_factory=list)  # 示例 SQL key

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_llm_detected_issues(proposal: dict[str, Any]) -> list[dict[str, Any]]:
    """从 LLM 输出中提取发现的问题

    LLM 可能在分析问题时发现规则引擎未覆盖的模式。

    Args:
        proposal: 优化提案字典

    Returns:
        LLM 发现的问题列表
    """
    issues: list[dict[str, Any]] = []

    # 从 LLM 响应中提取问题
    llm_candidates = proposal.get("llmCandidates", [])
    if not llm_candidates:
        return issues

    for candidate in llm_candidates:
        # 检查是否有 LLM 附加的问题说明
        if "detectedIssues" in candidate:
            issues.extend(candidate["detectedIssues"])

        # 从改写说明中提取潜在问题
        rewrite_reasoning = str(candidate.get("rewriteReasoning", "")).strip()
        if rewrite_reasoning:
            # 检测 LLM 是否提到了性能或安全问题
            issue_keywords = {
                "performance": ["performance", "slow", "full scan", "index"],
                "security": ["sql injection", "security", "unsafe"],
                "semantic": ["semantic", "equivalent", "logic"],
            }

            reasoning_lower = rewrite_reasoning.lower()
            for issue_type, keywords in issue_keywords.items():
                if any(kw in reasoning_lower for kw in keywords):
                    issues.append({
                        "type": issue_type,
                        "source": "llm_reasoning",
                        "description": rewrite_reasoning[:200],  # 限制长度
                    })
                    break

    return issues


def collect_llm_feedback(
    sql_key: str,
    proposal: dict[str, Any],
    acceptance: dict[str, Any] | None,
    run_id: str,
    validation_errors: list[dict[str, Any]] | None = None,
) -> LlmFeedbackRecord:
    """收集单次 SQL 优化的 LLM 反馈

    Args:
        sql_key: SQL 标识符
        proposal: 优化提案
        acceptance: 验证接受结果（可选）
        run_id: 运行 ID
        validation_errors: 验证错误列表（可选）

    Returns:
        LLM 反馈记录
    """
    llm_detected = extract_llm_detected_issues(proposal)

    triggered_rules = [
        str(rule.get("ruleId", ""))
        for rule in (proposal.get("triggeredRules", []) or [])
        if str(rule.get("ruleId", "")).strip()
    ]

    acceptance_status = (acceptance or {}).get("status", "UNKNOWN")

    llm_candidates = proposal.get("llmCandidates", []) or []
    valid_candidates = [c for c in llm_candidates if c.get("passed", True)]

    return LlmFeedbackRecord(
        sql_key=sql_key,
        run_id=run_id,
        llm_detected_issues=llm_detected,
        triggered_rules=triggered_rules,
        acceptance_status=acceptance_status,
        llm_candidates_count=len(llm_candidates),
        valid_candidates_count=len(valid_candidates),
        validation_errors=validation_errors or [],
    )


def save_feedback_record(
    run_dir: Path,
    record: LlmFeedbackRecord,
) -> None:
    """保存反馈记录到文件

    Args:
        run_dir: 运行目录
        record: 反馈记录
    """
    feedback_file = run_dir / "ops" / "llm_feedback.jsonl"
    feedback_file.parent.mkdir(parents=True, exist_ok=True)
    append_jsonl(feedback_file, record.to_dict())


def analyze_feedback_patterns(
    feedback_records: list[LlmFeedbackRecord],
) -> list[LlmIssuePattern]:
    """分析反馈记录，发现高频问题模式

    Args:
        feedback_records: 反馈记录列表

    Returns:
        问题模式列表
    """
    pattern_counts: dict[str, dict[str, Any]] = {}

    for record in feedback_records:
        for issue in record.llm_detected_issues:
            issue_type = str(issue.get("type", "unknown"))
            issue_desc = str(issue.get("description", "unknown")[:50])

            key = f"{issue_type}:{issue_desc}"
            if key not in pattern_counts:
                pattern_counts[key] = {
                    "pattern_type": issue_type,
                    "description": issue_desc,
                    "frequency": 0,
                    "sample_sql_keys": [],
                }

            pattern_counts[key]["frequency"] += 1
            if len(pattern_counts[key]["sample_sql_keys"]) < 5:
                pattern_counts[key]["sample_sql_keys"].append(record.sql_key)

    # 转换为模式列表，按频率排序
    patterns = [
        LlmIssuePattern(**data)
        for data in pattern_counts.values()
    ]
    patterns.sort(key=lambda p: p.frequency, reverse=True)

    return patterns


def save_feedback_analysis(
    run_dir: Path,
    patterns: list[LlmIssuePattern],
) -> None:
    """保存反馈分析结果

    Args:
        run_dir: 运行目录
        patterns: 问题模式列表
    """
    analysis_file = run_dir / "ops" / "llm_feedback_analysis.json"
    analysis_file.parent.mkdir(parents=True, exist_ok=True)

    analysis_data = {
        "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_patterns": len(patterns),
        "patterns": [p.to_dict() for p in patterns],
    }

    with open(analysis_file, "w", encoding="utf-8") as f:
        json.dump(analysis_data, f, indent=2, ensure_ascii=False)


def generate_feedback_summary(
    feedback_records: list[LlmFeedbackRecord],
) -> dict[str, Any]:
    """生成反馈摘要统计

    Args:
        feedback_records: 反馈记录列表

    Returns:
        摘要统计字典
    """
    total_records = len(feedback_records)
    records_with_issues = sum(1 for r in feedback_records if r.llm_detected_issues)
    records_with_rules = sum(1 for r in feedback_records if r.triggered_rules)

    # 统计问题类型分布
    issue_type_counts: dict[str, int] = {}
    for record in feedback_records:
        for issue in record.llm_detected_issues:
            issue_type = str(issue.get("type", "unknown"))
            issue_type_counts[issue_type] = issue_type_counts.get(issue_type, 0) + 1

    # 统计规则触发分布
    rule_counts: dict[str, int] = {}
    for record in feedback_records:
        for rule_id in record.triggered_rules:
            rule_counts[rule_id] = rule_counts.get(rule_id, 0) + 1

    # 统计接受状态分布
    status_counts: dict[str, int] = {}
    for record in feedback_records:
        status = record.acceptance_status
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "total_records": total_records,
        "records_with_llm_issues": records_with_issues,
        "records_with_triggered_rules": records_with_rules,
        "issue_type_distribution": issue_type_counts,
        "rule_trigger_distribution": rule_counts,
        "acceptance_status_distribution": status_counts,
        "llm_issue_rate": round(records_with_issues / max(total_records, 1), 4),
    }
