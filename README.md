# SQL Optimizer Skill

面向 MyBatis XML 映射文件的 SQL 优化工具，支持从诊断到补丁应用的五阶段工作流。

**支持数据库**: PostgreSQL, MySQL 5.6+（不含 MariaDB）

## V9 五阶段架构

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              V9 SQL Optimizer Pipeline                                   │
│                                                                                         │
│  ┌─────────┐    ┌─────────┐    ┌────────────┐    ┌─────────────────┐    ┌─────────┐  │
│  │  Init   │───▶│  Parse  │───▶│ Recognition │───▶│     Optimize     │───▶│  Patch  │  │
│  └─────────┘    └─────────┘    └────────────┘    └─────────────────┘    └─────────┘  │
│                                                                                         │
│                                                 ▲                                       │
│                                                 │ (迭代重试)                              │
│                                                 └─────────────────────────────────────  │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

**直接方法调用架构**：V9 采用直接方法调用替代 Stage 委托模式，5 阶段流水线简化为 Init → Parse → Recognition → Optimize → Patch。详见 [V9 架构详解](docs/v9-design/V9_ARCHITECTURE_OVERVIEW.md)。

| 阶段 | 名称 | 说明 |
|------|------|------|
| 1 | Init | 连接数据库、解析 MyBatis XML、提取 SQL 单元 |
| 2 | Parse | 展开动态标签生成分支路径（if/choose/foreach）、风险检测 |
| 3 | Recognition | EXPLAIN 采集执行计划、记录性能基线 |
| 4 | Optimize | 规则引擎 + LLM 生成优化建议、迭代式验证 |
| 5 | Patch | 生成 XML 补丁、用户确认、应用变更 |

**V8→V9 阶段映射**: Discovery→Init, Branching+Pruning→Parse, Baseline→Recognition, Optimize+Validate→Optimize, Patch→Patch

**特性**: 直接方法调用 | 迭代式优化验证 | 可恢复执行 | 产物可追溯 | LLM 智能优化

## CLI 命令

```bash
# 验证配置
sqlopt-cli validate-config --config sqlopt.yml

# 执行完整流程
sqlopt-cli run --config sqlopt.yml

# 查看状态
sqlopt-cli status --run-id <run_id>

# 恢复中断的运行
sqlopt-cli resume --run-id <run_id>

# 应用补丁
sqlopt-cli apply --run-id <run_id>
```

## 快速开始

### 1. 安装

```bash
python3 install/install_skill.py
python3 install/install_skill.py --verify
```

### 2. 创建配置文件

在项目根目录创建 `sqlopt.yml`:

```yaml
config_version: v1

project:
  root_path: .

scan:
  mapper_globs:
    - src/main/resources/**/*.xml

db:
  platform: postgresql
  dsn: postgresql://user:password@localhost:5432/dbname

llm:
  enabled: true
  provider: opencode_run
```

### 3. 运行优化

```bash
sqlopt-cli run --config sqlopt.yml
```

## 数据存储

```
runs/<run_id>/
├── supervisor/                      # 运行状态与元信息
├── init/
│   └── sql_units.json              # SQL 单元列表
├── parse/
│   ├── sql_units_with_branches.json # 带分支的 SQL 单元
│   └── risks.json                  # 风险检测结果
├── recognition/
│   └── baselines.json              # 性能基线
├── optimize/
│   └── proposals.json              # 优化提案
├── patch/
│   └── patches.json                # 最终补丁
├── report.json                     # JSON 报告
├── report.md                       # Markdown 报告
└── report.summary.md              # 摘要报告
```

## 文档

- [快速入门](docs/QUICKSTART.md)
- [V9 架构详解](docs/v9-design/V9_ARCHITECTURE_OVERVIEW.md)
- [V9 流水线详解](docs/v9-design/V9_ARCHITECTURE.md)
- [V8 架构参考](docs/V8/V8_STAGES_OVERVIEW.md)
- [安装指南](docs/INSTALL.md)
- [故障排查](docs/TROUBLESHOOTING.md)
- [V8→V9 迁移指南](docs/MIGRATION.md)

## 开发验收

```bash
python3 -m pytest -q
python3 scripts/ci/release_acceptance.py
```
