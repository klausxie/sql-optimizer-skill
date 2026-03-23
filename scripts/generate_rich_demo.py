#!/usr/bin/env python3
"""
Generate Rich Mock Demo Data for V9 Pipeline Presentation

Creates comprehensive, realistic mock data for all 5 stages
with complete data contracts and detailed overview reports.
"""

from __future__ import annotations

import json
import random
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path("tests/real/mybatis-test/runs")
RUN_ID = f"demo_rich_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
RUN_DIR = ROOT / RUN_ID

SQL_KEYS = [
    "com.test.mapper.UserMapper.findById",
    "com.test.mapper.UserMapper.findByEmail",
    "com.test.mapper.UserMapper.findByStatus",
    "com.test.mapper.UserMapper.searchUsers",
    "com.test.mapper.UserMapper.testSingleIf",
    "com.test.mapper.UserMapper.testTwoIf",
    "com.test.mapper.UserMapper.testChooseOtherwise",
    "com.test.mapper.OrderMapper.findOrdersWithCommon",
]

RISK_TYPES = [
    {"type": "PREFIX_WILDCARD", "severity": "HIGH", "sql": "LIKE '%keyword%'"},
    {"type": "SUFFIX_WILDCARD", "severity": "LOW", "sql": "LIKE 'keyword%'"},
    {
        "type": "CONCAT_WILDCARD",
        "severity": "HIGH",
        "sql": "LIKE CONCAT('%', #{val}, '%')",
    },
    {
        "type": "MISSING_INDEX",
        "severity": "MEDIUM",
        "sql": "WHERE unindexed_column = #{val}",
    },
    {"type": "NO_LIMIT", "severity": "MEDIUM", "sql": "SELECT * FROM large_table"},
    {
        "type": "FULL_TABLE_SCAN",
        "severity": "HIGH",
        "sql": "SELECT * FROM users WHERE 1=1",
    },
    {
        "type": "N_PLUS_1",
        "severity": "MEDIUM",
        "sql": "SELECT * FROM orders WHERE user_id IN (SELECT id FROM users)",
    },
]

OPTIMIZATION_TYPES = [
    {"type": "INDEX_HINT", "benefit": "HIGH", "confidence": "HIGH"},
    {"type": "LIMIT_CLAUSE", "benefit": "MEDIUM", "confidence": "HIGH"},
    {"type": "WILDCARD_POSITION", "benefit": "HIGH", "confidence": "MEDIUM"},
    {"type": "QUERY_REWRITE", "benefit": "MEDIUM", "confidence": "MEDIUM"},
    {"type": "JOIN_OPTIMIZATION", "benefit": "HIGH", "confidence": "HIGH"},
]


def generate_sql_key():
    return random.choice(SQL_KEYS)


def generate_baseline(sql_key, idx):
    exec_time = random.uniform(0.5, 50.0)
    rows_scanned = random.randint(100, 100000)
    rows_returned = random.randint(1, min(1000, rows_scanned))

    scan_types = ["Index Scan", "Seq Scan", "Index Range Scan", "Bitmap Heap Scan"]
    node_type = random.choice(scan_types)

    platforms = ["postgresql", "mysql"]
    platform = random.choice(platforms)

    baseline = {
        "sql_key": f"{sql_key}#b{idx}",
        "execution_time_ms": round(exec_time, 2),
        "rows_scanned": rows_scanned,
        "rows_returned": rows_returned,
        "execution_plan": {
            "node_type": node_type,
            "index_used": f"idx_{random.choice(['user_id', 'email', 'status', 'created_at'])}"
            if "Index" in node_type
            else None,
            "cost": round(random.uniform(1.0, 100.0), 2),
        },
        "result_hash": hashlib.md5(f"{sql_key}_{idx}".encode()).hexdigest(),
        "database_platform": platform,
        "sample_params": {
            "id": random.randint(1, 1000),
            "status": random.choice(["active", "inactive"]),
        },
    }
    return baseline


def generate_proposal(sql_key, baseline):
    opt_type = random.choice(OPTIMIZATION_TYPES)

    issues = []
    if baseline["execution_time_ms"] > 10:
        issues.append("SLOW_QUERY")
    if baseline["rows_scanned"] > baseline["rows_returned"] * 10:
        issues.append("INEFFICIENT_SCAN")
    if random.random() > 0.5:
        issues.append(random.choice(["PREFIX_WILDCARD", "MISSING_LIMIT", "NO_INDEX"]))

    proposal = {
        "sqlKey": sql_key,
        "issues": issues if issues else ["PERFORMANCE_WARNING"],
        "suggestions": [
            {
                "type": opt_type["type"],
                "originalSql": f"SELECT * FROM users WHERE name LIKE '%{random.choice(['test', 'user', 'admin'])}%'",
                "suggestedSql": f"SELECT * FROM users WHERE name LIKE '{random.choice(['test', 'user', 'admin'])}%'",
                "rationale": f"Remove leading wildcard to enable index usage. Expected benefit: {opt_type['benefit']}",
                "estimated_improvement": f"{random.randint(30, 95)}%",
            }
        ],
        "verdict": random.choice(["ACTIONABLE", "NEEDS_REVIEW", "ACCEPTABLE"]),
        "estimatedBenefit": opt_type["benefit"],
        "confidence": opt_type["confidence"],
        "dbEvidenceSummary": {
            "executionTimeMs": baseline["execution_time_ms"],
            "rowsScanned": baseline["rows_scanned"],
            "indexUsed": baseline["execution_plan"].get("index_used", "NONE"),
        },
        "planSummary": {
            "nodeType": baseline["execution_plan"]["node_type"],
            "estimatedCost": baseline["execution_plan"]["cost"],
        },
    }
    return proposal


def generate_risk(sql_key, idx):
    risk = random.choice(RISK_TYPES)
    return {
        "sql_key": f"{sql_key}#b{idx}",
        "risk_type": risk["type"],
        "severity": risk["severity"],
        "location": risk["sql"],
        "description": f"Found {risk['type']} pattern in SQL",
        "recommendation": f"Optimize {risk['type']} for better performance",
    }


def generate_fragment():
    return {
        "fragmentId": f"fragment_{random.randint(1000, 9999)}",
        "sql": f"SELECT id, name, email FROM {random.choice(['users', 'orders', 'products'])} WHERE status = 'active'",
        "description": f"Common query fragment for {random.choice(['user', 'order', 'product'])} lookups",
    }


def create_init_stage():
    stage_dir = RUN_DIR / "init"
    stage_dir.mkdir(parents=True, exist_ok=True)

    sql_units = []
    for i, sql_key in enumerate(SQL_KEYS * 2):
        sql_unit = {
            "sqlKey": sql_key,
            "xmlPath": f"src/main/resources/mapper/{sql_key.split('.')[2]}.xml",
            "namespace": "com.test.mapper",
            "statementId": sql_key.split(".")[-1],
            "statementType": random.choice(
                ["SELECT", "SELECT", "SELECT", "INSERT", "UPDATE"]
            ),
            "variantId": f"v{i % 3 + 1}",
            "sql": f"SELECT * FROM users WHERE id = #{{id}} AND status = #{{status}}",
            "parameterMappings": [
                {"name": "id", "type": "Integer"},
                {"name": "status", "type": "String"},
            ],
            "paramExample": {"id": 1, "status": "active"},
            "locators": {"statementId": sql_key.split(".")[-1]},
            "riskFlags": random.sample(
                ["PREFIX_WILDCARD", "MISSING_LIMIT", "NO_INDEX"], k=random.randint(0, 2)
            ),
            "templateSql": 'SELECT * FROM users WHERE <if test="id != null">id = #{id}</if>',
            "dynamicFeatures": random.sample(
                ["IF", "WHERE", "CHOOSE", "FOREACH", "SET"], k=random.randint(1, 3)
            ),
            "branchCount": random.randint(1, 8),
            "crossFileRefs": random.randint(0, 3) if i % 3 == 0 else 0,
        }
        sql_units.append(sql_unit)

    with open(stage_dir / "sql_units.json", "w") as f:
        json.dump(sql_units, f, indent=2, ensure_ascii=False)

    fragment_registry = {
        "fragments": [generate_fragment() for _ in range(5)],
        "total_count": 5,
    }
    with open(stage_dir / "fragment_registry.json", "w") as f:
        json.dump(fragment_registry, f, indent=2, ensure_ascii=False)

    with open(stage_dir / "schema_metadata.json", "w") as f:
        json.dump(
            {
                "tables": [
                    {"name": "users", "columns": 8, "indexes": 3},
                    {"name": "orders", "columns": 6, "indexes": 2},
                    {"name": "products", "columns": 5, "indexes": 1},
                ],
                "platform": "postgresql",
            },
            f,
            indent=2,
        )

    with open(stage_dir / "db_connectivity.json", "w") as f:
        json.dump(
            {
                "ok": True,
                "platform": "postgresql",
                "db_version": "PostgreSQL 15.3",
                "driver": "psycopg2",
            },
            f,
            indent=2,
        )

    overview = f"""# Init Stage Overview

## 执行摘要
扫描完成，共提取 {len(sql_units)} 个 SQL 语句，检测到 {sum(1 for u in sql_units if u["dynamicFeatures"])} 个动态 SQL，发现 {sum(u["crossFileRefs"] for u in sql_units)} 个跨文件引用。

## 关键指标

| 指标 | 数值 |
| ------ | ------ |
| SQL 总数 | {len(sql_units)} |
| SELECT | {sum(1 for u in sql_units if u["statementType"] == "SELECT")} |
| INSERT | {sum(1 for u in sql_units if u["statementType"] == "INSERT")} |
| UPDATE | {sum(1 for u in sql_units if u["statementType"] == "UPDATE")} |
| DELETE | {sum(1 for u in sql_units if u["statementType"] == "DELETE")} |
| 动态 SQL | {sum(1 for u in sql_units if u["dynamicFeatures"])} |
| 跨文件引用 | {sum(u["crossFileRefs"] for u in sql_units)} |
| 风险标记 | {sum(len(u["riskFlags"]) for u in sql_units)} |

## 扫描详情

- **Mapper 文件**: UserMapper.xml, OrderMapper.xml, CommonMapper.xml
- **数据库平台**: PostgreSQL 15.3
- **表数量**: 3 (users, orders, products)
- **索引数量**: 6

## 风险分布

| 风险类型 | 数量 |
| -------- | ---- |
| PREFIX_WILDCARD | {sum(1 for u in sql_units if "PREFIX_WILDCARD" in u["riskFlags"])} |
| MISSING_LIMIT | {sum(1 for u in sql_units if "MISSING_LIMIT" in u["riskFlags"])} |
| NO_INDEX | {sum(1 for u in sql_units if "NO_INDEX" in u["riskFlags"])} |

## 下一步建议

1. **Parse 阶段**: 展开动态 SQL 生成分支路径
2. **Recognition 阶段**: 收集 EXPLAIN 执行计划
3. **Optimize 阶段**: 基于规则和 LLM 生成优化建议

## 详情
- 数据来源: `init/sql_units.json`
- SQL 片段注册: `init/fragment_registry.json`
- 扫描配置: `sqlopt.yml`
"""
    with open(stage_dir / "init.overview.md", "w") as f:
        f.write(overview)

    return len(sql_units)


def create_parse_stage(sql_count):
    stage_dir = RUN_DIR / "parse"
    stage_dir.mkdir(parents=True, exist_ok=True)

    sql_units_with_branches = []
    all_risks = []

    for i, sql_key in enumerate(SQL_KEYS * 2):
        branch_count = random.randint(2, 8)
        branches = []
        for j in range(branch_count):
            suffix = f" AND name LIKE '%{j}%'" if j % 2 == 0 else ""
            sql = f"SELECT * FROM users WHERE id = #{{id}} AND status = #{{status}}{suffix}"
            branch = {
                "id": j,
                "conditions": [
                    f"param_{k} != null" for k in range(random.randint(1, 3))
                ],
                "sql": sql,
                "type": "static" if j == 0 else "conditional",
                "estimated_cost": round(random.uniform(1.0, 50.0), 2),
            }
            branches.append(branch)

            if random.random() > 0.7:
                risk = generate_risk(sql_key, j)
                all_risks.append(risk)

        sql_unit = {
            "sqlKey": sql_key,
            "branches": branches,
            "branchCount": branch_count,
            "dynamicSql": len(branches) > 1,
            "fragmentRefs": random.randint(0, 2),
        }
        sql_units_with_branches.append(sql_unit)

    total_branches = sum(u["branchCount"] for u in sql_units_with_branches)

    with open(stage_dir / "sql_units_with_branches.json", "w") as f:
        json.dump(sql_units_with_branches, f, indent=2, ensure_ascii=False)

    with open(stage_dir / "risks.json", "w") as f:
        json.dump(all_risks, f, indent=2, ensure_ascii=False)

    risk_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for r in all_risks:
        risk_counts[r["severity"]] += 1

    overview = f"""# Parse Stage Overview

## 执行摘要
解析完成，共生成 {total_branches} 个分支路径，检测到 {len(all_risks)} 个风险。

## 关键指标

| 指标 | 数值 |
| ------ | ------ |
| SQL 单元数 | {len(sql_units_with_branches)} |
| 分支路径总数 | {total_branches} |
| 含分支的单元数 | {sum(1 for u in sql_units_with_branches if u["dynamicSql"])} |
| 静态 SQL 数 | {sum(1 for u in sql_units_with_branches if not u["dynamicSql"])} |
| 风险总数 | {len(all_risks)} |
| 🔴 高风险 | {risk_counts["HIGH"]} |
| 🟡 中风险 | {risk_counts["MEDIUM"]} |
| 🟢 低风险 | {risk_counts["LOW"]} |

## 分支分布

| SQL 单元 | 分支数 | 类型 |
| -------- | ------ | ---- |
| UserMapper.findById | {random.randint(2, 6)} | 动态 |
| UserMapper.findByEmail | {random.randint(2, 4)} | 动态 |
| UserMapper.searchUsers | {random.randint(4, 8)} | 复杂 |
| OrderMapper.findOrders | {random.randint(2, 6)} | 动态 |

## 风险类型分布

| 风险类型 | 高 | 中 | 低 |
| -------- | -- | -- | -- |
| PREFIX_WILDCARD | {risk_counts["HIGH"]} | 0 | 0 |
| MISSING_LIMIT | 0 | {risk_counts["MEDIUM"]} | 0 |
| FULL_TABLE_SCAN | 0 | 0 | {risk_counts["LOW"]} |

## 问题与风险

### 🔴 高风险 (需立即处理)
- PREFIX_WILDCARD: 使用 `LIKE '%keyword%'` 无法使用索引
- FULL_TABLE_SCAN: 全表扫描影响性能

### 🟡 中风险 (建议优化)
- MISSING_LIMIT: 缺少 LIMIT 子句
- N_PLUS_1: 可能存在 N+1 查询问题

### 🟢 低风险 (可接受)
- SUFFIX_WILDCARD: 后缀通配符可使用索引

## 下一步建议

1. **Recognition 阶段**: 对所有分支执行 EXPLAIN 收集性能基线
2. **Optimize 阶段**: 优先处理高风险 SQL
3. **建议关注**: findByEmail, searchUsers 等高频查询

## 详情
- 分支数据: `parse/sql_units_with_branches.json`
- 风险数据: `parse/risks.json`
- 平均分支数: {total_branches / len(sql_units_with_branches):.1f}
"""
    with open(stage_dir / "parse.overview.md", "w") as f:
        f.write(overview)

    return total_branches, len(all_risks)


def create_recognition_stage(sql_count, sql_keys):
    stage_dir = RUN_DIR / "recognition"
    stage_dir.mkdir(parents=True, exist_ok=True)

    baselines = []
    for i in range(sql_count):
        sql_key = sql_keys[i % len(sql_keys)]
        baseline = generate_baseline(sql_key, i % 8)
        baselines.append(baseline)

    slow_queries = [b for b in baselines if b["execution_time_ms"] > 20]
    high_cost = [b for b in baselines if b["execution_plan"]["cost"] > 50]

    with open(stage_dir / "baselines.json", "w") as f:
        json.dump(baselines, f, indent=2, ensure_ascii=False)

    with open(stage_dir / "execution_statistics.json", "w") as f:
        json.dump(
            {
                "total_queries": len(baselines),
                "slow_queries": len(slow_queries),
                "avg_execution_time_ms": sum(b["execution_time_ms"] for b in baselines)
                / len(baselines),
                "max_execution_time_ms": max(b["execution_time_ms"] for b in baselines),
                "total_rows_scanned": sum(b["rows_scanned"] for b in baselines),
                "platform_distribution": {
                    "postgresql": len(baselines) // 2,
                    "mysql": len(baselines) // 2,
                },
            },
            f,
            indent=2,
        )

    avg_time = sum(b["execution_time_ms"] for b in baselines) / len(baselines)

    overview = f"""# Recognition Stage Overview

## 执行摘要
识别完成，共分析 {len(baselines)} 个 SQL 执行计划，发现 {len(slow_queries)} 个慢查询和 {len(high_cost)} 个高成本查询。

## 关键指标

| 指标 | 数值 |
| ------ | ------ |
| EXPLAIN 分析数 | {len(baselines)} |
| 成功 | {len(baselines) - len(slow_queries)} |
| 失败 | {len(slow_queries)} |
| 慢查询 (>20ms) | {len(slow_queries)} |
| 高成本查询 (>50) | {len(high_cost)} |
| 平均执行时间 | {avg_time:.2f}ms |
| 最长执行时间 | {max(b["execution_time_ms"] for b in baselines):.2f}ms |

## 性能分布

| 执行时间范围 | SQL 数量 | 占比 |
| ------------ | -------- | ---- |
| < 5ms | {sum(1 for b in baselines if b["execution_time_ms"] < 5)} | {sum(1 for b in baselines if b["execution_time_ms"] < 5) / len(baselines) * 100:.1f}% |
| 5-20ms | {sum(1 for b in baselines if 5 <= b["execution_time_ms"] < 20)} | {sum(1 for b in baselines if 5 <= b["execution_time_ms"] < 20) / len(baselines) * 100:.1f}% |
| 20-100ms | {sum(1 for b in baselines if 20 <= b["execution_time_ms"] < 100)} | {sum(1 for b in baselines if 20 <= b["execution_time_ms"] < 100) / len(baselines) * 100:.1f}% |
| > 100ms | {sum(1 for b in baselines if b["execution_time_ms"] >= 100)} | {sum(1 for b in baselines if b["execution_time_ms"] >= 100) / len(baselines) * 100:.1f}% |

## 扫描类型分布

| 扫描类型 | 数量 |
| -------- | ---- |
| Index Scan | {sum(1 for b in baselines if "Index Scan" in b["execution_plan"]["node_type"])} |
| Seq Scan | {sum(1 for b in baselines if "Seq Scan" in b["execution_plan"]["node_type"])} |
| Index Range Scan | {sum(1 for b in baselines if "Index Range" in b["execution_plan"]["node_type"])} |

## 慢查询 TOP 5

| SQL Key | 执行时间 | 扫描行数 | 扫描类型 |
| -------- | -------- | -------- | -------- |
| {slow_queries[0]["sql_key"] if slow_queries else "N/A"} | {slow_queries[0]["execution_time_ms"]:.2f}ms | {slow_queries[0]["rows_scanned"]:,} | {slow_queries[0]["execution_plan"]["node_type"]} |
| {slow_queries[1]["sql_key"] if len(slow_queries) > 1 else "N/A"} | {slow_queries[1]["execution_time_ms"]:.2f}ms | {slow_queries[1]["rows_scanned"]:,} | {slow_queries[1]["execution_plan"]["node_type"]} |
| {slow_queries[2]["sql_key"] if len(slow_queries) > 2 else "N/A"} | {slow_queries[2]["execution_time_ms"]:.2f}ms | {slow_queries[2]["rows_scanned"]:,} | {slow_queries[2]["execution_plan"]["node_type"]} |

## 数据库平台分布

| 平台 | 数量 | 占比 |
| ---- | ---- | ---- |
| PostgreSQL | {sum(1 for b in baselines if b["database_platform"] == "postgresql")} | {sum(1 for b in baselines if b["database_platform"] == "postgresql") / len(baselines) * 100:.1f}% |
| MySQL | {sum(1 for b in baselines if b["database_platform"] == "mysql")} | {sum(1 for b in baselines if b["database_platform"] == "mysql") / len(baselines) * 100:.1f}% |

## 下一步建议

1. **Optimize 阶段**: 优先优化慢查询 TOP 5
2. **索引建议**: 为高频查询字段添加索引
3. **SQL 重写**: 消除全表扫描

## 详情
- 基线数据: `recognition/baselines.json`
- 统计数据: `recognition/execution_statistics.json`
- 执行时间阈值: 慢查询 > 20ms, 高成本 > 50
"""
    with open(stage_dir / "recognition.overview.md", "w") as f:
        f.write(overview)

    return len(baselines)


def create_optimize_stage(sql_count, sql_keys, baselines):
    stage_dir = RUN_DIR / "optimize"
    stage_dir.mkdir(parents=True, exist_ok=True)

    proposals = []
    for i in range(sql_count):
        sql_key = sql_keys[i % len(sql_keys)]
        baseline = baselines[i % len(baselines)]
        proposal = generate_proposal(sql_key, baseline)
        proposals.append(proposal)

    actionable = [p for p in proposals if p["verdict"] == "ACTIONABLE"]
    needs_review = [p for p in proposals if p["verdict"] == "NEEDS_REVIEW"]
    acceptable = [p for p in proposals if p["verdict"] == "ACCEPTABLE"]

    high_benefit = [p for p in proposals if p["estimatedBenefit"] == "HIGH"]

    with open(stage_dir / "proposals.json", "w") as f:
        json.dump(proposals, f, indent=2, ensure_ascii=False)

    with open(stage_dir / "optimization_summary.json", "w") as f:
        json.dump(
            {
                "total_proposals": len(proposals),
                "by_verdict": {
                    "actionable": len(actionable),
                    "needs_review": len(needs_review),
                    "acceptable": len(acceptable),
                },
                "by_benefit": {
                    "high": len(high_benefit),
                    "medium": len(proposals) - len(high_benefit),
                },
                "estimated_total_improvement": f"{len(high_benefit) * 30}%",
            },
            f,
            indent=2,
        )

    overview = f"""# Optimize Stage Overview

## 执行摘要
优化完成，共生成 {len(proposals)} 个优化建议，其中 {len(actionable)} 个可立即执行，预计整体性能提升 {len(high_benefit) * 30}%。

## 关键指标

| 指标 | 数值 |
| ------ | ------ |
| 优化建议总数 | {len(proposals)} |
| ✅ 可执行 | {len(actionable)} |
| ⚠️ 需审核 | {len(needs_review)} |
| ✓ 可接受 | {len(acceptable)} |
| 🔥 高收益 | {len(high_benefit)} |
| 📊 中收益 | {len(proposals) - len(high_benefit)} |

## 优化类型分布

| 优化类型 | 数量 | 收益等级 |
| -------- | ---- | -------- |
| INDEX_HINT | {sum(1 for p in proposals if p["suggestions"][0]["type"] == "INDEX_HINT")} | HIGH |
| LIMIT_CLAUSE | {sum(1 for p in proposals if p["suggestions"][0]["type"] == "LIMIT_CLAUSE")} | MEDIUM |
| WILDCARD_POSITION | {sum(1 for p in proposals if p["suggestions"][0]["type"] == "WILDCARD_POSITION")} | HIGH |
| QUERY_REWRITE | {sum(1 for p in proposals if p["suggestions"][0]["type"] == "QUERY_REWRITE")} | MEDIUM |
| JOIN_OPTIMIZATION | {sum(1 for p in proposals if p["suggestions"][0]["type"] == "JOIN_OPTIMIZATION")} | HIGH |

## 问题类型分布

| 问题类型 | 数量 |
| -------- | ---- |
| SLOW_QUERY | {sum(1 for p in proposals if "SLOW_QUERY" in p["issues"])} |
| INEFFICIENT_SCAN | {sum(1 for p in proposals if "INEFFICIENT_SCAN" in p["issues"])} |
| PREFIX_WILDCARD | {sum(1 for p in proposals if "PREFIX_WILDCARD" in p["issues"])} |
| MISSING_LIMIT | {sum(1 for p in proposals if "MISSING_LIMIT" in p["issues"])} |
| NO_INDEX | {sum(1 for p in proposals if "NO_INDEX" in p["issues"])} |

## 高收益优化 TOP 5

| SQL Key | 问题 | 优化类型 | 预估提升 |
| ------- | ---- | -------- | -------- |
| {actionable[0]["sqlKey"] if actionable else "N/A"} | {actionable[0]["issues"][0] if actionable else "N/A"} | {actionable[0]["suggestions"][0]["type"] if actionable else "N/A"} | {actionable[0]["estimatedBenefit"]} |
| {actionable[1]["sqlKey"] if len(actionable) > 1 else "N/A"} | {actionable[1]["issues"][0] if len(actionable) > 1 else "N/A"} | {actionable[1]["suggestions"][0]["type"] if len(actionable) > 1 else "N/A"} | {actionable[1]["estimatedBenefit"] if len(actionable) > 1 else "N/A"} |
| {actionable[2]["sqlKey"] if len(actionable) > 2 else "N/A"} | {actionable[2]["issues"][0] if len(actionable) > 2 else "N/A"} | {actionable[2]["suggestions"][0]["type"] if len(actionable) > 2 else "N/A"} | {actionable[2]["estimatedBenefit"] if len(actionable) > 2 else "N/A"} |

## 验证状态

| 状态 | 数量 | 说明 |
| ---- | ---- | ---- |
| 已验证 | {len(actionable)} | 可直接应用 |
| 待验证 | {len(needs_review)} | 需人工确认 |
| 无需优化 | {len(acceptable)} | 当前性能可接受 |

## 下一步建议

1. **Patch 阶段**: 优先应用高收益优化
2. **人工审核**: 对需审核建议进行确认
3. **回归测试**: 应用前建议备份

## 详情
- 优化建议: `optimize/proposals.json`
- 优化摘要: `optimize/optimization_summary.json`
- 验证通过率: {len(actionable) / len(proposals) * 100:.1f}%
"""
    with open(stage_dir / "optimize.overview.md", "w") as f:
        f.write(overview)

    return len(proposals), len(actionable)


def create_patch_stage(proposal_count, actionable_count):
    stage_dir = RUN_DIR / "patch"
    stage_dir.mkdir(parents=True, exist_ok=True)

    patch_count = actionable_count
    patches = []

    for i in range(patch_count):
        patch = {
            "patch_id": f"PATCH_{i + 1:04d}",
            "sql_key": f"com.test.mapper.UserMapper.testSingleIf#{i}",
            "status": random.choice(["pending", "confirmed", "applied"]),
            "original_sql": f"SELECT * FROM users WHERE name LIKE '%test%' AND status = #{{status}}",
            "optimized_sql": f"SELECT * FROM users WHERE name LIKE 'test%' AND status = #{{status}}",
            "optimization_type": "WILDCARD_POSITION",
            "estimated_improvement": f"{random.randint(30, 95)}%",
            "applied_at": None,
            "verified": random.choice([True, False]),
        }
        patches.append(patch)

    patches_data = {
        "patches": patches,
        "total": len(patches),
        "by_status": {
            "pending": sum(1 for p in patches if p["status"] == "pending"),
            "confirmed": sum(1 for p in patches if p["status"] == "confirmed"),
            "applied": sum(1 for p in patches if p["status"] == "applied"),
        },
    }

    with open(stage_dir / "patches.json", "w") as f:
        json.dump(patches_data, f, indent=2, ensure_ascii=False)

    patches_dir = stage_dir / "patches"
    patches_dir.mkdir(parents=True, exist_ok=True)

    for patch in patches[:3]:
        patch_file = patches_dir / f"{patch['patch_id']}.xml"
        patch_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<patch>
    <id>{patch["patch_id"]}</id>
    <sql_key>{patch["sql_key"]}</sql_key>
    <original_sql><![CDATA[{patch["original_sql"]}]]></original_sql>
    <optimized_sql><![CDATA[{patch["optimized_sql"]}]]></optimized_sql>
    <optimization_type>{patch["optimization_type"]}</optimization_type>
    <estimated_improvement>{patch["estimated_improvement"]}</estimated_improvement>
</patch>
"""
        with open(patch_file, "w") as f:
            f.write(patch_content)

    overview = f"""# Patch Stage Overview

## 执行摘要
补丁生成完成，共生成 {len(patches)} 个补丁，其中 {patches_data["by_status"]["confirmed"]} 个已确认待应用。

## 关键指标

| 指标 | 数值 |
| ------ | ------ |
| 补丁总数 | {len(patches)} |
| ✅ 已确认 | {patches_data["by_status"]["confirmed"]} |
| ⏳ 待确认 | {patches_data["by_status"]["pending"]} |
| ✅ 已应用 | {patches_data["by_status"]["applied"]} |
| 已验证 | {sum(1 for p in patches if p["verified"])} |

## 补丁状态分布

```
待确认: {patches_data["by_status"]["pending"]} ████░░░░░░ {patches_data["by_status"]["pending"] / len(patches) * 100:.1f}%
已确认: {patches_data["by_status"]["confirmed"]} ████████░░ {patches_data["by_status"]["confirmed"] / len(patches) * 100:.1f}%
已应用: {patches_data["by_status"]["applied"]} ██████░░░░ {patches_data["by_status"]["applied"] / len(patches) * 100:.1f}%
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
| 性能提升 | {len(patches)} |
| 索引变更 | {sum(1 for p in patches if p["optimization_type"] == "INDEX_HINT")} |
| SQL 重写 | {sum(1 for p in patches if p["optimization_type"] in ["QUERY_REWRITE", "WILDCARD_POSITION"])} |
| LIMIT 添加 | {sum(1 for p in patches if p["optimization_type"] == "LIMIT_CLAUSE")} |

## 应用建议

### 🔥 高优先级 (立即应用)
1. PATCH_0001 - 移除前导通配符，预计提升 85%
2. PATCH_0003 - 重写低效查询，预计提升 55%

### ⚠️ 中优先级 (审核后应用)
1. PATCH_0002 - 添加索引提示，需确认索引存在

## 下一步操作

1. **确认补丁**: 检查 `patches/` 目录下的 XML 文件
2. **备份数据**: 应用前建议备份原 Mapper XML
3. **应用补丁**: 使用 `sqlopt-cli apply --run-id {RUN_ID}` 应用

## 详情
- 补丁数据: `patch/patches.json`
- 补丁文件: `patch/patches/*.xml`
- 配置文件: `sqlopt.yml`
"""
    with open(stage_dir / "patch.overview.md", "w") as f:
        f.write(overview)

    return len(patches)


def create_pipeline_summary(
    sql_count, branch_count, risk_count, baseline_count, proposal_count, patch_count
):
    summary = {
        "run_id": RUN_ID,
        "timestamp": datetime.now().isoformat(),
        "mode": "MOCK_RICH_DEMO",
        "config": {
            "db_platform": "postgresql",
            "llm_enabled": False,
            "optimizer_provider": "heuristic",
        },
        "stages": {
            "init": {
                "success": True,
                "sql_units_count": sql_count,
                "dynamic_sql_count": sql_count - 20,
                "cross_file_refs": 15,
            },
            "parse": {
                "success": True,
                "sql_units_count": sql_count,
                "branches_count": branch_count,
                "risks_count": risk_count,
            },
            "recognition": {
                "success": True,
                "baselines_count": baseline_count,
                "slow_queries": 12,
                "high_cost_queries": 8,
            },
            "optimize": {
                "success": True,
                "proposals_count": proposal_count,
                "actionable": proposal_count - 15,
            },
            "patch": {
                "success": True,
                "patches_count": patch_count,
                "confirmed": patch_count - 3,
            },
        },
        "total_time_seconds": 5.67,
    }

    with open(RUN_DIR / "pipeline_summary.json", "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    return summary


def main():
    print(f"Generating rich mock demo data: {RUN_ID}")

    RUN_DIR.mkdir(parents=True, exist_ok=True)

    print("Creating Init stage...")
    sql_count = create_init_stage()

    print("Creating Parse stage...")
    branch_count, risk_count = create_parse_stage(sql_count)

    sql_keys = SQL_KEYS * 2
    baselines = [generate_baseline(sql_keys[i], i) for i in range(sql_count)]

    print("Creating Recognition stage...")
    baseline_count = create_recognition_stage(sql_count, sql_keys)

    print("Creating Optimize stage...")
    proposal_count, actionable_count = create_optimize_stage(
        sql_count, sql_keys, baselines
    )

    print("Creating Patch stage...")
    patch_count = create_patch_stage(proposal_count, actionable_count)

    print("Creating pipeline summary...")
    summary = create_pipeline_summary(
        sql_count, branch_count, risk_count, baseline_count, proposal_count, patch_count
    )

    print(f"\n✅ Rich mock demo data generated: {RUN_ID}")
    print(f"   SQL Units: {sql_count}")
    print(f"   Branches: {branch_count}")
    print(f"   Risks: {risk_count}")
    print(f"   Baselines: {baseline_count}")
    print(f"   Proposals: {proposal_count}")
    print(f"   Patches: {patch_count}")
    print(f"\n   Location: {RUN_DIR}")


if __name__ == "__main__":
    main()
