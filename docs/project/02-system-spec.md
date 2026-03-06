# 系统规格（当前实现）

## 1. 逻辑架构
当前实现按三层组织：
1. `orchestrator`：命令入口、阶段编排、状态推进、超时与重试。
2. `stage core`：`scan / optimize / validate / patch_generate / report` 领域逻辑。
3. `contracts & artifacts`：schema 校验、运行产物落盘、报告与 ops 诊断。

稳定约束：
1. 阶段之间通过运行目录产物衔接，不直接绕过 orchestrator 互调。
2. 阶段输出必须是结构化对象，不能只输出自然语言。
3. 每个阶段结束后都要写可消费产物，失败时也要写可诊断事件。

## 2. 阶段行为

### 2.1 `scan`
Current:
1. 输出 `scan.sqlunits.jsonl`。
2. 默认额外输出 `scan.fragments.jsonl`（内部默认开启）。
3. 对动态 MyBatis mapper statement 同时保留两种视图：
   - `templateSql`：模板视图，保留 `<foreach> / <include>` 等标签
   - `sql`：逻辑分析视图，可用于 optimize / validate
4. 输出 statement / fragment 的源码 range locator，以及 `<include><property>` 绑定信息。

Default:
1. fragment catalog 内部默认开启
2. schema 校验失败会终止本次运行

### 2.2 `optimize`
Current:
1. 输入 `SqlUnit[]`
2. 输出 `proposals/optimization.proposals.jsonl`
3. prompt 会看到 `sql`、`templateSql`、`dynamicFeatures`
4. optimize 只生成分析候选，不直接生成 XML patch

### 2.3 `validate`
Current:
1. 输入 `SqlUnit[] + OptimizationProposal[]`
2. 输出 `acceptance.results.jsonl`
3. 除语义 / 性能 / 安全判断外，还会输出模板物化判定：
   - `rewriteMaterialization`
   - `templateRewriteOps`
4. 片段级模板物化能力默认关闭，但判定结果仍会写出

Default:
1. fragment 级模板物化由内部策略保持默认关闭

### 2.4 `patch_generate`
Current:
1. 优先消费 validate 已批准的模板级计划（`templateRewriteOps`）
2. 只有当 `rewriteMaterialization.replayVerified=true` 时，才允许真正落地模板级 patch
3. 若没有模板级计划，则回退到原有静态 SQL patch 路径
4. 对动态模板 statement，不允许直接用扁平 SQL 覆盖 mapper XML

Current template paths:
1. `STATEMENT_TEMPLATE_SAFE`
   - 已实现
   - 仅在 statement-level include-safe 且 replay 校验通过时生效
2. `FRAGMENT_TEMPLATE_SAFE`
   - 已实现
   - 仅在 feature flag 打开且 materializer 判定安全时才可用

### 2.5 `report`
Current:
1. 输出 `report.md`、`report.summary.md`、`report.json`
2. 报告会聚合：
   - phase 状态
   - acceptance / patch 统计
   - materialization mode / reason / grouped action 统计
3. 即使上游失败，也会尽量收口 report

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

## 5. 外部稳定面
1. CLI：`run / status / resume / apply`
2. 运行目录：`runs/<run_id>/...`
3. 核心契约主干：
   - `SqlUnit`
   - `OptimizationProposal`
   - `AcceptanceResult`
   - `PatchResult`
   - `RunReport`

## 6. 技术难点（当前约束）
1. scan 依赖 Java MyBatis 渲染，但只读取 mapper 文件；类解析失败时必须降级而不是中断整轮扫描。
2. `<include>` 指向的 `<sql id>` 片段可能继续包含其他动态标签，且调用点可能带 `<property>` 绑定；因此系统必须同时维护模板视图、逻辑视图、递归依赖链和源码定位信息，不能只保留扁平 SQL。
3. 模板级 patch 不能依赖扁平 SQL 直接覆盖 XML；必须先通过 deterministic materializer 生成模板替换计划，并通过 replay 校验后才允许落地。
