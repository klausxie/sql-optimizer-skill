# ResultStage

## 目标

ResultStage 负责把前面四个阶段的实体组织成可以消费的最终交付物。

## 输入

- `slow_sql_findings`
- `optimization_proposals`
- `optimization_validations`
- `sql_units`
- `xml_mappings`

## 输出

- 全局报告
- namespace 报告
- 排行结果
- patch
- 覆盖率说明

## 核心职责

### 1. 排名

按 `impact_score` 排序，而不是按 LLM `confidence` 排序。

### 2. 分类

最终输出至少分三类：

- `Verified Slow SQL`
- `High-Risk Candidates`
- `Need More Validation`

### 3. patch 生成

对被接受的 SQL 改写 proposal 生成 statement 级 patch：

- 原始 XML
- 建议 XML
- diff

### 4. 覆盖率说明

报告中需要明确：

- 扫描了多少 statement
- 展开了多少 branch
- 跑了多少 `EXPLAIN`
- 做了多少真实执行基线
- 有多少 finding 已验证
- 有多少 finding 只有 explain 证据

## 成功标准

- 用户可以快速看到优先级最高的慢 SQL
- 每条结果都能回溯到原始 statement 与 branch
- patch 可以按 statement 或 namespace 维度交付
