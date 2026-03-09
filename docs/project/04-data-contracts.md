# 数据契约与格式约定（当前行为）

本文件描述当前代码已经落地的字段语义。若与 `contracts/*.schema.json` 有冲突，以 schema 为准。

## 1. `SqlUnit`
文件：`scan.sqlunits.jsonl`

必填主干：
1. `sqlKey`
2. `xmlPath`
3. `namespace`
4. `statementId`
5. `statementType`
6. `variantId`
7. `sql`
8. `parameterMappings`
9. `paramExample`
10. `locators`
11. `riskFlags`

已实现的可选加法：
1. `templateSql`
   - 模板视图
   - 动态 mapper statement 的 patch 判定应优先使用它
2. `dynamicFeatures`
   - 当前常见值：`FOREACH`、`INCLUDE`、`IF`、`CHOOSE`、`WHERE`、`TRIM`、`SET`、`BIND`
3. `includeTrace`
   - statement 递归依赖的片段引用链
4. `dynamicTrace`
   - statement 自身与依赖片段的动态特征摘要
5. `includeBindings`
   - 当前 statement 中 `<include><property .../></include>` 的调用绑定上下文
6. `templateTarget`
7. `primaryFragmentTarget`
8. `locators.range`
   - statement body 的源码范围

语义约束：
1. `sql` 是逻辑分析视图，不保证可直接回写源码。
2. `templateSql` 是模板真相源。
3. `locators.range` 用于模板级局部替换 patch，优先使用 offset。

## 1.1 `FragmentRecord`
文件：`scan.fragments.jsonl`

当前默认：
1. 在 fragment catalog 内置开关开启时生成
2. 当前默认开启

字段：
1. `fragmentKey`
2. `displayRef`
3. `xmlPath`
4. `namespace`
5. `fragmentId`
6. `templateSql`
7. `dynamicFeatures`
8. `includeTrace`
9. `dynamicTrace`
10. `includeBindings`
11. `locators`

语义约束：
1. `fragmentKey` 是内部稳定键，包含 `xmlPath + namespace.fragmentId`
2. `locators.range` 指向 `<sql id>` body 范围
3. `includeBindings` 描述片段内部直接 include 的绑定信息

## 2. `OptimizationProposal`
文件：`proposals/optimization.proposals.jsonl`

主干：
1. `sqlKey`
2. `issues`
3. `dbEvidenceSummary`
4. `planSummary`
5. `suggestions`
6. `verdict`

当前实现的常见扩展：
1. `llmCandidates`
2. `llmTraceRefs`
3. `estimatedBenefit`
4. `confidence`
5. `triggeredRules`

说明：
1. optimize 输出分析候选，不直接输出 XML 级 rewrite。
2. `dbEvidenceSummary.dbType` 当前可能是 `postgresql` 或 `mysql`
3. 当数据库 `EXPLAIN` 在 optimize 证据收集阶段因 SQL 语法失败时：
   - 原始错误保留在 `dbEvidenceSummary.explainError`
   - verification 会产出 `OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR`
   - report / 诊断摘要会把它提升为用户可见 warning

## 3. `AcceptanceResult`
文件：`acceptance/acceptance.results.jsonl`

必填主干：
1. `sqlKey`
2. `status`
3. `equivalence`
4. `perfComparison`
5. `securityChecks`

当前实现的常用扩展：
1. `rewrittenSql`
2. `feedback`
3. `selectedCandidateSource`
4. `selectedCandidateId`
5. `candidateEvaluations`
6. `candidateEval`
7. `warnings`
8. `riskFlags`
9. `rewriteMaterialization`
10. `templateRewriteOps`
11. `selectionRationale`
12. `deliveryReadiness`
13. `decisionLayers`

### 3.0 `decisionLayers`
当前行为：
1. 这是 validate 的分层决策摘要，不取代顶层 `status`
2. 用于解释“为什么通过/为什么未通过”，并给 `report` 与内部诊断聚合更稳定的依据

当前四层：
1. `feasibility`
   - 候选是否存在、DB 是否可达、compare 是否可执行
2. `evidence`
   - 语义/性能证据是否实际完成，是否降级
3. `delivery`
   - 当前交付准备度、选中候选、replay 验证状态
4. `acceptance`
   - 最终 `status` 与 validate 策略口径（profile / strategy flags）

### 3.0.1 诊断摘要相关输出
当前内部诊断聚合会基于 `AcceptanceResult`、`PatchResult` 与 verification ledger 生成：
1. `delivery_assessment`
2. `evidence_state`
3. `decision_summary`
4. `why_now`
5. `critical_gaps`
6. `warnings`
7. `recommended_next_step`

说明：
1. `warnings` 用于承载非 blocking 但用户应看到的诊断（例如 `OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR`）
2. `critical_gaps` 仍只保留 `UNVERIFIED` 级别缺口，不与 warning 混用

### 3.1 `rewriteMaterialization`
当前行为：
1. validate 在候选已选中后生成
2. 即使 fragment 自动物化默认关闭，也会写出判定结果

关键字段：
1. `mode`
   - 当前常见值：
   - `STATEMENT_SQL`
   - `STATEMENT_TEMPLATE_SAFE`
   - `FRAGMENT_TEMPLATE_SAFE`
   - `UNMATERIALIZABLE`
2. `targetType`
3. `targetRef`
4. `reasonCode`
5. `reasonMessage`
6. `replayVerified`
7. `featureFlagApplied`

### 3.2 `templateRewriteOps`
当前行为：
1. 仅在系统能安全生成模板替换计划时出现
2. `patch_generate` 会优先消费它
3. 仅当 `rewriteMaterialization.replayVerified=true` 时允许真正落地模板级 patch

当前常见 op：
1. `replace_statement_body`
2. `replace_fragment_body`

## 4. `PatchResult`
文件：`patches/patch.results.jsonl`

必填主干：
1. `sqlKey`
2. `patchFiles`
3. `diffSummary`
4. `applyMode`
5. `rollback`

当前常见扩展：
1. `statementKey`
2. `selectedCandidateId`
3. `candidatesEvaluated`
4. `selectionReason`
5. `rejectedCandidates`
6. `applicable`
7. `applyCheckError`

语义约束：
1. 动态模板 statement 不能直接用扁平 SQL 覆盖 XML
2. 模板级 patch 必须先由 validate 输出 `templateRewriteOps`
3. `git apply --check` 仍是 applicability 的最终验证

## 5. `RunReport`
文件：`report.json`

必填主干：
1. `run_id`
2. `mode`
3. `policy`
4. `stats`
5. `items`

当前新增的重点统计：
1. `stats.materialization_mode_counts`
2. `stats.materialization_reason_counts`
3. `stats.materialization_reason_group_counts`

说明：
1. `materialization_reason_group_counts` 是将 `reasonCode` 汇总成更可执行的操作分组。

## 6. 兼容策略
1. 新字段只做加法，不移除原有主干字段
2. 旧 run 缺少新增字段时，report / schema 仍应尽量兼容读取
3. 文档写的是当前行为，不代表未来所有预留字段都会立即生效
