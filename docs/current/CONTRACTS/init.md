# 阶段一：Init（初始化阶段）

## 阶段简介
- 输入：MyBatis XML mapper 文件
- 输出：SQLUnit, TableSchema, FieldDistribution, InitOutput
- 职责：解析 XML，提取 SQL，收集表元数据

## 数据契约

### SQLUnit
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | str | 是 | 唯一标识符 |
| mapper_file | str | 是 | XML 文件相对路径 |
| sql_id | str | 是 | statement 的 id 属性 |
| sql_text | str | 是 | 原始 SQL XML 文本 |
| statement_type | str | 是 | SELECT/INSERT/UPDATE/DELETE |

**示例**：
```json
{
  "id": "src/main/resources/mapper/UserMapper.xml:findUserById",
  "mapper_file": "src/main/resources/mapper/UserMapper.xml",
  "sql_id": "findUserById",
  "sql_text": "<select id=\"findUserById\">SELECT * FROM users WHERE id = #{id}</select>",
  "statement_type": "SELECT"
}
```

### SQLFragment
可复用的 <sql id=""> 片段。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| fragment_id | str | 是 | 片段唯一标识 |
| xml_path | str | 是 | XML 文件路径 |
| start_line | int | 是 | 起始行号 |
| end_line | int | 是 | 结束行号 |
| xml_content | str | 是 | 原始 XML 内容 |

### TableSchema
表结构信息。

| 字段 | 类型 | 说明 |
|------|------|------|
| table_name | str | 表名 |
| columns | list | 列信息列表 |
| indexes | list | 索引信息列表 |
| statistics | dict | 统计信息 |

### FieldDistribution
字段数据分布统计。

| 字段 | 类型 | 说明 |
|------|------|------|
| table_name | str | 表名 |
| column_name | str | 列名 |
| distinct_count | int | 不同值数量 |
| null_count | int | NULL 值数量 |
| total_count | int | 总行数 |
| top_values | list | 最高频的值及次数 |
| min_value | any | 最小值 |
| max_value | any | 最大值 |

### InitOutput
顶级输出容器。

| 字段 | 类型 | 说明 |
|------|------|------|
| run_id | str | 运行唯一标识 |
| timestamp | str | ISO 时间戳 |
| sql_units | list | 所有 SQL 单元 |
| sql_fragments | list | 所有 SQL 片段 |
| table_schemas | dict | 表名 → TableSchema 映射 |
| field_distributions | list | 字段分布数据 |
| xml_mappings | XMLMapping | XML 文件映射 |
| table_relationships | list | 表关系 |
| table_hotspots | dict | 表热度/风险 profile |

## 输出文件清单

| 文件路径 | 内容 | 生成时机 | 用途 |
|----------|------|----------|------|
| runs/{run_id}/init/sql_units.json | SQLUnit 列表 | Init 结束时 | Parse 输入 |
| runs/{run_id}/init/sql_fragments.json | SQLFragment 列表 | Init 结束时 | 片段复用 |
| runs/{run_id}/init/table_schemas.json | 表结构映射 | Init 结束时 | Recognition 参考 |
| runs/{run_id}/init/field_distributions.json | 字段分布 | Init 结束时 | 风险评估 |
| runs/{run_id}/init/xml_mappings.json | XML 映射 | Init 结束时 | Result 定位 |
| runs/{run_id}/init/SUMMARY.html | 可视化报告 | Init 结束时 | 人工查看 |

## 常见问题

### Q: 为什么有些 SQL 没被提取？
只有 <select>, <insert>, <update>, <delete> 标签会被提取。

### Q: field_distributions 有什么用？
用于评估 SQL 风险，如字段倾斜会导致索引失效。