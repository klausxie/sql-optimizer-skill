# SQL 优化报告：run_3dbefe4327c4

## 执行决策
- 发布就绪度：`CONDITIONAL_GO`
- 优化结论：`PASS`
- 证据置信度：`HIGH`
- 范围：SQL 单元 `1`, 优化建议 `1`
- 交付快照：补丁 `0`, 可应用 `0`, 阻塞 SQL `0`
- 性能证据：改进 `0`, 未改进 `0`
- 验证状态：已验证 `3`, 部分 `0`, 未验证 `0`
- 物化模式：`{'UNMATERIALIZABLE': 1}`
- 物化原因：`{'DYNAMIC_SUBTREE_PRESENT': 1}`
- 物化操作：`{'OTHER': 1}`

## 优先处理的 SQL
| SQL 键 | 优先级 | 可操作性 | 交付状态 | 补丁可应用 | 当前原因 | 摘要 |
|---|---|---|---|---|---|---|
| `com.test.mapper.TestFourIfMapper.testFourIf#v1` | `P0` | `MEDIUM` | `PATCHABLE_WITH_REWRITE` | `n/a` | 在模板安全的 mapper 重构后立即成为高价值 | patch can likely land after template-aware mapper refactoring |

## 主要风险
- 无

## 交付状态
- preflight: `DONE`
- scan: `DONE` (尝试 `1`)
- optimize: `DONE` (尝试 `1`)
- validate: `DONE` (尝试 `1`)
- patch_generate: `DONE` (尝试 `1`)
- report: `DONE`

## 变更组合
| SQL 键 | 状态 | 来源 | 性能 | 物化 | 补丁可应用 | 补丁决策 |
|---|---|---|---|---|---|---|
| `com.test.mapper.TestFourIfMapper.testFourIf#v1` | `PASS` | `llm` | `未知` | `UNMATERIALIZABLE` | `n/a` | `PATCH_DYNAMIC_XML_REQUIRES_TEMPLATE_AWARE_REWRITE` |

## 优化建议分析
| SQL 键 | 结论 | 问题 | LLM 候选 |
|---|---|---|---|
| `com.test.mapper.TestFourIfMapper.testFourIf#v1` | `CAN_IMPROVE` | `SELECT_STAR,FULL_SCAN_RISK,NO_LIMIT` | `1` |

## 技术证据
- `com.test.mapper.TestFourIfMapper.testFourIf#v1`: 行检查 `MATCH`, 成本 `None` -> `None`
  物化：`UNMATERIALIZABLE` / `DYNAMIC_SUBTREE_PRESENT`
  证据：`/Users/hzz/workspace/sql-optimizer-skill/test-files/mybatis-test/runs/run_3dbefe4327c4/evidence/com.test.mapper.TestFourIfMapper.testFourIf#v1/candidate_1/equivalence.json`

## 行动计划（未来 24 小时）
- 后端：重构 mapper 以支持模板感知重写

## 验证警告
- 无

## 验证覆盖
- 阶段覆盖：`{'optimize': {'recorded': 1, 'expected': 1, 'ratio': 1.0}, 'validate': {'recorded': 1, 'expected': 1, 'ratio': 1.0}, 'patch_generate': {'recorded': 1, 'expected': 1, 'ratio': 1.0}}`
- 主要差距：`[]`
- 阻塞 SQL: `[]`

## 附录
- report.json: `run_3dbefe4327c4/report.json`
- proposals: `run_3dbefe4327c4/proposals/optimization.proposals.jsonl`
- acceptance: `run_3dbefe4327c4/acceptance/acceptance.results.jsonl`
- patches: `run_3dbefe4327c4/patches/patch.results.jsonl`
- verification: `run_3dbefe4327c4/verification/ledger.jsonl`
- failures: `run_3dbefe4327c4/ops/failures.jsonl`
