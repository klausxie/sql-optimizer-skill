# 系统规格（当前实现）

## 1. 逻辑架构
当前实现按三层组织：
1. `orchestrator`：命令入口、阶段编排、状态推进、超时与重试。
2. `stage core`：`diagnose / optimize / validate / apply / report` 领域逻辑。
3. `contracts & artifacts`：schema 校验、运行产物落盘、报告与 ops 诊断。

稳定约束：
1. 阶段之间通过运行目录产物衔接，不直接绕过 orchestrator 互调。
2. 阶段输出必须是结构化对象，不能只输出自然语言。
3. 每个阶段结束后都要写可消费产物，失败时也要写可诊断事件。

## 2. 阶段行为

### 2.1 `scan`
**职责**：只推断动态分支，不做问题分析

Current:
1. 解析用户指定范围（不扩散到其他文件）
2. 输出 `scan.sqlunits.jsonl`
3. 默认额外输出 `branches.jsonl`（分支执行模板）
4. 推断动态分支 (if/foreach/choose)
5. 输出 statement / fragment 的源码 range locator

**Scan 阶段不做**：
- ❌ 不调用 diagnose_branches（问题分析）
- ❌ 不计算 problemBranchCount
- ❌ 不做深度优化建议

### 2.2 `execute`
**职责**：执行SQL收集性能数据

**⚠️ 必须交互提示**：扫描完成后，Agent 必须提示用户确认是否执行。

Current:
1. 输入 `scan.sqlunits.jsonl` + `branches.jsonl`
2. 收集 EXPLAIN 执行计划
3. 收集实际耗时和返回行数
4. 输出 `execute_results.jsonl`

### 2.3 `analyze`
**职责**：诊断分支问题，确认瓶颈

Current:
1. 输入 `scan.sqlunits.jsonl` + `execute_results.jsonl`
2. 调用 `diagnose_branches` 进行分支诊断
3. 计算 `problemBranchCount`（问题分支数量）
4. 判断复杂度 (simple/complex)
5. 选择优化方式 (rules/llm)
6. 输出 `analyzed.sqlunits.jsonl`

**Analyze 阶段做**：
- ✅ 调用 diagnose_branches（EXPLAIN分析）
- ✅ 计算 problemBranchCount
- ✅ 确认慢SQL及其瓶颈

### 2.4 `optimize`
Current:
1. 输入 `SqlUnit[]`
2. 输出 `pipeline/optimize/optimization.proposals.jsonl`
3. prompt 会看到 `sql`、`templateSql`、`dynamicFeatures`
4. optimize 只生成分析候选，不直接生成 XML patch
5. optimize 之后会先经过候选治理层：
   - low-value pruning
   - degraded diagnostics
   - safe baseline recovery
6. 当前会额外输出：
   - `candidateGenerationDiagnostics`
   - `sql/<sql-key>/candidate_generation_diagnostics.json`

### 2.5 `validate`
Current:
1. 输入 `SqlUnit[] + OptimizationProposal[]`
2. 输出 `pipeline/validate/acceptance.results.jsonl`
3. 除语义 / 性能 / 安全判断外，还会输出补丁规划摘要：
   - `patchability`
   - `selectedPatchStrategy`
   - `canonicalization`
4. 仍会输出模板物化判定：
   - `rewriteMaterialization`
   - `templateRewriteOps`
5. 还会输出每条 SQL 的内部诊断 artifacts：
   - `rewrite_facts.json`
   - `patchability.assessment.json`
   - `patch.strategy.plan.json`
   - `canonicalization.assessment.json`
   - `candidate.selection.trace.json`
6. 片段级模板物化能力默认关闭，但判定结果仍会写出
7. 对动态模板 statement，当前还会输出：
   - `dynamicTemplate`
   - `dynamicBaselineFamily`
   - `dynamicDeliveryClass`
   - `dynamic_candidate_intent.json`

Default:
1. fragment 级模板物化由内部策略保持默认关闭

### 2.6 `apply`
Current:
1. 优先消费 validate 已规划的 `selectedPatchStrategy`
2. 当前策略选择由内部 planner 统一产出：
   - `SAFE_WRAPPER_COLLAPSE`
   - `EXACT_TEMPLATE_EDIT`
3. `templateRewriteOps` 仍是 apply 的直接执行输入
4. 只有当 `rewriteMaterialization.replayVerified=true` 时，才允许真正落地模板级 patch
5. 若没有模板级计划，则回退到原有静态 SQL patch 路径
6. 对动态模板 statement，不允许直接用扁平 SQL 覆盖 mapper XML

Current dynamic template paths:
1. `DYNAMIC_STATEMENT_TEMPLATE_EDIT`
   - 已实现
   - 仅允许 template-preserving statement-body rewrite
   - 必须保留原动态标签和 include tag
2. review-only dynamic families
   - `IF_GUARDED_FILTER_STATEMENT`
   - `FOREACH_IN_PREDICATE`
   - `SET_SELECTIVE_UPDATE`
   - 当前仍默认阻断，除非命中显式 safe baseline

Current template paths:
1. `STATEMENT_TEMPLATE_SAFE`
   - 已实现
   - 仅在 statement-level include-safe 且 replay 校验通过时生效
2. `FRAGMENT_TEMPLATE_SAFE`
   - 已实现
   - 仅在 feature flag 打开且 materializer 判定安全时才可用

### 2.7 `report`
Current:
1. 输出 `overview/report.md`、`overview/report.summary.md`、`overview/report.json`
2. 报告会聚合：
   - phase 状态
   - acceptance / patch 统计
   - materialization mode / reason / grouped action 统计
   - patch strategy 分布
   - canonical rule 命中与采用统计
3. 即使上游失败，也会尽量收口 report
4. 当前还会聚合动态模板摘要：
   - `dynamic_baseline_family_counts`
   - `dynamic_delivery_class_counts`

## 3. SQL 视图约束
1. `templateSql`
   - 源码模板视图
   - 用于动态模板判定和模板级 patch
   - 不参与 DB 执行
2. `sql`
   - 逻辑分析视图
   - 供 optimize / validate 使用
   - 不保证可直接回写源码
3. `executableSql`
   - validate 内部临时派生
   - 仅用于执行计划和语义比较
   - 不落盘，不得作为 patch 源

## 4. 默认开关与兼容性
1. fragment catalog
   - 低风险观测能力，内部默认开启
2. fragment 模板物化
   - 高风险行为路径，内部默认关闭
3. 新增字段全部按加法兼容，不改变已有主干契约

## 5. 局部运行与调试
Current:
1. CLI 支持按局部范围执行：
   - `--mapper-path`
   - `--sql-key`
2. 选择范围会固化到 run plan：
   - `selection.mapper_paths`
   - `selection.sql_keys`
   - `selection.selected_sql_keys`
3. `status/report` 会带 `selection_scope` 摘要

推荐策略：
1. 日常调试优先局部 run
2. full run 只用于阶段验收
3. 只有在修改 report 聚合、capability 主链、candidate governance registry 后才优先补 full run

当前阶段验收基线：
1. `run_fixture_project_full_stability_gate_v10`
2. 当前 full-run 基线要求：
   - `semantic_gate_uncertain_count = 0`
   - `dynamic_ready_patch_count >= 6`
   - `patch_strategy_counts.DYNAMIC_STATEMENT_TEMPLATE_EDIT >= 6`
3. dynamic/filter/DML 脏回归已在该基线收敛为 clean blocker 或 ready patch
4. 下一阶段重点不再是扩 dynamic patch family，而是处理：
   - `aggregation wrapper / plain aggregation`
   - 剩余 review-only plain shapes
   - `${}` 安全阻断之外的候选稳定性尾项

## 6. 外部稳定面
1. CLI：`run / status / resume / apply`
2. 运行目录：`runs/<run-id>/...`
3. 核心契约主干：
   - `SqlUnit`
   - `OptimizationProposal`
   - `AcceptanceResult`
   - `PatchResult`
   - `RunReport`

## 7. 阶段职责边界

| 阶段 | 职责 | 不应该做 |
|------|------|----------|
| **Scan** | 解析范围、推断动态分支 | 问题分析、优化建议 |
| **Execute** | 执行SQL收集性能数据 | - |
| **Analyze** | 诊断分支问题、确认瓶颈 | - |
| **Optimize** | 生成优化建议 | - |
| **Validate** | 验证优化效果 | - |
| **PatchGenerate** | 生成XML补丁 | - |
| **Report** | 生成报告 | - |

## 8. 技术难点（当前约束）
1. scan 依赖 Java MyBatis 渲染，但只读取 mapper 文件；类解析失败时必须降级而不是中断整轮扫描。
2. `<include>` 指向的 `<sql id>` 片段可能继续包含其他动态标签，且调用点可能带 `<property>` 绑定；因此系统必须同时维护模板视图、逻辑视图、递归依赖链和源码定位信息，不能只保留扁平 SQL。
3. 模板级 patch 不能依赖扁平 SQL 直接覆盖 XML；必须先通过 deterministic materializer 生成模板替换计划，并通过 replay 校验后才允许落地。
4. 候选选择不能直接依赖自然语言 LLM fallback；系统必须先经过 SQL 候选词法门，再进入 semantic / canonical / patchability 评估链。
5. 候选规范化、候选 patchability、patch safety、patch strategy planning 已拆成独立内部层；后续新增规则时不应继续把判断塞回 `candidate_selection` 或 `validate` 主流程。
6. 动态模板交付必须同时满足 `rewriteFacts.dynamicTemplate` 与 `dynamic_candidate_intent`，不能只凭扁平 SQL 候选直接决定可交付性。
