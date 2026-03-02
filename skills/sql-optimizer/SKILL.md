---
name: sql-optimizer
description: 面向 MyBatis 项目的 SQL 优化执行与排障技能，覆盖 run/status/resume/apply 命令、契约校验、扫描桥接检查、回放基线与 patch-only 输出。
---

# sql-optimizer

## 工作流
1. 先校验配置与 contracts。
2. `sql-optimizer-run` 是单次时间片命令（约 95 秒，不保证一次完成）。
3. skill 必须自动循环执行多个时间片，直到 `complete=true` 或失败。
4. 当 `report.enabled=true`（默认）时，即使 `to_stage` 更早，运行收尾也会完成 report。
5. 生成报告并检查 ops 产物。

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

## 命令入口
- `python scripts/run_until_budget.py --config ./sqlopt.yml --to-stage patch_generate --max-seconds 95`
- `python scripts/run_with_resolved_id.py status --project . [--run-id <run_id>]`
- `python scripts/run_with_resolved_id.py resume --project . [--run-id <run_id>]`
- `python scripts/run_with_resolved_id.py apply --project . [--run-id <run_id>]`
- 推荐先做首轮检查：`python scripts/sqlopt_cli.py run --config <path> --to-stage preflight`
- 如需在 apply 阶段直接修改项目文件，在 `sqlopt.yml` 中设置 `apply.mode: APPLY_IN_PLACE`（默认是 `PATCH_ONLY`）。

## 参考资料
- `references/contracts.md`
- `references/postgresql.md`
- `references/failure-codes.md`
- `references/runtime-budget.md`
