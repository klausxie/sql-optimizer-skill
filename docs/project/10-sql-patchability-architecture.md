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

## 7. 当前已验证的闭环

代表性闭环是 `countUser`：

1. 识别为 `COUNT wrapper + static include tree`
2. 通过 canonicalization 选择 `COUNT(*)`
3. 通过 patch safety 放行 `SAFE_WRAPPER_COLLAPSE`
4. 通过 planner 生成 statement-level wrapper collapse patch
5. 最终 patch 形态为：
   - `select count(1) from (<include .../>) tmp`
   - `-> SELECT COUNT(*) FROM users`

## 8. 后续建议

如果继续按“只做对架构有利的事”推进，优先级建议如下：

1. typed 化 `selection_rationale` / `delivery_readiness`
2. 把 diagnostics artifact 统一成 artifact models
3. 在 `rewrite_facts` 中补 `projectionFacts` / `subqueryFacts`
4. 给 canonicalization / patchability rule registry 增加显式冲突决策策略
