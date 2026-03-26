# InitStage

## 目标

InitStage 的目标不是只“扫描 XML”，而是一次性产出后续阶段需要的全部基础事实：

- statement 清单
- 表结构
- 索引
- 表行数
- 查询条件字段的实际分布统计
- statement 到字段使用情况的映射

## 输入

- MyBatis mapper XML 文件
- 数据库连接信息
- 扫描配置

## 输出

- `sql_units`
- `table_metadata`
- `column_distributions`
- `column_usage_maps`
- `sql_fragments`
- `xml_mappings`

## 关键动作

### 1. XML 扫描与 statement 提取

- 扫描 `select / update / delete / insert`
- 保留 namespace、statement_id、原始 XML、fragment 引用关系

### 2. 字段使用识别

对每条 statement 识别：

- `where_columns`
- `join_columns`
- `group_by_columns`
- `order_by_columns`
- `range_columns`
- `like_columns`
- `in_columns`
- `foreach_collections`

### 3. 表级元数据采集

采集：

- 表字段
- 索引及索引列顺序
- 唯一索引
- 表行数
- 数据大小

### 4. 条件字段分布采集

这是阶段 1 的一级产物。

优先采集：

- `distinct_count`
- `null_count`
- `top_n_values`
- 数值/时间直方图
- `min/max`
- 平均长度、最大长度
- 偏斜分数

对高频联合条件，额外采集联合统计：

- 双字段联合基数
- 热点组合

## 关键策略

### 字段分布采集范围

默认只对以下字段采集：

- 出现在 `WHERE` 中的字段
- 出现在 `JOIN ON` 中的字段
- 出现在 `ORDER BY / GROUP BY` 中的字段
- 出现在 `IN / foreach` 中的字段

### 联合统计优先级

当 statement 中满足以下条件时，优先采集字段对联合统计：

- 多个条件经常一起出现
- 参与复合索引
- 一高一低选择性组合
- 常见租户字段 + 业务字段组合

## 成功标准

- 所有 statement 均有稳定 `statement_key`
- 所有候选查询字段都映射到表列
- 表结构、索引和表行数可被阶段 2/3 直接消费
- 字段分布足以支持阶段 3 生成代表性参数 case

## 失败处理

- 若字段分布采集失败，不允许静默吞掉
- 需要在 `manifest.json` 中明确标注缺失范围
- 下游阶段可以降级运行，但 finding 置信度要下降
