# 分支对比：Main vs Feature

## 一、概览对比

| 对比项 | Main 分支 | Feature 分支 |
|--------|----------|--------------|
| **最新提交** | 946dc71 | a4e46c8 |
| **提交数领先** | - | 约 70 个提交 |
| **流水线阶段** | 6 阶段 | 7 阶段 (+diagnose) |
| **SQL ID 索引** | ❌ | ✅ |
| **基线采集** | ❌ | ✅ |
| **分支生成** | ❌ | ✅ |
| **DB 配置强制** | ❌ | ✅ |

---

## 二、流水线对比

```mermaid
graph LR
    subgraph Main 分支
        M1[preflight] --> M2[scan] --> M3[optimize] --> M4[validate] --> M5[patch_generate] --> M6[report]
    end
    
    subgraph Feature 分支
        F1[preflight] --> F2[scan] --> F3[diagnose] --> F4[optimize] --> F5[validate] --> F6[patch_generate] --> F7[report]
    end
    
    style F3 fill:#e1f5fe,stroke:#01579b
```

---

## 三、功能对比

### 3.1 诊断能力

| 功能 | Main | Feature |
|------|------|---------|
| diagnose 阶段 | ❌ | ✅ |
| SQL 分支展开 | ❌ | ✅ |
| 基线性能 | ❌ | ✅ |
| 表元数据 | ❌ | ✅ |

### 3.2 SQL ID 索引

| 功能 | Main | Feature |
|------|------|---------|
| SQL ID 索引 | ❌ | ✅ |
| 查找方式 | 顺序 O(n) | 索引 O(1) |

### 3.3 基线系统

| 功能 | Main | Feature |
|------|------|---------|
| 数据生成 | ❌ | ✅ |
| 性能采集 | ❌ | ✅ |
| 类型提取 | ❌ | ✅ |

### 3.4 脚本引擎

| 功能 | Main | Feature |
|------|------|---------|
| 分支上下文 | ❌ | ✅ |
| 分支生成器 | ❌ | ✅ |
| 表达式求值 | ❌ | ✅ |
| 互斥检测 | ❌ | ✅ |

### 3.5 配置校验

| 功能 | Main | Feature |
|------|------|---------|
| DSN 校验 | 宽松 | 严格 (缺失则阻止) |
| 策略显示 | 基础 | 始终显示默认标记 |

### 3.6 命令

| 命令 | Main | Feature |
|------|------|---------|
| baseline | ❌ | ✅ |
| branch | ❌ | ✅ |
| dsn_input | ❌ | ✅ |

---

## 四、数据流对比

### Main 分支数据流

```mermaid
flowchart LR
    Y[sqlopt.yml] --> CS[配置解析]
    CS --> WE[工作流引擎]
    WE --> PIPELINE[流水线]
    
    PIPELINE --> S1[scan.sqlunits]
    PIPELINE --> S2[proposals/]
    PIPELINE --> S3[acceptance/]
    PIPELINE --> S4[patches/]
    PIPELINE --> S5[report.md]
```

### Feature 分支数据流

```mermaid
flowchart LR
    Y[sqlopt.yml] --> CS[配置解析]
    CS --> WE[工作流引擎]
    WE --> PIPELINE[流水线]
    
    PIPELINE --> S1[scan.sqlunits]
    PIPELINE --> SNEW1[branches.jsonl]:::new
    PIPELINE --> S2[proposals/]
    PIPELINE --> S3[acceptance/]
    PIPELINE --> S4[patches/]
    PIPELINE --> SNEW2[baseline/]:::new
    PIPELINE --> SNEW3[diagnosis/]:::new
    PIPELINE --> S5[report.md]
    
    classDef new fill:#e1f5fe,stroke:#01579b
    class SNEW1,SNEW2,SNEW3 new
```

---

## 五、新增文件汇总

| 目录 | 文件数 | 主要功能 |
|------|--------|----------|
| `stages/` | 2 | diagnose, execute |
| `baseline/` | 8 | 基线数据生成与采集 |
| `scripting/` | 11 | 分支生成与脚本引擎 |
| `adapters/` | 3 | 分支适配器 |
| `application/` | 1 | SQL ID 索引器 |
| `commands/` | 3 | 新 CLI 命令 |
| **总计** | **28** | 约 6,658 行代码 |

---

## 六、配置对比

### Main 分支 (精简)

```yaml
config_version: v1
project:
  root_path: .
scan:
  mapper_globs:
    - src/main/resources/**/*.xml
db:
  platform: postgresql
  dsn: postgresql://user:pass@host/db
llm:
  enabled: true
```

### Feature 分支 (增强)

```yaml
config_version: v1
project:
  root_path: .
scan:
  mapper_globs:
    - src/main/resources/**/*.xml
  enable_fragment_catalog: true    # 新增
db:
  platform: postgresql
  dsn: postgresql://user:pass@host/db
llm:
  enabled: true
diagnose:                           # 新增
  enabled: true
  include_baseline: true
  include_branches: true
  include_metadata: true
```

---

## 七、产物对比

| 产物 | Main | Feature |
|------|------|---------|
| `scan.sqlunits.jsonl` | ✅ | ✅ |
| `branches.jsonl` | ❌ | ✅ |
| `scan.fragments.jsonl` | ✅ | ✅ |
| `proposals/` | ✅ | ✅ |
| `acceptance/` | ✅ | ✅ |
| `patches/` | ✅ | ✅ |
| `baseline/` | ❌ | ✅ |
| `diagnosis/` | ❌ | ✅ |
| `report.md` | 基础版 | 增强版 |

---

## 八、结论

**feature/diagnose-report-enhancement** 分支新增了以下重要能力：

1. **新增 diagnose 阶段** - 位于 scan 和 optimize 之间
2. **SQL 分支展开** - 分析所有可能的 SQL 路径
3. **基线性能** - 追踪优化前后的指标
4. **SQL ID 索引** - 更快的查找速度
5. **脚本引擎** - 高级 SQL 操作
6. **DB 强制校验** - 更严格的配置验证

### 适用场景

| 场景 | Main | Feature |
|------|------|---------|
| 基础 SQL 优化 | ✅ | ✅ |
| 复杂 MyBatis 分析 | - | ✅ |
| 性能基线追踪 | - | ✅ |
| 高级诊断场景 | - | ✅ |
| 生产级优化工作流 | - | ✅ |
