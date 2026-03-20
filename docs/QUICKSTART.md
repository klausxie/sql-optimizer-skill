# SQL Optimizer 快速入门（15 分钟）

目标：在项目里完成一轮可恢复的 SQL 优化运行，并拿到报告与补丁。

## 1. 前置条件

- Python 3.9+
- MyBatis XML mapper 文件
- 数据库：PostgreSQL 或 MySQL 5.6+（不支持 MariaDB）

## 2. 安装并自检

```bash
# 安装 Skill
python3 install/install_skill.py

# 验证安装
python3 install/install_skill.py --verify

# 环境诊断（可选）
python3 install/doctor.py --project .
```

安装后 `sqlopt-cli` 命令全局可用。

## 3. 准备配置文件

在项目根目录创建 `sqlopt.yml`：

```yaml
config_version: v1

project:
  root_path: .

scan:
  mapper_globs:
    - src/main/resources/**/*.xml

db:
  platform: postgresql
  dsn: postgresql://user:pass@127.0.0.1:5432/dbname?sslmode=disable

llm:
  enabled: true
  provider: opencode_run
```

关键字段说明：

| 字段 | 说明 |
|------|------|
| `config_version` | 配置版本，当前为 `v1` |
| `scan.mapper_globs` | MyBatis XML 文件路径模式 |
| `db.platform` | `postgresql` 或 `mysql` |
| `db.dsn` | 数据库连接串 |
| `llm.provider` | LLM 提供者：`opencode_run`（推荐）或 `opencode_builtin`（离线） |

## 4. V8 七阶段流水线

```
┌──────────────────────────────────────────────────────────────────┐
│                    V8 优化流程                                    │
│                                                                  │
│  [1.Discovery] → [2.Branching] → [3.Pruning] → [4.Baseline]   │
│       ↓                ↓                ↓               ↓        │
│   连接数据库        分支展开         风险标记         EXPLAIN    │
│   采集表结构       if/foreach/      prefix_wildcard   性能基线  │
│   解析 XML         choose           suffix_wildcard               │
│                                    function_wrap                  │
│                                                                  │
│  → [5.Optimize] → [6.Validate] → [7.Patch]                    │
│       ↓               ↓              ↓                           │
│   规则引擎         语义验证        生成补丁                     │
│   LLM 建议         性能对比        应用确认                     │
└──────────────────────────────────────────────────────────────────┘
```

| 阶段 | 名称 | 耗时 | 说明 |
|------|------|------|------|
| 1 | Discovery | DB | 连接数据库、采集表结构、解析 XML |
| 2 | Branching | CPU | 分支展开（if/foreach/choose） |
| 3 | Pruning | CPU | 风险标记（prefix_wildcard, suffix_wildcard, function_wrap） |
| 4 | Baseline | DB | EXPLAIN 分析、性能采集 |
| 5 | Optimize | LLM | 规则引擎 + LLM 优化建议 |
| 6 | Validate | DB | 语义验证、性能对比 |
| 7 | Patch | FS | 生成补丁、用户确认、应用 |

## 5. 完整使用流程

### 5.1 验证配置

```bash
sqlopt-cli validate-config --config sqlopt.yml
```

同时检查：数据库连接、mapper 文件、配置格式。

### 5.2 执行优化

```bash
sqlopt-cli run --config sqlopt.yml
```

默认持续推进到完成，中断后可恢复。

### 5.3 查看状态

```bash
sqlopt-cli status --run-id <run-id>
```

省略 `--run-id` 时自动选择最新运行。

### 5.4 恢复运行（如中断）

```bash
sqlopt-cli resume --run-id <run-id>
```

### 5.5 应用补丁

```bash
sqlopt-cli apply --run-id <run-id>
```

## 6. CLI 与 Skill 职责分工

```
┌────────────────────────────────┐     ┌─────────────────────────┐
│           sqlopt-cli           │     │    OpenCode Skill       │
├────────────────────────────────┤     ├─────────────────────────┤
│                                │     │                         │
│  • Discovery: 连接DB/解析XML   │────▶│  Optimize: LLM 优化    │
│  • Branching: 分支展开         │     │  • 生成优化建议         │
│  • Pruning: 风险标记           │     │  • 决策判断             │
│  • Baseline: EXPLAIN/性能采集   │     │                         │
│  • Validate: 语义/性能验证     │◀────│                         │
│  • Patch: 生成补丁/应用        │     │                         │
│                                │     │                         │
└────────────────────────────────┘     └─────────────────────────┘
```

**职责分离**：
- **CLI**：工程化能力（扫描、执行、SQL 验证）
- **Skill**：AI 能力（调用 LLM、生成优化建议）

## 7. 常用命令参考

### 执行控制

| 命令 | 说明 |
|------|------|
| `sqlopt-cli validate-config --config sqlopt.yml` | 验证配置 |
| `sqlopt-cli run --config sqlopt.yml` | 执行完整流程 |
| `sqlopt-cli run --config sqlopt.yml --to-stage <stage>` | 执行到指定阶段 |
| `sqlopt-cli resume --run-id <run-id>` | 恢复中断的运行 |
| `sqlopt-cli apply --run-id <run-id>` | 应用补丁 |

### 状态查询

| 命令 | 说明 |
|------|------|
| `sqlopt-cli status --run-id <run-id>` | 查看运行状态 |
| `sqlopt-cli verify --run-id <run-id>` | 验证证据链 |

### 局部调试

| 命令 | 说明 |
|------|------|
| `sqlopt-cli run --config sqlopt.yml --sql-key <key>` | 只诊断特定 SQL |
| `sqlopt-cli run --config sqlopt.yml --to-stage parse` | 只跑到 Parse 阶段 |

### 阶段推进选项

```bash
# 执行到 patch 阶段（V9 五阶段完整流水线终点）
sqlopt-cli run --config sqlopt.yml --to-stage patch --run-id <run-id>
```

`--sql-key` 支持多种格式：`sqlKey`、`namespace.statementId`、`statementId`、`statementId#vN`。

## 8. 产物结构

```
runs/<run-id>/
├── supervisor/
│   ├── meta.json          # 运行元信息
│   ├── state.json         # 旧 supervisor 状态
│   ├── v9_state.json      # V9 阶段状态
│   └── results/           # 步骤结果
├── init/
│   └── sql_units.json
├── parse/
│   ├── sql_units_with_branches.json
│   └── risks.json
├── recognition/
│   └── baselines.json
├── optimize/
│   └── proposals.json
└── patch/
    ├── patches.json
    └── patches/
```

## 9. 已知限制

- MySQL 5.6 不支持 `MAX_EXECUTION_TIME`
- PostgreSQL 方言（如 `ILIKE`）不会自动转换为 MySQL
- 语法问题会以 `OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR` 暴露在报告中

## 10. 下一步

- [安装指南](INSTALL.md) — 详细安装说明
- [故障排查](TROUBLESHOOTING.md) — 常见问题解决
- [文档导航](INDEX.md) — 完整文档索引
