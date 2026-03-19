# SQL Optimizer V8 - 7 阶段功能全景图

> 版本：V8 | 更新日期：2026-03-19

---

## 一、Stage 插件架构

V8 架构采用**插件式 Stage 设计**，所有 7 个阶段均通过统一的基础架构实现，便于扩展和维护。

### 1.1 核心组件

| 组件 | 文件 | 说明 |
|------|------|------|
| `Stage` | `python/sqlopt/stages/base.py` | 阶段基类，定义接口契约 |
| `StageContext` | `python/sqlopt/stages/base.py` | 阶段执行上下文，传递运行信息 |
| `StageResult` | `python/sqlopt/stages/base.py` | 阶段执行结果，包含产物和错误 |
| `StageRegistry` | `python/sqlopt/application/stage_registry.py` | 单例注册表，管理所有阶段 |

### 1.2 Stage 接口

所有阶段必须实现以下抽象方法：

```python
class Stage(ABC):
    name: str = "base"           # 阶段名称
    version: str = "1.0.0"       # 阶段版本
    dependencies: list[str] = []  # 依赖阶段列表

    @abstractmethod
    def execute(self, context: StageContext) -> StageResult:
        """执行阶段逻辑"""
        pass

    @abstractmethod
    def get_input_contracts(self) -> list[str]:
        """返回输入契约列表（如 sqlunit_v1, branch_v1）"""
        pass

    @abstractmethod
    def get_output_contracts(self) -> list[str]:
        """返回输出契约列表（如 risk_v1, baseline_v1）"""
        pass
```

### 1.3 可选钩子方法

| 钩子 | 说明 |
|------|------|
| `validate_input` | 验证输入是否有效 |
| `can_process` | 判断是否能处理该 SQL 单元 |
| `on_stage_start` | 阶段开始前调用 |
| `on_stage_end` | 阶段结束后调用 |
| `cleanup` | 清理资源 |

### 1.4 阶段注册

使用 `@stage_registry.register` 装饰器注册阶段：

```python
from sqlopt.application.stage_registry import stage_registry
from sqlopt.stages.base import Stage, StageContext, StageResult

@stage_registry.register
class DiscoveryStage(Stage):
    name: str = "discovery"
    version: str = "1.0.0"
    dependencies: list[str] = []

    def execute(self, context: StageContext) -> StageResult:
        # 实现阶段逻辑
        ...

    def get_input_contracts(self) -> list[str]:
        return []

    def get_output_contracts(self) -> list[str]:
        return ["sqlunit_v1"]
```

### 1.5 获取阶段实例

```python
from sqlopt.application.stage_registry import stage_registry

# 获取阶段实例（懒加载，单例）
stage = stage_registry.get("discovery")

# 列出所有注册的阶段
all_stages = stage_registry.list_stages()
# => ["baseline", "branching", "discovery", "optimize", "patch", "pruning", "validate"]

# 获取阶段依赖
deps = stage_registry.get_dependencies("optimize")
# => ["baseline", "pruning"]
```

### 1.6 已注册的阶段

| 阶段 | 类名 | 说明 |
|------|------|------|
| `discovery` | `DiscoveryStage` | 连接数据库、采集表结构、解析 MyBatis XML |
| `branching` | `BranchingStage` | 展开动态标签生成分支路径（if/choose/foreach） |
| `pruning` | `PruningStage` | 静态分析、风险标记、低价值分支过滤 |
| `baseline` | `BaselineStage` | EXPLAIN 采集执行计划、记录性能基线 |
| `optimize` | `OptimizeStage` | 规则引擎 + LLM 生成优化建议 |
| `validate` | `ValidateStage` | 语义验证、性能对比、结果集校验 |
| `patch` | `PatchStage` | 生成 XML 补丁、用户确认、应用变更 |

---

## 二、7 阶段总体流程

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                         V8 Pipeline                                                              │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                                 │
│  ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐  │
│  │ Discovery │ → │ Branching │ → │  Pruning  │ → │  Baseline │ → │  Optimize │ → │  Validate │ → │   Patch   │  │
│  │   发现    │   │   分支    │   │   剪枝    │   │   基线    │   │   优化    │   │   验证    │   │   补丁    │  │
│  └─────┬─────┘   └─────┬─────┘   └─────┬─────┘   └─────┬─────┘   └─────┬─────┘   └─────┬─────┘   └─────┬─────┘  │
│        │                │                │                │                │                │                │         │
│        ▼                ▼                ▼                ▼                ▼                ▼                ▼         │
│  ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐  │
│  │ DB连接    │   │ 分支生成  │   │ 前缀通配符 │   │ EXPLAIN   │   │ 规则引擎  │   │ 语义验证  │   │ 补丁生成  │  │
│  │ XML解析   │   │ 条件展开  │   │ 后缀通配符 │   │ 性能采集  │   │ LLM优化   │   │ 性能对比  │   │ 用户确认  │  │
│  │ SQL提取   │   │ 风险标记  │   │ 函数包裹   │   │ 表统计    │   │ 候选生成  │   │ 结果集   │   │ 文件备份  │  │
│  │ 表结构采集│   │ 分支裁剪  │   │ SELECT*   │   │ 参数绑定  │   │ 成本估算  │   │ 验证     │   │ 应用补丁  │  │
│  └───────────┘   └───────────┘   └───────────┘   └───────────┘   └───────────┘   └───────────┘   └───────────┘  │
│                                                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、各阶段详细功能

### 阶段 1: Discovery（发现）

**目标**：建立数据库连接、采集表结构、解析 MyBatis XML、提取 SQL 语句

| 功能项 | 描述 |
|--------|------|
| **连接数据库** | 连接目标数据库，获取连接信息，支持 PostgreSQL 和 MySQL |
| **采集表结构** | 获取所有表的列信息、索引、主键、约束 |
| **解析 XML** | 解析 MyBatis Mapper XML 文件，识别动态标签 |
| **提取 SQL** | 提取所有 SELECT/INSERT/UPDATE/DELETE 语句 |
| **识别动态 SQL** | 识别 `<if>`, `<choose>`, `<foreach>`, `<where>`, `<set>` 等动态标签 |
| **构建目录** | 生成 sqlmap_catalog 索引，建立 SQL Key 映射 |

**输入**：
- `sqlopt.yml` 配置文件
- MyBatis Mapper XML 文件（`mapper_globs` 指定路径）

**输出产物**：
- `runs/<run_id>/scan.sqlunits.jsonl` - SQL 单元列表
- `runs/<run_id>/sqlmap_catalog/` - SQL 片段目录

**CLI 命令**：
```bash
sqlopt-cli run --config sqlopt.yml --stage discovery
sqlopt-cli diagnose --config sqlopt.yml
```

---

### 阶段 2: Branching（分支）

**目标**：将动态 SQL 展开为具体执行分支，分析分支路径，标记风险点

| 功能项 | 描述 |
|--------|------|
| **分支生成策略** | 支持三种策略：AllCombinations（全组合）/ Pairwise（成对）/ Boundary（边界值） |
| **条件展开** | 将 `<if test="...">` 条件展开为具体分支 |
| **Choose 展开** | 展开 `<choose><when>...<otherwise>` 分支路径 |
| **Foreach 展开** | 展开 `<foreach>` 循环为多个具体路径 |
| **风险标记** | 标记每个分支的风险点（高危/中危/低危） |
| **分支裁剪** | 根据规则裁剪无效分支，减少冗余路径 |

**输入**：
- `runs/<run_id>/scan.sqlunits.jsonl`

**输出产物**：
- `runs/<run_id>/branches/` - 分支列表目录
  - `<sql_key>.json` - 单个 SQL 的分支数据

**CLI 命令**：
```bash
sqlopt-cli run --config sqlopt.yml --stage branching
sqlopt-cli branch --mapper "src/**/*.xml" --dsn postgresql://...
```

---

### 阶段 3: Pruning（剪枝）

**目标**：静态分析 SQL，检测潜在性能问题，标记高风险模式

| 功能项 | 描述 |
|--------|------|
| **前缀通配符检测** | 检测 `LIKE '%value'` 模式，无法使用索引 |
| **后缀通配符检测** | 检测 `LIKE 'value%'` 模式 |
| **函数包裹检测** | 检测 `WHERE UPPER(col) = ?`、`WHERE YEAR(date) = ?` 等索引失效模式 |
| **SELECT * 检测** | 检测全列查询，建议明确列名 |
| **N+1 检测** | 检测子查询 N+1 模式 |
| **缺失索引提示** | 检测 WHERE 条件中无索引的列 |
| **拼接 SQL 检测** | 检测字符串拼接导致的 SQL 注入风险 |

**风险等级**：

| 风险类型 | 模式 | 风险等级 |
|----------|------|----------|
| `prefix_wildcard` | `LIKE '%value'` | 高 |
| `suffix_wildcard_only` | `LIKE 'value%'` | 低 |
| `concat_wildcard` | `CONCAT('%', name)` | 高 |
| `function_wrap` | `UPPER(col)`, `YEAR(date)` | 中 |
| `select_star` | `SELECT *` | 中 |

**输入**：
- `runs/<run_id>/branches/` - 分支数据

**输出产物**：
- `runs/<run_id>/risks/` - 风险列表目录
  - `<sql_key>.json` - 单个 SQL 的风险数据

**CLI 命令**：
```bash
sqlopt-cli run --config sqlopt.yml --stage pruning
```

---

### 阶段 4: Baseline（基线）

**目标**：采集当前 SQL 的执行计划，建立性能基线

| 功能项 | 描述 |
|--------|------|
| **EXPLAIN 分析** | 执行 `EXPLAIN` 或 `EXPLAIN ANALYZE` 获取执行计划 |
| **性能采集** | 采集执行时间、扫描行数、缓存命中率 |
| **表统计信息** | 采集表统计信息（行数、索引数） |
| **参数绑定** | 绑定实际参数值，模拟真实查询 |
| **执行计划缓存** | 缓存 EXPLAIN 结果，避免重复执行 |

**输入**：
- `runs/<run_id>/branches/` - 分支数据
- 数据库连接

**输出产物**：
- `runs/<run_id>/baseline/` - 性能基线目录
  - `<sql_key>.json` - 单个 SQL 的基线数据

**CLI 命令**：
```bash
sqlopt-cli run --config sqlopt.yml --stage baseline
sqlopt-cli baseline --mapper "src/**/*.xml" --dsn postgresql://...
```

---

### 阶段 5: Optimize（优化）

**目标**：应用优化规则，调用 LLM 生成优化建议

| 功能项 | 描述 |
|--------|------|
| **规则引擎** | 应用内置优化规则（索引建议、重写规则） |
| **LLM 优化** | 调用 LLM（opencode_run）生成智能优化建议 |
| **候选生成** | 生成多个优化候选方案供选择 |
| **成本估算** | 估算优化后的性能提升比例 |
| **优化建议** | 生成具体可执行的 SQL 改写建议 |

**输入**：
- `runs/<run_id>/baseline/` - 性能基线数据
- `runs/<run_id>/risks/` - 风险数据
- LLM 配置

**输出产物**：
- `runs/<run_id>/proposals/` - 优化建议目录
  - `<sql_key>/prompt.json` - 发送给 LLM 的提示
  - `<sql_key>/proposal.json` - LLM 返回的优化建议

**CLI 命令**：
```bash
sqlopt-cli run --config sqlopt.yml --stage optimize
sqlopt-cli optimize --config sqlopt.yml --sql-key <sqlKey>
```

---

### 阶段 6: Validate（验证）

**目标**：验证优化建议的正确性，确保语义等价和性能提升

| 功能项 | 描述 |
|--------|------|
| **语义验证** | 验证优化后 SQL 与原始 SQL 语义等价 |
| **性能对比** | 对比优化前后执行计划，确认性能提升 |
| **结果集验证** | 执行两组 SQL，验证返回结果一致 |
| **回滚计划** | 生成回滚计划，确保可撤销 |
| **验收标准** | 定义验收通过标准（性能提升 > 20%，结果一致） |

**输入**：
- `runs/<run_id>/proposals/` - 优化建议
- `runs/<run_id>/baseline/` - 基线数据

**输出产物**：
- `runs/<run_id>/acceptance/` - 验证结果目录
  - `<sql_key>.json` - 单个 SQL 的验证结果
- `runs/<run_id>/verification/` - 验证证据链目录

**CLI 命令**：
```bash
sqlopt-cli run --config sqlopt.yml --stage validate
sqlopt-cli verify --run-id <run_id> --sql-key <sqlKey>
```

---

### 阶段 7: Patch（补丁）

**目标**：生成补丁文件，应用到 MyBatis XML

| 功能项 | 描述 |
|--------|------|
| **补丁生成** | 生成 MyBatis XML 补丁文件 |
| **用户确认** | 等待用户确认后应用（`require_confirm: true`） |
| **备份原文件** | 自动备份原始 XML 文件 |
| **应用补丁** | 将优化建议应用到 XML 文件 |
| **原子性** | 支持原子性回滚，失败时恢复原文件 |

**输入**：
- `runs/<run_id>/acceptance/` - 验证通过的优化建议
- 原始 MyBatis XML 文件

**输出产物**：
- `runs/<run_id>/patches/` - 补丁文件目录
  - `<sql_key>/patch.xml` - 生成的补丁文件
- `runs/<run_id>/report.json` - JSON 报告
- `runs/<run_id>/report.md` - Markdown 报告
- `runs/<run_id>/report.summary.md` - 摘要报告

**CLI 命令**：
```bash
sqlopt-cli run --config sqlopt.yml --stage patch
sqlopt-cli apply --run-id <run_id>
```

---

## 三、阶段数据流

```
┌────────────┐     ┌────────────┐     ┌────────────┐     ┌────────────┐     ┌────────────┐     ┌────────────┐     ┌────────────┐
│ Discovery  │     │ Branching  │     │  Pruning   │     │  Baseline  │     │  Optimize  │     │  Validate  │     │   Patch   │
└─────┬──────┘     └─────┬──────┘     └─────┬──────┘     └─────┬──────┘     └─────┬──────┘     └─────┬──────┘     └─────┬──────┘
      │                   │                   │                   │                   │                   │                   │
      ▼                   ▼                   ▼                   ▼                   ▼                   ▼                   ▼
┌────────────┐     ┌────────────┐     ┌────────────┐     ┌────────────┐     ┌────────────┐     ┌────────────┐     ┌────────────┐
│  Mapper    │     │  SQL单元   │     │ SQL单元    │     │ SQL单元    │     │ SQL单元    │     │ 优化建议   │     │ 验证结果   │
│  XML文件   │ ──▶ │  +分支     │ ──▶ │ +风险标记  │ ──▶ │ +基线数据  │ ──▶ │ +LLM建议   │ ──▶ │ +性能对比  │ ──▶ │ +补丁文件  │
│  sqlopt.yml│     │            │     │            │     │            │     │            │     │            │     │            │
└────────────┘     └────────────┘     └────────────┘     └────────────┘     └────────────┘     └────────────┘     └────────────┘
```

---

## 四、阶段产物与存储路径映射

```
runs/<run_id>/
│
├── supervisor/                           # 运行状态（所有阶段共用）
│   ├── meta.json                        # 运行元信息
│   ├── state.json                       # 阶段状态
│   └── plan.json                        # SQL 执行计划
│
├── scan.sqlunits.jsonl                   # [阶段1] SQL 单元列表
│
├── sqlmap_catalog/                       # [阶段1] SQL 片段目录
│   ├── index.json                       # 索引文件
│   └── <sql_key>.json                   # 单个 SQL 详情
│
├── branches/                             # [阶段2] 分支数据
│   └── <sql_key>.json                   # 单个 SQL 的分支
│
├── risks/                                # [阶段3] 风险数据
│   └── <sql_key>.json                   # 单个 SQL 的风险
│
├── baseline/                             # [阶段4] 性能基线
│   └── <sql_key>.json                   # 单个 SQL 的基线
│
├── proposals/                            # [阶段5] 优化建议
│   └── <sql_key>/
│       ├── prompt.json                  # LLM 提示词
│       └── proposal.json                # LLM 优化建议
│
├── acceptance/                           # [阶段6] 验证结果
│   └── <sql_key>.json                   # 单个 SQL 的验证结果
│
├── verification/                         # [阶段6] 验证证据链
│   └── <sql_key>.json                   # 验证证据
│
├── patches/                              # [阶段7] 补丁文件
│   └── <sql_key>/
│       └── patch.xml                    # 生成的 XML 补丁
│
├── report.json                           # [阶段7] JSON 报告
├── report.md                             # [阶段7] Markdown 报告
└── report.summary.md                     # [阶段7] 摘要报告
```

---

## 五、CLI 命令与阶段映射

| CLI 命令 | 执行阶段 | 说明 |
|---------|---------|------|
| `sqlopt-cli run --config sqlopt.yml` | 1-7 全部 | 自动执行完整流程 |
| `sqlopt-cli run --config sqlopt.yml --stage <stage>` | 指定阶段 | 只执行特定阶段 |
| `sqlopt-cli diagnose` | 1-3 | 诊断模式（发现+分支+剪枝） |
| `sqlopt-cli branch --mapper <path> --dsn <dsn>` | 2 | 分析 SQL 分支 |
| `sqlopt-cli baseline --mapper <path> --dsn <dsn>` | 4 | 采集性能基线 |
| `sqlopt-cli optimize --config sqlopt.yml [--sql-key <key>]` | 5 | 执行优化 |
| `sqlopt-cli verify --run-id <id> --sql-key <key>` | 6 | 验证特定 SQL |
| `sqlopt-cli apply --run-id <id>` | 7 | 应用补丁 |
| `sqlopt-cli status --run-id <id>` | - | 查看运行状态 |
| `sqlopt-cli resume --run-id <id>` | 断点恢复 | 恢复中断的运行 |

---

## 六、阶段配置

```yaml
config_version: v1

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

*本文档最后更新：2026-03-19*
