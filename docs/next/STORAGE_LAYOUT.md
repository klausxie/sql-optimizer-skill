# 存储布局设计

## 目标

存储布局需要同时满足：

- 支持大项目
- 避免单个超大 JSON 文件
- 避免高基数场景下的小文件爆炸
- 允许按 namespace、table、severity 等维度局部读取

## 总体规则

### 规则 1：每个阶段必须有 `manifest.json`

用于描述：

- 阶段状态
- 版本
- 统计信息
- 分区索引入口

### 规则 2：根级 `_index.json` 只保存分区入口

根级 `_index.json` 不直接列出所有实体，只列出分区。

### 规则 3：稳定实体用单文件 JSON

例如：

- statement
- table metadata
- branch candidate
- slow SQL finding
- optimization proposal

### 规则 4：高基数测量数据用分片 JSONL

例如：

- parameter cases
- explain baselines
- execution baselines
- optimization validations

## 统一目录模式

```text
runs/{run_id}/{stage}/
├── manifest.json
├── SUMMARY.md
├── _index.json
├── {entity_a}/
├── {entity_b}/
└── shards/
```

## 分区约定

### 按 namespace 分区

适用于 statement、branch、proposal、patch。

```text
by_namespace/{namespace}/...
```

### 按 table 分区

适用于表结构、字段分布。

```text
by_table/{table_name}/...
```

### 按 severity 分区

适用于慢 SQL finding。

```text
by_severity/{severity}/...
```

## 推荐的根级 `_index.json` 结构

```json
{
  "schema_version": "next-v1",
  "entity": "branch_candidates",
  "total_items": 12840,
  "partitions": [
    {
      "partition_key": "com.foo.user",
      "item_count": 320,
      "index_file": "units/by_namespace/com.foo.user/_index.json"
    }
  ]
}
```

## 推荐的局部分区 `_index.json` 结构

```json
{
  "partition_key": "com.foo.user",
  "entity": "branch_candidates",
  "total_items": 320,
  "items": [
    {
      "id": "com.foo.user.UserMapper.findById",
      "file": "units/by_namespace/com.foo.user/findById/statement.json"
    }
  ]
}
```

## JSONL 分片约定

对于高基数测量数据，每个 shard 使用：

- 单个 JSONL 文件
- 对应一个 `_index.json`
- shard 内按 `statement_key + path_id` 局部聚集

示例：

```text
recognition/execution/
├── _index.json
└── shards/
    ├── part-00001.jsonl
    ├── part-00002.jsonl
    └── ...
```

分片索引示例：

```json
{
  "entity": "execution_baselines",
  "total_records": 86000,
  "shards": [
    {
      "shard": "shards/part-00001.jsonl",
      "record_count": 5000,
      "namespace_range": ["com.foo.order", "com.foo.user"]
    }
  ]
}
```

## 阶段间兼容规则

- 小型项目可以额外输出轻量聚合文件作为便捷视图
- 但聚合文件不能是唯一真源
- 真源必须是可分区、可增量读取的实体文件和分片文件

## 文件命名规则

- `statement.json`: statement 级元数据
- `{path_id}.json`: branch/finding/proposal 等稳定实体
- `part-00001.jsonl`: 高基数记录分片
- `_index.json`: 局部索引
- `manifest.json`: 阶段元信息

## 大项目阈值建议

- 当单阶段实体数 > 5,000 时，禁止输出根级全量实体聚合文件
- 当单阶段测量记录 > 50,000 时，必须切换到 JSONL 分片
- 当单 namespace 实体数 > 1,000 时，namespace 内再按 statement 子目录拆分
