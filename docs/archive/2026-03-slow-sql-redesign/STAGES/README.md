# 阶段设计

## 阶段列表

- `init.md`: 扫描 XML、采集表与字段统计事实
- `parse.md`: 展开动态 SQL、生成高召回 branch 候选
- `recognition.md`: 执行 `EXPLAIN`、基线执行、识别慢 SQL
- `optimize.md`: 生成优化方案并验证收益
- `result.md`: 汇总排名、报告和 patch

## 统一阶段约束

- 每个阶段都必须输出 `manifest.json`
- 每个阶段都必须支持分区索引
- 高基数记录必须支持 JSONL 分片
- 每个阶段的核心输出都必须可被下游直接引用，而不是依赖人工拼接
