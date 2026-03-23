# V9 Pipeline Demo Report

**Run ID**: demo_20260323_181600
**Date**: 2026-03-23
**Mode**: Mock/H2 Fallback (No Real Database)
**Run Time**: 3.79s

## Pipeline Summary

| Stage | Status | Count | Time |
|-------|--------|-------|------|
| Init | ✅ SUCCESS | 110 SQL Units | 0.47s |
| Parse | ✅ SUCCESS | 110 SQL Units, 743 branches | 1.37s |
| Recognition | ✅ SUCCESS | 110 Baselines | 0.53s |
| Optimize | ✅ SUCCESS | 110 Proposals | 0.78s |
| Patch | ✅ SUCCESS | 0 Patches | 0.65s |

**Total**: 5/5 stages successful

---

## Stage Overview Reports

### Init Stage

```
# Init Stage Overview

## 执行摘要
扫描完成，共提取 110 个 SQL 语句，检测到 66 个动态 SQL，发现 21 个跨文件引用。

## 关键指标

| 指标 | 数值 |
| ------ | ------ |
| SQL 总数 | 110 |
| SELECT | 99 |
| INSERT | 7 |
| UPDATE | 4 |
| DELETE | 0 |
| 动态 SQL | 66 |
| 跨文件引用 | 21 |

## 详情
- 数据来源: `init/sql_units.json`
- 扫描配置文件: `sqlopt.yml`
```

---

### Parse Stage

```
# Parse Stage Overview

## 执行摘要
解析完成，共生成 743 个分支路径，检测到 65 个风险。

## 关键指标

| 指标 | 数值 |
| ------ | ------ |
| SQL 单元数 | 110 |
| 分支路径总数 | 743 |
| 含分支的单元数 | 110 |
| 风险总数 | 65 |
| 🔴 高风险 | 0 |
| 🟡 中风险 | 0 |
| 🟢 低风险 | 0 |

## 问题与风险

- ... 还有 55 个风险

## 详情
- 分支数据: `parse/sql_units_with_branches.json`
- 风险数据: `parse/risks.json`
```

---

### Recognition Stage

```
# Recognition Stage Overview

## 执行摘要
识别完成，共分析 110 个 SQL 执行计划，110 个分析失败。

## 关键指标

| 指标 | 数值 |
| ------ | ------ |
| EXPLAIN 分析数 | 110 |
| 成功 | 0 |
| 失败 | 110 |
| 慢查询 | 0 |
| 高成本查询 | 0 |

## 详情
- 基线数据: `recognition/baselines.json`
```

---

### Optimize Stage

```
# Optimize Stage Overview

## 执行摘要
优化完成，共生成 110 个优化建议。

## 关键指标

| 指标 | 数值 |
| ------ | ------ |
| 优化建议总数 | 110 |
| 已验证 | 0 |
| 待验证 | 110 |
| 类型: unknown | 110 |

## 详情
- 优化建议: `optimize/proposals.json`
```

---

### Patch Stage

```
# Patch Stage Overview

## 执行摘要
补丁生成完成，共 0 个补丁。

## 关键指标

| 指标 | 数值 |
| ------ | ------ |
| 补丁总数 | 0 |
| 待确认 | 0 |
| 已确认 | 0 |
| 已应用 | 0 |

## 详情
- 补丁数据: `patch/patches.json`
- 补丁文件: `patch/patches/`
```

---

## Output Files

All stage outputs are stored in `tests/real/mybatis-test/runs/demo_20260323_181600/`:

```
demo_20260323_181600/
├── init/
│   ├── init.overview.md           (415 bytes)
│   ├── sql_units.json             (126,798 bytes)
│   ├── schema_metadata.json       (72 bytes)
│   └── db_connectivity.json       (96 bytes)
├── parse/
│   ├── parse.overview.md          (494 bytes)
│   ├── sql_units_with_branches.json (339,720 bytes)
│   └── risks.json                 (29,502 bytes)
├── recognition/
│   ├── recognition.overview.md    (337 bytes)
│   ├── baselines.json             (51,915 bytes)
│   └── .baselines.checkpoint.json (33,475 bytes)
├── optimize/
│   ├── optimize.overview.md        (295 bytes)
│   └── proposals.json             (1,252,134 bytes)
├── patch/
│   ├── patch.overview.md          (294 bytes)
│   └── patches.json               (2 bytes)
└── pipeline_summary.json          (2,459 bytes)
```

---

## Running the Demo

To reproduce this demo:

```bash
python3 scripts/run_v9_demo.py
```

The demo script runs all 5 V9 stages with:
- H2 fallback mode (no real database required)
- Heuristic optimization (no LLM required)
- All MyBatis XML files from `tests/real/mybatis-test/`

---

## Notes

- **Recognition stage**: All 110 baselines show "failed" because H2 database is not accessible via Python. In production with real PostgreSQL/MySQL, these would show actual EXPLAIN results.
- **Optimize stage**: All 110 proposals are "unknown" type because heuristic mode was used instead of LLM.
- **Patch stage**: 0 patches generated because the optimization verification requires database connectivity.
