# Init Stage Overview

## 执行摘要
扫描完成，共提取 16 个 SQL 语句，检测到 16 个动态 SQL，发现 7 个跨文件引用。

## 关键指标

| 指标 | 数值 |
| ------ | ------ |
| SQL 总数 | 16 |
| SELECT | 11 |
| INSERT | 2 |
| UPDATE | 3 |
| DELETE | 0 |
| 动态 SQL | 16 |
| 跨文件引用 | 7 |
| 风险标记 | 18 |

## 扫描详情

- **Mapper 文件**: UserMapper.xml, OrderMapper.xml, CommonMapper.xml
- **数据库平台**: PostgreSQL 15.3
- **表数量**: 3 (users, orders, products)
- **索引数量**: 6

## 风险分布

| 风险类型 | 数量 |
| -------- | ---- |
| PREFIX_WILDCARD | 6 |
| MISSING_LIMIT | 8 |
| NO_INDEX | 4 |

## 下一步建议

1. **Parse 阶段**: 展开动态 SQL 生成分支路径
2. **Recognition 阶段**: 收集 EXPLAIN 执行计划
3. **Optimize 阶段**: 基于规则和 LLM 生成优化建议

## 详情
- 数据来源: `init/sql_units.json`
- SQL 片段注册: `init/fragment_registry.json`
- 扫描配置: `sqlopt.yml`
