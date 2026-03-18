# SQL Optimizer Skill

面向 MyBatis XML 映射文件的 SQL 优化工具，支持从诊断到补丁应用的七阶段工作流。

**支持数据库**: PostgreSQL, MySQL 5.6+（不含 MariaDB）

## V8 七阶段架构

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        V8 Pipeline                                     │
│                                                                          │
│  Discovery → Branching → Pruning → Baseline → Optimize → Validate → Patch │
└──────────────────────────────────────────────────────────────────────────┘
```

| 阶段 | 名称 | 说明 |
|------|------|------|
| 1 | Discovery | 连接数据库、采集表结构、解析 MyBatis XML |
| 2 | Branching | 展开动态标签生成分支路径（if/choose/foreach） |
| 3 | Pruning | 静态分析、风险标记、低价值分支过滤 |
| 4 | Baseline | EXPLAIN 采集执行计划、记录性能基线 |
| 5 | Optimize | 规则引擎 + LLM 生成优化建议 |
| 6 | Validate | 语义验证、性能对比、结果集校验 |
| 7 | Patch | 生成 XML 补丁、用户确认、应用变更 |

**特性**: 可恢复执行 | 产物可追溯 | LLM 智能优化

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
├── supervisor/          # 运行状态与元信息
├── scan.sqlunits.jsonl  # 扫描产物
├── proposals/           # 优化建议
├── acceptance/          # 验证结果
├── patches/            # 补丁文件
└── report.md          # 最终报告
```

## 文档

- [快速入门](docs/QUICKSTART.md)
- [V8 架构详解](docs/V8/V8_STAGES_OVERVIEW.md)
- [安装指南](docs/INSTALL.md)
- [故障排查](docs/TROUBLESHOOTING.md)

## 开发验收

```bash
python3 -m pytest -q
python3 scripts/ci/release_acceptance.py
```
