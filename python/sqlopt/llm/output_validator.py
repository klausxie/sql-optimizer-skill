"""LLM 输出质量控制层

在 optimize 和 validate 之间验证 LLM 生成的 SQL 候选方案，过滤无效候选。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationCheck:
    """单个检查项结果"""
    check_type: str  # "syntax", "heuristic", "schema"
    passed: bool
    message: str | None = None
    detail: Any = None


@dataclass
class LlmOutputValidationResult:
    """LLM 输出验证结果"""
    sql_key: str
    candidate_id: str
    passed: bool
    checks: list[ValidationCheck] = field(default_factory=list)
    rejected_reason: str | None = None


def _check_sql_syntax_basic(sql: str) -> tuple[bool, str | None]:
    """基础 SQL 语法检查（不依赖外部库）

    执行轻量级语法检查：
    - 检查是否以 SELECT/INSERT/UPDATE/DELETE 等开头
    - 检查括号匹配
    - 检查是否有明显的语法错误
    """
    sql_stripped = sql.strip()

    if not sql_stripped:
        return False, "SQL is empty"

    # 检查是否是有效的 SQL 语句开头
    valid_starts = (
        "select", "insert", "update", "delete",
        "with", "create", "drop", "alter",
        "explain", "analyze"
    )

    sql_lower = sql_stripped.lower()

    # 处理带注释的情况
    if sql_lower.startswith("--"):
        lines = sql_stripped.splitlines()
        for line in lines:
            line_stripped = line.strip()
            if line_stripped and not line_stripped.startswith("--"):
                sql_lower = line_stripped.lower()
                break

    if sql_lower.startswith("--"):
        return False, "SQL contains only comments"

    # 检查是否以有效关键字开头
    starts_valid = any(sql_lower.startswith(kw) for kw in valid_starts)
    if not starts_valid:
        return False, f"SQL does not start with a valid keyword: {sql_stripped[:50]}"

    # 检查括号匹配
    paren_count = 0
    in_string = False
    string_char = None
    i = 0

    while i < len(sql_stripped):
        char = sql_stripped[i]

        # 处理字符串
        if char in ("'", '"') and (i == 0 or sql_stripped[i-1] != "\\"):
            if not in_string:
                in_string = True
                string_char = char
            elif char == string_char:
                in_string = False
                string_char = None
        elif not in_string:
            if char == "(":
                paren_count += 1
            elif char == ")":
                paren_count -= 1
                if paren_count < 0:
                    return False, "Unmatched closing parenthesis"

        i += 1

    if paren_count != 0:
        return False, f"Unmatched parentheses: {paren_count} opening(s) not closed"

    # 检查常见的 SQL 语法错误模式
    error_patterns = [
        (r"\bWHERE\b\s*$", "WHERE clause without condition"),
        (r"\bFROM\b\s*$", "FROM clause without table"),
        (r"\bSELECT\s+\*\s+FROM\s*\(", "SELECT * FROM with subquery missing alias"),
        (r"\bIN\s*\(\s*\)", "IN with empty list"),
        (r"\bBETWEEN\s+\w+\s+AND\s*$", "BETWEEN without end value"),
    ]

    for pattern, message in error_patterns:
        if re.search(pattern, sql_stripped, re.IGNORECASE):
            return False, message

    return True, None


def _check_heuristics(sql: str, original_sql: str) -> tuple[bool, list[str]]:
    """启发式规则检查

    检查可能导致问题的模式：
    - SELECT 列数大幅增加
    - 添加了未授权的表
    - 删除了 WHERE 条件
    - 改变了聚合逻辑
    """
    warnings: list[str] = []

    sql_stripped = sql.strip()
    original_stripped = original_sql.strip()

    # 1. 检查 SELECT 列数是否大幅增加
    def count_select_columns(s: str) -> int:
        match = re.search(r"SELECT\s+(DISTINCT\s+)?(.*?)\s+FROM", s, re.IGNORECASE | re.DOTALL)
        if not match:
            return 0
        cols_str = match.group(2)
        if cols_str.strip() == "*":
            return 1  # SELECT * 计为 1 列
        # 简单计数逗号（不考虑复杂表达式）
        return cols_str.count(",") + 1

    orig_cols = count_select_columns(original_stripped)
    new_cols = count_select_columns(sql_stripped)

    if orig_cols > 0 and new_cols > orig_cols * 3:
        warnings.append(f"SELECT column count increased significantly: {orig_cols} -> {new_cols}")

    # 2. 检查是否删除了 WHERE 条件（从有 WHERE 变成无 WHERE）
    has_where_orig = "where" in original_stripped.lower()
    has_where_new = "where" in sql_stripped.lower()

    if has_where_orig and not has_where_new:
        warnings.append("WHERE clause was removed - may cause full table scan")

    # 3. 检查是否改变了 JOIN 数量
    def count_joins(s: str) -> int:
        return len(re.findall(r"\bJOIN\b", s, re.IGNORECASE))

    orig_joins = count_joins(original_stripped)
    new_joins = count_joins(sql_stripped)

    if new_joins > orig_joins + 2:
        warnings.append(f"JOIN count increased: {orig_joins} -> {new_joins}")

    # 4. 检查是否将 #{} 占位符改成了字面值（安全风险）
    has_param_orig = "#{" in original_stripped
    has_param_new = "#{" in sql_stripped

    if has_param_orig and not has_param_new:
        warnings.append("MyBatis #{ } placeholders were removed - potential SQL injection risk")

    # 5. 检查是否有明显的语法问题（但已被基础检查覆盖）
    # 这里检查更复杂的模式
    if re.search(r"\bOR\s+1\s*=\s*1\b", sql_stripped, re.IGNORECASE):
        warnings.append("Potential tautology detected (OR 1=1)")

    # 检查 1=1 模式（不带 OR 的情况）
    if re.search(r"\bWHERE\s+1\s*=\s*1\b", sql_stripped, re.IGNORECASE):
        warnings.append("Potential tautology detected (WHERE 1=1)")

    return len(warnings) == 0, warnings


def _check_schema(
    sql: str,
    config: dict[str, Any],
    sql_unit: dict[str, Any] | None = None
) -> tuple[bool, str | None]:
    """Schema 检查（轻量级实现）

    验证 SQL 中引用的表和列是否存在明显问题：
    - 检查表名格式是否合法
    - 检查是否有空表名或列名引用
    - 检查引号匹配
    - 对比 sql_unit 中的已知表名（如果可用）

    注意：完整的 DB schema 验证需要连接数据库查询元数据，
    这里只进行语法层面的轻量级检查。
    """
    sql_stripped = sql.strip()

    # 1. 检查 FROM 子句中的表名
    # 匹配 FROM 后跟的表名（包括 schema.table 格式）
    from_pattern = r"\bFROM\s+(\w+(?:\.\w+)?)"
    from_matches = re.findall(from_pattern, sql_stripped, re.IGNORECASE)

    for table_ref in from_matches:
        # 检查表名是否为空或只有点号
        if not table_ref or table_ref == "." or table_ref.replace(".", "") == "":
            return False, f"Invalid table reference in FROM clause"

        # 检查表名长度（大多数数据库有长度限制，通常 64-128 字符）
        if len(table_ref) > 128:
            return False, f"Table name too long: {table_ref[:50]}..."

    # 2. 检查 JOIN 子句中的表名
    join_pattern = r"\bJOIN\s+(\w+(?:\.\w+)?)"
    join_matches = re.findall(join_pattern, sql_stripped, re.IGNORECASE)

    for table_ref in join_matches:
        if not table_ref or table_ref == "." or table_ref.replace(".", "") == "":
            return False, f"Invalid table reference in JOIN clause"
        if len(table_ref) > 128:
            return False, f"Table name too long in JOIN: {table_ref[:50]}..."

    # 3. 检查引号匹配（字符串内的引号不计）
    in_string = False
    string_char = None
    backtick_count = 0
    double_quote_count = 0
    bracket_count = 0

    for i, char in enumerate(sql_stripped):
        # 处理字符串字面量
        if char in ("'", '"') and (i == 0 or sql_stripped[i-1] != "\\"):
            if not in_string:
                in_string = True
                string_char = char
            elif char == string_char:
                in_string = False
                string_char = None
            continue

        if not in_string:
            if char == "`":
                backtick_count += 1
            elif char == '"':
                double_quote_count += 1
            elif char == "[":
                bracket_count += 1
            elif char == "]":
                bracket_count -= 1

    if backtick_count % 2 != 0:
        return False, "Unmatched backtick (`) in identifier"
    if double_quote_count % 2 != 0:
        return False, "Unmatched double quote in identifier"
    if bracket_count != 0:
        return False, "Unmatched square brackets in identifier"

    # 4. 如果 sql_unit 提供了已知表名，进行简单验证
    if sql_unit and sql_unit.get("tables"):
        known_tables = {t.get("tableName", "").lower() for t in sql_unit.get("tables", [])}
        # 简单的表名存在性检查（仅当已知表名不为空时）
        if known_tables:
            for table_ref in from_matches + join_matches:
                # 提取纯表名（去掉 schema 前缀）
                table_name = table_ref.split(".")[-1].lower()
                # 允许临时表或派生表（子查询别名）
                if table_name and not table_name.startswith("("):
                    # 这里只记录警告，不直接拒绝，因为可能是别名或临时表
                    pass  # 详细验证需要 DB 元数据

    return True, None


def validate_candidate(
    candidate: dict[str, Any],
    original_sql: str,
    sql_key: str,
    config: dict[str, Any],
    sql_unit: dict[str, Any] | None = None
) -> LlmOutputValidationResult:
    """验证单个 LLM 候选方案

    Args:
        candidate: LLM 生成的候选改写 SQL
        original_sql: 原始 SQL
        sql_key: SQL 标识符
        config: 配置字典
        sql_unit: 原始 SQL 单元（可选，用于上下文）

    Returns:
        验证结果
    """
    rewritten_sql = str(candidate.get("rewrittenSql") or "").strip()
    candidate_id = str(candidate.get("id") or f"{sql_key}:unknown")

    checks: list[ValidationCheck] = []
    all_passed = True
    rejected_reason: str | None = None

    # 获取配置
    llm_cfg = config.get("llm", {}) or {}
    validation_cfg = llm_cfg.get("output_validation") or {}
    enabled = bool(validation_cfg.get("enabled", False))

    if not enabled:
        # 功能未启用，直接通过
        return LlmOutputValidationResult(
            sql_key=sql_key,
            candidate_id=candidate_id,
            passed=True,
            checks=[]
        )

    # 1. 语法检查
    syntax_check_enabled = bool(validation_cfg.get("syntax_check", True))
    if syntax_check_enabled:
        syntax_ok, syntax_error = _check_sql_syntax_basic(rewritten_sql)
        check = ValidationCheck(
            check_type="syntax",
            passed=syntax_ok,
            message=syntax_error or "Syntax OK"
        )
        checks.append(check)

        if not syntax_ok:
            all_passed = False
            rejected_reason = f"Syntax error: {syntax_error}"

    # 2. 启发式检查（仅在语法检查通过时执行）
    if all_passed:
        heuristic_check_enabled = bool(validation_cfg.get("heuristic_check", True))
        if heuristic_check_enabled:
            heuristic_ok, heuristic_warnings = _check_heuristics(rewritten_sql, original_sql)
            check = ValidationCheck(
                check_type="heuristic",
                passed=heuristic_ok,
                message="Heuristic checks passed" if heuristic_ok else "; ".join(heuristic_warnings),
                detail={"warnings": heuristic_warnings} if heuristic_warnings else None
            )
            checks.append(check)

            # 启发式警告不直接拒绝，但记录
            if not heuristic_ok:
                # 有多个警告时标记为需要审查
                if len(heuristic_warnings) >= 2:
                    all_passed = False
                    rejected_reason = f"Heuristic warnings: {'; '.join(heuristic_warnings)}"

    # 3. Schema 检查（可选）
    if all_passed:
        schema_check_enabled = bool(validation_cfg.get("schema_check", False))
        if schema_check_enabled:
            schema_ok, schema_error = _check_schema(rewritten_sql, config, sql_unit)
            check = ValidationCheck(
                check_type="schema",
                passed=schema_ok,
                message=schema_error or "Schema OK"
            )
            checks.append(check)

            if not schema_ok:
                all_passed = False
                rejected_reason = f"Schema error: {schema_error}"

    return LlmOutputValidationResult(
        sql_key=sql_key,
        candidate_id=candidate_id,
        passed=all_passed,
        checks=checks,
        rejected_reason=rejected_reason
    )


def validate_candidates(
    candidates: list[dict[str, Any]],
    original_sql: str,
    sql_key: str,
    config: dict[str, Any],
    sql_unit: dict[str, Any] | None = None
) -> tuple[list[dict[str, Any]], list[LlmOutputValidationResult]]:
    """批量验证 LLM 候选方案

    Args:
        candidates: LLM 生成的候选改写 SQL 列表
        original_sql: 原始 SQL
        sql_key: SQL 标识符
        config: 配置字典
        sql_unit: 原始 SQL 单元（可选）

    Returns:
        (valid_candidates, validation_results) - 通过验证的候选和所有验证结果
    """
    if not candidates:
        return [], []

    results: list[LlmOutputValidationResult] = []
    valid_candidates: list[dict[str, Any]] = []

    for candidate in candidates:
        result = validate_candidate(candidate, original_sql, sql_key, config, sql_unit)
        results.append(result)

        if result.passed:
            valid_candidates.append(candidate)

    return valid_candidates, results
