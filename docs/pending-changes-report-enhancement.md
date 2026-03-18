# 待合并：报告系统增强 + Agent 友好输出

> 本文档记录 2025-03-16 本地未提交的改动特点，用于后续参考或重新实现。

---

## 改动概述

**主题**：报告系统增强，使输出更 Agent 友好，便于 AI 助手理解下一步操作。

**影响范围**：
- `skills/sql-optimizer/SKILL.md`
- `python/sqlopt/application/diagnostics_summary.py`
- `python/sqlopt/stages/report_stats.py`
- `python/sqlopt/stages/report_builder.py`
- `python/sqlopt/stages/report_render.py`
- `scripts/run_until_budget.py`
- 多个测试文件

---

## 1. SKILL.md 工作流指南优化

### 1.1 Entry Points 澄清

```markdown
当前有 3 个常见入口路径：

- 仓库开发态 Python 入口：`scripts/sqlopt_cli.py`
- 安装后的 runtime Python 入口：`runtime/scripts/sqlopt_cli.py`
- 安装后的 wrapper：
  - Windows: `bin/sqlopt-cli.cmd`
  - POSIX: `bin/sqlopt-cli`

优先顺序：
1. 如果 wrapper 存在，优先用 `sqlopt-cli`
2. wrapper 缺失或异常时，回退到 `runtime/scripts/sqlopt_cli.py`
3. 在当前仓库直接开发时，回退到 `scripts/sqlopt_cli.py`
```

### 1.2 Run vs Resume 明确

```markdown
- `run --config ...`
  - 用于启动新 run
  - 也可在显式提供 `--run-id <run-id>` 时只把已有 run 推进到某个目标阶段
- `resume --run-id <run-id>`
  - 用于继续已有 run
  - 这是"继续当前 run"的默认动作

对用户说"继续当前 run"时，优先对应 `resume`，不要默认给出新的 `run` 命令。
```

### 1.3 数据库只读边界

```markdown
数据库验证必须遵守"只读"边界：

- 允许：
  - 连接探测
  - `EXPLAIN` / `EXPLAIN ANALYZE` 的只读等价能力
  - `SELECT COUNT(*)`
  - 有上限、仅用于语义对比的 `SELECT`
- 不允许：
  - `ALTER`
  - `INSERT`
  - `UPDATE`
  - `DELETE`
  - `CREATE` / `DROP` / 其他 DDL
```

### 1.4 Preflight 说明

```markdown
`run` 已经会做数据库可达性探测，所以 `validate-config` 是调试入口，不是每次必跑的主流程。
```

---

## 2. 诊断报告增强

### 2.1 新增字段

| 字段 | 来源 | 用途 |
|------|------|------|
| `semantic_error_details` | `parse_sql_runtime_error()` | 结构化错误详情（缺失列/表等） |
| `semantic_error_message` | `humanize_sql_runtime_error()` | 人类可读的错误描述 |
| `performance_baseline_summary` | `_perf_baseline_summary()` | EXPLAIN 成本变化摘要 |

### 2.2 新增辅助函数

```python
def _semantic_feedback_details(acceptance_row, raw_tables) -> dict | None:
    """从 acceptance 提取结构化语义错误详情"""
    
def _semantic_feedback_message(acceptance_row, raw_tables) -> str | None:
    """生成人类可读的语义错误消息"""
    
def _perf_baseline_summary(perf_comparison) -> str | None:
    """生成 EXPLAIN 成本变化摘要，如 'EXPLAIN total cost improved: 123 -> 45'"""
```

### 2.3 blocker_primary_message 增强

当 `blocker_primary_code == "VALIDATE_SEMANTIC_ERROR"` 时，使用 `semantic_error_message` 替代原始消息。

---

## 3. Next Actions 结构化

### 3.1 统一 Action 结构

```python
def _structured_next_step(
    action_id: str,
    run_id: str,
    *,
    description: str,          # 给人类看的一行描述
    agent_instruction: str,    # 给 AI Agent 的执行指令
    stage: str | None,         # 所属阶段
    cli_hints: list[str] | None,  # CLI 命令提示
    action_type: str | None,   # 动作类型分类
) -> dict[str, Any]:
```

### 3.2 Action Type 分类

| action_type | 含义 |
|-------------|------|
| `review_verification_evidence` | 审查验证证据 |
| `fix_security_block` | 修复安全阻断（如 ${} 替换） |
| `restore_db_validation` | 恢复数据库验证能力 |
| `apply_patch` | 应用补丁 |
| `refactor_mapper` | 重构 mapper 结构 |
| `resolve_patch_conflict` | 解决补丁冲突 |
| `review_patchability` | 审查补丁可应用性 |
| `review_semantic_boundary` | 审查语义边界（聚合等） |
| `continue_run` | 继续运行 |

### 3.3 report_stats.py 中的 _make_action

```python
def _make_action(
    action_id: str,
    *,
    title: str,
    reason: str,
    applicability: str,
    expected_outcome: str,
    description: str,
    agent_instruction: str,
    stage: str | None = None,
    cli_hints: list[str] | None = None,
    action_type: str | None = None,
) -> dict[str, Any]:
    """构建标准化的 action 对象"""
```

---

## 4. Top Blockers 增强

### 4.1 新增字段

```python
{
    "code": "VALIDATE_SEMANTIC_ERROR",
    "count": 5,
    "ratio": None,
    "severity": "error",
    "sql_keys": ["mapper.xml#select1", ...],
    "human_message": "列 'user_name' 不存在",  # 新增
    "details": {"error_type": "MISSING_COLUMN", "column": "user_name"},  # 新增
    "performance_baseline_summary": "EXPLAIN total cost: 123 -> 45",  # 新增
}
```

### 4.2 智能采样

从 `sql_outcomes` 中选取有代表性的一条作为 `human_message` 和 `details` 的来源：

```python
sample = next(
    (
        row
        for row in matching_outcomes
        if row.get("semantic_error_message")
        or row.get("blocker_primary_message")
        or row.get("performance_baseline_summary")
    ),
    matching_outcomes[0] if matching_outcomes else {},
)
```

---

## 5. Why Now 增强

当存在语义错误时，`why_now` 字段会根据错误类型生成更具体的建议：

```python
if semantic_error_type == "MISSING_COLUMN":
    why_now = "当前先修复缺失列引用，否则无法完成语义验证与补丁交付"
elif semantic_error_type == "MISSING_TABLE":
    why_now = "当前先修复缺失表引用，否则无法继续语义验证"
else:
    why_now = "当前先修复数据库返回的语义错误，再重新执行 validate"

if performance_baseline_summary:
    why_now = f"{why_now}；现有降级 EXPLAIN 摘要可先用于判断收益"
```

---

## 6. 测试补充

- 新增 `tests/test_diagnostics_summary.py`
- 新增 `tests/test_report_stats.py`
- 更新 `tests/test_acceptance_policy.py`
- 更新 `tests/test_builtin_rules_detection.py`
- 更新 `tests/test_optimize_proposal.py`
- 更新 `tests/test_run_until_budget_script.py`

---

## 7. 文档更新

- `README.md`: 澄清 run/resume 使用场景，强调只读边界
- `docs/QUICKSTART.md`: 同步更新
- `docs/TROUBLESHOOTING.md`: 同步更新

---

## 8. 关键设计决策

1. **Agent Instruction 优先**：每个 action 都包含 `agent_instruction`，让 AI 助手知道具体该做什么
2. **语义错误可读化**：将数据库原始错误转换为 `human_message`
3. **降级证据不丢弃**：即使语义验证失败，EXPLAIN 成本摘要仍然保留
4. **动作类型分类**：通过 `action_type` 支持按类别筛选/处理

---

## 9. 依赖关系

这些改动依赖：
- `python/sqlopt/platforms/sql/error_intel.py` 中的 `parse_sql_runtime_error()` 和 `humanize_sql_runtime_error()`
- `python/sqlopt/verification/explain.py` 中的 `action_reason()`

---

## 10. 重新实现建议

如果远程分支有更大改动，重新实现时可：

1. 先合并远程分支
2. 检查 `report_stats.py` 和 `diagnostics_summary.py` 是否已有类似结构
3. 按 agent_instruction 模式补充缺失的字段
4. 确保 `_semantic_feedback_*` 和 `_perf_baseline_summary` 函数可用
5. 更新 SKILL.md 的工作流说明
