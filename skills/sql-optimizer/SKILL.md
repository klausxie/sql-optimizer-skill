---
name: sql-optimizer
description: 面向 MyBatis 项目的 SQL 优化 skill。用于在本地仓库里运行 `sqlopt-cli` 的完整工作流，排查 SQL key 选择、数据库连通性、报告与补丁产物问题；适合需要按 mapper、statementId 或 sqlKey 做可恢复分析时使用。
---

# SQL Optimizer Skill

## 架构设计

```
┌─────────────────────┐          ┌─────────────────────┐
│   sqlopt-cli       │          │   OpenCode Skill   │
├─────────────────────┤          ├─────────────────────┤
│                     │          │                     │
│  • 扫描 MyBatis  │          │  • 调用 LLM        │
│  • 生成分支      │─────────▶│  • 生成建议        │
│  • 静态规则检测  │  prompt  │  • 决策判断        │
│  • 构建 LLM prompt│          │  • 用户交互         │
│  • 执行 SQL     │          │                     │
│  • 生成补丁     │          │                     │
│                     │          │                     │
└─────────────────────┘          └─────────────────────┘
```

**职责分离**:
- **CLI**: 工程化能力 (扫描、执行、构建 prompt)
- **Skill**: AI 能力 (调用 LLM、生成建议)

## 阶段顺序

`diagnose → optimize → validate → apply → report`

| 阶段 | 功能 | CLI 输出 |
|------|------|----------|
| diagnose | 扫描 MyBatis XML，生成分支，静态规则检测 | scan.sqlunits.jsonl, branches.jsonl |
| optimize | 构建 LLM prompt (Skill 读取后调用 LLM) | proposals/<sql_key>.prompt.json |
| validate | 数据库验证优化效果 | acceptance.results.jsonl |
| apply | 生成并应用补丁 | patches/*.xml |
| report | 生成总结报告 | report.json, report.md |

## Use The Real Workflow

当前 CLI 的真实阶段顺序是：

`diagnose -> optimize -> validate -> apply -> report`

按下面的方式引导，而不是虚构额外阶段：

1. `run --to-stage diagnose` - 执行诊断阶段
   - CLI 会自动检查数据库配置并生成 `preflight.json`
   - **Skill 读取 `runs/<run_id>/preflight.json` 获取配置状态**
2. **【关键】根据 preflight.json 提示用户选择策略**:
   - 如果 `needs_user_choice: true`，向用户展示提示信息
   - 根据用户选择更新配置
3. 读取 `runs/<run_id>/scan.sqlunits.jsonl` 查看诊断结果
4. `run --to-stage optimize` - 构建 LLM prompt
5. 读取 `proposals/<sql_key>.prompt.json` 获取 prompt
6. 调用 LLM 生成优化建议
7. 将 LLM 建议写入 `proposals/<sql_key>.json`
8. `run --to-stage validate` - 验证优化效果
9. `run --to-stage apply` - 生成补丁
10. 查看报告

### 诊断前策略选择

当 `run --to-stage diagnose` 完成后，Skill 应该：

1. 读取 `runs/<run_id>/preflight.json`
2. 如果 `needs_user_choice: true`，向用户展示：
   
```
【数据库配置】
当前 DSN: postgresql://user:***@localhost:5432/demo
状态: ✅ 已配置

【数据库验证策略】
[1] 完整验证 - 需要数据库可达，真实执行 SQL 验证
[2] 降级验证 - 不需要数据库，仅静态分析 + LLM 推测

【分支生成策略】
[1] AllCombinations - 生成所有组合，覆盖全面
[2] Pairwise - 快速验证
[3] Boundary - 边界测试

请输入选项 (如: 1 1):
```

3. 根据用户选择，引导后续流程或更新配置

## 分支生成策略

诊断阶段会根据 MyBatis XML 中的动态条件（if/choose/foreach）生成分支进行测试。

### 支持的策略

| 策略 | 说明 | 分支数 | 适用场景 |
|------|------|--------|----------|
| **AllCombinations** | 生成所有 2^n 组合 | 2^n | 小数据量，需要全覆盖 |
| **Pairwise** | 每个条件单独测试 | n | 大数据量，快速验证 |
| **Boundary** | 边界测试（全 false、全 true） | 2 | 简单场景 |

### 配置方式

在 `sqlopt.yml` 中配置：

```yaml
branch:
  strategy: pairwise  # all_combinations / pairwise / boundary
  max_branches: 100  # 最大分支数限制
```

### 策略自动选择

系统会根据条件数量自动建议策略：
- 条件 ≤ 4: 建议 AllCombinations
- 条件 ≤ 16: 建议 AllCombinations  
- 条件 > 16: 建议 Pairwise

### 风险标记

分支生成时会检测以下性能风险：

| 风险类型 | 模式 | 等级 |
|----------|------|------|
| prefix_wildcard | `'%'+name+'%'` | 高 |
| suffix_wildcard_only | `name+'%'` | 低 |
| concat_wildcard | `CONCAT('%',name)` | 高 |
| function_wrap | `UPPER(name)` | 中 |

## AI 增强模式

当用户想要 AI 辅助优化时：

1. **diagnose 阶段** (CLI):
   - 扫描 MyBatis XML
   - 生成分支 (if/choose/foreach)
   - 静态规则检测 (SELECT *, 无 LIMIT, 全表扫描风险等)
   - 输出: `scan.sqlunits.jsonl`, `branches.jsonl`

2. **optimize 阶段** (Skill 调用 LLM):
   - CLI 构建 LLM prompt → `proposals/<sql_key>.prompt.json`
   - Skill 读取 prompt
   - Skill 调用 LLM 生成优化建议
   - Skill 将建议写入 `proposals/<sql_key>.json`

3. **validate 阶段** (CLI):
   - 在数据库上验证优化建议
   - 输出: `acceptance.results.jsonl`

## Run vs Resume

- **`run`**: 从头开始执行，会创建新的 run_id。适用于首次运行或重新开始。
- **`resume`**: 继续已存在的 run，从上次中断的阶段继续推进。适用于中断后恢复。
- **`status`**: 查看当前 run 的状态，包括 next_action、剩余语句数等。

使用场景：
- 首次运行：`sqlopt-cli run --config sqlopt.yml`
- 中断后继续：`sqlopt-cli resume --run-id <run-id>`
- 查看状态：`sqlopt-cli status --run-id <run-id>`

## Do Not Over-Promise

- 不要声称 diagnose 之后一定会出现"是否继续执行 SQL"的交互确认。当前 CLI 没有独立的手动确认闸门；如果你调用了目标阶段为 `validate` 或更后的命令，就表示继续推进。
- 不要把 `sqlopt-cli apply` 描述成"必然改动源码"。默认 `PATCH_ONLY` 模式只汇总 patch 结果，不修改项目文件。
- 不要把没有数据库证据的结果描述成"已完成真实性能分析"。数据库不可达时，validate 会明确降级。
- 不要把 skipped patch、空 patch 目录或 `NEED_MORE_PARAMS` 结果包装成成功交付。

## SQL Key Selection

`--sql-key` 现在支持 4 种输入：

- 完整 `sqlKey`
- `namespace.statementId`
- `statementId`
- `statementId#vN`

如果一个 `statementId` 命中了多个 SQL，CLI 会返回候选 full key 列表。遇到这种情况时：

- 向用户展示冲突项
- 改用更具体的 `namespace.statementId` 或完整 `sqlKey`
- 不要假设工具会替用户自动选一个

当用户已经给了明确文件范围时，优先配合 `--mapper-path` 一起缩小扫描面。

## Database Guidance

在任何 DB-backed run 之前：

- 先跑 `sqlopt-cli validate-config --config sqlopt.yml`
- 如果 `db.dsn` 还包含占位符，先修配置，不要继续推进
- 如果数据库不可达，明确告诉用户当前结果会降级，或者先修复连通性再继续

优先解释这些失败：

- `DB_CONNECTION_FAILED`
- `SCAN_SELECTION_SQL_KEY_NOT_FOUND`
- `SCAN_SELECTION_SQL_KEY_AMBIGUOUS`
- `VALIDATE_DB_UNREACHABLE`

更多细节见 [failure-codes.md](references/failure-codes.md)。

## Time Budgets

- 单条命令可能被外部环境限制在约 120 秒内。
- 需要分时间片推进时，优先使用 [runtime-budget.md](references/runtime-budget.md) 里的 `run_until_budget.py` 方案。
- 如果 `status.next_action=report-rebuild`，继续用 `run --to-stage report --run-id <run-id>`，不要误判为“已经完全结束”。

## Windows

- 在 Windows 上优先使用 `sqlopt-cli`、`python scripts/sqlopt_cli.py`，或 skill 自带的 `scripts/run_one_step.cmd`。
- `*.sh` 辅助脚本默认面向 POSIX shell；不要假设它们在 PowerShell / CMD / Git Bash 中都能直接工作。
- 如果命令包装器异常，直接调用 Python 入口比继续调 shell wrapper 更可靠。

## Output Expectations

优先给用户这些高信号产物和结论：

- 当前 `run_id`
- `current_phase`、`next_action`、剩余语句数
- 是否已验证数据库配置
- 是否存在真实 patch 文件
- 如果没有 patch，给出 skipped reason code，而不是只说“可应用”

## References

- [runtime-budget.md](references/runtime-budget.md)
- [failure-codes.md](references/failure-codes.md)
- [contracts.md](references/contracts.md)
- [README.md](../../README.md)
- [docs/QUICKSTART.md](../../docs/QUICKSTART.md)
