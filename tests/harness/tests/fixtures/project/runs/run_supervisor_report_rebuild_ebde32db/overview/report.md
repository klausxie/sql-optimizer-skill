# SQL 优化报告：run_supervisor_report_rebuild_ebde32db

## 执行决策
- 发布就绪度：`NO_GO`
- 优化结论：`BLOCKED`
- 证据置信度：`HIGH`
- 范围：SQL 单元 `0`, 优化建议 `0`
- 交付快照：补丁 `0`, 可应用 `0`, 阻塞 SQL `0`
- 性能证据：改进 `0`, 未改进 `0`
- 验证状态：已验证 `0`, 部分 `0`, 未验证 `0`
- 语义门：PASS `0`, FAIL `0`, UNCERTAIN `0`
- 置信度升级：`0` (`0.0`), 来源 `{}`
- 误拦截恢复：`0`, include 自动物化：`0`
- 策略恢复：wrapper collapse `0`, 策略分布 `{}`
- 规范化：采用 `0`, 规则分布 `{}`
- 物化模式：`{}`
- 物化原因：`{}`
- 物化操作：`{}`

## 优先处理的 SQL
- 无

## 主要风险
- `SCAN_MAPPER_NOT_FOUND` (`fatal`): 数量 `3`, 影响 SQL `0`

## 交付状态
- preflight: `DONE`
- scan: `FAILED` (尝试 `0`)
- optimize: `PENDING` (尝试 `0`)
- validate: `PENDING` (尝试 `0`)
- patch_generate: `PENDING` (尝试 `0`)
- report: `DONE`

## 变更组合
| SQL 键 | 状态 | 语义门 | 置信度 | 升级轨迹 | 未升级主因 | 阻断主因 | 来源 | 性能 | 物化 | 补丁可应用 | 补丁决策 |
|---|---|---|---|---|---|---|---|---|---|---|---|

## 优化建议分析
| SQL 键 | 结论 | 问题 | LLM 候选 |
|---|---|---|---|
| `n/a` | `n/a` | `n/a` | `0` |

## 技术证据
- 无通过项的技术证据。

## 行动计划（未来 24 小时）
- 平台：恢复运行: `PYTHONPATH=python python3 scripts/sqlopt_cli.py resume --run-id run_supervisor_report_rebuild_ebde32db`

## 验证警告
- 无

## 验证覆盖
- 阶段覆盖：`{}`
- 主要差距：`[]`
- 阻塞 SQL: `[]`

## 附录

- run index: `run_supervisor_report_rebuild_ebde32db/run.index.json`
- overview report: `run_supervisor_report_rebuild_ebde32db/overview/report.json`
- overview markdown: `run_supervisor_report_rebuild_ebde32db/overview/report.md`
- pipeline manifest: `run_supervisor_report_rebuild_ebde32db/pipeline/manifest.jsonl`
- sql catalog: `run_supervisor_report_rebuild_ebde32db/sql/catalog.jsonl`
- pipeline scan units: `run_supervisor_report_rebuild_ebde32db/pipeline/scan/sqlunits.jsonl`
- pipeline scan fragments: `run_supervisor_report_rebuild_ebde32db/pipeline/scan/fragments.jsonl`
- pipeline proposals: `run_supervisor_report_rebuild_ebde32db/pipeline/optimize/optimization.proposals.jsonl`
- pipeline acceptance: `run_supervisor_report_rebuild_ebde32db/pipeline/validate/acceptance.results.jsonl`
- pipeline patches: `run_supervisor_report_rebuild_ebde32db/pipeline/patch_generate/patch.results.jsonl`
- verification: `run_supervisor_report_rebuild_ebde32db/pipeline/verification/ledger.jsonl`
- failures: `run_supervisor_report_rebuild_ebde32db/pipeline/ops/failures.jsonl`
- sql outcomes: `run_supervisor_report_rebuild_ebde32db/diagnostics/sql_outcomes.jsonl`
- sql artifacts: `run_supervisor_report_rebuild_ebde32db/diagnostics/sql_artifacts.jsonl`
- blockers summary: `run_supervisor_report_rebuild_ebde32db/diagnostics/blockers.summary.json`
