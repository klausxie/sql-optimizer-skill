# Main 分支架构文档

## 一、系统概述

SQL Optimizer 是一个基于 Python 的 MyBatis SQL 优化工具，通过 LLM 生成优化建议，验证后生成 XML 补丁。

**当前分支**: main (commit: 946dc71)

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
    end

    subgraph 核心阶段
        PF[preflight<br/>配置校验]
        SCAN[scan<br/>SQL扫描]
        OPT[optimize<br/>LLM优化]
        VAL[validate<br/>数据库验证]
        PG[patch_generate<br/>补丁生成]
        REP[report<br/>报告生成]
    end

    subgraph 平台层
        SQLP[SQL平台适配]
        LLM[LLM Provider]
    end

    CLI --> CS
    CS --> RS
    RS --> WE
    WE --> PH
    PH --> PF
    PF --> SCAN
    SCAN --> OPT
    OPT --> VAL
    VAL --> PG
    PG --> REP
    
    OPT --> LLM
    VAL --> SQLP
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
        OPT[optimize]
        VAL[validate]
        PG[patch_generate]
        REP[report]
    end

    subgraph 输出 artifacts
        META[manifest.jsonl]
        SQLUNITS[scan.sqlunits.jsonl]
        PROPOSALS[proposals/]
        ACCEPT[acceptance/]
        PATCHES[patches/]
        REPORT[report.md]
    end

    YML --> CS1
    CS1 --> PF
    PF --> SCAN
    SCAN --> SQLUNITS
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

## 四、核心模块说明

### 4.1 应用层 (`python/sqlopt/application/`)

| 模块 | 功能 |
|------|------|
| `config_service.py` | 配置加载与校验 |
| `run_service.py` | 运行生命周期管理 |
| `workflow_engine.py` | 核心工作流编排 |
| `phase_handlers.py` | 阶段转换处理 |
| `status_resolver.py` | 状态解析逻辑 |

### 4.2 阶段层 (`python/sqlopt/stages/`)

| 阶段 | 输入 | 输出 | 功能 |
|------|------|------|------|
| preflight | sqlopt.yml | - | 配置校验、策略选择 |
| scan | mapper.xml | scan.sqlunits.jsonl | 提取SQL |
| optimize | sqlunits | proposals/ | LLM生成优化建议 |
| validate | proposals | acceptance/ | EXPLAIN验证 |
| patch_generate | acceptance | patches/ | 生成XML补丁 |
| report | all artifacts | report.md | 聚合报告 |

### 4.3 平台层 (`python/sqlopt/platforms/`)

- SQL 平台抽象（PostgreSQL / MySQL）
- 规则优化逻辑

---

## 五、运行产物

```
runs/<run_id>/
├── manifest.jsonl              # 运行清单
├── scan.sqlunits.jsonl        # 扫描的SQL单元
├── scan.fragments.jsonl       # SQL片段目录
├── proposals/
│   └── optimization.proposals.jsonl
├── acceptance/
│   └── acceptance.results.jsonl
├── patches/
│   └── patch.results.jsonl
├── supervisor/
│   ├── meta.json
│   ├── plan.json
│   └── state.json
├── report.md                  # 优化报告
├── report.summary.md          # 摘要
└── report.json                # JSON格式报告
```

---

## 六、配置示例

```yaml
config_version: v1
project:
  root_path: .
scan:
  mapper_globs:
    - src/main/resources/**/*.xml
db:
  platform: postgresql
  dsn: postgresql://user:pass@127.0.0.1:5432/db
llm:
  enabled: true
  provider: opencode_run
```

---

## 七、依赖

- Python 3.10+
- PostgreSQL / MySQL 数据库
- LLM Provider (OpenAI 兼容)
- Java 扫描器 (XML 解析)
