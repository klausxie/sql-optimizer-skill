# RecognitionStage

## 目标

RecognitionStage 是整条链路的核心识别阶段，负责把 branch 候选变成有证据的慢 SQL finding。

## 输入

- `branch_candidates`
- `table_metadata`
- `column_distributions`
- `column_usage_maps`

## 输出

- `parameter_cases`
- `explain_baselines`
- `execution_baselines`
- `slow_sql_findings`

## 核心职责

### 1. 生成代表性参数 case

参数 case 不能只使用启发式占位值，而要根据字段分布自动生成：

- 热点值
- 冷门值
- 空值
- 极端范围
- 大列表
- 低选择性值
- 复合条件热点组合

### 2. 执行 `EXPLAIN`

对优先级较高的 branch/case 组合执行 `EXPLAIN`，提取：

- 估算成本
- 扫描行数
- 计划节点
- 是否全表扫
- 是否 filesort / temporary
- join 顺序与 join 类型

### 3. 执行基线 SQL

对更高优先级的 branch/case 组合执行真实 SQL，提取：

- `actual_time_ms`
- 返回行数
- 扫描行数
- 结果集签名
- 多次执行统计

### 4. 慢 SQL 识别

基于计划与执行结果输出结构化 finding：

- `is_slow`
- `severity`
- `impact_score`
- `root_causes`
- `evidence_refs`
- `optimization_ready`

## 为什么把 `EXPLAIN` 和基线执行放在阶段 3

- 这是识别阶段，不是优化阶段
- 阶段 4 应该只处理已经明确的慢 SQL
- 阶段 3 的输出必须能直接回答“它为什么慢”

## 典型根因

- `full_table_scan`
- `low_selectivity_predicate`
- `leading_wildcard_like`
- `function_wrapped_column`
- `sort_without_index`
- `group_without_index`
- `large_offset_pagination`
- `large_in_list`
- `join_order_amplification`
- `subquery_recheck`

## 结果集基线

阶段 3 需要保存结果集签名，而不是保存整份结果集：

- `row_count`
- 排序后主键摘要
- 稳定 checksum
- 可选样本行摘要

该签名将供阶段 4 比较优化前后结果是否一致。

## 成功标准

- 每个高优先级 branch 至少有 `EXPLAIN`
- Top finding 必须有真实执行基线
- 所有 finding 都可以追溯到 `statement_key + path_id + case_id`
