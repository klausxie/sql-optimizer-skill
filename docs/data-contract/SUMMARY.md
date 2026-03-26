# 数据契约与数据流汇总

> 生成时间: 2026-03-26

---

## 一、整体架构

```
MyBatis XML ──► Init ──► Parse ──► Recognition ──► Optimize ──► Result ──► 报告+补丁
                  │        │           │             │           │
                  └────────┴───────────┴─────────────┴───────────┘
                              依赖关系如箭头所示
```

---

## 二、五阶段快速概览

| 阶段 | 名称 | 输入 | 输出 | 核心功能 |
|------|------|------|------|----------|
| **1** | Init | MyBatis XML | sql_units, table_schemas | 扫描解析 |
| **2** | Parse | sql_units | sql_units_with_branches | 展开动态SQL |
| **3** | Recognition | branches + schemas | baselines | 采集EXPLAIN |
| **4** | Optimize | branches + baselines | proposals | LLM优化建议 |
| **5** | Result | proposals + sql_units | report + patches | 生成报告 |

---

## 三、数据依赖详情

### Stage 1: Init（无依赖）

**输入**: MyBatis XML Files

**输出文件**:
- `sql_units.json` - SQL单元列表
- `sql_fragments.json` - SQL片段
- `table_schemas.json` - 表结构
- `xml_mappings.json` - XML映射
- `field_distributions.json` - 字段分布

---

### Stage 2: Parse（依赖 Init）

**输入**:
- `InitOutput.sql_units`
- `InitOutput.sql_fragments`
- `InitOutput.table_schemas`

**输出文件**:
- `sql_units_with_branches.json` - 单文件
- `units/*.json` - Per-unit文件
- `units/_index.json` - 索引

---

### Stage 3: Recognition（依赖 Parse + Init）

**输入**:
- `ParseOutput.sql_units_with_branches` (分支详情)
- `InitOutput.table_schemas` (表结构)

**输出文件**:
- `baselines.json` - 单文件
- `units/*.json` - Per-unit文件
- `units/_index.json` - 索引

**⚠️ 注意**: 当前没有存储原始SQL，需要回查Parse输出

---

### Stage 4: Optimize（依赖 Parse + Recognition）

**输入**:
- `ParseOutput.sql_units_with_branches` (原始SQL)
- `RecognitionOutput.baselines` (性能基线)

**输出文件**:
- `proposals.json` - 单文件
- `units/*.json` - Per-unit文件
- `units/_index.json` - 索引

---

### Stage 5: Result（依赖 Init + Parse + Recognition + Optimize）

**输入**:
- `OptimizeOutput.proposals` (优化建议)
- `InitOutput.sql_units` (SQL单元)
- `InitOutput.xml_mappings` (XML映射)
- `RecognitionOutput.baselines` (性能基线)

**输出文件**:
- `report.json` - 最终报告

---

## 四、契约字段汇总

### 4.1 InitOutput (Stage 1 → others)

```python
sql_units: List[SQLUnit]                    # Stage 2, 3, 5 依赖
sql_fragments: List[SQLFragment]            # Stage 2 依赖
table_schemas: Dict[str, TableSchema]        # Stage 2, 3 依赖
xml_mappings: Optional[XMLMapping]           # Stage 5 依赖
```

### 4.2 ParseOutput (Stage 2 → others)

```python
sql_units_with_branches: List[SQLUnitWithBranches]
    └── branches: List[SQLBranch]
            ├── path_id
            ├── expanded_sql          # Stage 3, 4, 5 依赖
            ├── is_valid
            ├── risk_flags
            └── branch_type
```

### 4.3 RecognitionOutput (Stage 3 → others)

```python
baselines: List[PerformanceBaseline]
    ├── sql_unit_id
    ├── path_id
    ├── plan                       # Stage 5 依赖（风险分析）
    ├── estimated_cost
    └── branch_type
    # ⚠️ 缺少: original_sql
```

### 4.4 OptimizeOutput (Stage 4 → others)

```python
proposals: List[OptimizationProposal]
    ├── sql_unit_id
    ├── path_id
    ├── original_sql             # Stage 5 依赖
    ├── optimized_sql             # Stage 5 依赖
    ├── rationale
    └── confidence
```

### 4.5 ResultOutput (Stage 5 输出)

```python
can_patch: bool
report: Report
    ├── summary
    ├── details
    ├── risks
    └── recommendations
patches: List[Patch]
    ├── sql_unit_id
    ├── original_xml              # 从 InitOutput.sql_units 获取
    ├── patched_xml
    └── diff
```

---

## 五、关键问题

### 问题 1: Recognition 缺少 original_sql

**现状**: `PerformanceBaseline` 没有 `original_sql`，Optimize 需要回查 Parse

**影响**: 
- 数据冗余
- 如果 Parse 输出变化，Optimize 的 lookup 会过期

**建议**: 在 `PerformanceBaseline` 添加 `original_sql: str` 字段

### 问题 2: 命名风格不统一

**现状**: 部分使用 camelCase (`fragmentId`)，部分使用 snake_case (`sql_unit_id`)

**建议**: 统一迁移到 snake_case

### 问题 3: RiskOutput 未使用

**现状**: `parse.py` 定义了 `RiskOutput`，但没有任何阶段使用

**建议**: 删除或移到 Result 阶段

---

## 六、契约版本

| 字段 | 类型 | 说明 | 使用阶段 |
|------|------|------|----------|
| `sql_unit.id` | str | 唯一标识 | 2,3,4,5 |
| `sql_unit.sql_text` | str | 原始SQL | 2 |
| `branch.expanded_sql` | str | 展开后SQL | 3,4 |
| `branch.branch_type` | str | baseline_only/full_analysis | 3 |
| `baseline.plan` | dict | EXPLAIN计划 | 5 |
| `baseline.estimated_cost` | float | 估计成本 | - |
| `proposal.original_sql` | str | 原始SQL | 5 |
| `proposal.optimized_sql` | str | 优化后SQL | 5 |
| `patch.original_xml` | str | 原始XML | - |
| `patch.patched_xml` | str | 补丁XML | - |

---

## 七、文件输出路径对照

```
runs/{run_id}/
├── init/
│   ├── sql_units.json
│   ├── sql_fragments.json
│   ├── table_schemas.json
│   ├── xml_mappings.json
│   └── field_distributions.json
├── parse/
│   ├── sql_units_with_branches.json     # 向后兼容
│   └── units/                           # Per-unit 格式
│       ├── _index.json
│       └── {unit_id}.json
├── recognition/
│   ├── baselines.json                   # 向后兼容
│   └── units/                           # Per-unit 格式
│       ├── _index.json
│       └── {unit_id}.json
├── optimize/
│   ├── proposals.json                   # 向后兼容
│   └── units/                           # Per-unit 格式
│       ├── _index.json
│       └── {unit_id}.json
└── result/
    └── report.json
```
