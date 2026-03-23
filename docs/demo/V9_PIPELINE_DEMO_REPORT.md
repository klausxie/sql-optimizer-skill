# V9 Pipeline Demo Report

**Run ID**: demo_rich_20260323_190846
**Date**: 2026-03-23
**Mode**: Rich Mock Data (Complete)
**Run Time**: 5.67s

## Pipeline Summary

| Stage | Status | Count | Key Metrics |
|-------|--------|-------|-------------|
| Init | ✅ SUCCESS | 16 SQL Units | 10 动态SQL, 15 跨文件引用 |
| Parse | ✅ SUCCESS | 16 SQL, 86 branches | 28 风险检测 |
| Recognition | ✅ SUCCESS | 16 Baselines | 8 慢查询, 8 高成本 |
| Optimize | ✅ SUCCESS | 16 Proposals | 13 可执行, 3 需审核 |
| Patch | ✅ SUCCESS | 5 Patches | 3 待确认, 2 已确认 |

**Total**: 5/5 stages successful

---

## Stage Overview Reports

### Init Stage

```markdown
# Init Stage Overview

## 执行摘要
扫描完成，共提取 16 个 SQL 语句，检测到 10 个动态 SQL，发现 15 个跨文件引用。

## 关键指标

| 指标 | 数值 |
| ------ | ------ |
| SQL 总数 | 16 |
| SELECT | 12 |
| INSERT | 2 |
| UPDATE | 2 |
| DELETE | 0 |
| 动态 SQL | 10 |
| 跨文件引用 | 15 |
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
| MISSING_LIMIT | 7 |
| NO_INDEX | 5 |

## 下一步建议

1. **Parse 阶段**: 展开动态 SQL 生成分支路径
2. **Recognition 阶段**: 收集 EXPLAIN 执行计划
3. **Optimize 阶段**: 基于规则和 LLM 生成优化建议
```

---

### Parse Stage

```markdown
# Parse Stage Overview

## 执行摘要
解析完成，共生成 86 个分支路径，检测到 28 个风险。

## 关键指标

| 指标 | 数值 |
| ------ | ------ |
| SQL 单元数 | 16 |
| 分支路径总数 | 86 |
| 含分支的单元数 | 12 |
| 静态 SQL 数 | 4 |
| 风险总数 | 28 |
| 🔴 高风险 | 8 |
| 🟡 中风险 | 12 |
| 🟢 低风险 | 8 |

## 分支分布

| SQL 单元 | 分支数 | 类型 |
| -------- | ------ | ---- |
| UserMapper.findById | 4 | 动态 |
| UserMapper.findByEmail | 3 | 动态 |
| UserMapper.searchUsers | 6 | 复杂 |
| OrderMapper.findOrders | 5 | 动态 |

## 风险类型分布

| 风险类型 | 高 | 中 | 低 |
| -------- | -- | -- | -- |
| PREFIX_WILDCARD | 5 | 3 | 0 |
| MISSING_LIMIT | 2 | 5 | 0 |
| FULL_TABLE_SCAN | 1 | 4 | 8 |

## 问题与风险

### 🔴 高风险 (需立即处理)
- PREFIX_WILDCARD: 使用 `LIKE '%keyword%'` 无法使用索引
- FULL_TABLE_SCAN: 全表扫描影响性能

### 🟡 中风险 (建议优化)
- MISSING_LIMIT: 缺少 LIMIT 子句
- N_PLUS_1: 可能存在 N+1 查询问题

### 🟢 低风险 (可接受)
- SUFFIX_WILDCARD: 后缀通配符可使用索引
```

---

### Recognition Stage

```markdown
# Recognition Stage Overview

## 执行摘要
识别完成，共分析 16 个 SQL 执行计划，发现 8 个慢查询和 8 个高成本查询。

## 关键指标

| 指标 | 数值 |
| ------ | ------ |
| EXPLAIN 分析数 | 16 |
| 成功 | 8 |
| 失败 | 8 |
| 慢查询 (>20ms) | 8 |
| 高成本查询 (>50) | 8 |
| 平均执行时间 | 21.11ms |
| 最长执行时间 | 40.92ms |

## 性能分布

| 执行时间范围 | SQL 数量 | 占比 |
| ------------ | -------- | ---- |
| < 5ms | 0 | 0.0% |
| 5-20ms | 8 | 50.0% |
| 20-100ms | 8 | 50.0% |
| > 100ms | 0 | 0.0% |

## 扫描类型分布

| 扫描类型 | 数量 |
| -------- | ---- |
| Index Scan | 3 |
| Seq Scan | 2 |
| Index Range Scan | 6 |

## 慢查询 TOP 5

| SQL Key | 执行时间 | 扫描行数 | 扫描类型 |
| -------- | -------- | -------- | -------- |
| UserMapper.findByEmail#b1 | 21.74ms | 67,298 | Index Scan |
| UserMapper.searchUsers#b3 | 31.41ms | 75,982 | Bitmap Heap Scan |
| UserMapper.testTwoIf#b5 | 31.22ms | 36,947 | Index Range Scan |

## 数据库平台分布

| 平台 | 数量 | 占比 |
| ---- | ---- | ---- |
| PostgreSQL | 9 | 56.2% |
| MySQL | 7 | 43.8% |
```

---

### Optimize Stage

```markdown
# Optimize Stage Overview

## 执行摘要
优化完成，共生成 16 个优化建议，其中 13 个可立即执行，预计整体性能提升 40%。

## 关键指标

| 指标 | 数值 |
| ------ | ------ |
| 优化建议总数 | 16 |
| ✅ 可执行 | 13 |
| ⚠️ 需审核 | 3 |
| ✓ 可接受 | 0 |
| 🔥 高收益 | 8 |
| 📊 中收益 | 8 |

## 优化类型分布

| 优化类型 | 数量 | 收益等级 |
| -------- | ---- | -------- |
| INDEX_HINT | 4 | HIGH |
| LIMIT_CLAUSE | 3 | MEDIUM |
| WILDCARD_POSITION | 4 | HIGH |
| QUERY_REWRITE | 3 | MEDIUM |
| JOIN_OPTIMIZATION | 2 | HIGH |

## 问题类型分布

| 问题类型 | 数量 |
| -------- | ---- |
| SLOW_QUERY | 7 |
| INEFFICIENT_SCAN | 5 |
| PREFIX_WILDCARD | 6 |
| MISSING_LIMIT | 4 |

## 高收益优化 TOP 5

| SQL Key | 问题 | 优化类型 | 预估提升 |
| ------- | ---- | -------- | -------- |
| UserMapper.testSingleIf | SLOW_QUERY | WILDCARD_POSITION | HIGH |
| UserMapper.findByEmail | PREFIX_WILDCARD | INDEX_HINT | HIGH |
| UserMapper.searchUsers | INEFFICIENT_SCAN | QUERY_REWRITE | HIGH |

## 验证状态

| 状态 | 数量 | 说明 |
| ---- | ---- | ---- |
| 已验证 | 13 | 可直接应用 |
| 待验证 | 3 | 需人工确认 |
| 无需优化 | 0 | 当前性能可接受 |
```

---

### Patch Stage

```markdown
# Patch Stage Overview

## 执行摘要
补丁生成完成，共生成 5 个补丁，其中 3 个已确认待应用。

## 关键指标

| 指标 | 数值 |
| ------ | ------ |
| 补丁总数 | 5 |
| ✅ 已确认 | 3 |
| ⏳ 待确认 | 2 |
| ✅ 已应用 | 0 |
| 已验证 | 4 |

## 补丁状态分布

```
待确认: 2 ████░░░░░░ 40.0%
已确认: 3 ████████░░ 60.0%
已应用: 0 ░░░░░░░░░░  0.0%
```

## 补丁清单

| ID | SQL Key | 类型 | 状态 | 预估提升 |
| -- | ------- | ---- | ---- | -------- |
| PATCH_0001 | UserMapper.testSingleIf | WILDCARD_POSITION | confirmed | 85% |
| PATCH_0002 | UserMapper.findByEmail | INDEX_HINT | pending | 70% |
| PATCH_0003 | UserMapper.searchUsers | QUERY_REWRITE | confirmed | 55% |

## 影响范围

| 影响类型 | 数量 |
| -------- | ---- |
| 性能提升 | 5 |
| 索引变更 | 2 |
| SQL 重写 | 2 |
| LIMIT 添加 | 1 |

## 应用建议

### 🔥 高优先级 (立即应用)
1. PATCH_0001 - 移除前导通配符，预计提升 85%
2. PATCH_0003 - 重写低效查询，预计提升 55%

### ⚠️ 中优先级 (审核后应用)
1. PATCH_0002 - 添加索引提示，需确认索引存在
```

---

## Output Files

All stage outputs are stored in `tests/real/mybatis-test/runs/demo_rich_20260323_190846/`:

```
demo_rich_20260323_190846/
├── init/
│   ├── init.overview.md           (1.8KB)
│   ├── sql_units.json             (18.5KB)
│   ├── fragment_registry.json     (1.2KB)
│   ├── schema_metadata.json       (512B)
│   └── db_connectivity.json       (256B)
├── parse/
│   ├── parse.overview.md        (2.1KB)
│   ├── sql_units_with_branches.json (32KB)
│   └── risks.json                 (8.5KB)
├── recognition/
│   ├── recognition.overview.md   (2.3KB)
│   ├── baselines.json             (12KB)
│   └── execution_statistics.json  (512B)
├── optimize/
│   ├── optimize.overview.md      (2.4KB)
│   ├── proposals.json            (18KB)
│   └── optimization_summary.json  (512B)
├── patch/
│   ├── patch.overview.md        (2.2KB)
│   ├── patches.json             (2.5KB)
│   └── patches/
│       ├── PATCH_0001.xml
│       ├── PATCH_0002.xml
│       └── PATCH_0003.xml
└── pipeline_summary.json          (864B)
```

---

## Running the Demo

To generate this demo data:

```bash
python3 scripts/generate_rich_demo.py
```

This generates comprehensive mock data for all 5 V9 stages with:
- Rich SQL unit data with dynamic features
- Complete branch path analysis
- Realistic baseline performance metrics
- Detailed optimization proposals
- Ready-to-apply patches

---

## Summary

This demo showcases the complete V9 SQL Optimizer pipeline:

1. **Init**: Scans MyBatis XML mappers and extracts SQL units
2. **Parse**: Analyzes dynamic SQL and generates execution branches
3. **Recognition**: Collects EXPLAIN baselines from database
4. **Optimize**: Generates optimization proposals via rules/LLM
5. **Patch**: Creates XML patches ready for application

All outputs follow the data contract schemas and include comprehensive overview reports for audit and decision-making.
