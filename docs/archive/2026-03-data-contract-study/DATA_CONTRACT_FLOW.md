# SQL Optimizer 数据契约与数据流文档

> 生成时间: 2026-03-26
> 状态: 进行中

---

## 目录

1. [整体数据流视图](#1-整体数据流视图)
2. [Stage 1: Init（初始化阶段）](#2-stage-1-init初始化阶段)
3. [Stage 2: Parse（解析阶段）](#3-stage-2-parse解析阶段)
4. [Stage 3: Recognition（基线识别阶段）](#4-stage-3-recognition基线识别阶段)
5. [Stage 4: Optimize（优化阶段）](#5-stage-4-optimize优化阶段)
6. [Stage 5: Result（结果阶段）](#6-stage-5-result结果阶段)
7. [契约依赖汇总表](#7-契约依赖汇总表)
8. [问题与改进建议](#8-问题与改进建议)

---

## 1. 整体数据流视图

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                      MyBatis XML Mapper Files                               │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
                                             │
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│  Stage 1: Init                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ 输入: MyBatis XML Files                                                             │ │
│  │ 处理: 扫描、解析、提取 SQL 单元                                                     │ │
│  │ 输出: InitOutput                                                                    │ │
│  └─────────────────────────────────────────────────────────────────────────────────────┘ │
│  依赖: 无                                                                              │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
                                             │
                        ┌─────────────────────┬─────────────────────┐
                        │                     │                     │
                        ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│  Stage 2: Parse                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ 输入: InitOutput (sql_units)                                                        │ │
│  │ 处理: 展开动态标签(if/include/foreach)，生成执行分支                                │ │
│  │ 输出: ParseOutput                                                                  │ │
│  └─────────────────────────────────────────────────────────────────────────────────────┘ │
│  依赖: Stage 1 的 sql_units                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
                                             │
                        ┌─────────────────────┬─────────────────────┐
                        │                     │                     │
                        ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│  Stage 3: Recognition                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ 输入: ParseOutput + TableSchema                                                     │ │
│  │ 处理: 采集 EXPLAIN 计划，生成性能基线                                               │ │
│  │ 输出: RecognitionOutput                                                            │ │
│  └─────────────────────────────────────────────────────────────────────────────────────┘ │
│  依赖: Stage 2 的 sql_units_with_branches + Stage 1 的 table_schemas                      │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
                                             │
                        ┌─────────────────────┬─────────────────────┐
                        │                     │                     │
                        ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│  Stage 4: Optimize                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ 输入: ParseOutput + RecognitionOutput                                               │ │
│  │ 处理: 基于规则 + LLM 生成优化建议                                                   │ │
│  │ 输出: OptimizeOutput                                                                │ │
│  └─────────────────────────────────────────────────────────────────────────────────────┘ │
│  依赖: Stage 2 的 sql_units_with_branches + Stage 3 的 baselines                         │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
                                             │
                        ┌─────────────────────┬─────────────────────┐
                        │                     │                     │
                        ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│  Stage 5: Result                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ 输入: OptimizeOutput + InitOutput + RecognitionOutput                                │ │
│  │ 处理: 生成优化报告和 XML 补丁                                                       │ │
│  │ 输出: ResultOutput                                                                 │ │
│  └─────────────────────────────────────────────────────────────────────────────────────┘ │
│  依赖: Stage 4 的 proposals + Stage 1 的 sql_units + Stage 3 的 baselines                  │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
                                             │
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                      优化报告 + XML 补丁                                   │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Stage 1: Init（初始化阶段）

### 2.1 阶段概述

| 属性 | 值 |
|------|-----|
| 阶段名称 | Init |
| 功能 | 扫描 MyBatis XML 文件，提取 SQL 单元和表结构 |
| 输入 | MyBatis Mapper XML 文件 |
| 输出 | InitOutput |

### 2.2 输入数据

**来源**: 用户配置的 `scan_mapper_globs` 指定的 XML 文件

### 2.3 输出文件

| 文件路径 | 契约类型 | 大小(典型) | 说明 |
|----------|----------|-----------|------|
| `runs/{run_id}/init/sql_units.json` | `List[SQLUnit]` | 143KB | SQL 单元列表 |
| `runs/{run_id}/init/sql_fragments.json` | `List[SQLFragment]` | 6.6KB | SQL 片段列表 |
| `runs/{run_id}/init/table_schemas.json` | `Dict[str, TableSchema]` | 2.2KB | 表结构信息 |
| `runs/{run_id}/init/xml_mappings.json` | `XMLMapping` | 66KB | XML 文件映射 |
| `runs/{run_id}/init/field_distributions.json` | `List[FieldDistribution]` | 1.2KB | 字段分布 |

### 2.4 契约定义

#### SQLUnit
```python
@dataclass
class SQLUnit:
    id: str                    # 唯一标识符，格式: "{mapper_path}.{sql_id}"
    mapper_file: str           # 源 XML 文件路径
    sql_id: str                # XML statement 的 id 属性
    sql_text: str              # 保留 MyBatis 标签的原始 SQL
    statement_type: str        # SELECT | INSERT | UPDATE | DELETE
```

#### SQLFragment
```python
@dataclass
class SQLFragment:
    fragmentId: str           # 片段 ID (camelCase - 待统一)
    xmlPath: str              # 所在文件路径
    startLine: int           # 开始行号
    endLine: int             # 结束行号
    xmlContent: str          # 片段内容
```

#### TableSchema
```python
@dataclass
class TableSchema:
    columns: List[Dict]       # [{name, type, nullable, default, ...}]
    indexes: List[Dict]       # 索引信息
    statistics: Dict          # 统计信息 (行数等)
```

#### FieldDistribution
```python
@dataclass
class FieldDistribution:
    table_name: str           # 表名
    column_name: str          # 列名
    distinct_count: int       # 不同值数量
    null_count: int           # NULL 数量
    top_values: List[Dict]   # 热门值
    min_value: Optional[str]
    max_value: Optional[str]
```

#### InitOutput
```python
@dataclass
class InitOutput:
    sql_units: List[SQLUnit]                    # SQL 单元列表
    run_id: str                               # 运行 ID
    timestamp: str                             # 时间戳
    sql_fragments: List[SQLFragment]          # SQL 片段列表
    table_schemas: Dict[str, TableSchema]     # 表结构字典
    xml_mappings: Optional[XMLMapping]         # XML 映射
```

### 2.5 阶段依赖

```
Init 阶段
├── 依赖: 无
└── 被依赖: Stage 2 (Parse), Stage 3 (Recognition), Stage 5 (Result)
```

---

## 3. Stage 2: Parse（解析阶段）

### 3.1 阶段概述

| 属性 | 值 |
|------|-----|
| 阶段名称 | Parse |
| 功能 | 展开动态 SQL 标签(if/include/foreach)，生成执行分支 |
| 输入 | InitOutput |
| 输出 | ParseOutput |

### 3.2 输入数据

| 来源 | 契约 | 字段 |
|------|------|------|
| Stage 1 | `InitOutput.sql_units` | SQL 单元列表 |
| Stage 1 | `InitOutput.sql_fragments` | SQL 片段（用于 include 解析） |
| Stage 1 | `InitOutput.table_schemas` | 表结构（用于风险评估） |

### 3.3 输出文件

| 文件路径 | 契约类型 | 大小(典型) | 说明 |
|----------|----------|-----------|------|
| `runs/{run_id}/parse/sql_units_with_branches.json` | `ParseOutput` | 313KB | 向后兼容单文件 |
| `runs/{run_id}/parse/units/{unit_id}.json` | `SQLUnitWithBranches` | - | Per-unit 文件 |
| `runs/{run_id}/parse/units/_index.json` | `List[str]` | 4.5KB | Unit ID 列表 |

### 3.4 契约定义

#### SQLBranch
```python
@dataclass
class SQLBranch:
    path_id: str                    # 分支路径 ID (如 "branch_0")
    condition: Optional[str]        # 触发条件 (如 "status == 'active'")
    expanded_sql: str               # 展开后的完整 SQL
    is_valid: bool                 # SQL 是否语法有效
    risk_flags: list[str]          # 风险标记 (NO_INDEX, FULL_SCAN, ...)
    active_conditions: list[str]   # 激活的条件列表
    risk_score: Optional[float]    # 风险评分 0.0-1.0
    score_reasons: list[str]       # 评分原因
    branch_type: Optional[str]      # 分支类型: "baseline_only" | "full_analysis"
```

**branch_type 说明**:
- `"baseline_only"`: 无激活条件，跳过 EXPLAIN
- `"full_analysis"`: 需要完整分析，执行 EXPLAIN

#### SQLUnitWithBranches
```python
@dataclass
class SQLUnitWithBranches:
    sql_unit_id: str                # 引用 InitOutput.SQLUnit.id
    branches: List[SQLBranch]       # 该单元的所有分支
```

#### ParseOutput
```python
@dataclass
class ParseOutput:
    sql_units_with_branches: List[SQLUnitWithBranches]
```

### 3.5 阶段依赖

```
Parse 阶段
├── 依赖: Stage 1 (InitOutput.sql_units, sql_fragments, table_schemas)
└── 被依赖: Stage 3 (Recognition), Stage 4 (Optimize)
```

---

## 4. Stage 3: Recognition（基线识别阶段）

### 4.1 阶段概述

| 属性 | 值 |
|------|-----|
| 阶段名称 | Recognition |
| 功能 | 采集 SQL 执行计划，生成性能基线 |
| 输入 | ParseOutput + TableSchema |
| 输出 | RecognitionOutput |

### 4.2 输入数据

| 来源 | 契约 | 字段 |
|------|------|------|
| Stage 2 | `ParseOutput.sql_units_with_branches` | SQL 单元及分支 |
| Stage 1 | `TableSchema` (via table_schemas.json) | 表结构信息 |

### 4.3 输出文件

| 文件路径 | 契约类型 | 大小(典型) | 说明 |
|----------|----------|-----------|------|
| `runs/{run_id}/recognition/baselines.json` | `RecognitionOutput` | 251KB | 向后兼容单文件 |
| `runs/{run_id}/recognition/units/{unit_id}.json` | `PerformanceBaseline` | - | Per-unit 文件 |
| `runs/{run_id}/recognition/units/_index.json` | `List[str]` | 4.5KB | Unit ID 列表 |

### 4.4 契约定义

#### PerformanceBaseline
```python
@dataclass
class PerformanceBaseline:
    sql_unit_id: str                    # 引用 SQLUnit.id
    path_id: str                       # 引用 SQLBranch.path_id
    plan: Optional[dict]                # EXPLAIN 执行计划
    estimated_cost: float               # 估计执行成本
    actual_time_ms: Optional[float]     # 实际执行时间
    branch_type: Optional[str]          # 分支类型
    # ⚠️ 待添加: original_sql: str     # 原始 SQL (用于 Optimize 回溯)
```

**问题**: 当前 `PerformanceBaseline` 缺少 `original_sql` 字段，Optimize 阶段需要回查 Parse 输出。

#### RecognitionOutput
```python
@dataclass
class RecognitionOutput:
    baselines: List[PerformanceBaseline]
```

### 4.5 阶段依赖

```
Recognition 阶段
├── 依赖: 
│   ├── Stage 2 (ParseOutput.sql_units_with_branches)
│   └── Stage 1 (table_schemas.json)
└── 被依赖: Stage 4 (Optimize), Stage 5 (Result)
```

---

## 5. Stage 4: Optimize（优化阶段）

### 5.1 阶段概述

| 属性 | 值 |
|------|-----|
| 阶段名称 | Optimize |
| 功能 | 基于规则 + LLM 生成 SQL 优化建议 |
| 输入 | ParseOutput + RecognitionOutput |
| 输出 | OptimizeOutput |

### 5.2 输入数据

| 来源 | 契约 | 字段 |
|------|------|------|
| Stage 2 | `ParseOutput.sql_units_with_branches` | SQL 单元及分支（用于获取原始 SQL） |
| Stage 3 | `RecognitionOutput.baselines` | 性能基线 |

### 5.3 输出文件

| 文件路径 | 契约类型 | 大小(典型) | 说明 |
|----------|----------|-----------|------|
| `runs/{run_id}/optimize/proposals.json` | `OptimizeOutput` | 41KB | 向后兼容单文件 |
| `runs/{run_id}/optimize/units/{unit_id}.json` | `OptimizationProposal` | - | Per-unit 文件 |
| `runs/{run_id}/optimize/units/_index.json` | `List[str]` | - | Unit ID 列表 |

### 5.4 契约定义

#### OptimizationProposal
```python
@dataclass
class OptimizationProposal:
    sql_unit_id: str               # 引用 SQLUnit.id
    path_id: str                   # 引用 SQLBranch.path_id
    original_sql: str               # 原始 SQL
    optimized_sql: str              # 优化后 SQL
    rationale: str                   # 优化理由
    confidence: float               # 置信度 0.0-1.0
```

#### OptimizeOutput
```python
@dataclass
class OptimizeOutput:
    proposals: List[OptimizationProposal]
```

### 5.5 阶段依赖

```
Optimize 阶段
├── 依赖: 
│   ├── Stage 2 (ParseOutput.sql_units_with_branches)
│   └── Stage 3 (RecognitionOutput.baselines)
└── 被依赖: Stage 5 (Result)
```

---

## 6. Stage 5: Result（结果阶段）

### 6.1 阶段概述

| 属性 | 值 |
|------|-----|
| 阶段名称 | Result |
| 功能 | 生成优化报告和 XML 补丁 |
| 输入 | OptimizeOutput + InitOutput + RecognitionOutput |
| 输出 | ResultOutput |

### 6.2 输入数据

| 来源 | 契约 | 字段 |
|------|------|------|
| Stage 4 | `OptimizeOutput.proposals` | 优化建议列表 |
| Stage 1 | `InitOutput.sql_units` | SQL 单元列表 |
| Stage 1 | `InitOutput.xml_mappings` | XML 映射（用于生成补丁） |
| Stage 3 | `RecognitionOutput.baselines` | 性能基线（用于风险分析） |

### 6.3 输出文件

| 文件路径 | 契约类型 | 大小(典型) | 说明 |
|----------|----------|-----------|------|
| `runs/{run_id}/result/report.json` | `ResultOutput` | 154KB | 最终报告 |

### 6.4 契约定义

#### Report
```python
@dataclass
class Report:
    summary: str                    # 简要总结
    details: str                   # 详细说明
    risks: List[str]                # 识别的风险
    recommendations: List[str]      # 优化建议
```

#### Patch
```python
@dataclass
class Patch:
    sql_unit_id: str               # 要打补丁的 SQL 单元
    original_xml: str               # 原始 XML 内容
    patched_xml: str               # 打补丁后 XML
    diff: str                      # unified diff 格式
```

#### ResultOutput
```python
@dataclass
class ResultOutput:
    can_patch: bool               # 是否可以安全打补丁
    report: Report                # 优化报告
    patches: List[Patch]          # 要应用的补丁列表
```

### 6.5 阶段依赖

```
Result 阶段
├── 依赖: 
│   ├── Stage 4 (OptimizeOutput.proposals)
│   ├── Stage 1 (InitOutput.sql_units, xml_mappings)
│   └── Stage 3 (RecognitionOutput.baselines)
└── 被依赖: 无
```

---

## 7. 契约依赖汇总表

### 7.1 阶段依赖矩阵

| 阶段 | 依赖阶段 | 依赖数据 |
|------|----------|----------|
| **Init** | 无 | 无 |
| **Parse** | Init | `sql_units`, `sql_fragments`, `table_schemas` |
| **Recognition** | Parse, Init | `sql_units_with_branches`, `table_schemas` |
| **Optimize** | Parse, Recognition | `sql_units_with_branches`, `baselines` |
| **Result** | Init, Parse, Recognition, Optimize | `sql_units`, `xml_mappings`, `baselines`, `proposals` |

### 7.2 文件依赖矩阵

| 输出文件 | Init | Parse | Recognition | Optimize | Result |
|----------|------|-------|-------------|---------|--------|
| `sql_units.json` | ✅ 写 | ✅ 读 | | | ✅ 读 |
| `sql_fragments.json` | ✅ 写 | ✅ 读 | | | |
| `table_schemas.json` | ✅ 写 | ✅ 读 | ✅ 读 | | |
| `xml_mappings.json` | ✅ 写 | | | | ✅ 读 |
| `field_distributions.json` | ✅ 写 | | | | |
| `sql_units_with_branches.json` | | ✅ 写 | ✅ 读 | ✅ 读 | |
| `baselines.json` | | | ✅ 写 | ✅ 读 | ✅ 读 |
| `proposals.json` | | | | ✅ 写 | ✅ 读 |
| `report.json` | | | | | ✅ 写 |

### 7.3 契约字段传递图

```
Init.sql_units[SQLUnit]
    │
    ├── sql_unit.id ──────────────────────────────► Recognition.baseline.sql_unit_id
    │                                               │
    │                                               ▼
    ├── sql_unit.sql_text ──► Parse ──► branches[SQLBranch].expanded_sql
    │                                               │
    │                                               ▼
    │                                           Optimize ──► proposals[OptimizationProposal].original_sql
    │                                               │
    │                                               ▼
    │                                           Result ──► patches[Patch].original_xml
    │
    └── sql_unit.mapper_file ──► Init.xml_mappings ──► Result.patches[Patch].original_xml
```

---

## 8. 问题与改进建议

### 8.1 高优先级问题

#### 问题 1: Recognition 缺少原始 SQL 字段

| 项目 | 说明 |
|------|------|
| 问题 | `PerformanceBaseline` 没有存储 `original_sql`，Optimize 阶段需要回查 Parse 输出 |
| 影响 | 数据冗余，依赖关系不清晰 |
| 修复 | 在 `PerformanceBaseline` 添加 `original_sql: str` 字段 |

#### 问题 2: 命名风格不统一

| 项目 | 说明 |
|------|------|
| 问题 | `fragmentId` (camelCase) vs `sql_unit_id` (snake_case) 混用 |
| 影响 | 代码风格不一致，容易混淆 |
| 修复 | 统一迁移到 snake_case |

### 8.2 中优先级问题

#### 问题 3: RiskOutput 未使用

| 项目 | 说明 |
|------|------|
| 问题 | `parse.py` 定义了 `Risk` 和 `RiskOutput`，但没有阶段使用 |
| 影响 | 无用代码增加维护负担 |
| 修复 | 删除或移到 Result 阶段使用 |

### 8.3 低优先级问题

#### 问题 4: Patch 缺少版本信息

| 项目 | 说明 |
|------|------|
| 问题 | `Patch` 没有版本字段，原文件变更后可能不一致 |
| 修复 | 添加 `version` 和 `created_at` 字段 |

---

## 附录: 契约版本历史

| 版本 | 日期 | 修改内容 |
|------|------|----------|
| v1.0 | 2026-03-26 | 初始版本，包含 5 个阶段的契约定义 |
