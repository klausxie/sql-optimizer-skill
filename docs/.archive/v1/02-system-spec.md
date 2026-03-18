# 系统规格（V8 架构）

## 1. 逻辑架构

V8 实现按三层组织：
1. `orchestrator`：命令入口、阶段编排、状态推进、超时与重试。
2. `stage core`：`Discovery / Branching / Pruning / Baseline / Optimize / Validate / Patch` 领域逻辑。
3. `contracts & artifacts`：schema 校验、运行产物落盘、报告与 ops 诊断。

V8 七阶段流水线：
```
[1.发现] → [2.分支] → [3.剪枝] → [4.基线] → [5.优化] → [6.验证] → [7.补丁]
```

| 阶段 | 名称 | 功能 | 耗时节点 |
|------|------|------|----------|
| 1 | Discovery | 连接数据库、采集表结构、解析 XML、提取 SQL | DB 🐢 |
| 2 | Branching | 分支展开（3种策略：all_combinations/pairwise/boundary） | - |
| 3 | Pruning | 静态分析、风险标记（prefix_wildcard/suffix_wildcard/function_wrap） | CPU ⚡ |
| 4 | Baseline | EXPLAIN 分析、性能采集、表统计信息 | DB 🐢 |
| 5 | Optimize | 规则引擎 + LLM 优化建议 | LLM ⏱️ |
| 6 | Validate | 语义验证、性能对比、结果集验证 | DB 🐢 |
| 7 | Patch | 生成补丁、用户确认、备份、应用 | FS 💾 |

**图例**: 🐢 耗时操作(IO) | ⚡ 快速操作(CPU) | ⏱️ 大模型调用 | 💾 文件操作

稳定约束：
1. 阶段之间通过运行目录产物衔接，不直接绕过 orchestrator 互调。
2. 阶段输出必须是结构化对象，不能只输出自然语言。
3. 每个阶段结束后都要写可消费产物，失败时也要写可诊断事件。

## 2. 阶段行为

### 2.1 `Discovery` (发现)
**职责**：连接数据库、采集表结构、解析 XML、提取 SQL

Current:
1. 解析用户指定范围（不扩散到其他文件）
2. 输出 `sqlunits.jsonl`（SQL 单元目录）
3. 连接数据库采集表结构信息
4. 解析 MyBatis XML 映射文件
5. 提取 SQL 语句及其元数据

**Discovery 阶段不做**：
- ❌ 不执行 SQL
- ❌ 不生成优化建议
- ❌ 不做风险分析

### 2.2 `Branching` (分支)
**职责**：分支展开，生成所有可能的执行路径

Current:
1. 输入 `sqlunits.jsonl`
2. 分析动态标签（if/foreach/choose）
3. 应用分支策略展开：
   - `all_combinations`：全组合展开
   - `pairwise`：成对展开
   - `boundary`：边界值展开
4. 输出 `branches.jsonl`（分支执行模板）
5. 输出 statement / fragment 的源码 range locator

**Branching 阶段不做**：
- ❌ 不执行 SQL
- ❌ 不做性能分析
- ❌ 不生成优化建议

### 2.3 `Pruning` (剪枝)
**职责**：静态分析、风险标记、聚合剪枝

Current:
1. 输入 `sqlunits.jsonl` + `branches.jsonl`
2. 静态分析检测潜在性能问题
3. 风险标记：
   - `prefix_wildcard`：前置通配符（如 `'%'+name`）
   - `suffix_wildcard_only`：后置通配符（如 `name+'%'`）
   - `function_wrap`：函数包裹（如 `UPPER(name)`）
4. 聚合剪枝（根据配置策略）
5. 输出 `risks.jsonl`（风险标记结果）

**Pruning 阶段做**：
- ✅ 静态分析检测
- ✅ 风险标记
- ✅ 分支剪枝

### 2.4 `Baseline` (基线)
**职责**：EXPLAIN 分析、性能采集、表统计信息

**⚠️ 必须交互提示**：Pruning 完成后，Agent 必须提示用户确认是否执行。

Current:
1. 输入 `sqlunits.jsonl` + `branches.jsonl`
2. 收集 EXPLAIN 执行计划
3. 收集实际耗时和返回行数
4. 采集表统计信息
5. 输出 `baseline_results.jsonl`

**Baseline 阶段不做**：
- ❌ 不生成优化建议
- ❌ 不验证补丁

### 2.5 `Optimize` (优化)
**职责**：规则引擎 + LLM 优化建议

Current:
1. 输入 `SqlUnit[]`
2. 输出 `proposals.jsonl`（优化建议）
3. prompt 会看到 `sql`、`templateSql`、`dynamicFeatures`
4. Optimize 只生成分析候选，不直接生成 XML patch
5. Optimize 之后会先经过候选治理层：
   - low-value pruning
   - degraded diagnostics
   - safe baseline recovery
6. 当前会额外输出：
   - `candidateGenerationDiagnostics`
   - `sql/<sql-key>/candidate_generation_diagnostics.json`

### 2.6 `Validate` (验证)
**职责**：语义验证、性能对比、结果集验证

Current:
1. 输入 `SqlUnit[] + OptimizationProposal[]`
2. 输出 `acceptance.results.jsonl`
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

### 2.7 `Patch` (补丁)
**职责**：生成补丁、用户确认、备份、应用

Current:
1. 优先消费 Validate 已规划的 `selectedPatchStrategy`
2. 当前策略选择由内部 planner 统一产出：
   - `SAFE_WRAPPER_COLLAPSE`
   - `EXACT_TEMPLATE_EDIT`
3. `templateRewriteOps` 仍是 Patch 的直接执行输入
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

## 3. SQL 视图约束
1. `templateSql`
   - 源码模板视图
   - 用于动态模板判定和模板级 patch
   - 不参与 DB 执行
2. `sql`
   - 逻辑分析视图
   - 供 Optimize / Validate 使用
   - 不保证可直接回写源码
3. `executableSql`
   - Validate 内部临时派生
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
| **Discovery** | 连接数据库、采集表结构、解析 XML、提取 SQL | 执行 SQL、生成优化建议 |
| **Branching** | 分支展开（if/foreach/choose）、生成执行路径 | 执行 SQL、分析性能 |
| **Pruning** | 静态分析、风险标记（prefix_wildcard/suffix_wildcard/function_wrap） | 执行 SQL、生成补丁 |
| **Baseline** | EXPLAIN 分析、性能采集、表统计信息 | 生成优化建议、验证补丁 |
| **Optimize** | 规则引擎 + LLM 优化建议 | 执行 SQL、应用补丁 |
| **Validate** | 语义验证、性能对比、结果集验证 | 生成补丁、应用补丁 |
| **Patch** | 生成补丁、用户确认、备份、应用 | 执行 SQL、修改业务逻辑 |

## 8. 技术难点（当前约束）
1. Discovery 依赖数据库连接和 XML 解析，连接失败时必须降级而不是中断整轮扫描。
2. `<include>` 指向的 `<sql id>` 片段可能继续包含其他动态标签，且调用点可能带 `<property>` 绑定；因此系统必须同时维护模板视图、逻辑视图、递归依赖链和源码定位信息，不能只保留扁平 SQL。
3. 模板级 patch 不能依赖扁平 SQL 直接覆盖 XML；必须先通过 deterministic materializer 生成模板替换计划，并通过 replay 校验后才允许落地。
4. 候选选择不能直接依赖自然语言 LLM fallback；系统必须先经过 SQL 候选词法门，再进入 semantic / canonical / patchability 评估链。
5. 候选规范化、候选 patchability、patch safety、patch strategy planning 已拆成独立内部层；后续新增规则时不应继续把判断塞回 `candidate_selection` 或 `Validate` 主流程。
6. 动态模板交付必须同时满足 `rewriteFacts.dynamicTemplate` 与 `dynamic_candidate_intent`，不能只凭扁平 SQL 候选直接决定可交付性。
