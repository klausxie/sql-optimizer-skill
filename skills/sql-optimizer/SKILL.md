---
name: sql-optimizer
description: 面向 MyBatis 项目的 SQL 优化 skill。用于在本地仓库里运行 `sqlopt-cli` 的完整工作流，排查 SQL key 选择、数据库连通性、报告与补丁产物问题；适合需要按 mapper、statementId 或 sqlKey 做可恢复分析时使用。
---

# SQL Optimizer Skill

## 阶段顺序

`diagnose → optimize → validate → apply → report`

| 阶段 | 功能 |
|------|------|
| diagnose | 扫描 MyBatis XML，生成分支，收集性能基线 |
| optimize | LLM 生成优化建议 |
| validate | 数据库验证优化效果 |
| apply | 生成并应用补丁 |
| report | 生成总结报告 |

## Use The Real Workflow

当前 CLI 的真实阶段顺序是：

`diagnose -> optimize -> validate -> apply -> report`

按下面的方式引导，而不是虚构额外阶段：

1. `validate-config` - 验证配置和数据库连通性
2. `run` - 执行到 diagnose 阶段
3. `run --to-stage optimize` - 进入优化阶段
4. `run --to-stage validate` - 进入验证阶段
5. `run --to-stage apply` - 生成补丁
6. `status` 或 `scripts/run_until_budget.py` - 查看状态
7. 查看 `runs/<run-id>/overview/report.summary.md` 和 `runs/<run-id>/pipeline/patch_generate/patch.results.jsonl`
8. 只有存在可应用 patch 时再 `apply`

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
