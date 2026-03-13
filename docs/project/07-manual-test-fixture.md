# Fixture 项目手工测试指南

本文档说明如何在本地手工跑通 `tests/fixtures/project`，并查看每个阶段输出。

## 1. 约定与前提

- 测试项目固定路径：`tests/fixtures/project`
- 配置文件固定：`tests/fixtures/project/sqlopt.yml`
- scan-only 配置：`tests/fixtures/project/sqlopt.scan.local.yml`
- MySQL 示例配置：`tests/fixtures/project/sqlopt.mysql.yml`
- MySQL 本地 schema：`tests/fixtures/sql_local/schema.mysql.sql`
- run 数据目录固定：`tests/fixtures/project/runs/<run-id>`
- 以下命令都在仓库根目录执行：`/Users/klaus/Desktop/sql-optimizer-skill`

前提环境：

1. Python 3 可用。
2. 本地 PostgreSQL 可连通（以 `sqlopt.yml` 里的 `db.dsn` 为准）。
3. 若启用在线 LLM：
   - `llm.provider=opencode_run`：`opencode` 命令可用；
   - `llm.provider=direct_openai_compatible`：`api_base/api_key/api_model` 可用且网络可达。

若要验证 MySQL 5.6+（含 5.7、8.0+），建议先从 `tests/fixtures/project/sqlopt.mysql.yml` 复制一份到临时目录，并先保持：
- `llm.enabled=false`
- `llm.provider=heuristic`

确认离线链路通过后，再切换成真实 `mysql://` DSN 打开 compare。

若本地还没有测试库，可先初始化：

```bash
mysql -h 127.0.0.1 -u root -p sqlopt_test < tests/fixtures/sql_local/schema.mysql.sql
```

这会创建并填充：
- `users`
- `orders`
- `shipments`

## 2. 快速自检（建议每次先做）

### 2.1 数据库连通性

```bash
psql "postgresql://postgres:Aa28012801@127.0.0.1:5432/postgres?sslmode=disable" -c "select 1;"
```

预期：返回 `1`。

### 2.2 LLM 连通性

当 `llm.provider=opencode_run`：

```bash
opencode run --format json --variant minimal "ping"
```

预期：输出事件里有 `"text":"pong"`。

如果这里失败，不要继续跑 pipeline，先修复 opencode 配置。

当 `llm.provider=direct_openai_compatible`：
1. 先确认 `sqlopt.yml` 中 `api_base/api_key/api_model` 已配置。
2. 直接执行 preflight（见 3.1）验证连通性。

## 3. 启动一次手工 run

## 3.1 运行命令

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py run \
  --config tests/fixtures/project/sqlopt.yml \
  --run-id run_manual_$(date +%Y%m%d_%H%M%S)
```

预期：返回类似：

```text
{'run_id': 'run_manual_20260226_213000', 'result': {'complete': False, 'phase': 'scan'}}
```

记录返回的 `run_id`，后续都用它。

### 3.1.1 局部运行（默认推荐）

日常调试不要优先跑 full run。当前 CLI 已支持按 mapper 和 sql key 收缩范围：

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py run \
  --config tests/fixtures/project/sqlopt.yml \
  --run-id run_partial_manual_$(date +%Y%m%d_%H%M%S) \
  --mapper-path src/main/resources/com/example/mapper/user/advanced_user_mapper.xml \
  --sql-key demo.user.advanced.listUsersFilteredAliased#v17
```

当前建议策略：

1. 日常调试优先局部 run
2. full run 只在阶段验收时执行
3. 只有修改以下路径后，才优先补 full run：
   - report 聚合逻辑
   - dynamic / aggregation capability 主链
   - candidate governance registry

## 3.2 查看状态

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py status --run-id <run-id>
```

关键信息：

- `current_phase`
- `phase_status`
- `last_reason_code`
- `next_action`

`next_action` 判定：

- `resume`：继续推进未完成阶段
- `report-rebuild`：主流程已完成，只需执行 `run --to-stage report --run-id <run-id>`
- `none`：当前目标阶段已完成，无需继续

## 3.3 持续推进到完成

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py resume --run-id <run-id>
```

如未完成，重复执行 `resume` + `status`，直到 `complete: True`。

若 `status` 返回 `next_action: 'report-rebuild'`，改为执行：

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py run --config tests/fixtures/project/sqlopt.yml --to-stage report --run-id <run-id>
```

可用轮询命令：

```bash
for i in {1..60}; do
  PYTHONPATH=python python3 scripts/sqlopt_cli.py resume --run-id <run-id> >/tmp/sqlopt_resume.out
  PYTHONPATH=python python3 scripts/sqlopt_cli.py status --run-id <run-id>
  sleep 1
done
```

## 3.4 只验证 scan 覆盖（推荐用于 scanner 相关改动）

当你只修改了 scanner / scan verification，不需要把整条 pipeline 跑完时，优先执行：

```bash
python3 scripts/run_until_budget.py \
  --config tests/fixtures/project/sqlopt.scan.local.yml \
  --to-stage scan \
  --max-steps 10 \
  --max-seconds 30
```

这份配置只扫描：

- `tests/fixtures/project/scan_samples/dynamic_tags_mapper.xml`

当前样例覆盖：

- `bind`
- `choose/when/otherwise`
- `where`
- `if`
- `foreach`
- `include`
- `trim`
- `set`

建议至少检查：

1. `pipeline/scan/sqlunits.jsonl`
   - `searchUsersAdvanced.dynamicFeatures` 含 `FOREACH/INCLUDE/IF/CHOOSE/WHERE/BIND`
   - `patchUserStatusAdvanced.sql` 不含重复 `SET SET`
2. `pipeline/scan/fragments.jsonl`
   - `ActiveOnly` / `TenantGuard` 两个 fragment 都存在
3. `pipeline/verification/ledger.jsonl`
   - 两条 statement 都是 `SCAN_EVIDENCE_VERIFIED`

## 4. 查看输出结果

run 目录：

```text
tests/fixtures/project/runs/<run-id>/
```

核心文件：

1. `pipeline/manifest.jsonl`：阶段事件、失败原因。
2. `pipeline/optimize/optimization.proposals.jsonl`：优化候选。
3. `pipeline/validate/acceptance.results.jsonl`：validate 结论。
4. `pipeline/patch_generate/patch.results.jsonl`：补丁生成与 apply-check 结果。
5. `overview/report.json`：汇总统计。

常用查看命令：

```bash
tail -n 50 tests/fixtures/project/runs/<run-id>/pipeline/manifest.jsonl
cat tests/fixtures/project/runs/<run-id>/overview/report.json
cat tests/fixtures/project/runs/<run-id>/pipeline/validate/acceptance.results.jsonl
cat tests/fixtures/project/runs/<run-id>/pipeline/patch_generate/patch.results.jsonl
```

## 5. 手工应用 patch（可选）

当 patch 阶段完成后，可执行：

```bash
PYTHONPATH=python python3 scripts/sqlopt_cli.py apply --run-id <run-id>
```

注意：当前 `apply` 语义为内置 `PATCH_ONLY`，主要用于产出 patch 文件与可应用性检查。

## 6. 常见问题排查

## 6.1 `RUNTIME_RETRY_EXHAUSTED` + `Was there a typo in the url or port?`

这通常是 `opencode` 调用的模型端点不可达。

排查顺序：

1. 先跑 `opencode run --format json --variant minimal "ping"`。
2. 检查 `~/.opencode/opencode.json` 的 `provider/options/baseURL/apiKey/model`。
3. 如果网络不稳定，可在 `sqlopt.yml` 调高：
   - `llm.timeout_ms`
4. 当前运行时超时/重试参数已内置，不再通过 `runtime.*` 暴露
5. 当前策略为 LLM 严格模式：`opencode_run` 或 `direct_openai_compatible` 不可达都直接失败，不做降级。

## 6.2 数据库未连通

表现：validate 阶段出现 `VALIDATE_DB_UNREACHABLE` 相关结果。

检查：

1. `db.dsn` 是否正确。
2. PostgreSQL 是否启动、端口是否监听。
3. 用户权限是否能执行 `EXPLAIN` / 查询目标表。

## 6.3 patch 文件无法 apply

检查 `pipeline/patch_generate/patch.results.jsonl`：

- `applicable: false` 表示 `git apply --check` 未通过。
- `applyCheckError` 会给出具体冲突/上下文不匹配原因。

## 7. 推荐的最小回归用例

每次改动后至少做一次：

1. `run` + 多次 `resume` 到 `complete: True`。
2. 确认 `overview/report.json` 存在且可解析。
3. 确认 `patch.results.jsonl` 中至少有一条 `applicable: true`（针对可 patch SQL）。
4. 抽查 `acceptance.results.jsonl` 中 `selectedCandidateSource/selectedCandidateId/warnings/riskFlags` 字段。
5. 若是 MySQL run，抽查 `overview/report.json.validation_warnings` 或 `overview/report.summary.md` 的 warnings，确认是否出现 `OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR`。

## 8. 当前 dynamic baseline 版图

当前 fixture 项目里，动态模板已经分成两类：

1. `READY_DYNAMIC_PATCH`
2. `REVIEW_ONLY` / `SAFE_BASELINE_BLOCKED`

当前已验证的 dynamic success baseline：

1. `demo.user.advanced.countUsersFilteredWrapped#v4`
   - `DYNAMIC_COUNT_WRAPPER_COLLAPSE`
2. `demo.user.advanced.listUsersViaStaticIncludeWrapped#v14`
   - `STATIC_INCLUDE_WRAPPER_COLLAPSE`
3. `demo.user.advanced.listUsersFilteredWrapped#v15`
   - `DYNAMIC_FILTER_WRAPPER_COLLAPSE`
4. `demo.user.advanced.listUsersRecentPagedWrapped#v16`
   - `STATIC_INCLUDE_PAGED_WRAPPER_COLLAPSE`
5. `demo.user.advanced.listUsersFilteredAliased#v17`
   - `DYNAMIC_FILTER_SELECT_LIST_CLEANUP`
6. `demo.user.advanced.listUsersFilteredTableAliased#v18`
   - `DYNAMIC_FILTER_FROM_ALIAS_CLEANUP`

当前已收干净的 dynamic blocked baseline：

1. `demo.user.advanced.countUsersDirectFiltered#v3`
   - `DYNAMIC_FILTER_SUBTREE`
2. `demo.user.advanced.listUsersRecentPaged#v5`
   - `STATIC_INCLUDE_NO_EFFECTIVE_DIFF`
3. `demo.order.harness.findOrdersByNos#v1`
   - `FOREACH_INCLUDE_PREDICATE`

当前建议的局部 real run 调试顺序：

1. success baseline
   - `listUsersFilteredAliased#v17`
   - `listUsersRecentPagedWrapped#v16`
2. blocked baseline
   - `countUsersDirectFiltered#v3`
   - `listUsersRecentPaged#v5`
   - `findOrdersByNos#v1`

## 9. dynamic 阶段验收门槛

阶段性 full run 时，当前建议至少检查以下 report 统计：

1. `stats.dynamic_ready_patch_count`
   - 当前应不低于 `6`
2. `stats.dynamic_ready_baseline_family_counts`
   - 当前应至少覆盖：
   - `DYNAMIC_COUNT_WRAPPER_COLLAPSE`
   - `STATIC_INCLUDE_WRAPPER_COLLAPSE`
   - `DYNAMIC_FILTER_WRAPPER_COLLAPSE`
   - `STATIC_INCLUDE_PAGED_WRAPPER_COLLAPSE`
   - `DYNAMIC_FILTER_SELECT_LIST_CLEANUP`
   - `DYNAMIC_FILTER_FROM_ALIAS_CLEANUP`
3. `stats.dynamic_safe_baseline_blocked_count`
   - 应主要由 `SAFE_BASELINE_NO_DIFF` 类构成，而不是脏 semantic fail
4. `stats.dynamic_review_only_count`
   - 当前允许存在，但不应伴随大量 `SEMANTIC_FAIL/UNCERTAIN` 回流

当前阶段基线：

1. full run 基线固定为 `run_fixture_project_full_aggregation_ready_v2`
2. 当前阶段验收通过条件：
   - `semantic_gate_uncertain_count = 0`
   - `semantic_gate_fail_count = 0`
   - `dynamic_ready_patch_count >= 6`
   - `patch_strategy_counts.DYNAMIC_STATEMENT_TEMPLATE_EDIT >= 6`
   - `aggregation_ready_patch_count >= 5`
   - 3 条 DML clean blocker 为 `PASS`：
   - `demo.order.harness.updateOrderStatusByNos#v6`
   - `demo.shipment.harness.markShipmentsDeleted#v5`
   - `demo.user.advanced.updateUserSelective#v9`
   - 下列 review-only case 保持 clean blocker：
   - `demo.order.harness.findOrdersByNos#v1`
   - `demo.order.harness.listOrdersWithUsersPaged#v3`
   - `demo.user.advanced.countUsersDirectFiltered#v3`
   - `demo.user.advanced.findUsersByKeyword#v8`
   - `demo.user.listUsers#v1`
   - `demo.order.harness.updateOrderStatusByNos#v6`
   - `demo.shipment.harness.markShipmentsDeleted#v5`
   - 下列 plain aggregation case 保持 `PASS + PATCH_NO_EFFECTIVE_CHANGE`：
   - `demo.order.harness.aggregateOrdersByStatus#v5`
   - `demo.order.harness.listOrderAmountWindowRanks#v7`
   - `demo.order.harness.listOrderUserCountsHaving#v8`
   - `demo.shipment.harness.listShipmentStatusUnion#v6`
   - `demo.user.advanced.listUserCountsByStatus#v10`
   - `demo.user.advanced.listDistinctUserStatuses#v11`
   - 下列 aggregation ready case 保持 patch-ready：
   - `demo.order.harness.aggregateOrdersByStatusWrapped#v9`
   - `demo.order.harness.listOrderUserCountsHavingWrapped#v10`
   - `demo.user.advanced.listDistinctUserStatusesWrapped#v13`
   - `demo.order.harness.aggregateOrdersByStatusAliased#v11`
   - `demo.order.harness.listOrderUserCountsHavingAliased#v12`
3. 如果后续 full run 回退上述任一条件，应先修 candidate governance / semantic normalization，再考虑新增 baseline

这几项的作用：

1. `dynamic_ready_patch_count` 看当前可交付 dynamic 基线总量
2. `dynamic_ready_baseline_family_counts` 看成功路径是否过度集中在单一子类
3. `dynamic_safe_baseline_blocked_count` 看 safe baseline 是否主要停在 no-diff，而不是错误候选
4. `dynamic_review_only_count` 看尚未放开的动态家族规模
5. `dml_review_only_count` 看 DML clean blocker 是否持续保持 `PASS + review-only`
6. `aggregation_wrapper_review_only_count` 看 plain/wrapper aggregation 是否回到 clean review-only
7. `aggregation_review_only_family_counts` 看 plain aggregation 是否稳定落在 `GROUP_BY/HAVING/WINDOW/UNION/DISTINCT_REVIEW_ONLY`
8. `no_safe_baseline_shape_match_count` 看剩余泛化 shape recovery 白名单缺口
9. 当前 residual shape 收尾后，期望：
   - `no_safe_baseline_shape_match_count = 0`
   - `empty_candidate_blocked_reason_counts` 只剩明确 family，不再泛化落到 `NO_SAFE_BASELINE_SHAPE_MATCH`
10. `aggregation_ready_family_counts` 看当前 aggregation safe baseline 是否至少覆盖：
   - `REDUNDANT_GROUP_BY_WRAPPER`
   - `REDUNDANT_HAVING_WRAPPER`
   - `REDUNDANT_DISTINCT_WRAPPER`
   - `GROUP_BY_FROM_ALIAS_CLEANUP`
   - `GROUP_BY_HAVING_FROM_ALIAS_CLEANUP`

## 10. 下一阶段

dynamic/filter/DML 收尾阶段已收口，不再优先扩第 7 个 ready family。

下一阶段优先顺序固定为：

1. 剩余 `EMPTY_CANDIDATES / ONLY_LOW_VALUE_CANDIDATES / NO_SAFE_BASELINE_SHAPE_MATCH`
2. `${}` 安全阻断之外的普通静态/聚合尾项
3. 如需扩能力，优先继续扩新的 aggregation safe baseline family

执行原则：

1. 先局部 run 分析 `semantic_uncertain`
2. 先做 candidate governance 和语义归一化
3. 不先放新 capability

当前 MySQL 方言边界：
- 不做 PostgreSQL 方言兼容转换
- MySQL 5.6 不支持 `MAX_EXECUTION_TIME` 时会自动降级，不阻塞 evidence / compare
- 若原 SQL 或候选包含 `ILIKE` 等 MySQL 不支持语法，optimize 的 DB evidence / compare 会按语法错误处理
- 原始错误保留在 proposal 的 `dbEvidenceSummary.explainError`

## 8. 当前 fixture harness 布局

`tests/fixtures/project` 不再只有单个 `user mapper`，当前按领域拆成 4 份正式 mapper：

1. `src/main/resources/com/example/mapper/user/simple_user_mapper.xml`
   - 最小基线
   - 覆盖 `static include`、`count wrapper`、`${}` 安全阻断
2. `src/main/resources/com/example/mapper/user/advanced_user_mapper.xml`
   - 覆盖 `count wrapper`、`where/if`、`foreach`、`bind`、`choose`、`set/update`、`group by`、`distinct`、`cte`
   - 其中 `distinct` 同时包含：
     - unsafe 负例：直接去掉 `DISTINCT`
     - safe 正例：冗余 `DISTINCT wrapper` 扁平化
3. `src/main/resources/com/example/mapper/order/order_harness_mapper.xml`
   - 覆盖 `join + pagination`、`foreach`、`${}` 原始谓词、批量 update、聚合、`window`、`having`
4. `src/main/resources/com/example/mapper/shipment/shipment_harness_mapper.xml`
   - 覆盖 `where/if`、`choose`、`${}` 动态排序、`foreach`、分页、批量 update、`union`

场景矩阵固定放在：

- `tests/fixtures/project/fixture_scenarios.json`

矩阵字段用于表达每条 statement 的预期：

1. `sqlKey`
2. `statementType`
3. `mapperPath`
4. `domain`
5. `scenarioClass`
6. `expectedScanFeatures`
7. `expectedRiskFlags`
8. `validateCandidateSql`
9. `validateEvidenceMode`
10. `targetValidateStatus`
11. `targetSemanticGate`
12. `targetPatchability`
13. `targetPatchStrategy`
14. `targetPatchReasonCode`
15. `targetPrimaryBlocker`
16. `targetPatchMustContain`
17. `targetPatchMustNotContain`
18. `targetBlockerFamily`
19. `roadmapStage`
20. `roadmapTheme`

`targetBlockerFamily` 当前固定枚举：

1. `READY`
2. `SECURITY`
3. `SEMANTIC`
4. `TEMPLATE_UNSUPPORTED`

report harness 还会把这层抽象回灌到正式 report 统计：

1. `stats.blocker_family_counts`
2. `sql artifact blocker_family`
3. `stats.aggregation_shape_counts`
4. `stats.aggregation_constraint_counts`
5. `stats.aggregation_safe_baseline_counts`

`roadmapStage` 当前固定枚举：

1. `BASELINE`
2. `NEXT`
3. `FUTURE`

`roadmapTheme` 当前固定枚举：

1. `STATEMENT_PATCH`
2. `WRAPPER_COLLAPSE`
3. `DYNAMIC_TEMPLATE`
4. `SECURITY_GUARDRAIL`
5. `DML_BOUNDARY`
6. `AGGREGATION_SEMANTICS`
7. `CTE_ENABLEMENT`
8. `COMPLEX_QUERY_SHAPE`

这两个字段只属于 fixture harness，用来表达能力路线图，不进入正式产品 contract。
当前 `NEXT` 阶段唯一锚点是：

1. `demo.user.advanced.listDistinctUserStatuses#v11`

这表示：

1. `CTE` 已进入 baseline。
2. `DYNAMIC_TEMPLATE` 已有两条 safe baseline：
   `STATIC_INCLUDE_ONLY` statement rewrite 和 `IF_GUARDED_COUNT_WRAPPER` count wrapper collapse。
3. `DISTINCT` 已有一条 safe baseline：冗余 `DISTINCT wrapper` 扁平化。
4. `GROUP BY` 已有一条 safe baseline：冗余 `GROUP BY wrapper` 扁平化。
5. `HAVING` 已有一条 safe baseline：冗余 `HAVING wrapper` 扁平化。
6. 当前 `NEXT` 仍然是更难的 `DISTINCT` 语义边界：不能在没有证据时直接去掉 `DISTINCT`。

针对这条 `NEXT` 边界，当前 `rewriteFacts` 已经会显式输出聚合/去重 shape：

1. `aggregationQuery.distinctPresent`
2. `aggregationQuery.distinctRelaxationCandidate`
3. `aggregationQuery.blockers`
4. `aggregationQuery.groupByColumns`
5. `aggregationQuery.aggregateFunctions`
6. `aggregationQuery.havingExpression`
7. `aggregationQuery.orderByExpression`
8. `aggregationQuery.windowFunctions`
9. `aggregationQuery.unionBranches`
10. `aggregationQuery.capabilityProfile`

这意味着后续如果继续推进 `DISTINCT` 能力，不需要再从原始 SQL 文本临时猜测，而可以直接基于 typed facts 加规则。

同一层 typed facts 现在也覆盖：

1. `GROUP BY`
2. `HAVING`
3. `WINDOW`
4. `UNION`

其中 `aggregationQuery.capabilityProfile` 进一步把这些 facts 归并成统一能力视图：

1. `shapeFamily`
2. `capabilityTier`
3. `constraintFamily`
4. `safeBaselineFamily`
5. `wrapperFlattenCandidate`

后续如果新增聚合语义规则，优先基于这层 profile 扩展，而不是继续在 validate/patch 里按 SQL 文本拼特判。
当前 `patch_safety` 也已经显式消费 `constraintFamily`：`SAFE_BASELINE` 之外的聚合 shape 会统一映射到聚合 blocker，而不是落成零散策略原因。
report 的 `next_actions` 也会按 `constraintFamily` 分派到更细的治理建议，例如 `DISTINCT_RELAXATION`、`GROUP_BY_AGGREGATION`、`HAVING_AGGREGATION`、`WINDOW_AGGREGATION`、`UNION_AGGREGATION`。
validate 产物里的 `patchability` 现在也会显式带出：
1. `aggregationConstraintFamily`
2. `aggregationCapabilityTier`
3. `aggregationSafeBaselineFamily`

当 planner 因聚合约束无法生成策略时，`patchStrategyCandidates` 会保留一个 blocked hint，说明当前是被哪个 `aggregationConstraintFamily` 挡住，而不是只返回空列表。

所以后续聚合语义规则应继续建立在 `aggregationQuery` 之上，而不是再往 validate/patch 流程里塞新的 SQL 文本特判。

`validateEvidenceMode` 当前固定枚举：

1. `compare_disabled`
2. `exact_match_improved`
3. `rowcount_mismatch`

当前统一场景分类：

1. `PATCH_READY_STATEMENT`
2. `PATCH_READY_WRAPPER_COLLAPSE`
3. `PATCH_BLOCKED_SECURITY`
4. `PATCH_BLOCKED_SEMANTIC`
5. `PATCH_BLOCKED_TEMPLATE_OR_UNSUPPORTED`

## 9. harness 回归入口

当你修改 fixture mapper 或 scanner 行为时，优先跑：

```bash
PYTHONPATH=python .venv/bin/python -m unittest tests.test_fixture_project_harness
```

这组测试会：

1. 校验 `fixture_scenarios.json` 结构完整、`sqlKey` 唯一、分类枚举合法。
2. 校验 roadmap 分层完整，并确保 `NEXT` 目标明确存在。
3. 使用 scanner fallback 扫描整个 `src/main/resources/**/*.xml`。
4. 断言实际扫描出的 `sqlKey / statementType / dynamicFeatures / riskFlags` 与矩阵一致。

validate 层回归入口：

```bash
PYTHONPATH=python .venv/bin/python -m unittest tests.test_fixture_project_validate_harness
```

这组测试会：

1. 读取矩阵中的 `validateCandidateSql / validateEvidenceMode`。
2. 对每个 statement 调用真实 `validate_proposal(...)`。
3. 断言 `status / semantic gate / patchability / selected patch strategy / blocker` 与矩阵一致。

patch + report 回归入口：

```bash
PYTHONPATH=python .venv/bin/python -m unittest tests.test_fixture_project_patch_report_harness
```

这组测试会：

1. 复用矩阵驱动的 validate 结果。
2. 对每个 statement 调用真实 `patch_generate.execute_one(...)`。
3. 断言 `selectionReason.code / strategyType / patchFiles / applicable` 与矩阵一致。
4. 对 patch-ready 场景继续断言 patch 文本必须包含/不包含的关键片段。
5. 再基于真实 patch 结果构建 report，并校验核心统计项。
6. 同时校验 roadmap 摘要仍然指向约定的下一目标场景。

如果你同时改了 supervisor/pipeline 主流程，再补跑：

```bash
PYTHONPATH=python .venv/bin/python -m unittest tests.test_workflow_golden_e2e
```

这条 golden e2e 现在也会扫描整个 fixture 项目，而不是只扫单个 mapper。

## 10. 新增一个 fixture 场景的步骤

固定按下面顺序做，不要只加 XML 不加 harness：

1. 在对应领域 mapper 中新增 statement 或 fragment。
2. 在 `fixture_scenarios.json` 增加对应场景定义。
3. 跑 `tests.test_fixture_project_harness`，先把扫描层闭环补齐。
4. 如果场景会改变 pipeline 行为，再补充 validate/patch/report 断言或 golden e2e 断言。

这样 fixture 才能真正承担 TDD harness 的角色，而不是一堆无法校验预期的样本 XML。
