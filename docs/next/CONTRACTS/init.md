# 阶段 1 契约

## 目标实体

- `SQLUnit`
- `SQLFragment`
- `TableMetadata`
- `ColumnDistribution`
- `ColumnUsageMap`

## `SQLUnit`

```json
{
  "statement_key": "com.foo.user.UserMapper.findById",
  "namespace": "com.foo.user.UserMapper",
  "statement_id": "findById",
  "statement_type": "SELECT",
  "mapper_file": "UserMapper.xml",
  "xml_path": "src/main/resources/mapper/UserMapper.xml",
  "raw_sql_xml": "<select id=\"findById\">...</select>",
  "has_dynamic_sql": true,
  "referenced_tables": ["user"],
  "referenced_fragments": ["Base_Column_List"]
}
```

## `TableMetadata`

```json
{
  "table_name": "user",
  "row_count": 18500000,
  "data_bytes": 2147483648,
  "columns": [
    {"name": "id", "type": "bigint", "nullable": false},
    {"name": "status", "type": "varchar(16)", "nullable": true}
  ],
  "indexes": [
    {
      "name": "idx_user_status_created_at",
      "is_unique": false,
      "columns": ["status", "created_at"]
    }
  ]
}
```

## `ColumnDistribution`

由于当前设计不考虑安全限制，允许直接保存真实 top values。

```json
{
  "table_name": "user",
  "column_name": "status",
  "distinct_count": 5,
  "null_count": 0,
  "null_ratio": 0.0,
  "top_values": [
    {"value": "ACTIVE", "count": 16200000},
    {"value": "LOCKED", "count": 400000}
  ],
  "histogram": [],
  "skew_score": 0.91
}
```

## `ColumnUsageMap`

```json
{
  "statement_key": "com.foo.user.UserMapper.search",
  "where_columns": ["status", "name", "created_at"],
  "join_columns": ["tenant_id"],
  "group_by_columns": [],
  "order_by_columns": ["created_at"],
  "range_columns": ["created_at"],
  "like_columns": ["name"],
  "in_columns": ["id"],
  "foreach_collections": ["idList"]
}
```

## 存储布局

```text
init/
├── manifest.json
├── _index.json
├── sql_units/
│   ├── _index.json
│   └── by_namespace/{namespace}/{statement_id}.json
├── tables/
│   ├── _index.json
│   └── {table_name}.json
├── column_distributions/
│   ├── _index.json
│   └── {table_name}/{column_name}.json
├── column_usages/
│   ├── _index.json
│   └── by_namespace/{namespace}/{statement_id}.json
└── SUMMARY.md
```
