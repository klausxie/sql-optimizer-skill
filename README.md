# SQL Optimizer Skill

面向 MyBatis SQL 的分析与优化工具链，支持从扫描到补丁应用的可恢复工作流。

## 核心能力

- 端到端流程：`run -> status/resume -> report -> apply`
- 可恢复执行：支持中断后继续，支持 `report-rebuild`
- 产物可追溯：`runs/<run-id>/` 下保留状态、报告与中间产物
- 支持数据库：`postgresql`、`mysql`（5.6+，不含 MariaDB）

## 安装方式

### 全局安装（推荐）

安装到 OpenCode 全局技能目录：

```bash
# Linux / macOS
python3 install/install_skill.py

# Windows (PowerShell)
python install/install_skill.py
```

验证安装：

```bash
# Linux / macOS
python3 install/install_skill.py --verify

# Windows
python install/install_skill.py --verify
```

安装后技能位置：
- Linux/macOS: `~/.opencode/skills/sql-optimizer/`
- Windows: `%USERPROFILE%\.opencode\skills\sql-optimizer\`

> 安装时会自动覆盖旧版本，无需额外操作。

### 项目内安装

安装到指定项目的 `.sqlopt` 目录：

```bash
# Linux / macOS
python3 install/install_skill.py --project /path/to/your/project

# Windows
python install/install_skill.py --project C:\path\to\project
```

### 自定义目录

安装到任意指定目录：

```bash
# Linux / macOS
python3 install/install_skill.py --project /custom/path/sqlopt-skill

# Windows
python install/install_skill.py --project C:\custom\path\sqlopt-skill
```

### 覆盖安装说明

多次安装时会自动覆盖旧版本：

```bash
# 首次安装
python3 install/install_skill.py

# 再次安装（自动覆盖，无需额外参数）
python3 install/install_skill.py
```

如需手动删除后安装：

```bash
# Linux / macOS - 全局安装的卸载
rm -rf ~/.opencode/skills/sql-optimizer/

# Linux / macOS - 项目安装的卸载
rm -rf /path/to/your/project/.sqlopt

# Windows - 全局安装的卸载
rmdir /s /q "%USERPROFILE%\.opencode\skills\sql-optimizer"

# Windows - 项目安装的卸载
rmdir /s /q "C:\path\to\project\.sqlopt"

# 然后重新安装
python3 install/install_skill.py
```

## 在 OpenCode 中使用

### 1. 启动 OpenCode

在项目根目录启动 OpenCode：

```bash
opencode
```

### 2. 使用 Skill

当处理 MyBatis SQL 优化任务时，OpenCode 会自动加载 sql-optimizer skill。

#### OpenCode 命令方式

Skill 提供以下命令：

| 命令 | 说明 | 使用方式 |
|------|------|----------|
| `/sql-diagnose` | 诊断 SQL 性能问题 | `/sql-diagnose <SQL关键字或文件>` |
| `/sql-optimize` | 生成优化建议 | `/sql-optimize [run-id]` |
| `/sql-validate` | 验证优化效果 | `/sql-validate [run-id]` |
| `/sql-apply` | 应用补丁 | `/sql-apply [run-id]` |
| `/sql-report` | 生成总结报告 | `/sql-report [run-id]` |

#### 自然语言方式

也可以直接用自然语言描述需求：

```
帮我诊断一下 listUsers 这个 SQL
看看这个 Mapper 有什么性能问题
给个优化建议
验证一下优化效果
应用这些补丁
```

#### 完整优化流程

**方式一：OpenCode 命令**

```bash
# 1. 验证配置（创建 sqlopt.yml 后）
/sql-diagnose

# 2. 查看诊断结果后，生成优化建议
/sql-optimize

# 3. 验证优化效果
/sql-validate

# 4. 应用补丁
/sql-apply

# 5. 生成报告
/sql-report
```

**方式二：自然语言**

```
帮我诊断 listUsers 这个 SQL 的性能问题
生成优化建议
验证优化效果
应用补丁
```

**诊断单个 SQL**：

```
/sql-diagnose listUsers
# 或
/sql-diagnose UserMapper.xml
# 或自然语言
帮我看看 UserMapper.xml 里面 listUsers 这个 SQL 有什么性能问题
```

### 3. Skill 与 CLI 的协作

```
┌─────────────────────┐          ┌─────────────────────┐
│   sqlopt-cli       │          │   OpenCode Skill   │
├─────────────────────┤          ├─────────────────────┤
│                     │          │                     │
│  • 扫描 MyBatis   │          │  • 调用 LLM        │
│  • 生成分支       │─────────▶│  • 生成建议         │
│  • 静态规则检测   │  prompt   │  • 决策判断         │
│  • 构建 LLM prompt│          │  • 用户交互         │
│  • 执行 SQL       │          │                     │
│  • 生成补丁       │          │                     │
│                     │          │                     │
└─────────────────────┘          └─────────────────────┘
```

**职责分离**：
- **CLI**：工程化能力（扫描、执行、构建 prompt）
- **Skill**：AI 能力（调用 LLM、生成建议）

## 快速开始

### 1) 安装

```bash
python3 install/install_skill.py
python3 install/install_skill.py --verify
```

### 2) 创建配置文件

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
  dsn: postgresql://user:password@localhost:5432/dbname

llm:
  enabled: true
  provider: opencode_run
```

### 3) 开始使用

安装完成后，在 OpenCode 中直接使用自然语言或命令：

```
# 诊断 SQL
帮我诊断一下 listUsers 这个 SQL

# 查看诊断结果后，生成优化建议
如何优化这个 SQL

# 验证效果
验证一下优化效果

# 应用补丁
应用补丁
```

## 常见问题

### 恢复中断的运行

如果运行中断，可以使用自然语言恢复：

```
继续之前的优化
恢复运行
```

### 查看运行状态

```
查看优化状态
现在的进度怎么样
```

### 局部调试

如需只诊断特定 SQL：

```
/sql-diagnose listUsers
# 或
帮我诊断 UserMapper.xml 中的 listUsers 方法
```

## 关键边界

- PostgreSQL 方言（如 `ILIKE`）在 MySQL 平台不会自动兼容
- 此类语法问题会在报告中以 `OPTIMIZE_DB_EXPLAIN_SYNTAX_ERROR` 暴露
- 省略 run-id 时自动选择最新运行（可用 `--project` 限定目录）

## 文档入口

- [快速入门](docs/QUICKSTART.md)
- [安装指南](docs/INSTALL.md)
- [文档导航](docs/INDEX.md)
- [故障排查](docs/TROUBLESHOOTING.md)
- [系统规格](docs/project/02-system-spec.md)
- [工作流与状态机](docs/project/03-workflow-and-state-machine.md)
- [数据契约](docs/project/04-data-contracts.md)
- [SQL 补丁能力架构](docs/project/10-sql-patchability-architecture.md)

## 开发与验收

```bash
python3 -m pytest -q
python3 scripts/ci/release_acceptance.py
```

## 架构设计

- **功能全景图**：[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — 完整功能架构和执行流程
- **V8 架构**：[`docs/V8/V8_SUMMARY.md`](docs/V8/V8_SUMMARY.md) — V8 版本架构总览与实现状态

> 推荐先阅读功能全景图，了解整体设计后再深入其他文档。
