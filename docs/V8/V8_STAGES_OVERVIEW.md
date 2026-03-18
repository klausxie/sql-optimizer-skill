# SQL Optimizer V8 - 7 阶段功能全景图

> 版本：V8 | 更新日期：2024-03-18

---

## 一、7 阶段总体流程

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                           7 阶段处理流水线                                           │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐  │
│  │Discovery│──▶│Branching│──▶│ Pruning │──▶│Baseline │──▶│Optimize │──▶│Validate│──▶│  Patch  │  │
│  │  发现   │   │  分支   │   │  剪枝   │   │  基线   │   │  优化   │   │  验证  │   │  补丁   │  │
│  └────┬────┘   └────┬────┘   └────┬────┘   └────┬────┘   └────┬────┘   └────┬────┘   └────┬────┘  │
│       │           │           │           │           │           │           │           │
│       ▼           ▼           ▼           ▼           ▼           ▼           ▼           │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐  │
│  │ DB连接  │   │ 分支生成 │   │ 风险检测 │   │ EXPLAIN │   │  LLM   │   │ DB执行  │   │ 文件   │  │
│  │ XML解析 │   │ 条件展开 │   │ 静态分析 │   │ 性能采集 │   │ 优化建议 │   │ 性能对比 │   │ 补丁   │  │
│  └─────────┘   └─────────┘   └─────────┘   └─────────┘   └─────────┘   └─────────┘   └─────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、各阶段详细功能

### 阶段 1: Discovery（发现）

| 功能项 | 描述 |
|--------|------|
| **连接数据库** | 连接目标数据库，获取连接信息 |
| **采集表结构** | 获取所有表的列信息、索引、主键 |
| **解析 XML** | 解析 MyBatis Mapper XML 文件 |
| **提取 SQL** | 提取所有 SELECT/INSERT/UPDATE/DELETE 语句 |
| **识别动态 SQL** | 识别 `<if>`, `<choose>`, `<foreach>` 等动态标签 |
| **构建目录** | 生成 sqlmap_catalog 索引 |

**输出产物**：
- `sqlunits.jsonl` - SQL 单元列表
- `fragments.jsonl` - SQL 片段目录

---

### 阶段 2: Branching（分支）

| 功能项 | 描述 |
|--------|------|
| **分支生成策略** | 支持三种策略：AllCombinations / Pairwise / Boundary |
| **条件展开** | 将动态 SQL 展开为具体分支 |
| **风险标记** | 标记每个分支的风险点 |
| **分支裁剪** | 根据规则裁剪无效分支 |

**输出产物**：
- `branches.jsonl` - 分支列表

---

### 阶段 3: Pruning（剪枝）

| 功能项 | 描述 |
|--------|------|
| **前缀通配符检测** | 检测 `LIKE '%value'` 模式 |
| **后缀通配符检测** | 检测 `LIKE 'value%'` 模式 |
| **函数包裹检测** | 检测 `WHERE UPPER(col) = ?` |
| **SELECT * 检测** | 检测全列查询 |
| **N+1 检测** | 检测子查询 N+1 模式 |
| **缺失索引提示** | 检测无索引的 WHERE 条件 |

**输出产物**：
- `risks.jsonl` - 风险列表

---

### 阶段 4: Baseline（基线）

| 功能项 | 描述 |
|--------|------|
| **EXPLAIN 分析** | 执行 EXPLAIN 获取执行计划 |
| **性能采集** | 采集执行时间、扫描行数 |
| **统计信息** | 采集表统计信息 |
| **参数绑定** | 绑定实际参数值 |

**输出产物**：
- `baseline.jsonl` - 性能基线数据

---

### 阶段 5: Optimize（优化）

| 功能项 | 描述 |
|--------|------|
| **规则引擎** | 应用内置优化规则 |
| **LLM 优化** | 调用 LLM 生成优化建议 |
| **候选生成** | 生成多个优化候选方案 |
| **成本估算** | 估算优化后的性能提升 |

**输出产物**：
- `proposals/` - 优化建议目录

---

### 阶段 6: Validate（验证）

| 功能项 | 描述 |
|--------|------|
| **语义验证** | 验证优化后 SQL 语义等价 |
| **性能对比** | 对比优化前后性能 |
| **结果集验证** | 验证返回结果一致 |
| **回滚计划** | 生成回滚计划 |

**输出产物**：
- `acceptance.jsonl` - 验证结果

---

### 阶段 7: Patch（补丁）

| 功能项 | 描述 |
|--------|------|
| **补丁生成** | 生成 MyBatis XML 补丁 |
| **用户确认** | 等待用户确认 |
| **备份原文件** | 备份原始 XML |
| **应用补丁** | 将优化建议应用到 XML |

**输出产物**：
- `patches/` - 补丁文件目录

---

## 三、阶段数据流

```
阶段输入/输出：

Discovery          Branching           Pruning            Baseline           Optimize           Validate          Patch
   │                  │                  │                   │                   │                  │                 │
   ▼                  ▼                  ▼                   ▼                   ▼                  ▼                 ▼
┌─────────┐      ┌─────────┐       ┌─────────┐        ┌─────────┐         ┌─────────┐        ┌─────────┐       ┌─────────┐
│Mapper   │ ───▶ │SQL单元  │ ───▶  │SQL单元   │ ───▶  │SQL单元       │ ───▶    │SQL单元      │ ───▶    │优化建议    │ ───▶   │验证结果  │
│XML文件  │      │+分支    │       │+风险标记  │       │+基线数据   │         │+LLM建议    │        │+性能对比  │       │+补丁文件 │
└─────────┘      └─────────┘       └─────────┘        └─────────┘         └─────────┘        └─────────┘       └─────────┘
```

---

## 四、数据存储结构

```
runs/<run_id>/
├── sqlmap_catalog/           # SQL 目录
│   ├── index.json          # 索引文件
│   └── <sql_key>.json     # 单个 SQL 详情
├── branches/               # 分支数据
│   └── <sql_key>.json
├── risks/                  # 风险数据
│   └── <sql_key>.json
├── baseline/               # 基线数据
│   └── <sql_key>.json
├── proposals/              # 优化建议
│   └── <sql_key>/
│       ├── prompt.json
│       └── proposal.json
├── acceptance/            # 验证结果
│   └── <sql_key>.json
├── patches/               # 补丁文件
│   └── <sql_key>/
│       └── patch.xml
└── supervisor/            # 运行状态
    ├── meta.json
    ├── state.json
    └── plan.json
```

---

## 五、配置说明

### 5.1 阶段配置

```yaml
stages:
  discovery:
    enabled: true
    cache_schema: true
    
  branching:
    strategy: all_combinations  # all_combinations | pairwise | boundary
    max_branches: 100
    
  pruning:
    risk_threshold: medium  # high | medium | low
    
  baseline:
    timeout_ms: 5000
    sample_size: 100
    
  optimize:
    llm_provider: opencode_run
    max_candidates: 3
    
  validate:
    verify_semantics: true
    verify_performance: true
    
  patch:
    auto_backup: true
    require_confirm: true
```

---

## 六、CLI 命令与阶段映射

| CLI 命令 | 执行阶段 |
|---------|---------|
| `sqlopt-cli run` | 1-6 全部自动执行 |
| `sqlopt-cli diagnose` | 只执行阶段 1-3 |
| `sqlopt-cli optimize` | 只执行阶段 5 |
| `sqlopt-cli validate` | 只执行阶段 6 |
| `sqlopt-cli apply` | 只执行阶段 7 |

---

*本文档最后更新：2024-03-18*
