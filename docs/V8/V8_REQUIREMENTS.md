# SQL Optimizer 需求设计文档 V8

> 版本：V8 | 更新日期：2024-03-18

---

## 一、产品定位

SQL Optimizer 是一个面向 MyBatis 项目的 SQL 分析与优化工具，通过自动化流程发现性能问题并生成优化建议。

**目标用户**：后端工程师、DBA

**核心价值**：自动化 SQL 性能诊断与优化建议生成

---

## 二、用户场景

### 场景 1：日常巡检
工程师定期对项目进行 SQL 性能巡检，发现潜在风险。

### 场景 2：上线前检查
新功能上线前，检查新增 SQL 是否有性能问题。

### 场景 3：性能优化
针对已知的慢 SQL 进行深度分析和优化。

### 场景 4：数据库迁移
在数据库平台迁移（如 MySQL → PostgreSQL）时，评估 SQL 兼容性。

---

## 三、功能需求

### 3.1 核心功能

| 功能 | 描述 | 优先级 |
|------|------|--------|
| **SQL 扫描** | 扫描 MyBatis XML 文件，提取 SQL 模板 | P0 |
| **分支推断** | 解析动态 SQL，生成可执行分支 | P0 |
| **风险检测** | 静态分析，标记风险类型和等级 | P0 |
| **性能基线** | 执行 SQL，采集性能数据 | P0 |
| **优化建议** | 规则引擎 + LLM 生成优化建议 | P0 |
| **语义验证** | 验证优化前后语义等价 | P0 |
| **补丁生成** | 生成可应用的 XML 补丁 | P1 |

### 3.2 分支生成策略

| 策略 | 描述 | 适用场景 |
|------|------|----------|
| **all_combinations** | 所有条件组合 | 简单条件 |
| **pairwise** | 成对组合 | 条件较多 |
| **boundary** | 边界值组合 | 数值/日期范围 |

### 3.3 风险类型

| 风险类型 | 描述 | 等级 |
|----------|------|------|
| prefix_wildcard | 前导通配符 `%xxx%` | 高 |
| concat_wildcard | CONCAT('%', col) | 高 |
| function_wrap | 列被函数包装 | 中 |
| missing_limit | 缺少 LIMIT | 中 |
| full_table_scan | 全表扫描模式 | 高 |

---

## 四、非功能需求

### 4.1 性能

- 单个 SQL 分支展开 < 1s
- 静态分析 < 100ms/分支
- 支持 1000+ SQL 同时处理

### 4.2 可恢复性

- 支持中断后继续执行
- 产物持久化到磁盘

### 4.3 可扩展性

- 支持多数据库平台（PostgreSQL、MySQL）
- 规则引擎可扩展

---

## 五、用户交互

### 5.1 CLI 命令

#### sqlopt-cli（SQL 优化）

```
sqlopt-cli run --config <file>       # 开始优化
sqlopt-cli resume [--run-id <id>]   # 恢复运行
sqlopt-cli status [--run-id <id>]   # 查看状态
sqlopt-cli apply [--run-id <id>]    # 应用补丁
sqlopt-cli validate-config           # 验证配置
```

#### sqlopt-data（数据管理）

```
sqlopt-data get <path>              # 查询数据
sqlopt-data list <path>             # 列出内容
sqlopt-data set <path> <value>     # 修改数据
sqlopt-data diff <a> <b>            # 版本对比
sqlopt-data validate <path>         # 验证契约
sqlopt-data prune <target>         # 清理数据
```

### 5.2 Web 界面

| 模块 | 功能 |
|------|------|
| 仪表盘 | 统计概览、流水线状态 |
| 运行管理 | 列表、详情、控制 |
| 数据查询 | JSON 查询、版本对比 |
| 报告 | 优化建议、风险报告 |

---

## 六、数据架构

### 6.1 分层存储

```
项目根目录/
│
├── .sqlopt/cache/            # 项目级缓存（可复用）
│   └── db_schemas/         # 表结构缓存
│
├── runs/<run_id>/          # 运行时产物
│   ├── project_context/   # 全局上下文
│   ├── sqlmap_catalog/    # SQL 目录
│   └── supervisor/         # 运行状态
│
└── contracts/              # 数据契约 Schema
```

### 6.2 7 阶段流程

```
[1.发现] → [2.分支] → [3.剪枝] → [4.基线] → [5.优化] → [6.验证] → [7.补丁]
```

| 阶段 | 输入 | 输出 |
|------|------|------|
| 1.发现 | Mapper XML + DB | template + tableStructures |
| 2.分支 | template | branches |
| 3.剪枝 | branches | aggregatedBranches |
| 4.基线 | aggregatedBranches | baseline |
| 5.优化 | baseline | proposals |
| 6.验证 | proposals | validation |
| 7.验证 | validation | patches |

---

## 七、版本管理

- 数据契约使用语义化版本（MAJOR.MINOR.PATCH）
- 保持向前/向后兼容
- 变更记录在 CHANGELOG 中

---

## 八、未来扩展

| 功能 | 描述 | 优先级 |
|------|------|--------|
| Java 代码分析 | 分析 Java 层调用，检测 N+1 等问题 | 低 |
| LIMIT 缺失检测 | 自动检测缺失 LIMIT 的查询 | 低 |
| IDE 集成 | VS Code 插件 | 低 |

---

## 九、术语表

| 术语 | 定义 |
|------|------|
| SQL 模板 | 包含 ${} 和 #{} 的未解析 SQL |
| 分支 | 动态 SQL 展开后的具体 SQL |
| 风险等级 | high / medium / low |
| 基线 | SQL 执行时的性能数据 |

---

*文档版本：V8*
