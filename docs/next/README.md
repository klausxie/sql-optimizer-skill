# 下一代设计文档

本目录用于描述 SQL Optimizer 的下一代方案，目标从“通用 SQL 优化”收敛为：

- 尽可能高召回地发现 MyBatis XML 中的慢 SQL 候选
- 在测试环境中基于真实表结构、索引、数据量与字段分布做 `EXPLAIN` 和基线执行
- 在确认慢点之后，再进入优化与收益验证

## 设计前提

- 生产环境运行时明细、慢查询日志、真实参数样本默认不可直接接入
- 可以获取生产对应的表结构、索引信息、表行数等元数据
- 可以在测试环境执行 SQL、运行 `EXPLAIN`、执行基线 SQL
- 阶段 1 必须采集处于查询条件中的字段的实际分布统计信息
- 大项目场景下，阶段输出不能依赖“单个超大 JSON 文件”，必须采用分文件、分区、分片设计

## 文档结构

```text
next/
├── README.md
├── FUNCTIONAL_DESIGN.md
├── ARCHITECTURE.md
├── DATAFLOW.md
├── STORAGE_LAYOUT.md
├── STAGES/
│   ├── README.md
│   ├── init.md
│   ├── parse.md
│   ├── recognition.md
│   ├── optimize.md
│   └── result.md
└── CONTRACTS/
    ├── overview.md
    ├── common.md
    ├── init.md
    ├── parse.md
    ├── recognition.md
    ├── optimize.md
    └── result.md
```

## 阅读顺序

1. `FUNCTIONAL_DESIGN.md`
2. `ARCHITECTURE.md`
3. `DATAFLOW.md`
4. `STORAGE_LAYOUT.md`
5. `STAGES/*.md`
6. `CONTRACTS/*.md`

## 与当前实现的关系

- `docs/current/` 描述当前已实现系统
- `docs/next/` 描述面向慢 SQL 发现目标的下一代设计
- 本目录中的契约与目录布局是目标状态，不代表当前代码已经实现
