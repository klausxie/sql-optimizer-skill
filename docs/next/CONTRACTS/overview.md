# 数据契约总览

## 设计目标

下一代契约需要同时满足：

- 支持慢 SQL 发现链路
- 支持大项目分文件、分区、分片
- 支持跨阶段稳定引用
- 支持测试环境中的 explain 与基线执行

## 契约分层

| 文档 | 内容 |
|------|------|
| `common.md` | 公共 ID、manifest、index、共享类型 |
| `init.md` | 阶段 1 契约 |
| `parse.md` | 阶段 2 契约 |
| `recognition.md` | 阶段 3 契约 |
| `optimize.md` | 阶段 4 契约 |
| `result.md` | 阶段 5 契约 |

## 契约设计原则

- 稳定实体用单文件 JSON
- 高基数记录用 JSONL 分片
- 根级索引只存分区入口
- 所有记录都围绕稳定 ID 建立引用关系

## 统一引用链

```text
statement_key
  -> path_id
    -> case_id
      -> finding_id
        -> proposal_id
```

## 统一阶段输出

每个阶段都必须输出：

- `manifest.json`
- `_index.json`
- `SUMMARY.md`

并至少包含一种以下数据类型：

- 稳定实体 JSON
- 高基数 JSONL 分片

## 不允许的设计

- 单个阶段仅输出一个全量大 JSON 作为唯一真源
- 根级 `_index.json` 直接内联所有实体 ID
- 将所有 explain 与 execution 基线都拆成单个极小文件
