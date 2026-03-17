# Feature 分支架构文档

## 一、系统概述

SQL Optimizer 的 **feature/diagnose-report-enhancement** 分支包含约 70 个增强提交 (commit: a4e46c8)。该分支新增了诊断能力、性能基线采集和 SQL 分支分析功能。

---

## 二、功能架构图

```mermaid
graph TB
    subgraph CLI层
        CLI[CLI 入口<br/>sqlopt_cli.py]
    end

    subgraph 应用层
        CS[配置服务<br/>config_service.py]
        RS[运行服务<br/>run_service.py]
        WE[工作流引擎<br/>workflow_engine.py]
        PH[阶段处理器<br/>phase_handlers.py]
        IDX[SQL ID 索引器<br/>sql_id_indexer.py]
    end

    subgraph 核心阶段
        PF[preflight<br/>配置校验]
        SCAN[scan<br/>SQL扫描]
        DIAG[diagnose<br/>诊断分析]:::new
        OPT[optimize<br/>LLM优化]
        VAL[validate<br/>数据库验证]
        PG[patch_generate<br/>补丁生成]
        REP[report<br/>报告生成]
    end

    subgraph 新增子系统
        BG[基线系统<br/>baseline/]
        SE[脚本引擎<br/>scripting/]
        BA[分支适配器<br/>adapters/]
    end

    subgraph 平台层
        SQLP[SQL平台适配]
        LLM[LLM Provider]
    end

    classDef new fill:#e1f5fe,stroke:#01579b
    class DIAG,BG,SE,BA,IDX new

    CLI --> CS
    CS --> RS
    RS --> WE
    WE --> PH
    PH --> PF
    PF --> SCAN
    SCAN --> DIAG
    DIAG --> OPT
    OPT --> VAL
    VAL --> PG
    PG --> REP
    
    DIAG --> BG
    DIAG --> SE
    DIAG --> BA
    
    OPT --> LLM
    VAL --> SQLP
    SCAN --> IDX
```

---

## 三、数据流图

```mermaid
flowchart LR
    subgraph 输入
        YML[sqlopt.yml]
    end

    subgraph 处理流水线
        direction TB
        CS1[配置解析]
        PF[preflight]
        SCAN[scan]
        DIAG[diagnose]:::new
        OPT[optimize]
        VAL[validate]
        PG[patch_generate]
        REP[report]
    end

    subgraph 新增产物
        BRANCH[branches.jsonl]:::new
        BASELINE[baseline/]:::new
        DIAG_RES[diagnosis/]:::new
    end

    subgraph 输出 artifacts
        META[manifest.jsonl]
        SQLUNITS[scan.sqlunits.jsonl]
        PROPOSALS[proposals/]
        ACCEPT[acceptance/]
        PATCHES[patches/]
        REPORT[report.md]
    end

    classDef new fill:#e1f5fe,stroke:#01579b
    class DIAG,BRANCH,BASELINE,DIAG_RES new

    YML --> CS1
    CS1 --> PF
    PF --> SCAN
    SCAN --> DIAG
    DIAG --> BRANCH
    DIAG --> BASELINE
    DIAG --> DIAG_RES
    DIAG --> SQLUNITS
    SQLUNITS --> OPT
    OPT --> PROPOSALS
    PROPOSALS --> VAL
    VAL --> ACCEPT
    ACCEPT --> PG
    PG --> PATCHES
    PATCHES --> REP
    REP --> REPORT
    
    CS1 --> META
```

---

## 四、新增模块说明

### 4.1 诊断阶段 (`python/sqlopt/stages/`)

| 模块 | 功能 |
|------|------|
| `diagnose.py` | 诊断分析，增强报告（分支/基线/元数据）|
| `execute.py` | 执行阶段，运行 SQL |

### 4.2 SQL ID 索引器 (`python/sqlopt/application/`)

| 模块 | 功能 |
|------|------|
| `sql_id_indexer.py` | 快速 SQL ID 查找，O(1) 复杂度 |

### 4.3 基线系统 (`python/sqlopt/baseline/`)

| 模块 | 功能 |
|------|------|
| `data_generator.py` | 生成基线测试数据 |
| `data_sampler.py` | 采样测试数据 |
| `parameter_binder.py` | 绑定参数到 SQL |
| `parameter_parser.py` | 解析 SQL 参数 |
| `performance_collector.py` | 采集性能指标 |
| `reporter.py` | 基线报告生成 |
| `type_extractor.py` | 提取 SQL 类型 |

### 4.4 脚本引擎 (`python/sqlopt/scripting/`)

| 模块 | 功能 |
|------|------|
| `branch_context.py` | 分支执行上下文 |
| `branch_generator.py` | 生成分支 (1459行) |
| `branch_strategy.py` | 分支生成策略 |
| `dynamic_context.py` | 动态 SQL 上下文 |
| `expression_evaluator.py` | 表达式求值 |
| `fragment_registry.py` | 注册 SQL 片段 |
| `mutex_branch_detector.py` | 检测互斥分支 |
| `sql_node.py` | SQL 节点表示 |
| `xml_language_driver.py` | XML 语言驱动 |
| `xml_script_builder.py` | 构建 XML 脚本 |

### 4.5 分支适配器 (`python/sqlopt/adapters/`)

| 模块 | 功能 |
|------|------|
| `branch_diagnose.py` | 分支诊断适配器 |
| `branch_generator.py` | 分支生成适配器 |
| `strategy_selector.py` | 策略选择器 |

### 4.6 新增命令 (`python/sqlopt/commands/`)

| 模块 | 功能 |
|------|------|
| `baseline.py` | 基线命令 |
| `branch.py` | 分支命令 |
| `dsn_input.py` | DSN 输入处理 |

---

## 五、核心增强功能

### 5.1 诊断报告增强

diagnose 阶段为报告新增：
- **SQL 分支展开** - 所有可能的分支组合
- **基线性能数据** - 优化前的性能指标
- **表元数据** - 表和索引信息

### 5.2 SQL ID 快速匹配

- 索引机制实现快速 SQL ID 解析
- 查找时间从 O(n) 降低到 O(1)

### 5.3 DB 配置强制校验

- DSN 未正确配置时阻止执行
- 确保运行前数据库连通性

### 5.4 策略选择稳定性

- 策略选择始终显示默认标记
- 更一致的策略处理

---

## 六、运行产物

```
runs/<run_id>/
├── manifest.jsonl              # 运行清单
├── branches.jsonl              # NEW: SQL分支
├── scan.sqlunits.jsonl        # 扫描的SQL单元
├── scan.fragments.jsonl       # SQL片段目录
├── proposals/
│   └── optimization.proposals.jsonl
├── acceptance/
│   └── acceptance.results.jsonl
├── patches/
│   └── patch.results.jsonl
├── baseline/                  # NEW: 基线数据
├── diagnosis/                 # NEW: 诊断结果
├── supervisor/
│   ├── meta.json
│   ├── plan.json
│   └── state.json
├── report.md                  # 增强报告
├── report.summary.md          # 摘要
└── report.json                # JSON格式报告
```

---

## 七、配置示例

```yaml
config_version: v1
project:
  root_path: .
scan:
  mapper_globs:
    - src/main/resources/**/*.xml
  enable_fragment_catalog: true  # NEW
db:
  platform: postgresql
  dsn: postgresql://user:pass@127.0.0.1:5432/db
llm:
  enabled: true
  provider: opencode_run
diagnose:                      # NEW
  enabled: true
  include_baseline: true
  include_branches: true
  include_metadata: true
```

---

## 八、新增文件统计

| 目录 | 新增文件数 | 总行数 |
|------|-----------|--------|
| `stages/` | 2 | ~550 |
| `baseline/` | 8 | ~836 |
| `scripting/` | 11 | ~3,000 |
| `adapters/` | 3 | ~958 |
| `application/` | 1 | ~227 |
| `commands/` | 3 | ~1,087 |
| **总计** | **28** | **~6,658** |
