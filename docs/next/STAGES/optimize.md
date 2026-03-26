# OptimizeStage

## 目标

OptimizeStage 只处理阶段 3 已识别出的慢 SQL，不再承担慢 SQL 识别职责。

## 输入

- `slow_sql_findings`
- `explain_baselines`
- `execution_baselines`
- `table_metadata`
- `column_distributions`

## 输出

- `optimization_proposals`
- `optimization_validations`
- `accepted_actions`

## 核心职责

### 1. 生成优化方案

方案来源分三类：

- 规则
- LLM
- 规则 + LLM 混合

优化类型包括：

- SQL 改写
- 索引建议
- 排序/分页改写
- 子查询改写
- 聚合改写

### 2. 优化后验证

阶段 4 必须使用阶段 3 的同一组参数 case 做验证：

- 再跑 `EXPLAIN`
- 再跑真实 SQL
- 对比结果集签名
- 对比耗时与扫描量

### 3. 方案筛选

不是所有 proposal 都进入阶段 5。

只有满足以下条件的 proposal 才进入推荐集合：

- 结果集一致
- 性能收益达标
- 风险在可接受范围内

## 关键原则

### 规则优先

常见问题应优先由规则处理，例如：

- `SELECT *`
- 前导 `%LIKE%`
- 排序缺索引
- 大 `OFFSET`
- 低选择性字段顺序错误

### LLM 需要完整上下文

LLM 输入至少应包含：

- 原 SQL
- branch 信息
- 原始 `EXPLAIN`
- 原始执行基线
- 字段分布与索引信息
- 根因列表

## 成功标准

- Proposal 与 finding 建立一对多关系
- 每个被接受的 proposal 都有验证记录
- 阶段 5 可以直接展示 before/after 差异
