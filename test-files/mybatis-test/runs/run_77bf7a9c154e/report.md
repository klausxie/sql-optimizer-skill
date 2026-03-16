# SQL 优化报告：run_77bf7a9c154e

## 执行决策
- 发布就绪度：`NO_GO`
- 优化结论：`BLOCKED`
- 证据置信度：`HIGH`
- 范围：SQL 单元 `0`, 优化建议 `0`
- 交付快照：补丁 `0`, 可应用 `0`, 阻塞 SQL `0`
- 性能证据：改进 `0`, 未改进 `0`
- 验证状态：已验证 `0`, 部分 `0`, 未验证 `0`
- 物化模式：`{}`
- 物化原因：`{}`
- 物化操作：`{}`

## 优先处理的 SQL
- 无

## 主要风险
- `PREFLIGHT_DB_UNREACHABLE` (`fatal`): 数量 `1`, 影响 SQL `0`

## 交付状态
- preflight: `FAILED`
- scan: `PENDING` (尝试 `0`)
- optimize: `PENDING` (尝试 `0`)
- validate: `PENDING` (尝试 `0`)
- patch_generate: `PENDING` (尝试 `0`)
- report: `DONE`

## 变更组合
| SQL 键 | 状态 | 来源 | 性能 | 物化 | 补丁可应用 | 补丁决策 |
|---|---|---|---|---|---|---|

## 优化建议分析
| SQL 键 | 结论 | 问题 | LLM 候选 |
|---|---|---|---|
| `n/a` | `n/a` | `n/a` | `0` |

## 技术证据
- 无通过项的技术证据。

## 行动计划（未来 24 小时）
- 平台：恢复运行: `PYTHONPATH=python python3 scripts/sqlopt_cli.py resume --run-id run_77bf7a9c154e`

## 验证警告
- 无

## 验证覆盖
- 阶段覆盖：`{}`
- 主要差距：`[]`
- 阻塞 SQL: `[]`

## 附录
- report.json: `run_77bf7a9c154e/report.json`
- proposals: `run_77bf7a9c154e/proposals/optimization.proposals.jsonl`
- acceptance: `run_77bf7a9c154e/acceptance/acceptance.results.jsonl`
- patches: `run_77bf7a9c154e/patches/patch.results.jsonl`
- verification: `run_77bf7a9c154e/verification/ledger.jsonl`
- failures: `run_77bf7a9c154e/ops/failures.jsonl`
