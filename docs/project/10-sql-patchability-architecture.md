# SQL Patchability Architecture

本文总结本轮围绕 SQL/XML 自动补丁能力做的架构收敛，重点是把原来散落在 `validate`、`template_materializer`、`candidate_selection` 中的硬编码判断拆成稳定的内部层。

## 1. 当前内部骨架

当前 SQL 补丁链路已经收敛为五个可单测的内部层：

1. `rewrite_facts`
   - 负责抽取稳定事实，不直接决定能不能打补丁。
   - 当前 typed model 位于 `python/sqlopt/platforms/sql/rewrite_facts_models.py`
2. `canonicalization`
   - 负责在语义等价候选之间给出 canonical preference。
   - 采用 `models + rules + engine`
3. `candidate_patchability`
   - 负责候选级 patchability 启发式评分。
   - 采用 `models + rules + evaluator`
4. `patch_safety`
   - 负责 capability 级安全裁决。
   - 采用 `models + capability rules`
5. `patch_strategy_planner`
   - 负责在允许的 capability 内规划最终 patch strategy。
   - 采用 `strategy registry + planner facade`

动态模板补丁链路在这五层之上又补了两层专用能力：

1. `dynamic_candidate_intent`
   - 负责判断候选是否属于 template-preserving rewrite。
   - 采用 `models + rules + engine`
2. `candidate_generation`
   - 负责 degraded candidate 治理、本地 recovery、low-value pruning。
   - 采用 `models + rules + engine`

外部仍保持旧 contract：

1. `AcceptanceResult`
2. `PatchResult`
3. `RunReport`
4. `runs/<run-id>/sql/<sql-key>/...` diagnostics

## 2. Rewrite Facts

`rewrite_facts` 的职责是提供统一事实底座，避免后续层重复解析 SQL 或模板结构。

当前主要子结构：

1. `semantic`
   - `status`
   - `confidence`
   - `evidenceLevel`
   - `fingerprintStrength`
   - `hardConflicts`
2. `wrapperQuery`
   - `present`
   - `aggregate`
   - `staticIncludeTree`
   - `innerSql`
   - `innerFromSuffix`
   - `collapsible`
   - `collapseCandidate`
   - `blockers`
   - `rewrittenCountExpr`
   - `rewrittenFromSuffix`
3. 顶层事实
   - `effectiveChange`
   - `dynamicFeatures`
   - `templateAnchorStable`

设计约束：

1. `build_rewrite_facts_model(...)` 产出 typed model
2. `build_rewrite_facts(...)` 只负责向外导出兼容 dict
3. 上层逻辑默认消费 typed model，artifact 出口才写 dict

## 3. Canonicalization

`canonicalization` 不再直接嵌在 candidate selection 中，而是独立成：

1. `canonicalization_models.py`
2. `canonicalization_rules/`
3. `canonicalization_engine.py`

当前规则：

1. `COUNT_CANONICAL_FORM`
2. `REDUNDANT_SUBQUERY_CANONICAL_FORM`
3. `ALIAS_ONLY_CANONICAL_FORM`

关键点：

1. primary rule 由显式 priority 决定，不再靠 `max(score)` 偶然获胜
2. selection 只消费 canonical preference signal，不理解具体规则实现
3. diagnostics 仍保留完整 rule match 列表

## 4. Candidate Patchability

候选级 patchability 评分已从 `candidate_selection.py` 拆出：

1. `candidate_patchability_models.py`
2. `candidate_patchability_rules/`
3. `candidate_patchability.py`

当前规则：

1. `RULE_SOURCE_CONSERVATIVE`
2. `PROJECTION_REWRITE_PATCHABLE`
3. `ORDERING_REWRITE_PATCHABLE`
4. `MYBATIS_PLACEHOLDER_PRESERVED`
5. `JOIN_HEAVY_PATCH_SURFACE`
6. `GENERIC_PLACEHOLDER_PENALTY`

设计约束：

1. 选择器不再关心具体评分细节
2. `candidateEvaluations.patchability*` 继续兼容输出
3. 后续新增评分规则不需要改 selection 主流程

## 5. Patch Safety And Strategy

补丁侧已经拆成 capability 与 strategy 两层：

1. `patch_capability_rules/`
   - 判定允许哪些 capability
2. `patch_strategy_registry.py`
   - 在 capability 已允许的前提下尝试具体 strategy

当前 capability：

1. `SAFE_WRAPPER_COLLAPSE`
2. `EXACT_TEMPLATE_EDIT`

当前 strategy：

1. `SAFE_WRAPPER_COLLAPSE`
2. `EXACT_TEMPLATE_EDIT`

关键点：

1. `PatchSafetyEvaluator` 统一收口安全门限
2. `PatchStrategyPlanner` 只负责计划，不重复做安全判断
3. `rewriteMaterialization` 仍保留为兼容输出，不作为唯一判据

## 6. Diagnostics Artifacts

每个 SQL 目录下当前会输出以下诊断文件：

1. `rewrite_facts.json`
2. `patchability.assessment.json`
3. `patch.strategy.plan.json`
4. `canonicalization.assessment.json`
5. `candidate.selection.trace.json`

这些文件的定位：

1. 属于可重算 diagnostics
2. 用于解释“为什么能补”“为什么没补”“为什么选这个候选”
3. 不作为外部稳定状态 source of truth

当前动态模板相关 diagnostics 额外包括：

1. `dynamic_candidate_intent.json`
2. `candidate_generation_diagnostics.json`

它们分别回答：

1. 候选是否能被重建成保真模板改写
2. optimize 阶段为什么没有候选、为什么候选被剪掉、是否命中本地恢复

## 7. 当前已验证的闭环

代表性闭环是 `countUser`：

1. 识别为 `COUNT wrapper + static include tree`
2. 通过 canonicalization 选择 `COUNT(*)`
3. 通过 patch safety 放行 `SAFE_WRAPPER_COLLAPSE`
4. 通过 planner 生成 statement-level wrapper collapse patch
5. 最终 patch 形态为：
   - `select count(1) from (<include .../>) tmp`
   - `-> SELECT COUNT(*) FROM users`

当前动态模板已验证闭环包括：

1. `STATIC_INCLUDE_WRAPPER_COLLAPSE`
   - 代表样例：`demo.user.advanced.listUsersViaStaticIncludeWrapped#v14`
2. `STATIC_INCLUDE_PAGED_WRAPPER_COLLAPSE`
   - 代表样例：`demo.user.advanced.listUsersRecentPagedWrapped#v16`
3. `DYNAMIC_COUNT_WRAPPER_COLLAPSE`
   - 代表样例：`demo.user.advanced.countUsersFilteredWrapped#v4`
4. `DYNAMIC_FILTER_WRAPPER_COLLAPSE`
   - 代表样例：`demo.user.advanced.listUsersFilteredWrapped#v15`
5. `DYNAMIC_FILTER_SELECT_LIST_CLEANUP`
   - 代表样例：`demo.user.advanced.listUsersFilteredAliased#v17`
6. `DYNAMIC_FILTER_FROM_ALIAS_CLEANUP`
   - 代表样例：`demo.user.advanced.listUsersFilteredTableAliased#v18`

这些样例当前统一复用：

1. `DYNAMIC_STATEMENT_TEMPLATE_EDIT`
2. `rewriteFacts.dynamicTemplate.capabilityProfile`
3. `dynamic_candidate_intent`
4. `candidate_generation_diagnostics`

它们已经形成一套可扩的动态模板基线族谱，而不是单个 case。

阶段状态：

1. `run_fixture_project_full_aggregation_ready_v1` 已将 dynamic baseline、plain aggregation review-only、residual shape blocked reason 与 aggregation ready family 一并收敛到同一条 full-run 基线
2. 当前阶段可以认为 dynamic delivery 已从“实验性样例”进入“稳定能力版图”
3. `dynamic/filter/DML/plain aggregation` 这条线上此前的 `SEMANTIC_FAIL / UNCERTAIN` 回归已清零
4. DML clean blocker 已统一收正为 `PASS + review-only blocker`
5. tail cleanup gate 当前还会显式跟踪：
   - `dml_review_only_count`
   - `aggregation_wrapper_review_only_count`
   - `aggregation_review_only_family_counts`
   - `no_safe_baseline_shape_match_count`
6. residual shape 收尾后，`no_safe_baseline_shape_match_count` 已降为 `0`，剩余 empty blocked reason 已收敛到具体 family，而不再依赖泛化 `NO_SAFE_BASELINE_SHAPE_MATCH`
7. plain aggregation 当前已固定为 `PASS + PATCH_NO_EFFECTIVE_CHANGE`，并细分为 `GROUP_BY/HAVING/WINDOW/UNION/DISTINCT_REVIEW_ONLY`
8. aggregation ready family 当前至少包括：
   - `REDUNDANT_GROUP_BY_WRAPPER`
   - `REDUNDANT_HAVING_WRAPPER`
   - `REDUNDANT_DISTINCT_WRAPPER`
   - `GROUP_BY_FROM_ALIAS_CLEANUP`
9. 下一阶段不再优先扩 dynamic ready family，而是转向剩余候选稳定性尾项与新的 aggregation safe baseline 评估

## 8. 后续建议

如果继续按“只做对架构有利的事”推进，优先级建议如下：

1. typed 化 `selection_rationale` / `delivery_readiness`
2. 把 diagnostics artifact 统一成 artifact models
3. 在 `rewrite_facts` 中补 `projectionFacts` / `subqueryFacts`
4. 给 canonicalization / patchability rule registry 增加显式冲突决策策略
5. 继续扩 `dynamicBaselineFamily / dynamicDeliveryClass`，优先 `IF_GUARDED_FILTER_STATEMENT`，暂不放开 `FOREACH`

当前阶段之后的优先级已调整为：

1. 剩余 `EMPTY_CANDIDATES / ONLY_LOW_VALUE_CANDIDATES / NO_SAFE_BASELINE_SHAPE_MATCH`
2. `${}` 安全阻断之外的普通静态/聚合尾项
3. 是否扩新的 aggregation safe baseline family
