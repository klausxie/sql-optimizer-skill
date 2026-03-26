# ParseStage

## 目标

ParseStage 的目标是高召回地展开 MyBatis 动态 SQL，生成足够覆盖危险场景的 branch 候选。

## 输入

- `sql_units`
- `sql_fragments`
- `table_metadata`
- `column_distributions`
- `column_usage_maps`

## 输出

- `branch_candidates`
- `branch_priority_queue`

## 关键动作

### 1. 动态 SQL 展开

支持：

- `if`
- `choose / when / otherwise`
- `foreach`
- `bind`
- `include`
- `trim / where / set`

### 2. branch 覆盖策略

#### 条件数较少

当条件数较少时，采用全组合覆盖。

#### 条件数中等

采用：

- `choose` 全覆盖
- `if` pairwise
- `foreach` 边界桶

#### 条件数较多

采用风险优先采样，但必须强制覆盖：

- 全条件为空
- 单低选择性条件生效
- 每个 `choose` 的每条 `when`
- `foreach` 的 `1 / 10 / 100 / 1000` 桶
- 大 `offset` 分页

### 3. 静态风险评分

风险评分信号包括：

- 大表
- 无索引过滤列
- 低选择性列
- 热点值列
- 前导 `%LIKE%`
- 函数包列
- 大 `IN`
- 大 `OFFSET`
- 无索引排序
- `GROUP BY` 聚合扩张

### 4. 参数槽位建模

ParseStage 需要把 branch 里的参数抽象为 `parameter_slots`，供阶段 3 生成参数 case：

- 参数名
- 关联列
- 谓词类型
- 是否允许空值
- 是否取列表
- 是否取时间范围

## 成功标准

- branch 产出覆盖所有高风险动态路径
- 每个 branch 都有稳定 `path_id`
- 每个 branch 都有结构化 `parameter_slots`
- 阶段 3 可以直接基于 branch 生成测试参数

## 特别说明

ParseStage 的产物不是“最终慢 SQL”，而是“待验证的 branch 候选”。
