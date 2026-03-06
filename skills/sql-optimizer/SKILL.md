---
name: sql-optimizer
description: 面向 MyBatis 项目的 SQL 优化执行与排障技能，覆盖 run/status/resume/apply 命令、契约校验、扫描桥接检查、回放基线与 patch-only 输出。支持 LLM 增强功能（Phase 1-6）。
---

# sql-optimizer

## 工作流
1. 先校验配置与 contracts。
2. `sql-optimizer-run` 是单次时间片命令（约 95 秒，不保证一次完成）。
3. skill 必须自动循环执行多个时间片，直到 `complete=true` 或失败。
4. 当 `report.enabled=true`（默认）时，即使 `to_stage` 更早，运行收尾也会完成 report。
5. 生成报告并检查 ops 产物。
6. 若用户当前只在改 scanner/scan verification，优先先做一次 scan-only smoke，再决定是否继续全流程。
7. 数据库平台当前支持 `postgresql` 与 `mysql`；MySQL 支持 5.6+（含 5.7、8.0+），不支持 MariaDB。
8. MySQL 不做 PostgreSQL 方言兼容；若 SQL 含 `ILIKE` 等不支持语法，应按语法错误处理，并检查 `OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR`。

## LLM 增强功能（Phase 1-6）

所有 LLM 增强功能已集成到主流程，默认启用：

| Phase | 功能 | 产物位置 |
|-------|------|----------|
| Phase 1 | LLM 输出质量控制（语法/启发式检查） | `proposals/*.llmValidationResults` |
| Phase 2 | LLM 重试 + 反馈机制 | `proposals/*.llmRetryStats` |
| Phase 3 | validate 阶段 LLM 语义判断 | `acceptance/*.llmSemanticCheck` |
| Phase 4 | 规则引擎 ↔ LLM 双向反馈 | `ops/llm_feedback.jsonl` |
| Phase 5 | patch_generate 阶段 LLM 辅助 | `ops/template_suggestions/*.json` |
| Phase 6 | LLM Trace 完整性增强 | `traces/*.optimize.llm.json` |

配置控制见主文档 `LLM 增强功能配置` 章节。

## 自动续跑策略
1. 先执行 `python scripts/run_until_budget.py --config ./sqlopt.yml --to-stage patch_generate --max-seconds 95`。
2. 解析最新结构化输出 payload。
3. 若 `complete=true`，停止并汇报最终状态。
4. 若 payload 包含 `error` 或 `run_status=FAILED`，停止并汇报 `reason_code` 与恢复命令。
5. 若 `complete=false` 且无错误，立即继续：
   - 优先执行 payload 中的 `next_action`。
   - 若无 `next_action`，使用同一 `run_id` 重新执行 `run_until_budget.py`。
6. 每轮输出精简进度：`run_id`、`current_phase`、`remaining_statements`、`reason`。

默认目标阶段为 `patch_generate`，除非用户明确指定其他阶段。

## Scan-only 验证
当用户当前在改 scanner、动态标签覆盖或 scan verification：

1. 优先执行：
   `python3 scripts/run_until_budget.py --config tests/fixtures/project/sqlopt.scan.local.yml --to-stage scan --max-seconds 30 --max-steps 10`
2. 检查：
   - `tests/fixtures/project/runs/<run_id>/scan.sqlunits.jsonl`
   - `tests/fixtures/project/runs/<run_id>/scan.fragments.jsonl`
   - `tests/fixtures/project/runs/<run_id>/verification/ledger.jsonl`
3. 关键判断：
   - `searchUsersAdvanced` 应识别 `FOREACH / INCLUDE / IF / CHOOSE / WHERE / BIND`
   - `patchUserStatusAdvanced` 不应再出现重复 `SET SET`
   - `includeTrace` 已解析时，不应误报 `SCAN_INCLUDE_TRACE_PARTIAL`

## 命令入口
- `python scripts/run_until_budget.py --config ./sqlopt.yml --to-stage patch_generate --max-seconds 95`
- `python scripts/run_until_budget.py --config tests/fixtures/project/sqlopt.scan.local.yml --to-stage scan --max-seconds 30 --max-steps 10`
- `python scripts/run_with_resolved_id.py status --project . [--run-id <run_id>]`
- `python scripts/run_with_resolved_id.py resume --project . [--run-id <run_id>]`
- `python scripts/run_with_resolved_id.py apply --project . [--run-id <run_id>]`
- 推荐先做首轮检查：`python scripts/sqlopt_cli.py run --config <path> --to-stage preflight`
- MySQL 项目建议先设置 `llm.enabled=false` + `llm.provider=heuristic` 做一轮离线 smoke，再切换真实 `mysql://` DSN 打开 compare。
- MySQL 本地测试库可用：`mysql -h 127.0.0.1 -u root -p sqlopt_test < tests/fixtures/sql_local/schema.mysql.sql`
- apply 行为为内置 `PATCH_ONLY`（不通过 `sqlopt.yml` 暴露 `apply.mode` 配置）。

## 参考资料
- `references/contracts.md`
- `references/postgresql.md`
- `references/failure-codes.md`
- `references/runtime-budget.md`
